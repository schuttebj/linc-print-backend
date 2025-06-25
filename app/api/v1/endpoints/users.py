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
from app.crud.crud_user import user as crud_user
from app.crud.crud_location import location as crud_location
from app.services.audit_service import MadagascarAuditService, create_user_context
from app.models.enums import UserType, RoleHierarchy

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
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
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
    location_id: Optional[uuid.UUID] = Query(None, description="Location ID for location-based users"),
    province_code: Optional[str] = Query(None, description="Province code for provincial users"),
    request: Request = Request,
    current_user: User = Depends(require_permission("users.create")),
    db: Session = Depends(get_db)
):
    """
    Create new user with username generation based on user type
    Supports location-based, provincial, and national users
    """
    # Check if email already exists
    existing_user = crud_user.get_by_email(db=db, email=user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    
    # Check if Madagascar ID already exists
    existing_id_user = crud_user.get_by_madagascar_id(db=db, madagascar_id=user_data.madagascar_id_number)
    if existing_id_user:
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
    
    # Validate role hierarchy - creator must have higher level than target roles
    if user_data.role_ids:
        target_roles = db.query(Role).filter(Role.id.in_(user_data.role_ids)).all()
        if not target_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role IDs provided"
            )
        
        # Get current user's highest hierarchy level
        current_user_max_level = 0
        for role in current_user.roles:
            if hasattr(role, 'hierarchy_level') and role.hierarchy_level:
                current_user_max_level = max(current_user_max_level, role.hierarchy_level)
        
        # Check if current user can create target roles
        for target_role in target_roles:
            target_level = getattr(target_role, 'hierarchy_level', 1)
            if not current_user.is_superuser and current_user_max_level <= target_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Cannot create user with role '{target_role.display_name}' - insufficient role hierarchy level"
                )
    
    # Validate user type and required parameters
    user_type = user_data.user_type if hasattr(user_data, 'user_type') else UserType.LOCATION_USER
    
    try:
        if user_type == UserType.LOCATION_USER:
            if not location_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="location_id required for LOCATION_USER"
                )
            user = crud_user.create_with_location(
                db=db, 
                obj_in=user_data, 
                location_id=location_id,
                created_by=current_user.username
            )
        
        elif user_type == UserType.PROVINCIAL_USER:
            if not province_code:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="province_code required for PROVINCIAL_USER"
                )
            user = crud_user.create_provincial_user(
                db=db,
                obj_in=user_data,
                province_code=province_code,
                created_by=current_user.username
            )
        
        elif user_type == UserType.NATIONAL_USER:
            user = crud_user.create_national_user(
                db=db,
                obj_in=user_data,
                created_by=current_user.username
            )
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown user type: {user_type}"
            )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Log user creation
    log_user_action(
        db, current_user, "user_created", request,
        details={
            "created_user_id": str(user.id),
            "username": user.username,
            "user_type": user.user_type.value,
            "roles": [role.name for role in user.roles]
        }
    )
    
    return UserResponse.from_orm(user)


@router.post("/provincial", response_model=UserResponse, summary="Create Provincial User")
async def create_provincial_user(
    user_data: UserCreate,
    province_code: str = Query(..., description="Province code (T, A, D, F, M, U)"),
    request: Request = Request,
    current_user: User = Depends(require_permission("users.create")),
    db: Session = Depends(get_db)
):
    """
    Create provincial user (Traffic Department Head) with province-based username generation
    """
    # Validate province code
    valid_provinces = ["T", "A", "D", "F", "M", "U"]
    if province_code not in valid_provinces:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid province code. Must be one of: {', '.join(valid_provinces)}"
        )
    
    # Check role hierarchy - only system admins and higher can create provincial users
    current_user_max_level = 0
    for role in current_user.roles:
        if hasattr(role, 'hierarchy_level') and role.hierarchy_level:
            current_user_max_level = max(current_user_max_level, role.hierarchy_level)
    
    if not current_user.is_superuser and current_user_max_level < 4:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only System Administrators can create Provincial users"
        )
    
    # Check if email already exists
    existing_user = crud_user.get_by_email(db=db, email=user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    
    try:
        user = crud_user.create_provincial_user(
            db=db,
            obj_in=user_data,
            province_code=province_code,
            created_by=current_user.username
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Log user creation
    log_user_action(
        db, current_user, "provincial_user_created", request,
        details={
            "created_user_id": str(user.id),
            "username": user.username,
            "province_code": province_code,
            "roles": [role.name for role in user.roles]
        }
    )
    
    return UserResponse.from_orm(user)


@router.post("/national", response_model=UserResponse, summary="Create National User")
async def create_national_user(
    user_data: UserCreate,
    request: Request = Request,
    current_user: User = Depends(require_permission("users.create")),
    db: Session = Depends(get_db)
):
    """
    Create national user (National Admin) with national username generation
    """
    # Check role hierarchy - only system admins can create national users
    if not current_user.is_superuser:
        current_user_max_level = 0
        for role in current_user.roles:
            if hasattr(role, 'hierarchy_level') and role.hierarchy_level:
                current_user_max_level = max(current_user_max_level, role.hierarchy_level)
        
        if current_user_max_level < 4:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only System Administrators can create National users"
            )
    
    # Check if email already exists
    existing_user = crud_user.get_by_email(db=db, email=user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    
    try:
        user = crud_user.create_national_user(
            db=db,
            obj_in=user_data,
            created_by=current_user.username
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    # Log user creation
    log_user_action(
        db, current_user, "national_user_created", request,
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
    
    # Capture old data for audit logging
    old_data = {
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "full_name": user.full_name,
        "madagascar_id_number": user.madagascar_id_number,
        "phone_number": user.phone_number,
        "department": user.department,
        "job_title": user.job_title,
        "status": user.status.value if user.status else None,
        "roles": [role.name for role in user.roles],
        "primary_location_id": str(user.primary_location_id) if user.primary_location_id else None,
    }
    
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
    
    # Comprehensive audit logging
    audit_service = MadagascarAuditService(db)
    user_context = create_user_context(current_user, request)
    
    audit_service.log_data_change(
        resource_type="USER",
        resource_id=str(user_id),
        old_data=old_data,
        new_data=user_data.dict(exclude_unset=True),
        user_context=user_context,
        screen_reference="UserEditPage",
        endpoint=str(request.url.path),
        method=request.method
    )
    
    # Legacy audit logging for compatibility
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


@router.post("/{user_id}/assign-location", response_model=UserResponse, summary="Assign User to Location")
async def assign_user_to_location(
    user_id: uuid.UUID,
    location_id: uuid.UUID,
    is_primary: bool = Query(False, description="Set as primary location"),
    request: Request = Request,
    current_user: User = Depends(require_permission("users.update")),
    db: Session = Depends(get_db)
):
    """
    Assign user to location (primary or additional)
    """
    try:
        user = crud_user.assign_to_location(
            db=db,
            user_id=user_id,
            location_id=location_id,
            is_primary=is_primary,
            updated_by=str(current_user.id)
        )
        
        # Log location assignment
        log_user_action(
            db, current_user, "user_location_assigned", request,
            details={
                "user_id": str(user_id),
                "location_id": str(location_id),
                "is_primary": is_primary,
                "new_username": user.username if is_primary else None
            }
        )
        
        return UserResponse.from_orm(user)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{user_id}/remove-location/{location_id}", response_model=UserResponse, summary="Remove User from Location")
async def remove_user_from_location(
    user_id: uuid.UUID,
    location_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("users.update")),
    db: Session = Depends(get_db)
):
    """
    Remove user from location assignment
    """
    try:
        user = crud_user.remove_from_location(
            db=db,
            user_id=user_id,
            location_id=location_id,
            updated_by=str(current_user.id)
        )
        
        # Log location removal
        log_user_action(
            db, current_user, "user_location_removed", request,
            details={
                "user_id": str(user_id),
                "location_id": str(location_id)
            }
        )
        
        return UserResponse.from_orm(user)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{user_id}/assign-roles", response_model=UserResponse, summary="Assign Roles to User")
async def assign_roles_to_user(
    user_id: uuid.UUID,
    role_ids: List[uuid.UUID],
    request: Request,
    current_user: User = Depends(require_permission("users.update")),
    db: Session = Depends(get_db)
):
    """
    Assign roles to user
    """
    try:
        user = crud_user.assign_roles(
            db=db,
            user_id=user_id,
            role_ids=role_ids,
            updated_by=str(current_user.id)
        )
        
        # Log role assignment
        log_user_action(
            db, current_user, "user_roles_assigned", request,
            details={
                "user_id": str(user_id),
                "role_ids": [str(rid) for rid in role_ids],
                "role_names": [role.name for role in user.roles]
            }
        )
        
        return UserResponse.from_orm(user)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/location/{location_id}", response_model=List[UserResponse], summary="Get Users by Location")
async def get_users_by_location(
    location_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("users.read")),
    db: Session = Depends(get_db)
):
    """
    Get all users assigned to a specific location
    """
    users = crud_user.get_by_location(db=db, location_id=location_id)
    
    # Log location user access
    log_user_action(
        db, current_user, "location_users_accessed", request,
        details={
            "location_id": str(location_id),
            "user_count": len(users)
        }
    )
    
    return [UserResponse.from_orm(user) for user in users]


@router.get("/location/{location_id}/statistics", summary="Get Location User Statistics")
async def get_location_user_statistics(
    location_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("users.read")),
    db: Session = Depends(get_db)
):
    """
    Get user statistics for a specific location
    """
    stats = crud_user.get_location_statistics(db=db, location_id=location_id)
    
    # Log statistics access
    log_user_action(
        db, current_user, "location_user_statistics_accessed", request,
        details={
            "location_id": str(location_id),
            "total_users": stats["total_users"]
        }
    )
    
    return stats


@router.get("/search/advanced", response_model=UserListResponse, summary="Advanced User Search")
async def advanced_user_search(
    request: Request,
    search_params: UserQueryParams = Depends(),
    current_user: User = Depends(require_permission("users.read")),
    db: Session = Depends(get_db)
):
    """
    Advanced user search with comprehensive filtering
    """
    users, total = crud_user.search_users(db=db, search_params=search_params)
    
    # Calculate pagination info
    total_pages = math.ceil(total / search_params.per_page)
    
    # Log advanced search
    log_user_action(
        db, current_user, "advanced_user_search", request,
        details={
            "search_params": search_params.dict(),
            "total_results": total
        }
    )
    
    return UserListResponse(
        users=[UserResponse.from_orm(user) for user in users],
        total=total,
        page=search_params.page,
        per_page=search_params.per_page,
        total_pages=total_pages
    )


@router.get("/{user_id}/permissions", summary="Get User Permissions")
async def get_user_permissions(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("users.read")),
    db: Session = Depends(get_db)
):
    """
    Get all permissions for a user (from roles + individual overrides)
    """
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    permissions = crud_user.get_user_permissions(db=db, user_id=user_id)
    
    # Log permission access
    log_user_action(
        db, current_user, "user_permissions_accessed", request,
        details={"target_user_id": str(user_id)}
    )
    
    return {
        "user_id": user_id,
        "permissions": [
            {
                "id": str(perm.id),
                "name": perm.name,
                "display_name": perm.display_name,
                "category": perm.category,
                "resource": perm.resource,
                "action": perm.action
            }
            for perm in permissions
        ]
    }


# NEW ENDPOINTS - Phase 1 High Priority

@router.get("/by-type/{user_type}", response_model=UserListResponse, summary="Get Users by Type")
async def get_users_by_type(
    user_type: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    request: Request = Request,
    current_user: User = Depends(require_permission("users.read")),
    db: Session = Depends(get_db)
):
    """
    Get users filtered by user type (LOCATION_USER, PROVINCIAL_USER, NATIONAL_USER)
    """
    # Validate user type
    try:
        user_type_enum = UserType(user_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid user type. Must be one of: {[ut.value for ut in UserType]}"
        )
    
    # Build query
    query = db.query(User).options(
        joinedload(User.roles),
        joinedload(User.primary_location),
        joinedload(User.assigned_locations)
    ).filter(
        User.is_active == True,
        User.user_type == user_type_enum
    )
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    users = query.offset(offset).limit(per_page).all()
    
    # Calculate pagination info
    total_pages = math.ceil(total / per_page)
    
    # Log access
    log_user_action(
        db, current_user, "users_by_type_accessed", request,
        details={"user_type": user_type, "total_results": total}
    )
    
    return UserListResponse(
        users=[UserResponse.from_orm(user) for user in users],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/province/{province_code}", response_model=UserListResponse, summary="Get Users by Province")
async def get_users_by_province(
    province_code: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    user_type: Optional[str] = Query(None, description="Filter by user type"),
    request: Request = Request,
    current_user: User = Depends(require_permission("users.read")),
    db: Session = Depends(get_db)
):
    """
    Get all users in a specific province (for Traffic Dept Head management)
    Includes location users in that province + provincial users for that province
    """
    # Validate province code
    valid_provinces = ["T", "A", "D", "F", "M", "U"]
    if province_code.upper() not in valid_provinces:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid province code. Must be one of: {valid_provinces}"
        )
    
    province_code = province_code.upper()
    
    # Build query for users in this province
    query = db.query(User).options(
        joinedload(User.roles),
        joinedload(User.primary_location),
        joinedload(User.assigned_locations)
    ).filter(User.is_active == True)
    
    # Filter by province - includes both location users and provincial users
    query = query.filter(
        or_(
            User.province == province_code,  # Location users in this province
            User.scope_province == province_code  # Provincial users for this province
        )
    )
    
    # Apply user type filter if provided
    if user_type:
        try:
            user_type_enum = UserType(user_type)
            query = query.filter(User.user_type == user_type_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid user type. Must be one of: {[ut.value for ut in UserType]}"
            )
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    users = query.offset(offset).limit(per_page).all()
    
    # Calculate pagination info
    total_pages = math.ceil(total / per_page)
    
    # Log access
    log_user_action(
        db, current_user, "users_by_province_accessed", request,
        details={"province_code": province_code, "user_type": user_type, "total_results": total}
    )
    
    return UserListResponse(
        users=[UserResponse.from_orm(user) for user in users],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.post("/{user_id}/permissions/override", summary="Override User Permissions")
async def override_user_permissions(
    user_id: uuid.UUID,
    permissions: List[str],
    grant: bool = Query(..., description="True to grant permissions, False to revoke"),
    request: Request = Request,
    current_user: User = Depends(require_permission("users.manage_permissions")),
    db: Session = Depends(get_db)
):
    """
    Override individual permissions for a user (grant or revoke beyond their role defaults)
    """
    # Get target user
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Validate permissions exist
    from app.models.user import Permission
    valid_permissions = db.query(Permission).filter(Permission.name.in_(permissions)).all()
    valid_permission_names = [p.name for p in valid_permissions]
    
    invalid_permissions = set(permissions) - set(valid_permission_names)
    if invalid_permissions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid permissions: {list(invalid_permissions)}"
        )
    
    # Apply permission overrides
    from app.models.user import UserPermissionOverride
    
    overrides_applied = []
    for permission_name in valid_permission_names:
        permission = next(p for p in valid_permissions if p.name == permission_name)
        
        # Check if override already exists
        existing_override = db.query(UserPermissionOverride).filter(
            UserPermissionOverride.user_id == user_id,
            UserPermissionOverride.permission_id == permission.id
        ).first()
        
        if existing_override:
            # Update existing override
            existing_override.granted = grant
            existing_override.granted_by = current_user.id
            existing_override.updated_at = datetime.now(timezone.utc)
        else:
            # Create new override
            override = UserPermissionOverride(
                user_id=user_id,
                permission_id=permission.id,
                granted=grant,
                granted_by=current_user.id
            )
            db.add(override)
        
        overrides_applied.append({
            "permission": permission_name,
            "granted": grant
        })
    
    db.commit()
    
    # Log permission override
    log_user_action(
        db, current_user, "user_permissions_overridden", request,
        details={
            "target_user_id": str(user_id),
            "overrides": overrides_applied,
            "action": "granted" if grant else "revoked"
        }
    )
    
    return {
        "status": "success",
        "message": f"Permission overrides applied for user {user.username}",
        "user_id": user_id,
        "overrides_applied": overrides_applied
    }


@router.get("/statistics/summary", summary="Get User Statistics Summary")
async def get_user_statistics_summary(
    request: Request = Request,
    current_user: User = Depends(require_permission("users.read")),
    db: Session = Depends(get_db)
):
    """
    Get overall user statistics by type, location, province, and role
    """
    # User count by type
    user_type_stats = db.query(
        User.user_type,
        func.count(User.id).label('count')
    ).filter(User.is_active == True).group_by(User.user_type).all()
    
    # User count by province
    province_stats = db.query(
        User.province,
        func.count(User.id).label('count')
    ).filter(User.is_active == True).group_by(User.province).all()
    
    # User count by status
    status_stats = db.query(
        User.status,
        func.count(User.id).label('count')
    ).filter(User.is_active == True).group_by(User.status).all()
    
    # Role distribution
    role_stats = db.query(
        Role.name,
        func.count(User.id).label('count')
    ).join(User.roles).filter(User.is_active == True).group_by(Role.name).all()
    
    # Total users
    total_users = db.query(User).filter(User.is_active == True).count()
    
    # Log access
    log_user_action(
        db, current_user, "user_statistics_accessed", request,
        details={"total_users": total_users}
    )
    
    return {
        "total_users": total_users,
        "by_user_type": [{"type": str(stat[0]), "count": stat[1]} for stat in user_type_stats],
        "by_province": [{"province": stat[0], "count": stat[1]} for stat in province_stats],
        "by_status": [{"status": str(stat[0]), "count": stat[1]} for stat in status_stats],
        "by_role": [{"role": stat[0], "count": stat[1]} for stat in role_stats],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/statistics/province/{province_code}", summary="Get Province Statistics")
async def get_province_statistics(
    province_code: str,
    request: Request = Request,
    current_user: User = Depends(require_permission("users.read")),
    db: Session = Depends(get_db)
):
    """
    Get detailed statistics for a specific province
    """
    # Validate province code
    valid_provinces = ["T", "A", "D", "F", "M", "U"]
    if province_code.upper() not in valid_provinces:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid province code. Must be one of: {valid_provinces}"
        )
    
    province_code = province_code.upper()
    
    # Get all users in this province
    province_users = db.query(User).filter(
        User.is_active == True,
        or_(
            User.province == province_code,
            User.scope_province == province_code
        )
    ).all()
    
    # Statistics by user type
    type_stats = {}
    for user in province_users:
        user_type = str(user.user_type)
        type_stats[user_type] = type_stats.get(user_type, 0) + 1
    
    # Statistics by role
    role_stats = {}
    for user in province_users:
        for role in user.roles:
            role_stats[role.name] = role_stats.get(role.name, 0) + 1
    
    # Get locations in this province
    from app.models.user import Location
    locations = db.query(Location).filter(
        Location.province_code == province_code,
        Location.is_active == True
    ).all()
    
    # Location statistics
    location_stats = []
    for location in locations:
        location_users = [u for u in province_users if u.primary_location_id == location.id]
        location_stats.append({
            "location_id": str(location.id),
            "location_name": location.name,
            "location_code": location.code,
            "user_count": len(location_users),
            "capacity": location.max_staff_capacity,
            "utilization": len(location_users) / location.max_staff_capacity if location.max_staff_capacity > 0 else 0
        })
    
    # Log access
    log_user_action(
        db, current_user, "province_statistics_accessed", request,
        details={"province_code": province_code, "total_users": len(province_users)}
    )
    
    return {
        "province_code": province_code,
        "total_users": len(province_users),
        "by_user_type": [{"type": k, "count": v} for k, v in type_stats.items()],
        "by_role": [{"role": k, "count": v} for k, v in role_stats.items()],
        "locations": location_stats,
        "total_locations": len(locations),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# PHASE 2 - MEDIUM PRIORITY ENDPOINTS

@router.post("/bulk-create", summary="Bulk Create Users")
async def bulk_create_users(
    users_data: List[UserCreate],
    location_id: Optional[uuid.UUID] = Query(None, description="Default location ID for location-based users"),
    request: Request = Request,
    current_user: User = Depends(require_permission("users.bulk_create")),
    db: Session = Depends(get_db)
):
    """
    Create multiple users at once with role hierarchy validation
    """
    if len(users_data) > 50:  # Limit bulk operations
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 users can be created at once"
        )
    
    created_users = []
    failed_users = []
    
    for i, user_data in enumerate(users_data):
        try:
            # Validate role hierarchy for each user
            if user_data.role_ids:
                for role_id in user_data.role_ids:
                    role = db.query(Role).filter(Role.id == role_id).first()
                    if role:
                        # Get current user's max hierarchy level
                        current_user_max_level = max([r.hierarchy_level for r in current_user.roles], default=0)
                        if not current_user.is_superuser and role.hierarchy_level >= current_user_max_level:
                            raise ValueError(f"Cannot create user with role '{role.name}' - insufficient hierarchy level")
            
            # Check if email already exists
            existing_user = crud_user.get_by_email(db=db, email=user_data.email)
            if existing_user:
                raise ValueError(f"Email already exists: {user_data.email}")
            
            # Check if Madagascar ID already exists
            existing_id_user = crud_user.get_by_madagascar_id(db=db, madagascar_id=user_data.madagascar_id_number)
            if existing_id_user:
                raise ValueError(f"Madagascar ID already exists: {user_data.madagascar_id_number}")
            
            # Determine creation method based on user type
            user_type = user_data.user_type if hasattr(user_data, 'user_type') else UserType.LOCATION_USER
            
            if user_type == UserType.LOCATION_USER:
                if not location_id:
                    raise ValueError("location_id required for LOCATION_USER")
                user = crud_user.create_with_location(
                    db=db,
                    obj_in=user_data,
                    location_id=location_id,
                    created_by=current_user.username
                )
            elif user_type == UserType.PROVINCIAL_USER:
                if not user_data.scope_province:
                    raise ValueError("scope_province required for PROVINCIAL_USER")
                user = crud_user.create_provincial_user(
                    db=db,
                    obj_in=user_data,
                    province_code=user_data.scope_province,
                    created_by=current_user.username
                )
            elif user_type == UserType.NATIONAL_USER:
                user = crud_user.create_national_user(
                    db=db,
                    obj_in=user_data,
                    created_by=current_user.username
                )
            else:
                raise ValueError(f"Unknown user type: {user_type}")
            
            created_users.append({
                "index": i,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "user_type": str(user.user_type),
                "status": "created"
            })
            
        except Exception as e:
            failed_users.append({
                "index": i,
                "email": user_data.email,
                "error": str(e),
                "status": "failed"
            })
            # Continue with next user instead of failing entire batch
            continue
    
    # Log bulk creation
    log_user_action(
        db, current_user, "bulk_users_created", request,
        details={
            "total_attempted": len(users_data),
            "created_count": len(created_users),
            "failed_count": len(failed_users),
            "location_id": str(location_id) if location_id else None
        }
    )
    
    return {
        "status": "completed",
        "total_attempted": len(users_data),
        "created_count": len(created_users),
        "failed_count": len(failed_users),
        "created_users": created_users,
        "failed_users": failed_users,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/audit-log/province/{province_code}", summary="Get Province Audit Log")
async def get_province_audit_log(
    province_code: str,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    action: Optional[str] = Query(None, description="Filter by action"),
    request: Request = Request,
    current_user: User = Depends(require_permission("users.audit")),
    db: Session = Depends(get_db)
):
    """
    Get audit log for entire province (for Traffic Dept Head oversight)
    """
    # Validate province code
    valid_provinces = ["T", "A", "D", "F", "M", "U"]
    if province_code.upper() not in valid_provinces:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid province code. Must be one of: {valid_provinces}"
        )
    
    province_code = province_code.upper()
    
    # Get all users in this province
    province_user_ids = db.query(User.id).filter(
        User.is_active == True,
        or_(
            User.province == province_code,
            User.scope_province == province_code
        )
    ).subquery()
    
    # Build audit log query
    query = db.query(UserAuditLog).filter(
        UserAuditLog.user_id.in_(province_user_ids)
    ).options(
        joinedload(UserAuditLog.user),
        joinedload(UserAuditLog.location)
    )
    
    # Apply action filter
    if action:
        query = query.filter(UserAuditLog.action.like(f"%{action}%"))
    
    # Order by most recent first
    query = query.order_by(UserAuditLog.created_at.desc())
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * per_page
    audit_logs = query.offset(offset).limit(per_page).all()
    
    # Calculate pagination info
    total_pages = math.ceil(total / per_page)
    
    # Log access
    log_user_action(
        db, current_user, "province_audit_log_accessed", request,
        details={"province_code": province_code, "total_logs": total}
    )
    
    return {
        "province_code": province_code,
        "audit_logs": [
            {
                "id": str(log.id),
                "user": {
                    "id": str(log.user.id),
                    "username": log.user.username,
                    "full_name": log.user.full_name
                } if log.user else None,
                "action": log.action,
                "resource": log.resource,
                "resource_id": log.resource_id,
                "success": log.success,
                "error_message": log.error_message,
                "ip_address": log.ip_address,
                "endpoint": log.endpoint,
                "method": log.method,
                "location": log.location.name if log.location else None,
                "created_at": log.created_at.isoformat()
            }
            for log in audit_logs
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages
    } 