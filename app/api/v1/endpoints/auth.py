"""
Authentication Endpoints for Madagascar License System
Handles login, logout, token refresh, and password management

TODO: Authentication Enhancements
=================================
- TODO: Implement location-based authentication (device registration)
- TODO: Add rate limiting for login attempts
- TODO: Add 2FA support for high-privilege accounts  
- TODO: Add session management and concurrent login controls
- TODO: Add audit logging for all authentication events
- TODO: Implement location detection and validation
- TODO: Add password strength validation on change
- TODO: Add account lockout after failed attempts
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from typing import Optional
import uuid

from app.core.database import get_db
from app.core.security import (
    verify_password, get_password_hash, create_access_token, 
    create_refresh_token, verify_token, create_user_token_claims,
    validate_password_strength
)
from app.models.user import User, UserStatus, UserAuditLog
from app.schemas.user import (
    LoginRequest, LoginResponse, TokenRefreshRequest, TokenRefreshResponse,
    UserPasswordChange, UserResponse
)
from app.services.audit_service import MadagascarAuditService

router = APIRouter()
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token
    """
    try:
        # Verify and decode the JWT token
        payload = verify_token(credentials.credentials)
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user from token payload
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Find user in database
        user = db.query(User).filter(User.id == user_id).first()
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def log_user_action(
    db: Session, 
    user: User, 
    action: str, 
    request: Request,
    success: bool = True,
    error_message: Optional[str] = None,
    details: Optional[dict] = None
):
    """
    Log user actions for audit trail
    
    TODO: Enhanced Audit Logging
    - Add geolocation logging
    - Implement log retention policies
    - Add real-time security alerts
    - Enhanced details for sensitive operations
    """
    import json
    
    audit_log = UserAuditLog(
        user_id=user.id,
        action=action,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        endpoint=str(request.url.path),
        method=request.method,
        success=success,
        error_message=error_message,
        details=json.dumps(details) if details else None
    )
    
    db.add(audit_log)
    db.commit()


@router.post("/login", response_model=LoginResponse, summary="User Login")
async def login(
    login_data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return access tokens
    Sets refresh token as httpOnly cookie for security
    """
    # Find user by username or email
    user = db.query(User).filter(
        (User.username == login_data.username.lower()) | 
        (User.email == login_data.username.lower()),
        User.is_active == True
    ).first()
    
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    # Check account status
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Account is {user.status.value}"
        )
    
    # Check if account is locked
    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is temporarily locked"
        )
    
    # Reset failed login attempts on successful login
    user.failed_login_attempts = 0
    user.last_login_at = datetime.now(timezone.utc)
    user.last_login_ip = request.client.host if request.client else None
    
    # Create JWT tokens
    # User's location is determined by their assigned primary_location_id
    additional_claims = create_user_token_claims(user)
    access_token = create_access_token(user.id, additional_claims=additional_claims)
    refresh_token = create_refresh_token(user.id)
    
    # Store current token info
    user.current_token_id = access_token[:32]
    user.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=480)
    
    db.commit()
    
    # Set refresh token as httpOnly cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=30 * 24 * 60 * 60,  # 30 days
        httponly=True,
        secure=True,  # HTTPS only
        samesite="none"  # Required for cross-domain authentication (Render + Vercel)
    )
    
    # Log successful login
    log_user_action(
        db, user, "login_success", request,
        details={"primary_location_id": str(user.primary_location_id) if user.primary_location_id else None}
    )
    
    return LoginResponse(
        access_token=access_token,
        refresh_token="",  # Don't send in response, use cookie instead
        token_type="bearer",
        expires_in=480 * 60,  # 8 hours in seconds
        user=UserResponse.from_orm(user)
    )


@router.post("/logout", summary="User Logout")
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout current user and invalidate tokens
    """
    # Clear current token info
    current_user.current_token_id = None
    current_user.token_expires_at = None
    current_user.refresh_token_hash = None
    
    db.commit()
    
    # Clear refresh token cookie
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=True,
        samesite="none"  # Match the login cookie settings
    )
    
    # Log logout
    log_user_action(db, current_user, "logout", request)
    
    return {"message": "Successfully logged out"}


@router.post("/refresh", response_model=TokenRefreshResponse, summary="Refresh Access Token")
async def refresh_token(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token from httpOnly cookie
    """
    # Get refresh token from cookie
    refresh_token = request.cookies.get("refresh_token")
    
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided"
        )
    
    payload = verify_token(refresh_token)
    
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Get user
    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    
    if not user or user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new access token
    additional_claims = create_user_token_claims(user)
    access_token = create_access_token(user.id, additional_claims=additional_claims)
    
    # Update token info
    user.current_token_id = access_token[:32]
    user.token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=480)
    
    db.commit()
    
    # Log token refresh
    log_user_action(db, user, "token_refresh", request)
    
    return TokenRefreshResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=480 * 60
    )


@router.post("/change-password", summary="Change Password")
async def change_password(
    password_data: UserPasswordChange,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change user password
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.password_hash):
        log_user_action(
            db, current_user, "password_change_failed", request,
            success=False, error_message="Invalid current password"
        )
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Validate new password strength
    validation = validate_password_strength(password_data.new_password)
    if not validation["valid"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Password does not meet security requirements",
                "errors": validation["errors"],
                "warnings": validation["warnings"]
            }
        )
    
    # Update password
    current_user.password_hash = get_password_hash(password_data.new_password)
    current_user.require_password_change = False
    current_user.password_expires_at = None
    
    db.commit()
    
    # Log password change
    log_user_action(
        db, current_user, "password_changed", request,
        details={"strength": validation["strength"]}
    )
    
    return {"message": "Password changed successfully"}


@router.get("/me", response_model=UserResponse, summary="Get Current User")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information
    """
    return UserResponse.from_orm(current_user) 