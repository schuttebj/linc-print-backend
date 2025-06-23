"""
Security Module for Madagascar License System
Handles authentication, password hashing, and JWT tokens
Adapted from LINC Old with Madagascar-specific settings
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Union, Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
import secrets
import uuid

from app.core.config import get_settings

settings = get_settings()

# Password hashing context (using bcrypt 4.0.1 like working LINC Old setup)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    subject: Union[str, Any], 
    expires_delta: Optional[timedelta] = None,
    additional_claims: Optional[dict] = None
) -> str:
    """
    Create JWT access token for user authentication
    
    Args:
        subject: User ID or username to encode in token
        expires_delta: Custom expiration time (defaults to settings)
        additional_claims: Additional claims to include in token
    
    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Base token payload
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.now(timezone.utc),
        "type": "access"
    }
    
    # Add additional claims if provided
    if additional_claims:
        to_encode.update(additional_claims)
    
    # Encode token
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: Union[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT refresh token for token renewal
    
    Args:
        subject: User ID or username to encode in token
        expires_delta: Custom expiration time (defaults to 7 days)
    
    Returns:
        Encoded JWT refresh token string
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=7)  # Refresh tokens last longer
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """
    Verify and decode JWT token
    
    Args:
        token: JWT token string to verify
    
    Returns:
        Token payload if valid, None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against its hash
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Stored password hash
    
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Generate password hash from plain text password
    
    Args:
        password: Plain text password to hash
    
    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def generate_password_reset_token() -> str:
    """
    Generate secure random token for password reset
    
    Returns:
        Random token string
    """
    return secrets.token_urlsafe(32)


def generate_email_verification_token() -> str:
    """
    Generate secure random token for email verification
    
    Returns:
        Random token string
    """
    return secrets.token_urlsafe(32)


def generate_backup_codes(count: int = 10) -> list:
    """
    Generate backup codes for 2FA recovery
    
    Args:
        count: Number of backup codes to generate
    
    Returns:
        List of backup codes
    """
    return [secrets.token_hex(4).upper() for _ in range(count)]


def validate_password_strength(password: str) -> dict:
    """
    Validate password strength for Madagascar license system
    
    Args:
        password: Password to validate
    
    Returns:
        Dictionary with validation results
    """
    errors = []
    warnings = []
    
    # Minimum length check
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    
    # Character type checks
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
    
    if not has_upper:
        errors.append("Password must contain at least one uppercase letter")
    
    if not has_lower:
        errors.append("Password must contain at least one lowercase letter")
    
    if not has_digit:
        errors.append("Password must contain at least one number")
    
    if not has_special:
        warnings.append("Password should contain at least one special character")
    
    # Common password checks
    common_passwords = [
        "password", "123456", "password123", "admin", "madagascar",
        "qwerty", "abc123", "letmein", "welcome", "monkey"
    ]
    
    if password.lower() in common_passwords:
        errors.append("Password is too common, please choose a different one")
    
    # Length warnings
    if len(password) < 12:
        warnings.append("Consider using a longer password (12+ characters) for better security")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "strength": calculate_password_strength(password)
    }


def calculate_password_strength(password: str) -> str:
    """
    Calculate password strength score
    
    Args:
        password: Password to evaluate
    
    Returns:
        Strength level: weak, fair, good, strong
    """
    score = 0
    
    # Length scoring
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if len(password) >= 16:
        score += 1
    
    # Character variety scoring
    if any(c.isupper() for c in password):
        score += 1
    if any(c.islower() for c in password):
        score += 1
    if any(c.isdigit() for c in password):
        score += 1
    if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        score += 1
    
    # Return strength level
    if score <= 3:
        return "weak"
    elif score <= 5:
        return "fair"
    elif score <= 6:
        return "good"
    else:
        return "strong"


def create_user_token_claims(user, location_id: Optional[uuid.UUID] = None) -> dict:
    """
    Create additional JWT claims for Madagascar license system users
    
    Args:
        user: User model instance
        location_id: Current location ID if applicable
    
    Returns:
        Dictionary of additional claims
    """
    claims = {
        "user_id": str(user.id),
        "username": user.username,
        "email": user.email,
        "country_code": user.country_code,
        "language": user.language,
        "timezone": user.timezone,
        "roles": [role.name for role in user.roles],
        "permissions": []
    }
    
    # Collect all permissions from roles
    permissions = set()
    for role in user.roles:
        for permission in role.permissions:
            permissions.add(permission.name)
    
    claims["permissions"] = list(permissions)
    
    # Add location context if provided
    if location_id:
        claims["current_location"] = str(location_id)
    
    # Add primary location if available
    if user.primary_location_id:
        claims["primary_location"] = str(user.primary_location_id)
    
    return claims 