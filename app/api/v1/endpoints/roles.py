"""
Role Management Endpoints for Madagascar License System
Handles role CRUD operations and role-permission assignments
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import math

from app.core.database import get_db
from app.models.user import Role, Permission, User
from app.schemas.user import (
    RoleCreate, RoleUpdate, RoleResponse, RoleDetailResponse,
    PermissionResponse, RolePermissionAssignment
)
from app.api.v1.endpoints.auth import get_current_user, log_user_action

router = APIRouter()


def check_permission(user: User, permission: str) -> bool:
    """Check if user has specific permission"""
    if user.is_superuser:
        return True
    return user.has_permission(permission)


def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(current_user: User = Depends(get_current_user)):
        if not check_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}"
            )
        return current_user
    return decorator


@router.get("/", response_model=List[RoleResponse], summary="List Roles")
async def list_roles(
    request: Request,
    include_system: bool = Query(True, description="Include system roles"),
    current_user: User = Depends(require_permission("roles.read")),
    db: Session = Depends(get_db)
):
    """
    Get list of all roles
    """
    query = db.query(Role).filter(Role.is_active == True)
    
    if not include_system:
        query = query.filter(Role.is_system_role == False)
    
    roles = query.order_by(Role.name).all()
    
    # Log role list access
    log_user_action(
        db, current_user, "roles_list_accessed", request,
        details={"include_system": include_system, "total_results": len(roles)}
    )
    
    return [RoleResponse.from_orm(role) for role in roles]


@router.get("/{role_id}", response_model=RoleDetailResponse, summary="Get Role")
async def get_role(
    role_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("roles.read")),
    db: Session = Depends(get_db)
):
    """
    Get role by ID with detailed information including permissions
    """
    role = db.query(Role).options(
        joinedload(Role.permissions),
        joinedload(Role.parent_role),
        joinedload(Role.child_roles)
    ).filter(Role.id == role_id, Role.is_active == True).first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Log role access
    log_user_action(
        db, current_user, "role_accessed", request,
        details={"accessed_role_id": str(role_id), "role_name": role.name}
    )
    
    return RoleDetailResponse.from_orm(role)


@router.post("/", response_model=RoleResponse, summary="Create Role")
async def create_role(
    role_data: RoleCreate,
    request: Request,
    current_user: User = Depends(require_permission("roles.create")),
    db: Session = Depends(get_db)
):
    """
    Create new role
    """
    # Check if role name already exists
    existing_role = db.query(Role).filter(
        Role.name == role_data.name.lower(),
        Role.is_active == True
    ).first()
    
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role name already exists"
        )
    
    # Verify parent role exists if specified
    parent_role = None
    if role_data.parent_role_id:
        parent_role = db.query(Role).filter(
            Role.id == role_data.parent_role_id,
            Role.is_active == True
        ).first()
        if not parent_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent role not found"
            )
    
    # Create role
    role = Role(
        name=role_data.name.lower(),
        display_name=role_data.display_name,
        description=role_data.description,
        allowed_modules=str(role_data.allowed_modules) if role_data.allowed_modules else None,
        parent_role_id=role_data.parent_role_id,
        level=parent_role.level + 1 if parent_role else 0,
        is_system_role=False,  # Only system can create system roles
        created_by=current_user.id,
        updated_by=current_user.id
    )
    
    db.add(role)
    db.flush()  # Get the role ID
    
    # Assign permissions
    if role_data.permission_ids:
        permissions = db.query(Permission).filter(
            Permission.id.in_(role_data.permission_ids)
        ).all()
        role.permissions = permissions
    
    db.commit()
    db.refresh(role)
    
    # Log role creation
    log_user_action(
        db, current_user, "role_created", request,
        details={
            "created_role_id": str(role.id),
            "role_name": role.name,
            "permissions_count": len(role.permissions)
        }
    )
    
    return RoleResponse.from_orm(role)


@router.put("/{role_id}", response_model=RoleResponse, summary="Update Role")
async def update_role(
    role_id: uuid.UUID,
    role_data: RoleUpdate,
    request: Request,
    current_user: User = Depends(require_permission("roles.update")),
    db: Session = Depends(get_db)
):
    """
    Update role information
    """
    role = db.query(Role).filter(Role.id == role_id, Role.is_active == True).first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Prevent modification of system roles (unless superuser)
    if role.is_system_role and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify system roles"
        )
    
    # Update fields
    update_data = role_data.dict(exclude_unset=True)
    changes = {}
    
    for field, value in update_data.items():
        if field in ["permission_ids"]:
            continue  # Handle separately
        
        if hasattr(role, field):
            old_value = getattr(role, field)
            if field == "allowed_modules":
                value = str(value) if value else None
            
            if old_value != value:
                changes[field] = {"old": old_value, "new": value}
                setattr(role, field, value)
    
    # Handle permission assignments
    if role_data.permission_ids is not None:
        permissions = db.query(Permission).filter(
            Permission.id.in_(role_data.permission_ids)
        ).all()
        old_permissions = [p.name for p in role.permissions]
        new_permissions = [p.name for p in permissions]
        if old_permissions != new_permissions:
            changes["permissions"] = {"old": old_permissions, "new": new_permissions}
            role.permissions = permissions
    
    # Update audit fields
    role.updated_by = current_user.id
    role.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(role)
    
    # Log role update
    log_user_action(
        db, current_user, "role_updated", request,
        details={
            "updated_role_id": str(role_id),
            "role_name": role.name,
            "changes": changes
        }
    )
    
    return RoleResponse.from_orm(role)


@router.delete("/{role_id}", summary="Delete Role")
async def delete_role(
    role_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("roles.delete")),
    db: Session = Depends(get_db)
):
    """
    Soft delete role (deactivate)
    """
    role = db.query(Role).filter(Role.id == role_id, Role.is_active == True).first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Prevent deletion of system roles (unless superuser)
    if role.is_system_role and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system roles"
        )
    
    # Check if role is assigned to any users
    users_with_role = db.query(User).join(User.roles).filter(
        Role.id == role_id,
        User.is_active == True
    ).count()
    
    if users_with_role > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete role: {users_with_role} users still have this role"
        )
    
    # Soft delete
    role.soft_delete(current_user.id)
    
    db.commit()
    
    # Log role deletion
    log_user_action(
        db, current_user, "role_deleted", request,
        details={
            "deleted_role_id": str(role_id),
            "role_name": role.name
        }
    )
    
    return {"message": "Role deleted successfully"}


@router.post("/{role_id}/permissions", summary="Assign Permissions to Role")
async def assign_permissions_to_role(
    role_id: uuid.UUID,
    permission_assignment: RolePermissionAssignment,
    request: Request,
    current_user: User = Depends(require_permission("roles.assign_permissions")),
    db: Session = Depends(get_db)
):
    """
    Assign permissions to a role
    """
    role = db.query(Role).filter(Role.id == role_id, Role.is_active == True).first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Prevent modification of system roles (unless superuser)
    if role.is_system_role and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify permissions for system roles"
        )
    
    # Get permissions
    permissions = db.query(Permission).filter(
        Permission.id.in_(permission_assignment.permission_ids)
    ).all()
    
    if len(permissions) != len(permission_assignment.permission_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more permissions not found"
        )
    
    # Update role permissions
    old_permissions = [p.name for p in role.permissions]
    role.permissions = permissions
    new_permissions = [p.name for p in permissions]
    
    role.updated_by = current_user.id
    role.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    
    # Log permission assignment
    log_user_action(
        db, current_user, "role_permissions_assigned", request,
        details={
            "role_id": str(role_id),
            "role_name": role.name,
            "old_permissions": old_permissions,
            "new_permissions": new_permissions
        }
    )
    
    return {
        "message": "Permissions assigned successfully",
        "role_id": str(role_id),
        "permissions_count": len(permissions)
    }


@router.get("/{role_id}/users", summary="Get Users with Role")
async def get_users_with_role(
    role_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_permission("roles.read")),
    db: Session = Depends(get_db)
):
    """
    Get users that have this role
    """
    role = db.query(Role).filter(Role.id == role_id, Role.is_active == True).first()
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Get users with this role
    query = db.query(User).join(User.roles).filter(
        Role.id == role_id,
        User.is_active == True
    )
    
    total = query.count()
    offset = (page - 1) * per_page
    users = query.offset(offset).limit(per_page).all()
    
    return {
        "role": {
            "id": str(role.id),
            "name": role.name,
            "display_name": role.display_name
        },
        "users": [
            {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "status": user.status.value,
                "last_login_at": user.last_login_at
            }
            for user in users
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page)
    } 