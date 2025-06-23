"""
User Management Models for Madagascar License System
Adapted from LINC Old with Madagascar-specific requirements:
- CIN/CNI ID numbers
- Clerk/Supervisor/Printer roles  
- English language default
- UUID primary keys
- Distributed printing support
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Table, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PythonEnum
import uuid

from app.models.base import BaseModel

# Association table for many-to-many relationship between users and roles
user_roles = Table(
    'user_roles',
    BaseModel.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id'), primary_key=True),
    Column('role_id', UUID(as_uuid=True), ForeignKey('roles.id'), primary_key=True)
)

# Association table for many-to-many relationship between roles and permissions
role_permissions = Table(
    'role_permissions', 
    BaseModel.metadata,
    Column('role_id', UUID(as_uuid=True), ForeignKey('roles.id'), primary_key=True),
    Column('permission_id', UUID(as_uuid=True), ForeignKey('permissions.id'), primary_key=True)
)

# Association table for user location assignments
user_locations = Table(
    'user_locations',
    BaseModel.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id'), primary_key=True),
    Column('location_id', UUID(as_uuid=True), ForeignKey('locations.id'), primary_key=True)
)


class UserStatus(PythonEnum):
    """User account status for Madagascar License System"""
    ACTIVE = "active"
    INACTIVE = "inactive" 
    SUSPENDED = "suspended"
    LOCKED = "locked"
    PENDING_ACTIVATION = "pending_activation"


class MadagascarIDType(PythonEnum):
    """Madagascar ID document types"""
    CIN = "CIN"           # Carte d'Identité Nationale
    CNI = "CNI"           # Carte Nationale d'Identité
    PASSPORT = "PASSPORT" # Passport
    BIRTH_CERT = "BIRTH_CERT"  # Birth certificate (for minors)


class User(BaseModel):
    """
    User account model for Madagascar License System
    
    Adapted from LINC Old with Madagascar-specific requirements:
    - CIN/CNI ID number capture
    - Madagascar timezone and currency
    - English default language
    - Role-based access control for Clerk/Supervisor/Printer
    - Multi-location assignment for distributed printing
    
    TODO: User Model Enhancements
    =============================
    - TODO: Add biometric data fields (when Persons module is implemented)
    - TODO: Add location preferences and restrictions  
    - TODO: Add session management and device tracking
    - TODO: Add user activity logging enhancements
    - TODO: Add password policy enforcement
    - TODO: Add device registration for automatic location detection
    """
    __tablename__ = "users"
    
    # Authentication credentials
    username = Column(String(50), nullable=False, unique=True, index=True, comment="Unique username for login")
    email = Column(String(255), nullable=False, unique=True, index=True, comment="Email address")
    password_hash = Column(String(255), nullable=False, comment="Hashed password")
    
    # Personal information - Madagascar specific
    first_name = Column(String(100), nullable=False, comment="User's first name")
    last_name = Column(String(100), nullable=False, comment="User's last name")
    display_name = Column(String(200), nullable=True, comment="Display name for UI")
    
    # Madagascar ID information
    madagascar_id_number = Column(String(20), nullable=False, index=True, comment="CIN/CNI number")
    id_document_type = Column(SQLEnum(MadagascarIDType), nullable=False, comment="Type of ID document")
    
    # Account status and settings
    status = Column(SQLEnum(UserStatus), nullable=False, default=UserStatus.PENDING_ACTIVATION, comment="Account status")
    is_superuser = Column(Boolean, nullable=False, default=False, comment="Superuser flag")
    is_verified = Column(Boolean, nullable=False, default=False, comment="Email verification status")
    
    # Contact information
    phone_number = Column(String(20), nullable=True, comment="Contact phone number")
    employee_id = Column(String(50), nullable=True, unique=True, comment="Employee/staff ID number")
    department = Column(String(100), nullable=True, comment="Department or division")
    
    # Geographic assignment for distributed printing
    country_code = Column(String(3), nullable=False, default='MG', comment="Country code - Madagascar")
    province = Column(String(100), nullable=True, comment="Assigned province")
    region = Column(String(100), nullable=True, comment="Assigned region")
    office_location = Column(String(200), nullable=True, comment="Physical office location")
    
    # Primary location assignment
    primary_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=True, comment="Primary work location")
    
    # Security settings
    require_password_change = Column(Boolean, nullable=False, default=False, comment="Force password change on next login")
    password_expires_at = Column(DateTime, nullable=True, comment="Password expiration date")
    failed_login_attempts = Column(Integer, nullable=False, default=0, comment="Failed login attempt counter")
    locked_until = Column(DateTime, nullable=True, comment="Account lock expiration")
    last_login_at = Column(DateTime, nullable=True, comment="Last successful login timestamp")
    last_login_ip = Column(String(45), nullable=True, comment="Last login IP address")
    
    # Two-factor authentication (optional for Madagascar deployment)
    is_2fa_enabled = Column(Boolean, nullable=False, default=False, comment="Two-factor authentication enabled")
    totp_secret = Column(String(32), nullable=True, comment="TOTP secret for 2FA")
    backup_codes = Column(Text, nullable=True, comment="JSON array of backup codes")
    
    # Session and token management
    current_token_id = Column(String(255), nullable=True, comment="Current active token ID")
    token_expires_at = Column(DateTime, nullable=True, comment="Current token expiration")
    refresh_token_hash = Column(String(255), nullable=True, comment="Refresh token hash")
    
    # User preferences - Madagascar defaults
    language = Column(String(10), nullable=False, default='en', comment="Preferred language (en/fr/mg)")
    timezone = Column(String(50), nullable=False, default='Indian/Antananarivo', comment="Madagascar timezone")
    date_format = Column(String(20), nullable=False, default='YYYY-MM-DD', comment="Preferred date format")
    currency = Column(String(3), nullable=False, default='MGA', comment="Madagascar Ariary")
    
    # Activation and verification
    email_verification_token = Column(String(255), nullable=True, comment="Email verification token")
    email_verification_expires = Column(DateTime, nullable=True, comment="Email verification expiration")
    password_reset_token = Column(String(255), nullable=True, comment="Password reset token")
    password_reset_expires = Column(DateTime, nullable=True, comment="Password reset expiration")
    
    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    audit_logs = relationship("UserAuditLog", back_populates="user")
    primary_location = relationship("Location", foreign_keys=[primary_location_id])
    assigned_locations = relationship("Location", secondary=user_locations, back_populates="assigned_users")
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', madagascar_id='{self.madagascar_id_number}', status='{self.status}')>"
    
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_locked(self) -> bool:
        """Check if account is currently locked"""
        if self.locked_until:
            return self.locked_until > func.now()
        return False
    
    def has_permission(self, permission_name: str) -> bool:
        """Check if user has specific permission through any assigned role"""
        if self.is_superuser:
            return True
        
        for role in self.roles:
            if role.has_permission(permission_name):
                return True
        return False
    
    def has_role(self, role_name: str) -> bool:
        """Check if user has specific role"""
        return any(role.name == role_name for role in self.roles)
    
    def can_access_module(self, module_name: str) -> bool:
        """Check if user can access specific system module"""
        if self.is_superuser:
            return True
        
        for role in self.roles:
            if module_name in role.allowed_modules:
                return True
        return False
    
    def can_access_location(self, location_id: uuid.UUID) -> bool:
        """Check if user can access specific location"""
        if self.is_superuser:
            return True
        
        # Check primary location
        if self.primary_location_id == location_id:
            return True
            
        # Check assigned locations
        return any(location.id == location_id for location in self.assigned_locations)


class Role(BaseModel):
    """
    User role model for Madagascar License System
    
    Implements Madagascar-specific roles:
    - clerk: License processing and basic card operations
    - supervisor: All clerk functions plus approvals and reports  
    - printer: Printing operations only
    """
    __tablename__ = "roles"
    
    name = Column(String(50), nullable=False, unique=True, comment="Role name (clerk, supervisor, printer)")
    display_name = Column(String(100), nullable=False, comment="Human-readable role name")
    description = Column(Text, nullable=True, comment="Role description")
    
    # Role settings
    is_system_role = Column(Boolean, nullable=False, default=False, comment="System-defined role (cannot be deleted)")
    
    # Module access - JSON array of allowed modules
    allowed_modules = Column(Text, nullable=True, comment="JSON array of allowed system modules")
    
    # Role hierarchy for inheritance (supervisor inherits from clerk)
    parent_role_id = Column(UUID(as_uuid=True), ForeignKey('roles.id'), nullable=True, comment="Parent role for inheritance")
    level = Column(Integer, nullable=False, default=0, comment="Role hierarchy level")
    
    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    child_roles = relationship("Role", backref="parent_role", remote_side=[id])
    
    def __repr__(self):
        return f"<Role(id={self.id}, name='{self.name}', display_name='{self.display_name}')>"
    
    def has_permission(self, permission_name: str) -> bool:
        """Check if role has specific permission"""
        # Check direct permissions
        for permission in self.permissions:
            if permission.name == permission_name:
                return True
        
        # Check inherited permissions from parent role
        if self.parent_role:
            return self.parent_role.has_permission(permission_name)
        
        return False
    
    @property
    def allowed_modules_list(self) -> list:
        """Get allowed modules as a list"""
        if not self.allowed_modules:
            return []
        
        try:
            import json
            return json.loads(self.allowed_modules)
        except:
            return []


class Permission(BaseModel):
    """
    Permission model for Madagascar License System
    
    Implements granular permissions for:
    - License application processing (create, read, update, approve)
    - Card management (order, issue, reorder, approve, qa)
    - Biometric data handling
    - Payment processing
    - Printing operations (local, cross-location, queue management)
    - Reports (basic, advanced, export)
    """
    __tablename__ = "permissions"
    
    name = Column(String(100), nullable=False, unique=True, comment="Permission name/code (e.g., license_applications.create)")
    display_name = Column(String(150), nullable=False, comment="Human-readable permission name")
    description = Column(Text, nullable=True, comment="Permission description")
    
    # Permission categorization
    category = Column(String(50), nullable=False, comment="Permission category (license_applications, card_management, etc.)")
    resource = Column(String(100), nullable=False, comment="Resource being protected")
    action = Column(String(50), nullable=False, comment="Action being permitted (create, read, update, delete, approve)")
    
    # Permission settings
    is_system_permission = Column(Boolean, nullable=False, default=False, comment="System-defined permission")
    
    # Relationships
    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")
    
    def __repr__(self):
        return f"<Permission(id={self.id}, name='{self.name}', category='{self.category}')>"


class UserAuditLog(BaseModel):
    """
    User audit log for Madagascar License System
    Tracks all user actions for compliance and security
    """
    __tablename__ = "user_audit_logs"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True)
    
    # Action details
    action = Column(String(100), nullable=False, comment="Action performed")
    resource = Column(String(100), nullable=True, comment="Resource affected")
    resource_id = Column(String(100), nullable=True, comment="ID of affected resource")
    
    # Request details
    ip_address = Column(String(45), nullable=True, comment="Client IP address")
    user_agent = Column(Text, nullable=True, comment="Client user agent")
    endpoint = Column(String(200), nullable=True, comment="API endpoint accessed")
    method = Column(String(10), nullable=True, comment="HTTP method")
    
    # Result details
    success = Column(Boolean, nullable=False, comment="Whether action was successful")
    error_message = Column(Text, nullable=True, comment="Error message if failed")
    details = Column(Text, nullable=True, comment="Additional action details (JSON)")
    
    # Location context for distributed system
    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=True, comment="Location where action occurred")
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    location = relationship("Location")
    
    def __repr__(self):
        return f"<UserAuditLog(id={self.id}, user_id={self.user_id}, action='{self.action}', success={self.success})>"


# Location model placeholder for relationships (will be implemented in locations module)
class Location(BaseModel):
    """
    Location model placeholder for user assignment relationships
    Full implementation will be in the locations module
    """
    __tablename__ = "locations"
    
    name = Column(String(200), nullable=False, comment="Location name")
    code = Column(String(20), nullable=False, unique=True, comment="Location code")
    location_type = Column(String(50), nullable=False, comment="Type of location (office, test_center, etc.)")
    
    # Relationships
    assigned_users = relationship("User", secondary=user_locations, back_populates="assigned_locations")
    
    def __repr__(self):
        return f"<Location(id={self.id}, name='{self.name}', code='{self.code}')>" 