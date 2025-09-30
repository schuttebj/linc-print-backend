"""
User CRUD operations for Madagascar License System
Handles user creation, updates, location assignment, and username generation
"""

from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, and_, func, desc, asc
import uuid
from passlib.context import CryptContext

from app.crud.base import CRUDBase
from app.models.user import User, Location, Role, Permission
from app.schemas.user import UserCreate, UserUpdate, UserQueryParams
from app.crud.crud_location import location as crud_location
from app.models.enums import UserStatus

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    """CRUD operations for User model"""
    
    def create_with_location(
        self, 
        db: Session, 
        *, 
        obj_in: UserCreate,
        location_id: uuid.UUID,
        created_by: Optional[str] = None
    ) -> User:
        """Create user with location-based username generation"""
        from app.models.enums import UserType
        
        # Get location for username generation
        location = crud_location.get(db=db, id=location_id)
        if not location:
            raise ValueError("Location not found")
        
        if not location.is_operational:
            raise ValueError("Cannot create users for non-operational location")
        
        # Check location capacity
        if location.current_staff_count >= location.max_staff_capacity:
            raise ValueError(f"Location {location.code} is at maximum capacity")
        
        # Generate username based on user type
        # Convert Pydantic enum to SQLAlchemy enum
        if hasattr(obj_in, 'user_type') and obj_in.user_type:
            user_type = UserType(obj_in.user_type.value)
        else:
            user_type = UserType.LOCATION_USER
        
        if user_type == UserType.LOCATION_USER:
            username = location.generate_next_user_code()
        elif user_type == UserType.PROVINCIAL_ADMIN:
            if not obj_in.scope_province:
                raise ValueError("scope_province required for PROVINCIAL_ADMIN")
            username = User.generate_provincial_username(obj_in.scope_province, db)
        elif user_type == UserType.NATIONAL_ADMIN:
            username = User.generate_national_username(db)
        else:
            raise ValueError(f"Unknown user type: {user_type}")
        
        # Check if username already exists (should not happen with proper generation)
        existing_user = self.get_by_username(db=db, username=username)
        if existing_user:
            raise ValueError(f"Username {username} already exists")
        
        # Hash password
        hashed_password = pwd_context.hash(obj_in.password)
        
        # Create user object
        user_data = obj_in.dict(exclude={"password", "confirm_password", "role_ids", "permission_names", "permission_overrides"})
        user_data.update({
            "username": username,
            "password_hash": hashed_password,
            "user_type": user_type,
            "status": UserStatus.ACTIVE,  # Activate users by default
            "is_verified": True,  # Mark as verified
            "created_by": created_by
        })
        
        # Set location-specific fields for location users
        if user_type == UserType.LOCATION_USER:
            user_data.update({
                "primary_location_id": location_id,
                "assigned_location_code": location.code,
                "location_user_code": username,
            })
        
        user = User(**user_data)
        db.add(user)
        db.flush()  # Get user ID without committing
        
        # Assign roles
        if obj_in.role_ids:
            roles = db.query(Role).filter(Role.id.in_(obj_in.role_ids)).all()
            user.roles = roles
        
        # Apply permission overrides if provided
        if obj_in.permission_overrides:
            self._apply_permission_overrides(db, user.id, obj_in.permission_overrides, created_by)
        
        # Increment counters based on user type
        if user_type == UserType.LOCATION_USER:
            location.current_staff_count += 1
            location.increment_user_counter(db)
        
        db.commit()
        db.refresh(user)
        
        return user
    
    def create_provincial_user(
        self,
        db: Session,
        *,
        obj_in: UserCreate,
        province_code: str,
        created_by: Optional[str] = None
    ) -> User:
        """Create provincial user with province-based username generation"""
        from app.models.enums import UserType
        
        # Generate provincial username
        username = User.generate_provincial_username(province_code, db)
        
        # Check if username already exists
        existing_user = self.get_by_username(db=db, username=username)
        if existing_user:
            raise ValueError(f"Username {username} already exists")
        
        # Hash password
        hashed_password = pwd_context.hash(obj_in.password)
        
        # Create user object
        user_data = obj_in.dict(exclude={"password", "confirm_password", "role_ids", "permission_names", "permission_overrides"})
        user_data.update({
            "username": username,
            "password_hash": hashed_password,
            "user_type": UserType.PROVINCIAL_ADMIN,
            "scope_province": province_code,
            "can_create_roles": True,  # Provincial users can create office-level roles
            "status": UserStatus.ACTIVE,  # Activate users by default
            "is_verified": True,  # Mark as verified
            "created_by": created_by
        })
        
        user = User(**user_data)
        db.add(user)
        db.flush()
        
        # Assign roles
        if obj_in.role_ids:
            roles = db.query(Role).filter(Role.id.in_(obj_in.role_ids)).all()
            user.roles = roles
        
        # Apply permission overrides if provided
        if obj_in.permission_overrides:
            self._apply_permission_overrides(db, user.id, obj_in.permission_overrides, created_by)
        
        db.commit()
        db.refresh(user)
        
        return user
    
    def create_national_user(
        self,
        db: Session,
        *,
        obj_in: UserCreate,
        created_by: Optional[str] = None
    ) -> User:
        """Create national user with national username generation"""
        from app.models.enums import UserType
        
        # Generate national username
        username = User.generate_national_username(db)
        
        # Check if username already exists
        existing_user = self.get_by_username(db=db, username=username)
        if existing_user:
            raise ValueError(f"Username {username} already exists")
        
        # Hash password
        hashed_password = pwd_context.hash(obj_in.password)
        
        # Create user object
        user_data = obj_in.dict(exclude={"password", "confirm_password", "role_ids", "permission_names", "permission_overrides"})
        user_data.update({
            "username": username,
            "password_hash": hashed_password,
            "user_type": UserType.NATIONAL_ADMIN,
            "can_create_roles": True,  # National users can create all roles
            "status": UserStatus.ACTIVE,  # Activate users by default
            "is_verified": True,  # Mark as verified
            "created_by": created_by
        })
        
        user = User(**user_data)
        db.add(user)
        db.flush()
        
        # Assign roles
        if obj_in.role_ids:
            roles = db.query(Role).filter(Role.id.in_(obj_in.role_ids)).all()
            user.roles = roles
        
        # Apply permission overrides if provided
        if obj_in.permission_overrides:
            self._apply_permission_overrides(db, user.id, obj_in.permission_overrides, created_by)
        
        db.commit()
        db.refresh(user)
        
        return user
    
    def create_system_user(
        self,
        db: Session,
        *,
        obj_in: UserCreate,
        created_by: Optional[str] = None
    ) -> User:
        """Create system user with system username generation"""
        from app.models.enums import UserType
        
        # Generate system username
        username = User.generate_system_username(db)
        
        # Check if username already exists
        existing_user = self.get_by_username(db=db, username=username)
        if existing_user:
            raise ValueError(f"Username {username} already exists")
        
        # Hash password
        hashed_password = pwd_context.hash(obj_in.password)
        
        # Create user object
        user_data = obj_in.dict(exclude={"password", "confirm_password", "role_ids", "permission_names", "permission_overrides"})
        user_data.update({
            "username": username,
            "password_hash": hashed_password,
            "user_type": UserType.SYSTEM_USER,
            "can_create_roles": True,  # System users can create all roles
            "status": UserStatus.ACTIVE,  # Activate users by default
            "is_verified": True,  # Mark as verified
            "created_by": created_by
        })
        
        user = User(**user_data)
        db.add(user)
        db.flush()
        
        # Assign roles
        if obj_in.role_ids:
            roles = db.query(Role).filter(Role.id.in_(obj_in.role_ids)).all()
            user.roles = roles
        
        # Apply permission overrides if provided
        if obj_in.permission_overrides:
            self._apply_permission_overrides(db, user.id, obj_in.permission_overrides, created_by)
        
        db.commit()
        db.refresh(user)
        
        return user
    
    def get_by_username(self, db: Session, *, username: str) -> Optional[User]:
        """Get user by username"""
        return db.query(User).filter(User.username == username).first()
    
    def get_by_email(self, db: Session, *, email: str) -> Optional[User]:
        """Get user by email"""
        return db.query(User).filter(User.email == email).first()
    
    def get_by_madagascar_id(self, db: Session, *, madagascar_id: str) -> Optional[User]:
        """Get user by Madagascar ID number"""
        return db.query(User).filter(User.madagascar_id_number == madagascar_id).first()
    
    def get_by_location(self, db: Session, *, location_id: uuid.UUID) -> List[User]:
        """Get all users assigned to a location"""
        return db.query(User).filter(
            or_(
                User.primary_location_id == location_id,
                User.assigned_locations.any(Location.id == location_id)
            ),
            User.is_active == True
        ).all()
    
    def search_users(
        self, 
        db: Session, 
        *, 
        search_params: UserQueryParams
    ) -> Tuple[List[User], int]:
        """Search users with filters and pagination"""
        query = db.query(User).options(
            joinedload(User.roles),
            joinedload(User.primary_location),
            joinedload(User.assigned_locations)
        ).filter(User.is_active == True)
        
        # Apply search filter
        if search_params.search:
            search_term = f"%{search_params.search.upper()}%"
            query = query.filter(
                or_(
                    func.upper(User.username).like(search_term),
                    func.upper(User.email).like(search_term),
                    func.upper(User.first_name).like(search_term),
                    func.upper(User.last_name).like(search_term),
                    func.upper(User.madagascar_id_number).like(search_term),
                    func.upper(User.employee_id).like(search_term)
                )
            )
        
        # Apply status filter
        if search_params.status:
            query = query.filter(User.status == search_params.status.value)
        
        # Apply role filter
        if search_params.role:
            query = query.join(User.roles).filter(Role.name == search_params.role)
        
        # Apply department filter
        if search_params.department:
            query = query.filter(func.upper(User.department).like(f"%{search_params.department.upper()}%"))
        
        # Apply location filter
        if search_params.location_id:
            query = query.filter(
                or_(
                    User.primary_location_id == search_params.location_id,
                    User.assigned_locations.any(Location.id == search_params.location_id)
                )
            )
        
        # Get total count before pagination
        total = query.count()
        
        # Apply sorting
        sort_column = getattr(User, search_params.sort_by, User.created_at)
        if search_params.sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))
        
        # Apply pagination
        offset = (search_params.page - 1) * search_params.per_page
        users = query.offset(offset).limit(search_params.per_page).all()
        
        return users, total
    
    def authenticate(self, db: Session, *, username: str, password: str) -> Optional[User]:
        """Authenticate user with username/email and password"""
        # Try username first, then email
        user = self.get_by_username(db=db, username=username)
        if not user:
            user = self.get_by_email(db=db, email=username)
        
        if not user:
            return None
        
        if not self.verify_password(password, user.password_hash):
            return None
        
        # Check if user is active
        if user.status != "active":
            return None
        
        return user
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Get password hash"""
        return pwd_context.hash(password)
    
    def update_password(
        self, 
        db: Session, 
        *, 
        user: User, 
        new_password: str,
        updated_by: Optional[str] = None
    ) -> User:
        """Update user password"""
        hashed_password = self.get_password_hash(new_password)
        user.password_hash = hashed_password
        if updated_by:
            user.updated_by = updated_by
        
        db.commit()
        db.refresh(user)
        return user
    
    def assign_to_location(
        self, 
        db: Session, 
        *, 
        user_id: uuid.UUID, 
        location_id: uuid.UUID,
        is_primary: bool = False,
        updated_by: Optional[str] = None
    ) -> User:
        """Assign user to location"""
        user = self.get(db=db, id=user_id)
        if not user:
            raise ValueError("User not found")
        
        location = crud_location.get(db=db, id=location_id)
        if not location:
            raise ValueError("Location not found")
        
        if is_primary:
            # Update primary location
            old_location_id = user.primary_location_id
            user.primary_location_id = location_id
            
            # Update location-based codes if needed
            old_username, new_username = user.update_location_assignment(location, db)
            
            # Update staff counts
            if old_location_id and old_location_id != location_id:
                old_location = crud_location.get(db=db, id=old_location_id)
                if old_location:
                    old_location.current_staff_count = max(0, old_location.current_staff_count - 1)
            
            location.current_staff_count += 1
        else:
            # Add to assigned locations if not already assigned
            if location not in user.assigned_locations:
                user.assigned_locations.append(location)
        
        if updated_by:
            user.updated_by = updated_by
        
        db.commit()
        db.refresh(user)
        return user
    
    def remove_from_location(
        self, 
        db: Session, 
        *, 
        user_id: uuid.UUID, 
        location_id: uuid.UUID,
        updated_by: Optional[str] = None
    ) -> User:
        """Remove user from location"""
        user = self.get(db=db, id=user_id)
        if not user:
            raise ValueError("User not found")
        
        location = crud_location.get(db=db, id=location_id)
        if not location:
            raise ValueError("Location not found")
        
        # Remove from assigned locations
        if location in user.assigned_locations:
            user.assigned_locations.remove(location)
        
        # Cannot remove primary location without reassigning
        if user.primary_location_id == location_id:
            raise ValueError("Cannot remove user from primary location. Reassign to different location first.")
        
        if updated_by:
            user.updated_by = updated_by
        
        db.commit()
        db.refresh(user)
        return user
    
    def assign_roles(
        self, 
        db: Session, 
        *, 
        user_id: uuid.UUID, 
        role_ids: List[uuid.UUID],
        updated_by: Optional[str] = None
    ) -> User:
        """Assign roles to user"""
        user = self.get(db=db, id=user_id)
        if not user:
            raise ValueError("User not found")
        
        roles = db.query(Role).filter(Role.id.in_(role_ids)).all()
        if len(roles) != len(role_ids):
            raise ValueError("One or more roles not found")
        
        user.roles = roles
        if updated_by:
            user.updated_by = updated_by
        
        db.commit()
        db.refresh(user)
        return user
    
    def get_user_permissions(self, db: Session, *, user_id: uuid.UUID) -> List[Permission]:
        """Get all permissions for user (from roles and individual assignments)"""
        user = self.get(db=db, id=user_id)
        if not user:
            return []
        
        # Get permissions from roles
        role_permissions = set()
        for role in user.roles:
            role_permissions.update(role.permissions)
        
        # Get individual permission overrides
        from app.models.user import UserPermissionOverride
        overrides = db.query(UserPermissionOverride).filter(
            UserPermissionOverride.user_id == user_id,
            UserPermissionOverride.granted == True
        ).all()
        
        individual_permissions = set()
        for override in overrides:
            if override.permission and not override.is_expired:
                individual_permissions.add(override.permission)
        
        # Combine and return
        all_permissions = role_permissions.union(individual_permissions)
        return list(all_permissions)
    
    def get_users_by_permission(self, db: Session, *, permission_name: str) -> List[User]:
        """Get all users with specific permission"""
        return db.query(User).join(User.roles).join(Role.permissions).filter(
            Permission.name == permission_name,
            User.is_active == True
        ).distinct().all()
    
    def get_location_statistics(self, db: Session, *, location_id: uuid.UUID) -> Dict[str, Any]:
        """Get user statistics for location"""
        total_users = db.query(User).filter(
            User.primary_location_id == location_id,
            User.is_active == True
        ).count()
        
        active_users = db.query(User).filter(
            User.primary_location_id == location_id,
            User.status == "active",
            User.is_active == True
        ).count()
        
        # Users by role
        role_stats = db.query(
            Role.name,
            func.count(User.id).label('count')
        ).join(User.roles).filter(
            User.primary_location_id == location_id,
            User.is_active == True
        ).group_by(Role.name).all()
        
        users_by_role = {stat.name: stat.count for stat in role_stats}
        
        # Recent logins (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        recent_logins = db.query(User).filter(
            User.primary_location_id == location_id,
            User.last_login_at >= thirty_days_ago,
            User.is_active == True
        ).count()
        
        return {
            "total_users": total_users,
            "active_users": active_users,
            "users_by_role": users_by_role,
            "recent_logins": recent_logins,
            "activity_rate": (recent_logins / total_users * 100) if total_users > 0 else 0
        }
    
    def _apply_permission_overrides(
        self, 
        db: Session, 
        user_id: uuid.UUID, 
        permission_overrides: Dict[str, bool], 
        granted_by: Optional[str] = None
    ) -> None:
        """Apply permission overrides for a user during creation or update"""
        from app.models.user import Permission, UserPermissionOverride
        
        # Get all permissions that need to be overridden
        permission_names = list(permission_overrides.keys())
        permissions = db.query(Permission).filter(Permission.name.in_(permission_names)).all()
        
        # Create permission overrides
        for permission in permissions:
            if permission.name in permission_overrides:
                granted = permission_overrides[permission.name]
                
                # Check if override already exists
                existing_override = db.query(UserPermissionOverride).filter(
                    UserPermissionOverride.user_id == user_id,
                    UserPermissionOverride.permission_id == permission.id
                ).first()
                
                if existing_override:
                    # Update existing override
                    existing_override.granted = granted
                    if granted_by:
                        # Handle granted_by as either string or UUID
                        if isinstance(granted_by, str):
                            try:
                                existing_override.granted_by = uuid.UUID(granted_by)
                            except ValueError:
                                # If it's not a valid UUID string, it might be a username
                                # In this case, we'd need to look up the user, but for now skip
                                pass
                        else:
                            existing_override.granted_by = granted_by
                else:
                    # Create new override
                    granted_by_uuid = None
                    if granted_by:
                        if isinstance(granted_by, str):
                            try:
                                granted_by_uuid = uuid.UUID(granted_by)
                            except ValueError:
                                # If it's not a valid UUID string, skip for now
                                pass
                        else:
                            granted_by_uuid = granted_by
                    
                    override = UserPermissionOverride(
                        user_id=user_id,
                        permission_id=permission.id,
                        granted=granted,
                        granted_by=granted_by_uuid
                    )
                    db.add(override)


# Create instance
user = CRUDUser(User) 