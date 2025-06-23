"""
Permission Management Endpoints for Madagascar License System
Handles permission listing and management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict
import uuid

from app.core.database import get_db
from app.models.user import Permission, User
from app.schemas.user import PermissionResponse
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


@router.get("/", response_model=List[PermissionResponse], summary="List Permissions")
async def list_permissions(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    resource: Optional[str] = Query(None, description="Filter by resource"),
    action: Optional[str] = Query(None, description="Filter by action"),
    include_system: bool = Query(True, description="Include system permissions"),
    current_user: User = Depends(require_permission("permissions.read")),
    db: Session = Depends(get_db)
):
    """
    Get list of all permissions with optional filtering
    """
    query = db.query(Permission).filter(Permission.is_active == True)
    
    # Apply filters
    if category:
        query = query.filter(func.lower(Permission.category) == category.lower())
    
    if resource:
        query = query.filter(func.lower(Permission.resource) == resource.lower())
    
    if action:
        query = query.filter(func.lower(Permission.action) == action.lower())
    
    if not include_system:
        query = query.filter(Permission.is_system_permission == False)
    
    permissions = query.order_by(Permission.category, Permission.resource, Permission.action).all()
    
    # Log permission list access
    log_user_action(
        db, current_user, "permissions_list_accessed", request,
        details={
            "filters": {"category": category, "resource": resource, "action": action},
            "include_system": include_system,
            "total_results": len(permissions)
        }
    )
    
    return [PermissionResponse.from_orm(permission) for permission in permissions]


@router.get("/by-category", summary="Get Permissions Grouped by Category")
async def get_permissions_by_category(
    request: Request,
    current_user: User = Depends(require_permission("permissions.read")),
    db: Session = Depends(get_db)
):
    """
    Get permissions grouped by category for easier UI management
    """
    permissions = db.query(Permission).filter(
        Permission.is_active == True
    ).order_by(Permission.category, Permission.resource, Permission.action).all()
    
    # Group by category
    grouped = {}
    for permission in permissions:
        category = permission.category
        if category not in grouped:
            grouped[category] = []
        
        grouped[category].append({
            "id": str(permission.id),
            "name": permission.name,
            "display_name": permission.display_name,
            "description": permission.description,
            "resource": permission.resource,
            "action": permission.action,
            "is_system_permission": permission.is_system_permission
        })
    
    # Log category view access
    log_user_action(
        db, current_user, "permissions_by_category_accessed", request,
        details={"categories": list(grouped.keys()), "total_permissions": len(permissions)}
    )
    
    return grouped


@router.get("/categories", summary="Get Permission Categories")
async def get_permission_categories(
    current_user: User = Depends(require_permission("permissions.read")),
    db: Session = Depends(get_db)
):
    """
    Get list of all permission categories
    """
    categories = db.query(Permission.category).filter(
        Permission.is_active == True
    ).distinct().order_by(Permission.category).all()
    
    return [category[0] for category in categories]


@router.get("/resources", summary="Get Permission Resources")
async def get_permission_resources(
    category: Optional[str] = Query(None, description="Filter by category"),
    current_user: User = Depends(require_permission("permissions.read")),
    db: Session = Depends(get_db)
):
    """
    Get list of all permission resources, optionally filtered by category
    """
    query = db.query(Permission.resource).filter(Permission.is_active == True)
    
    if category:
        query = query.filter(func.lower(Permission.category) == category.lower())
    
    resources = query.distinct().order_by(Permission.resource).all()
    
    return [resource[0] for resource in resources]


@router.get("/actions", summary="Get Permission Actions")
async def get_permission_actions(
    category: Optional[str] = Query(None, description="Filter by category"),
    resource: Optional[str] = Query(None, description="Filter by resource"),
    current_user: User = Depends(require_permission("permissions.read")),
    db: Session = Depends(get_db)
):
    """
    Get list of all permission actions, optionally filtered by category and resource
    """
    query = db.query(Permission.action).filter(Permission.is_active == True)
    
    if category:
        query = query.filter(func.lower(Permission.category) == category.lower())
    
    if resource:
        query = query.filter(func.lower(Permission.resource) == resource.lower())
    
    actions = query.distinct().order_by(Permission.action).all()
    
    return [action[0] for action in actions]


@router.get("/{permission_id}", response_model=PermissionResponse, summary="Get Permission")
async def get_permission(
    permission_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("permissions.read")),
    db: Session = Depends(get_db)
):
    """
    Get permission by ID
    """
    permission = db.query(Permission).filter(
        Permission.id == permission_id,
        Permission.is_active == True
    ).first()
    
    if not permission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Permission not found"
        )
    
    # Log permission access
    log_user_action(
        db, current_user, "permission_accessed", request,
        details={
            "permission_id": str(permission_id),
            "permission_name": permission.name
        }
    )
    
    return PermissionResponse.from_orm(permission)


@router.get("/module/{module_name}", summary="Get Module Permissions")
async def get_module_permissions(
    module_name: str,
    request: Request,
    current_user: User = Depends(require_permission("permissions.read")),
    db: Session = Depends(get_db)
):
    """
    Get all permissions for a specific module
    
    Module names: users, persons, applications, printing, reports, locations
    """
    # Map module names to permission categories
    module_to_categories = {
        "users": ["users", "user_management"],
        "persons": ["persons", "person_management", "biometric_data"],
        "applications": ["license_applications", "application_processing"],
        "printing": ["printing", "card_management"],
        "reports": ["reports", "analytics"],
        "locations": ["locations", "location_management"],
    }
    
    if module_name not in module_to_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid module name. Valid modules: {list(module_to_categories.keys())}"
        )
    
    categories = module_to_categories[module_name]
    
    permissions = db.query(Permission).filter(
        Permission.category.in_(categories),
        Permission.is_active == True
    ).order_by(Permission.category, Permission.resource, Permission.action).all()
    
    # Log module permissions access
    log_user_action(
        db, current_user, "module_permissions_accessed", request,
        details={
            "module_name": module_name,
            "categories": categories,
            "total_permissions": len(permissions)
        }
    )
    
    return {
        "module": module_name,
        "categories": categories,
        "permissions": [PermissionResponse.from_orm(permission) for permission in permissions]
    }


@router.get("/check/{permission_name}", summary="Check Permission")
async def check_user_permission(
    permission_name: str,
    user_id: Optional[uuid.UUID] = Query(None, description="User ID to check (defaults to current user)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Check if a user has a specific permission
    """
    # Determine which user to check
    target_user = current_user
    if user_id and current_user.has_permission("permissions.check_others"):
        target_user = db.query(User).filter(
            User.id == user_id,
            User.is_active == True
        ).first()
        
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
    elif user_id and user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot check permissions for other users"
        )
    
    # Check permission
    has_permission = target_user.has_permission(permission_name)
    
    return {
        "user_id": str(target_user.id),
        "username": target_user.username,
        "permission": permission_name,
        "has_permission": has_permission,
        "is_superuser": target_user.is_superuser
    }


@router.get("/user/{user_id}/effective", summary="Get User's Effective Permissions")
async def get_user_effective_permissions(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("permissions.read")),
    db: Session = Depends(get_db)
):
    """
    Get all effective permissions for a user (through all their roles)
    """
    # Get target user
    target_user = db.query(User).filter(
        User.id == user_id,
        User.is_active == True
    ).first()
    
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get all permissions through roles
    all_permissions = set()
    role_permissions = {}
    
    for role in target_user.roles:
        role_perms = []
        for permission in role.permissions:
            all_permissions.add(permission.name)
            role_perms.append({
                "id": str(permission.id),
                "name": permission.name,
                "display_name": permission.display_name,
                "category": permission.category
            })
        
        role_permissions[role.name] = {
            "role_id": str(role.id),
            "role_display_name": role.display_name,
            "permissions": role_perms
        }
    
    # Log effective permissions access
    log_user_action(
        db, current_user, "user_effective_permissions_accessed", request,
        details={
            "target_user_id": str(user_id),
            "total_permissions": len(all_permissions),
            "roles": list(role_permissions.keys())
        }
    )
    
    return {
        "user": {
            "id": str(target_user.id),
            "username": target_user.username,
            "full_name": target_user.full_name,
            "is_superuser": target_user.is_superuser
        },
        "effective_permissions": sorted(list(all_permissions)),
        "role_permissions": role_permissions,
        "total_permissions": len(all_permissions)
    } 