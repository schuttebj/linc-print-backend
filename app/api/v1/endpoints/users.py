"""
User Management Endpoints for Madagascar License System
Handles user CRUD operations, search, and administration
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import math

from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User, Role, UserStatus, MadagascarIDType, UserAuditLog
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserListResponse, UserSummary,
    UserQueryParams, UserStatusEnum, MadagascarIDTypeEnum
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


@router.get("/", response_model=UserListResponse, summary="List Users")
async def list_users(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term"),
    status: Optional[UserStatusEnum] = Query(None, description="Filter by status"),
    role: Optional[str] = Query(None, description="Filter by role"),
    department: Optional[str] = Query(None, description="Filter by department"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    current_user: User = Depends(require_permission("users.read")),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of users with filtering and search
    """
    # Build query
    query = db.query(User).options(
        joinedload(User.roles),
        joinedload(User.primary_location),
        joinedload(User.assigned_locations)
    ).filter(User.is_active == True)
    
    # Apply search filter
    if search:
        search_term = f"%{search.lower()}%"
        query = query.filter(
            or_(
                func.lower(User.username).like(search_term),
                func.lower(User.email).like(search_term),
                func.lower(User.first_name).like(search_term),
                func.lower(User.last_name).like(search_term),
                func.lower(User.madagascar_id_number).like(search_term),
                func.lower(User.employee_id).like(search_term)
            )
        )
    
    # Apply status filter
    if status:
        query = query.filter(User.status == status.value)
    
    # Apply role filter
    if role:
        query = query.join(User.roles).filter(Role.name == role)
    
    # Apply department filter
    if department:
        query = query.filter(func.lower(User.department).like(f"%{department.lower()}%"))
    
    # Apply sorting
    sort_column = getattr(User, sort_by, User.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    users = query.offset(offset).limit(per_page).all()
    
    # Calculate pagination info
    total_pages = math.ceil(total / per_page)
    
    # Log user list access
    log_user_action(
        db, current_user, "users_list_accessed", request,
        details={
            "page": page,
            "per_page": per_page,
            "search": search,
            "filters": {"status": status, "role": role, "department": department},
            "total_results": total
        }
    )
    
    return UserListResponse(
        users=[UserResponse.from_orm(user) for user in users],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/{user_id}", response_model=UserResponse, summary="Get User")
async def get_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("users.read")),
    db: Session = Depends(get_db)
):
    """
    Get user by ID
    """
    user = db.query(User).options(
        joinedload(User.roles),
        joinedload(User.primary_location),
        joinedload(User.assigned_locations)
    ).filter(User.id == user_id, User.is_active == True).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Log user access
    log_user_action(
        db, current_user, "user_accessed", request,
        details={"accessed_user_id": str(user_id)}
    )
    
    return UserResponse.from_orm(user)


@router.post("/", response_model=UserResponse, summary="Create User")
async def create_user(
    user_data: UserCreate,
    request: Request,
    current_user: User = Depends(require_permission("users.create")),
    db: Session = Depends(get_db)
):
    """
    Create new user
    """
    # Check if username already exists
    existing_user = db.query(User).filter(
        or_(
            User.username == user_data.username.lower(),
            User.email == user_data.email.lower(),
            User.madagascar_id_number == user_data.madagascar_id_number.upper()
        ),
        User.is_active == True
    ).first()
    
    if existing_user:
        if existing_user.username == user_data.username.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        elif existing_user.email == user_data.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Madagascar ID number already exists"
            )
    
    # Check if employee ID exists (if provided)
    if user_data.employee_id:
        existing_employee = db.query(User).filter(
            User.employee_id == user_data.employee_id,
            User.is_active == True
        ).first()
        if existing_employee:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee ID already exists"
            )
    
    # Create user
    user = User(
        username=user_data.username.lower(),
        email=user_data.email.lower(),
        password_hash=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        display_name=user_data.display_name,
        madagascar_id_number=user_data.madagascar_id_number.upper(),
        id_document_type=user_data.id_document_type,
        phone_number=user_data.phone_number,
        employee_id=user_data.employee_id,
        department=user_data.department,
        province=user_data.province,
        region=user_data.region,
        office_location=user_data.office_location,
        language=user_data.language,
        timezone=user_data.timezone,
        currency=user_data.currency,
        primary_location_id=user_data.primary_location_id,
        status=UserStatus.PENDING_ACTIVATION,
        created_by=current_user.id,
        updated_by=current_user.id
    )
    
    db.add(user)
    db.flush()  # Get the user ID
    
    # Assign roles
    if user_data.role_ids:
        roles = db.query(Role).filter(Role.id.in_(user_data.role_ids)).all()
        user.roles = roles
    
    # Assign locations
    if user_data.assigned_location_ids:
        from app.models.user import Location
        locations = db.query(Location).filter(Location.id.in_(user_data.assigned_location_ids)).all()
        user.assigned_locations = locations
    
    db.commit()
    db.refresh(user)
    
    # Log user creation
    log_user_action(
        db, current_user, "user_created", request,
        details={
            "created_user_id": str(user.id),
            "username": user.username,
            "roles": [role.name for role in user.roles]
        }
    )
    
    return UserResponse.from_orm(user)


@router.put("/{user_id}", response_model=UserResponse, summary="Update User")
async def update_user(
    user_id: uuid.UUID,
    user_data: UserUpdate,
    request: Request,
    current_user: User = Depends(require_permission("users.update")),
    db: Session = Depends(get_db)
):
    """
    Update user information
    """
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Check if updating username/email/madagascar_id and they don't conflict
    if user_data.username and user_data.username.lower() != user.username:
        existing = db.query(User).filter(
            User.username == user_data.username.lower(),
            User.id != user_id,
            User.is_active == True
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
    
    if user_data.email and user_data.email.lower() != user.email:
        existing = db.query(User).filter(
            User.email == user_data.email.lower(),
            User.id != user_id,
            User.is_active == True
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
    
    if user_data.madagascar_id_number and user_data.madagascar_id_number.upper() != user.madagascar_id_number:
        existing = db.query(User).filter(
            User.madagascar_id_number == user_data.madagascar_id_number.upper(),
            User.id != user_id,
            User.is_active == True
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Madagascar ID number already exists"
            )
    
    # Update fields
    update_data = user_data.dict(exclude_unset=True)
    changes = {}
    
    for field, value in update_data.items():
        if field in ["role_ids", "assigned_location_ids"]:
            continue  # Handle these separately
        
        if hasattr(user, field):
            old_value = getattr(user, field)
            if old_value != value:
                changes[field] = {"old": old_value, "new": value}
                setattr(user, field, value)
    
    # Handle role assignments
    if user_data.role_ids is not None:
        roles = db.query(Role).filter(Role.id.in_(user_data.role_ids)).all()
        old_roles = [role.name for role in user.roles]
        new_roles = [role.name for role in roles]
        if old_roles != new_roles:
            changes["roles"] = {"old": old_roles, "new": new_roles}
            user.roles = roles
    
    # Handle location assignments
    if user_data.assigned_location_ids is not None:
        from app.models.user import Location
        locations = db.query(Location).filter(Location.id.in_(user_data.assigned_location_ids)).all()
        user.assigned_locations = locations
    
    # Update audit fields
    user.updated_by = current_user.id
    user.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(user)
    
    # Log user update
    log_user_action(
        db, current_user, "user_updated", request,
        details={
            "updated_user_id": str(user_id),
            "changes": changes
        }
    )
    
    return UserResponse.from_orm(user)


@router.delete("/{user_id}", summary="Delete User")
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("users.delete")),
    db: Session = Depends(get_db)
):
    """
    Soft delete user (deactivate)
    """
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Soft delete
    user.soft_delete(current_user.id)
    user.status = UserStatus.INACTIVE
    
    db.commit()
    
    # Log user deletion
    log_user_action(
        db, current_user, "user_deleted", request,
        details={
            "deleted_user_id": str(user_id),
            "username": user.username
        }
    )
    
    return {"message": "User deleted successfully"}


@router.post("/{user_id}/activate", response_model=UserResponse, summary="Activate User")
async def activate_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("users.update")),
    db: Session = Depends(get_db)
):
    """
    Activate user account
    """
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.status = UserStatus.ACTIVE
    user.is_verified = True
    user.updated_by = current_user.id
    user.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(user)
    
    # Log activation
    log_user_action(
        db, current_user, "user_activated", request,
        details={"activated_user_id": str(user_id)}
    )
    
    return UserResponse.from_orm(user)


@router.post("/{user_id}/deactivate", response_model=UserResponse, summary="Deactivate User")
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("users.update")),
    db: Session = Depends(get_db)
):
    """
    Deactivate user account
    """
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent self-deactivation
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )
    
    user.status = UserStatus.INACTIVE
    user.updated_by = current_user.id
    user.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(user)
    
    # Log deactivation
    log_user_action(
        db, current_user, "user_deactivated", request,
        details={"deactivated_user_id": str(user_id)}
    )
    
    return UserResponse.from_orm(user)


@router.get("/{user_id}/audit-logs", summary="Get User Audit Logs")
async def get_user_audit_logs(
    user_id: uuid.UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_permission("users.audit")),
    db: Session = Depends(get_db)
):
    """
    Get audit logs for specific user
    """
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get audit logs
    query = db.query(UserAuditLog).filter(UserAuditLog.user_id == user_id)
    query = query.order_by(UserAuditLog.created_at.desc())
    
    total = query.count()
    offset = (page - 1) * per_page
    logs = query.offset(offset).limit(per_page).all()
    
    return {
        "audit_logs": [
            {
                "id": str(log.id),
                "action": log.action,
                "resource": log.resource,
                "success": log.success,
                "ip_address": log.ip_address,
                "created_at": log.created_at,
                "details": log.details
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total / per_page)
    } 