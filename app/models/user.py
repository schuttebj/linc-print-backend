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
import re
from typing import List, Optional

from app.models.base import BaseModel
from app.models.enums import MadagascarIDType, UserStatus, UserType, RoleHierarchy

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
    username = Column(String(50), nullable=False, unique=True, index=True, comment="Location-based username (e.g., T010001)")
    email = Column(String(255), nullable=False, unique=True, index=True, comment="Email address")
    password_hash = Column(String(255), nullable=False, comment="Hashed password")
    
    # Personal information - Madagascar specific
    first_name = Column(String(100), nullable=False, comment="User's first name")
    last_name = Column(String(100), nullable=False, comment="User's last name")
    display_name = Column(String(200), nullable=True, comment="Display name for UI")
    
    # Madagascar ID information
    madagascar_id_number = Column(String(20), nullable=False, index=True, comment="CIN/CNI/Passport number")
    id_document_type = Column(SQLEnum(MadagascarIDType), nullable=False, comment="Type of ID document")
    
    # Location-based user identification
    location_user_code = Column(String(10), nullable=True, unique=True, comment="Location-based user code (e.g., T010001)")
    assigned_location_code = Column(String(5), nullable=True, comment="Location code where user is assigned (e.g., T01)")
    
    # User type and role hierarchy - NEW FIELDS
    user_type = Column(SQLEnum(UserType), nullable=False, default=UserType.LOCATION_USER, comment="User type determines username format and scope")
    scope_province = Column(String(1), nullable=True, comment="Province scope for provincial users (T, A, etc.)")
    can_create_roles = Column(Boolean, default=False, nullable=False, comment="Permission to create other user roles")
    
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
    permission_overrides = relationship("UserPermissionOverride", foreign_keys="UserPermissionOverride.user_id")
    
    # Issue tracking relationships
    reported_issues = relationship("Issue", foreign_keys="Issue.reported_by", back_populates="reported_by_user")
    assigned_issues = relationship("Issue", foreign_keys="Issue.assigned_to", back_populates="assigned_to_user")
    resolved_issues = relationship("Issue", foreign_keys="Issue.resolved_by", back_populates="resolved_by_user")
    
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
        """Check if user has specific permission through any assigned role or inherent user type permissions"""
        if self.is_superuser:
            return True
        
        # System users have all permissions (like superuser but through user type)
        if self.user_type == UserType.SYSTEM_USER:
            return True
        
        # National admins have comprehensive system-wide permissions
        if self.user_type == UserType.NATIONAL_ADMIN:
            national_permissions = [
                # User management at national level
                "users.create", "users.read", "users.update", "users.activate", "users.deactivate", 
                "users.view_statistics", "users.manage_permissions", "users.bulk_create",
                # Role management (viewing and assigning existing roles)
                "roles.read", "roles.view_hierarchy", "roles.view_statistics",
                # National oversight
                "national.manage_all", "national.view_statistics", "national.manage_provinces",
                # Provincial management
                "provinces.manage_users", "provinces.view_statistics", "provinces.view_audit_logs",
                # Location management system-wide
                "locations.create", "locations.read", "locations.update", "locations.delete", "locations.view_statistics",
                # Person management
                "persons.create", "persons.read", "persons.update", "persons.delete",
                "person_aliases.create", "person_aliases.read", "person_aliases.update", "person_aliases.delete",
                "person_addresses.create", "person_addresses.read", "person_addresses.update", "person_addresses.delete",
                # Reporting
                "reports.national", "reports.provincial", "reports.advanced", "reports.export",
                # Applications module - full permissions
                "applications.create", "applications.read", "applications.update", "applications.delete", "applications.approve",
                "applications.submit", "applications.cancel", "applications.view_statistics", "applications.bulk_process",
                "applications.assign", "applications.change_status", "applications.view_drafts", "applications.manage_associated",
                # Application documents and biometrics
                "application_documents.create", "application_documents.read", "application_documents.update", "application_documents.delete",
                "application_documents.verify", "application_biometrics.create", "application_biometrics.read", 
                "application_biometrics.update", "application_biometrics.verify",
                # Test management
                "application_tests.create", "application_tests.read", "application_tests.update", "application_tests.schedule",
                "application_tests.conduct", "application_tests.grade", "application_tests.approve_results",
                # Fee management - national level
                "fees.create", "fees.read", "fees.update", "fees.delete", "fees.configure", "fees.view_structure",
                "fee_payments.process", "fee_payments.refund", "fee_payments.view_history", "fees.discount",
                # Printing and collection
                "printing.queue", "printing.process", "printing.reprint", "printing.view_status", "printing.manage_collection",
                # Audit access
                "audit.read", "audit.national"
            ]
            if permission_name in national_permissions:
                return True
        
        # Provincial admins have provincial-level permissions
        if self.user_type == UserType.PROVINCIAL_ADMIN:
            provincial_permissions = [
                # User management at provincial level
                "users.create", "users.read", "users.update", "users.activate", "users.deactivate", 
                "users.view_statistics", "users.manage_permissions",
                # Role management (viewing and assigning existing roles)
                "roles.read", "roles.view_hierarchy", "roles.view_statistics",
                # Provincial oversight
                "provinces.manage_users", "provinces.view_statistics", "provinces.view_audit_logs",
                # Location management within province
                "locations.read", "locations.update", "locations.view_statistics",
                # Person management
                "persons.create", "persons.read", "persons.update", "persons.delete",
                "person_aliases.create", "person_aliases.read", "person_aliases.update", "person_aliases.delete",
                "person_addresses.create", "person_addresses.read", "person_addresses.update", "person_addresses.delete",
                # Reporting
                "reports.provincial", "reports.advanced", "reports.export",
                # Applications module - provincial level
                "applications.create", "applications.read", "applications.update", "applications.approve",
                "applications.submit", "applications.cancel", "applications.view_statistics", "applications.assign",
                "applications.change_status", "applications.view_drafts", "applications.manage_associated",
                # Application documents and biometrics
                "application_documents.create", "application_documents.read", "application_documents.update",
                "application_documents.verify", "application_biometrics.create", "application_biometrics.read", 
                "application_biometrics.update", "application_biometrics.verify",
                # Test management
                "application_tests.create", "application_tests.read", "application_tests.update", "application_tests.schedule",
                "application_tests.conduct", "application_tests.grade", "application_tests.approve_results",
                # Fee management - view only at provincial level
                "fees.read", "fees.view_structure", "fee_payments.process", "fee_payments.view_history",
                # Printing and collection
                "printing.queue", "printing.process", "printing.reprint", "printing.view_status", "printing.manage_collection",
                # Audit access
                "audit.read", "audit.provincial"
            ]
            if permission_name in provincial_permissions:
                return True

        # Check role-based permissions for location users
        for role in self.roles:
            for permission in role.permissions:
                if permission.name == permission_name:
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
        
        # System users and National admins can access any location
        if self.user_type in [UserType.SYSTEM_USER, UserType.NATIONAL_ADMIN]:
            return True
        
        # Provincial admins can access locations in their province
        # This check will be handled in the API layer to avoid circular imports
        if self.user_type == UserType.PROVINCIAL_ADMIN and self.scope_province:
            # Return True here - detailed province check will be done in the API layer
            return True
        
        # Check primary location
        if self.primary_location_id == location_id:
            return True
            
        # Location users have access only to their primary location
        return False
    
    def get_accessible_locations(self) -> Optional[List[uuid.UUID]]:
        """Get list of location IDs this user can access"""
        if self.is_superuser:
            # Superusers can access all locations - return None to indicate no filtering needed
            return None
        
        # System users and National admins can access any location
        if self.user_type in [UserType.SYSTEM_USER, UserType.NATIONAL_ADMIN]:
            return None
        
        # Provincial admins can access locations in their province
        if self.user_type == UserType.PROVINCIAL_ADMIN and self.scope_province:
            # Return None here - province filtering should be handled at API level
            return None
        
        # Location users can access their primary location and assigned locations
        accessible_locations = []
        
        if self.primary_location_id:
            accessible_locations.append(self.primary_location_id)
            
        for location in self.assigned_locations:
            if location.id not in accessible_locations:
                accessible_locations.append(location.id)
                
        return accessible_locations
    
    @classmethod
    def generate_system_username(cls, db_session) -> str:
        """Generate username for system user (e.g., S001, S002)"""
        from sqlalchemy.orm.exc import NoResultFound
        
        try:
            counter = db_session.query(SystemUserCounter).first()
            if not counter:
                counter = SystemUserCounter(next_user_number=1)
                db_session.add(counter)
                db_session.commit()
        except NoResultFound:
            # Create new counter
            counter = SystemUserCounter(next_user_number=1)
            db_session.add(counter)
            db_session.commit()
        
        username = counter.generate_next_user_code()
        counter.increment_counter(db_session)
        return username

    @classmethod
    def generate_provincial_username(cls, province_code: str, db_session) -> str:
        """Generate username for provincial user (e.g., T007, A002)"""
        from sqlalchemy.orm.exc import NoResultFound
        
        try:
            counter = db_session.query(ProvinceUserCounter).filter(
                ProvinceUserCounter.province_code == province_code
            ).one()
        except NoResultFound:
            # Create new counter for this province
            counter = ProvinceUserCounter(province_code=province_code, next_user_number=1)
            db_session.add(counter)
            db_session.commit()
        
        username = counter.generate_next_user_code()
        counter.increment_counter(db_session)
        return username

    @classmethod
    def generate_national_username(cls, db_session) -> str:
        """Generate username for national user (e.g., N001, N002)"""
        from sqlalchemy.orm.exc import NoResultFound
        
        try:
            counter = db_session.query(NationalUserCounter).first()
            if not counter:
                counter = NationalUserCounter(next_user_number=1)
                db_session.add(counter)
                db_session.commit()
        except NoResultFound:
            # Create new counter
            counter = NationalUserCounter(next_user_number=1)
            db_session.add(counter)
            db_session.commit()
        
        username = counter.generate_next_user_code()
        counter.increment_counter(db_session)
        return username

    @classmethod
    def generate_username_by_type(cls, user_type: UserType, db_session, location_id=None, province_code=None) -> str:
        """Generate username based on user type"""
        if user_type == UserType.SYSTEM_USER:
            return cls.generate_system_username(db_session)
        elif user_type == UserType.NATIONAL_ADMIN:
            return cls.generate_national_username(db_session)
        elif user_type == UserType.PROVINCIAL_ADMIN:
            if not province_code:
                raise ValueError("province_code required for PROVINCIAL_ADMIN")
            return cls.generate_provincial_username(province_code, db_session)
        elif user_type == UserType.LOCATION_USER:
            if not location_id:
                raise ValueError("location_id required for LOCATION_USER")
            location = db_session.query(Location).filter(Location.id == location_id).first()
            if not location:
                raise ValueError("Location not found")
            return location.generate_next_user_code()
        else:
            raise ValueError(f"Unknown user type: {user_type}")

    @classmethod
    def validate_username_format(cls, username: str) -> bool:
        """
        Validate username follows Madagascar username formats:
        - Location Users: {Province}{Office}{User} - T010001, A020003 (7 chars)
        - Provincial Users: {Province}{3digits} - T007, A002 (4 chars)  
        - National Users: N{3digits} - N001, N002 (4 chars)
        """
        # Location Users: Province code (1 letter) + Office number (2 digits) + User number (4 digits)
        location_pattern = r'^[TDFMAU]\d{6}$'
        
        # Provincial Users: Province code (1 letter) + User number (3 digits)
        provincial_pattern = r'^[TDFMAU]\d{3}$'
        
        # National Users: N + User number (3 digits)
        national_pattern = r'^N\d{3}$'
        
        return bool(
            re.match(location_pattern, username) or 
            re.match(provincial_pattern, username) or 
            re.match(national_pattern, username)
        )
    
    @classmethod
    def get_user_type_from_username(cls, username: str) -> UserType:
        """Determine user type from username format"""
        if username.startswith('S'):
            return UserType.SYSTEM_USER
        elif username.startswith('N'):
            return UserType.NATIONAL_ADMIN
        elif len(username) == 4 and username[0].isalpha():
            return UserType.PROVINCIAL_ADMIN
        elif len(username) == 6 and username[0].isalpha():
            return UserType.LOCATION_USER
        else:
            # Default fallback
            return UserType.LOCATION_USER
    
    @classmethod
    def can_create_user_role(cls, creator_role_level: int, target_role_level: int) -> bool:
        """Check if creator role can create target role based on hierarchy"""
        return creator_role_level > target_role_level
    
    @classmethod
    def extract_location_code_from_username(cls, username: str) -> str:
        """Extract location code from username (e.g., T010001 -> T01)"""
        if cls.validate_username_format(username):
            return username[:3]  # First 3 characters (province + office number)
        return ""
    
    @property
    def location_display_code(self) -> str:
        """Get display-friendly location code with MG- prefix"""
        if self.assigned_location_code:
            return f"MG-{self.assigned_location_code}"
        return "NO LOCATION"
    
    def update_location_assignment(self, location: 'Location', db_session) -> None:
        """Update user's location assignment and generate new username if needed"""
        # Update location codes
        self.assigned_location_code = location.code
        
        # If username doesn't match location format, generate new one
        if not self.validate_username_format(self.username) or not self.username.startswith(location.user_code_prefix):
            old_username = self.username
            new_username = location.generate_next_user_code()
            
            # Check if new username is available
            existing_user = db_session.query(User).filter(User.username == new_username).first()
            if existing_user:
                raise ValueError(f"Username {new_username} already exists")
            
            self.username = new_username
            self.location_user_code = new_username
            
            # Increment location's user counter
            location.increment_user_counter(db_session)
            
            return old_username, new_username
        
        return None, None


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
    
    # NEW FIELDS for enhanced role hierarchy
    hierarchy_level = Column(Integer, nullable=False, default=1, comment="Hierarchy level (1-4): 1=Clerk, 2=Supervisor, 3=Traffic Dept Head, 4=System Admin")
    user_type_restriction = Column(SQLEnum(UserType), nullable=True, comment="Restrict role to specific user type")
    scope_type = Column(String(20), nullable=False, default='location', comment="Role scope: location, province, national")
    
    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")
    child_roles = relationship("Role", backref="parent_role", remote_side="Role.id")
    
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


class UserPermissionOverride(BaseModel):
    """
    Individual user permission overrides for Madagascar License System
    Allows granting or revoking specific permissions beyond role defaults
    """
    __tablename__ = "user_permission_overrides"
    
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, index=True, comment="User receiving the override")
    permission_id = Column(UUID(as_uuid=True), ForeignKey('permissions.id'), nullable=False, index=True, comment="Permission being overridden")
    
    # Override details
    granted = Column(Boolean, nullable=False, comment="True=permission granted, False=permission revoked")
    granted_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who granted the override")
    reason = Column(Text, nullable=True, comment="Reason for the override")
    
    # Expiration (optional)
    expires_at = Column(DateTime, nullable=True, comment="When the override expires (null = permanent)")
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], overlaps="permission_overrides")
    permission = relationship("Permission")
    granted_by_user = relationship("User", foreign_keys=[granted_by])
    
    def __repr__(self):
        return f"<UserPermissionOverride(user_id={self.user_id}, permission={self.permission.name if self.permission else 'Unknown'}, granted={self.granted})>"
    
    @property
    def is_expired(self) -> bool:
        """Check if override has expired"""
        if self.expires_at:
            return self.expires_at < func.now()
        return False


class ApiRequestLog(BaseModel):
    """
    Lightweight API request logging for system monitoring and analytics
    Separate from detailed transaction audit logs for performance and storage optimization
    """
    __tablename__ = "api_request_logs"
    
    # Request identification
    request_id = Column(String(36), nullable=False, unique=True, index=True, comment="Unique request identifier")
    
    # Request details
    method = Column(String(10), nullable=False, comment="HTTP method")
    endpoint = Column(String(500), nullable=False, comment="API endpoint path")
    query_params = Column(Text, nullable=True, comment="Query parameters (JSON)")
    
    # User context
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, index=True, comment="User making request")
    ip_address = Column(String(45), nullable=True, comment="Client IP address")
    user_agent = Column(Text, nullable=True, comment="Client user agent")
    
    # Response details
    status_code = Column(Integer, nullable=False, comment="HTTP response status code")
    response_size_bytes = Column(Integer, nullable=True, comment="Response size in bytes")
    
    # Performance metrics
    duration_ms = Column(Integer, nullable=False, comment="Request duration in milliseconds")
    
    # Location context
    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=True, comment="Location where request originated")
    
    # Error tracking
    error_message = Column(Text, nullable=True, comment="Error message if request failed")
    
    # Relationships
    user = relationship("User")
    location = relationship("Location")
    
    def __repr__(self):
        return f"<ApiRequestLog(id={self.id}, method={self.method}, endpoint={self.endpoint}, status={self.status_code}, duration={self.duration_ms}ms)>"


class SystemUserCounter(BaseModel):
    """Counter for system user username generation"""
    __tablename__ = "system_user_counters"
    
    next_user_number = Column(Integer, nullable=False, default=1, comment="Next available user number")
    
    def generate_next_user_code(self) -> str:
        """Generate next system user code (S001, S002, etc.)"""
        return f"S{self.next_user_number:03d}"
    
    def increment_counter(self, db_session):
        """Increment the counter and save"""
        self.next_user_number += 1
        db_session.commit()


class ProvinceUserCounter(BaseModel):
    """Counter for provincial user username generation by province"""
    __tablename__ = "province_user_counters"
    
    province_code = Column(String(1), nullable=False, unique=True, comment="Province code (T, A, D, F, M, U)")
    next_user_number = Column(Integer, nullable=False, default=1, comment="Next available user number for this province")
    
    def generate_next_user_code(self) -> str:
        """Generate next provincial user code (T007, A002, etc.)"""
        return f"{self.province_code}{self.next_user_number:03d}"
    
    def increment_counter(self, db_session):
        """Increment the counter and save"""
        self.next_user_number += 1
        db_session.commit()


class NationalUserCounter(BaseModel):
    """Counter for national user username generation"""
    __tablename__ = "national_user_counters"
    
    next_user_number = Column(Integer, nullable=False, default=1, comment="Next available user number")
    
    def generate_next_user_code(self) -> str:
        """Generate next national user code (N001, N002, etc.)"""
        return f"N{self.next_user_number:03d}"
    
    def increment_counter(self, db_session):
        """Increment the counter and save"""
        self.next_user_number += 1
        db_session.commit()


# Location model placeholder for relationships (will be implemented in locations module)
class Location(BaseModel):
    """
    Location model for Madagascar License System offices
    Supports distributed printing with location-based user codes
    
    Location Code Format: MG-{PROVINCE_CODE}{OFFICE_NUMBER}
    User Code Format: {PROVINCE_CODE}{OFFICE_NUMBER}{USER_NUMBER}
    
    Examples:
    - Location: MG-T01 (Antananarivo, Office 01)
    - User: T010001 (First user at T01)
    """
    __tablename__ = "locations"
    
    # Basic information
    name = Column(String(200), nullable=False, comment="Location name (e.g., 'Antananarivo Central Office')")
    code = Column(String(20), nullable=False, unique=True, comment="Location code (e.g., 'T01' for Antananarivo Office 01)")
    full_code = Column(String(20), nullable=False, unique=True, comment="Full location code with MG- prefix (e.g., 'MG-T01')")
    
    # Madagascar province mapping
    province_code = Column(String(1), nullable=False, comment="Madagascar province code (T, D, F, M, A, U)")
    province_name = Column(String(50), nullable=False, comment="Full province name")
    office_number = Column(String(2), nullable=False, comment="Office number within province (01-99)")
    
    # Office classification
    office_type = Column(String(20), nullable=False, default="MAIN", comment="Office type: MAIN, MOBILE, TEMPORARY")
    
    # Address information
    street_address = Column(String(255), nullable=True, comment="Street address")
    locality = Column(String(100), nullable=False, comment="City/town/locality")
    postal_code = Column(String(10), nullable=True, comment="Postal code")
    
    # Contact information
    phone_number = Column(String(20), nullable=True, comment="Office phone number")
    email = Column(String(100), nullable=True, comment="Office email address")
    manager_name = Column(String(100), nullable=True, comment="Office manager name")
    
    # Operational settings
    is_operational = Column(Boolean, default=True, nullable=False, comment="Whether office is currently operational")
    accepts_applications = Column(Boolean, default=True, nullable=False, comment="Accepts new license applications")
    accepts_renewals = Column(Boolean, default=True, nullable=False, comment="Accepts license renewals")
    accepts_collections = Column(Boolean, default=True, nullable=False, comment="Accepts license collections")
    
    # Capacity management
    max_daily_capacity = Column(Integer, default=50, nullable=False, comment="Maximum applications per day")
    current_staff_count = Column(Integer, default=0, nullable=False, comment="Current number of staff")
    max_staff_capacity = Column(Integer, default=10, nullable=False, comment="Maximum staff capacity")
    
    # User code generation tracking
    next_user_number = Column(Integer, default=1, nullable=False, comment="Next user number to assign (1-9999)")
    
    # Operating hours and notes
    operating_hours = Column(Text, nullable=True, comment="Legacy operating hours (JSON string)")
    operational_schedule = Column(Text, nullable=True, comment="Structured operational schedule (JSON array of day schedules)")
    special_notes = Column(Text, nullable=True, comment="Special instructions or notes")
    
    # Relationships
    primary_users = relationship("User", foreign_keys="User.primary_location_id", back_populates="primary_location")
    
    def __repr__(self):
        return f"<Location(id={self.id}, code='{self.code}', name='{self.name}', type='{self.office_type}')>"
    
    @property
    def display_code(self) -> str:
        """Get display-friendly code with MG- prefix"""
        return self.full_code
    
    @property
    def user_code_prefix(self) -> str:
        """Get the prefix for user codes at this location"""
        return f"{self.province_code}{self.office_number}"
    
    def generate_next_user_code(self) -> str:
        """Generate the next user code for this location"""
        user_code = f"{self.user_code_prefix}{self.next_user_number:04d}"
        return user_code
    
    def increment_user_counter(self, db_session) -> None:
        """Increment the user counter after creating a new user"""
        if self.next_user_number >= 9999:
            raise ValueError(f"Maximum user capacity (9999) reached for location {self.code}")
        
        self.next_user_number += 1
        db_session.commit()
    
    @classmethod
    def validate_province_code(cls, province_code: str) -> bool:
        """Validate Madagascar province code"""
        valid_codes = ["T", "D", "F", "M", "A", "U"]  # Antananarivo, Antsiranana, Fianarantsoa, Mahajanga, Toamasina, Toliara
        return province_code.upper() in valid_codes
    
    @classmethod
    def get_province_name(cls, province_code: str) -> str:
        """Get full province name from code"""
        province_map = {
            "T": "ANTANANARIVO",
            "D": "ANTSIRANANA", 
            "F": "FIANARANTSOA",
            "M": "MAHAJANGA",
            "A": "TOAMASINA",
            "U": "TOLIARA"
        }
        return province_map.get(province_code.upper(), "UNKNOWN")
    
    @classmethod
    def validate_office_type(cls, office_type: str) -> bool:
        """Validate office type"""
        valid_types = ["MAIN", "MOBILE", "TEMPORARY"]
        return office_type.upper() in valid_types 