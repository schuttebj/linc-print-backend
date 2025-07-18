"""
User Schemas for Madagascar License System API
Pydantic models for request/response validation
"""

from pydantic import BaseModel, EmailStr, Field, validator, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

from app.models.enums import UserStatus, MadagascarIDType, UserType, RoleHierarchy


class UserStatusEnum(str, Enum):
    """User status enum for API"""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"
    LOCKED = "LOCKED"
    PENDING_ACTIVATION = "PENDING_ACTIVATION"


class MadagascarIDTypeEnum(str, Enum):
    """Madagascar ID type enum for API"""
    MADAGASCAR_ID = "MADAGASCAR_ID"
    PASSPORT = "PASSPORT"
    FOREIGN_ID = "FOREIGN_ID"


class UserTypeEnum(str, Enum):
    """User type enum for API"""
    SYSTEM_USER = "SYSTEM_USER"
    NATIONAL_ADMIN = "NATIONAL_ADMIN"
    PROVINCIAL_ADMIN = "PROVINCIAL_ADMIN"
    LOCATION_USER = "LOCATION_USER"


class RoleHierarchyEnum(int, Enum):
    """Role hierarchy enum for API"""
    CLERK = 1
    OFFICE_SUPERVISOR = 2
    NATIONAL_ADMIN = 3
    SYSTEM_ADMIN = 4


# Base schemas
class UserBase(BaseModel):
    """Base user schema with common fields"""
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    email: EmailStr = Field(..., description="Email address")
    first_name: str = Field(..., min_length=1, max_length=100, description="First name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Last name")
    display_name: Optional[str] = Field(None, max_length=200, description="Display name")
    
    # Madagascar-specific fields
    madagascar_id_number: str = Field(..., min_length=5, max_length=20, description="CIN/CNI/Passport number")
    id_document_type: MadagascarIDTypeEnum = Field(..., description="Type of ID document")
    
    # NEW FIELDS - User type and role hierarchy
    user_type: UserTypeEnum = Field(default=UserTypeEnum.LOCATION_USER, description="User type determines username format and scope")
    scope_province: Optional[str] = Field(None, max_length=1, description="Province scope for provincial users")
    can_create_roles: bool = Field(default=False, description="Permission to create other user roles")
    
    # Location-based assignment
    primary_location_id: Optional[uuid.UUID] = Field(None, description="Primary location assignment")
    assigned_location_ids: List[uuid.UUID] = Field(default=[], description="Additional location assignments")
    
    # Contact information
    phone_number: Optional[str] = Field(None, max_length=20, description="Phone number")
    employee_id: Optional[str] = Field(None, max_length=50, description="Employee ID")
    department: Optional[str] = Field(None, max_length=100, description="Department")
    
    # Geographic assignment
    province: Optional[str] = Field(None, max_length=100, description="Province")
    region: Optional[str] = Field(None, max_length=100, description="Region")
    office_location: Optional[str] = Field(None, max_length=200, description="Office location")
    
    # User preferences
    language: str = Field(default="en", description="Preferred language")
    timezone: str = Field(default="Indian/Antananarivo", description="Timezone")
    currency: str = Field(default="MGA", description="Currency")
    
    @validator('username')
    def validate_username(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username can only contain letters, numbers, hyphens, and underscores')
        return v.lower()
    
    @validator('madagascar_id_number')
    def validate_madagascar_id(cls, v):
        # Basic validation - can be enhanced with actual CIN/CNI format rules
        if not v.replace('-', '').replace(' ', '').isalnum():
            raise ValueError('Madagascar ID number contains invalid characters')
        return v.upper()


class UserCreate(UserBase):
    """Schema for creating a new user"""
    password: str = Field(..., min_length=8, description="Password")
    confirm_password: str = Field(..., description="Password confirmation")
    role_ids: List[uuid.UUID] = Field(default=[], description="List of role IDs to assign")
    primary_location_id: Optional[uuid.UUID] = Field(None, description="Primary location ID")
    assigned_location_ids: List[uuid.UUID] = Field(default=[], description="Assigned location IDs")
    
    # Permission management fields
    permission_names: Optional[List[str]] = Field(None, description="Final list of permission names for the user")
    permission_overrides: Optional[Dict[str, bool]] = Field(None, description="Permission overrides (differences from role defaults)")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    display_name: Optional[str] = Field(None, max_length=200)
    
    # Madagascar-specific fields
    madagascar_id_number: Optional[str] = Field(None, min_length=5, max_length=20)
    id_document_type: Optional[MadagascarIDTypeEnum] = None
    
    # Location-based assignment
    primary_location_id: Optional[uuid.UUID] = None
    assigned_location_ids: Optional[List[uuid.UUID]] = None
    
    # Contact information
    phone_number: Optional[str] = Field(None, max_length=20)
    employee_id: Optional[str] = Field(None, max_length=50)
    department: Optional[str] = Field(None, max_length=100)
    
    # Geographic assignment
    province: Optional[str] = Field(None, max_length=100)
    region: Optional[str] = Field(None, max_length=100)
    office_location: Optional[str] = Field(None, max_length=200)
    
    # User preferences
    language: Optional[str] = None
    timezone: Optional[str] = None
    currency: Optional[str] = None
    
    # Status updates (admin only)
    status: Optional[UserStatusEnum] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None
    
    # Role and location assignments
    role_ids: Optional[List[uuid.UUID]] = None
    
    # Permission management fields
    permission_names: Optional[List[str]] = Field(None, description="Final list of permission names for the user")
    permission_overrides: Optional[Dict[str, bool]] = Field(None, description="Permission overrides (differences from role defaults)")


class UserPasswordChange(BaseModel):
    """Schema for password change"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    confirm_password: str = Field(..., description="New password confirmation")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class UserPasswordReset(BaseModel):
    """Schema for password reset"""
    email: EmailStr = Field(..., description="Email address")


class UserPasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation"""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")
    confirm_password: str = Field(..., description="Password confirmation")
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


# Response schemas
class RoleResponse(BaseModel):
    """Role information in user responses"""
    id: uuid.UUID
    name: str
    display_name: str
    description: Optional[str]
    hierarchy_level: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


class LocationResponse(BaseModel):
    """Location information in user responses"""
    id: uuid.UUID
    name: str
    code: str
    office_type: str
    
    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    """Schema for user response"""
    id: uuid.UUID
    username: str
    email: str
    first_name: str
    last_name: str
    display_name: Optional[str]
    full_name: str
    
    # Madagascar-specific fields
    madagascar_id_number: str
    id_document_type: MadagascarIDTypeEnum
    
    # NEW FIELDS - User type and role hierarchy
    user_type: UserTypeEnum
    scope_province: Optional[str]
    can_create_roles: bool
    
    # Contact information
    phone_number: Optional[str]
    employee_id: Optional[str]
    department: Optional[str]
    
    # Geographic assignment
    country_code: str
    province: Optional[str]
    region: Optional[str]
    office_location: Optional[str]
    
    # Status and settings
    status: UserStatusEnum
    is_superuser: bool
    is_verified: bool
    
    # User preferences
    language: str
    timezone: str
    currency: str
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]
    
    # Relationships
    roles: List[RoleResponse]
    primary_location: Optional[LocationResponse]
    assigned_locations: List[LocationResponse]
    
    model_config = ConfigDict(from_attributes=True)
    
    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm to populate permission overrides"""
        # Get the basic user data
        user_data = {
            'id': obj.id,
            'username': obj.username,
            'email': obj.email,
            'first_name': obj.first_name,
            'last_name': obj.last_name,
            'display_name': obj.display_name,
            'full_name': obj.full_name,
            'madagascar_id_number': obj.madagascar_id_number,
            'id_document_type': obj.id_document_type,
            'user_type': obj.user_type,
            'scope_province': obj.scope_province,
            'can_create_roles': obj.can_create_roles,
            'phone_number': obj.phone_number,
            'employee_id': obj.employee_id,
            'department': obj.department,
            'country_code': obj.country_code,
            'province': obj.province,
            'region': obj.region,
            'office_location': obj.office_location,
            'status': obj.status,
            'is_superuser': obj.is_superuser,
            'is_verified': obj.is_verified,
            'language': obj.language,
            'timezone': obj.timezone,
            'currency': obj.currency,
            'created_at': obj.created_at,
            'updated_at': obj.updated_at,
            'last_login_at': obj.last_login_at,
            'roles': obj.roles,
            'primary_location': obj.primary_location,
            'assigned_locations': obj.assigned_locations,
        }
        
        # Get permission overrides
        permission_overrides = {}
        if hasattr(obj, 'permission_overrides') and obj.permission_overrides:
            for override in obj.permission_overrides:
                if override.permission and not override.is_expired:
                    permission_overrides[override.permission.name] = override.granted
        
        user_data['permission_overrides'] = permission_overrides if permission_overrides else None
        
        return cls(**user_data)


class UserListResponse(BaseModel):
    """Schema for paginated user list response"""
    users: List[UserResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class UserSummary(BaseModel):
    """Summary user information for lists"""
    id: uuid.UUID
    username: str
    email: str
    full_name: str
    madagascar_id_number: str
    status: UserStatusEnum
    roles: List[str]  # Just role names
    department: Optional[str]
    last_login_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


# Authentication schemas
class LoginRequest(BaseModel):
    """User login request"""
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")
    
    # NOTE: Location removed - using one account per employee per location model
    # Each user is assigned to a specific location and cannot access multiple locations


class LoginResponse(BaseModel):
    """User login response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserResponse


class TokenRefreshRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str = Field(..., description="Refresh token")


class TokenRefreshResponse(BaseModel):
    """Token refresh response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# Role and Permission schemas
class PermissionResponse(BaseModel):
    """Permission information"""
    id: uuid.UUID
    name: str
    display_name: str
    description: Optional[str]
    category: str
    resource: str
    action: str
    
    model_config = ConfigDict(from_attributes=True)


class RoleDetailResponse(BaseModel):
    """Detailed role information"""
    id: uuid.UUID
    name: str
    display_name: str
    description: Optional[str]
    is_system_role: bool
    allowed_modules: Optional[List[str]] = []
    level: int
    
    # NEW FIELDS - Enhanced role hierarchy
    hierarchy_level: Optional[int] = None
    user_type_restriction: Optional[UserTypeEnum] = None
    scope_type: Optional[str] = "location"
    
    permissions: List[PermissionResponse] = []
    parent_role: Optional[RoleResponse] = None
    child_roles: List[RoleResponse] = []
    
    model_config = ConfigDict(from_attributes=True)
    
    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm to handle data conversion"""
        # Handle allowed_modules conversion from string to list
        allowed_modules = []
        if hasattr(obj, 'allowed_modules') and obj.allowed_modules:
            try:
                if isinstance(obj.allowed_modules, str):
                    # Try to parse as JSON list, fallback to simple split
                    import json
                    try:
                        allowed_modules = json.loads(obj.allowed_modules)
                    except:
                        # Fallback to split by comma
                        allowed_modules = [m.strip() for m in obj.allowed_modules.split(',') if m.strip()]
                elif isinstance(obj.allowed_modules, list):
                    allowed_modules = obj.allowed_modules
            except:
                allowed_modules = []
        
        # Handle parent_role - ensure it's a single object or None
        parent_role = None
        if hasattr(obj, 'parent_role') and obj.parent_role:
            if isinstance(obj.parent_role, list):
                parent_role = obj.parent_role[0] if obj.parent_role else None
            else:
                parent_role = obj.parent_role
        
        # Handle child_roles - ensure it's a list
        child_roles = []
        if hasattr(obj, 'child_roles') and obj.child_roles:
            if isinstance(obj.child_roles, list):
                child_roles = obj.child_roles
            else:
                child_roles = [obj.child_roles]
        
        # Handle permissions - ensure it's a list
        permissions = []
        if hasattr(obj, 'permissions') and obj.permissions:
            permissions = obj.permissions if isinstance(obj.permissions, list) else [obj.permissions]
        
        return cls(
            id=obj.id,
            name=obj.name,
            display_name=obj.display_name,
            description=obj.description,
            is_system_role=obj.is_system_role,
            allowed_modules=allowed_modules,
            level=obj.level,
            hierarchy_level=getattr(obj, 'hierarchy_level', None),
            user_type_restriction=getattr(obj, 'user_type_restriction', None),
            scope_type=getattr(obj, 'scope_type', 'location'),
            permissions=permissions,
            parent_role=parent_role,
            child_roles=child_roles
        )


class RoleCreate(BaseModel):
    """Schema for creating a role"""
    name: str = Field(..., min_length=2, max_length=50)
    display_name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    allowed_modules: List[str] = Field(default=[])
    permission_ids: List[uuid.UUID] = Field(default=[])
    parent_role_id: Optional[uuid.UUID] = None
    
    # NEW FIELDS - Enhanced role hierarchy
    hierarchy_level: int = Field(..., ge=1, le=4, description="Hierarchy level (1-4)")
    user_type_restriction: Optional[UserTypeEnum] = Field(None, description="Restrict role to specific user type")
    scope_type: str = Field(default='location', description="Role scope: location, province, national")


class RoleUpdate(BaseModel):
    """Schema for updating a role"""
    display_name: Optional[str] = Field(None, min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    allowed_modules: Optional[List[str]] = None
    permission_ids: Optional[List[uuid.UUID]] = None
    parent_role_id: Optional[uuid.UUID] = None
    
    # NEW FIELDS - Enhanced role hierarchy
    hierarchy_level: Optional[int] = Field(None, ge=1, le=4, description="Hierarchy level (1-4)")
    user_type_restriction: Optional[UserTypeEnum] = Field(None, description="Restrict role to specific user type")
    scope_type: Optional[str] = Field(None, description="Role scope: location, province, national")


# Permission assignment schemas
class UserPermissionAssignment(BaseModel):
    """Schema for assigning permissions to user"""
    user_id: uuid.UUID
    permission_ids: List[uuid.UUID]


class RolePermissionAssignment(BaseModel):
    """Schema for assigning permissions to role"""
    role_id: uuid.UUID
    permission_ids: List[uuid.UUID]


# Audit schemas
class UserAuditLogResponse(BaseModel):
    """User audit log response"""
    id: uuid.UUID
    user_id: uuid.UUID
    action: str
    resource: Optional[str]
    resource_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    endpoint: Optional[str]
    method: Optional[str]
    success: bool
    error_message: Optional[str]
    details: Optional[Dict[str, Any]]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# Query parameters
class UserQueryParams(BaseModel):
    """Query parameters for user search"""
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    search: Optional[str] = None
    status: Optional[UserStatusEnum] = None
    role: Optional[str] = None
    department: Optional[str] = None
    location_id: Optional[uuid.UUID] = None
    sort_by: str = Field(default="created_at")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$") 