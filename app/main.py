"""
Main FastAPI Application for Madagascar License System
Adapted from LINC Old with Madagascar-specific configuration

TODO: Future Enhancements
========================
1. Location System Enhancements:
   - TODO: Add device registration by MAC address for automatic location detection
   - TODO: Implement location-specific login URLs (subdomains or paths)
   - TODO: Add IP address-based location detection with fallback
   - TODO: Create hybrid approach (device registration + manual selection)
   
2. Security Enhancements:
   - TODO: Add rate limiting for admin endpoints
   - TODO: Implement proper admin authentication for database operations
   - TODO: Add audit logging for admin actions
   - TODO: Remove admin endpoints in production or add proper security

3. Module Expansion:
   - TODO: Implement Persons Module (Madagascar ID validation)
   - TODO: Implement Applications Module (license application processing)
   - TODO: Implement Printing Module (distributed card printing)
   - TODO: Implement Locations Module (multi-office management)
   - TODO: Implement Reports Module (audit and compliance)

4. Data Import:
   - TODO: Add data import functionality from existing systems
   - TODO: Implement OCR for document processing
   - TODO: Add bulk user import capabilities

5. Production Readiness:
   - TODO: Add comprehensive logging and monitoring
   - TODO: Implement backup and recovery procedures
   - TODO: Add health checks for external dependencies
   - TODO: Performance optimization and caching
"""

from fastapi import FastAPI, Request, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import logging
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import create_tables, get_db
from app.api.v1.api import api_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events
    Handles startup and shutdown tasks
    """
    # Startup
    logger.info("Starting Madagascar License System...")
    
    # Create database tables
    try:
        create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Madagascar License System...")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Madagascar Driver's License Management System",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add request processing time to response headers"""
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    except Exception as e:
        # Handle middleware errors gracefully
        logger.warning(f"Request processing error: {e}")
        process_time = time.time() - start_time
        logger.info(f"Request failed after {process_time:.4f}s")
        raise


# Specific handler for h11 protocol errors
@app.exception_handler(Exception)
async def handle_h11_errors(request: Request, exc: Exception):
    """Handle h11 protocol errors specifically"""
    exc_str = str(exc)
    exc_type = str(type(exc))
    
    # Handle h11 protocol errors - these usually mean client disconnected
    if "h11" in exc_type.lower() or "localprotocolerror" in exc_str.lower():
        logger.warning(f"HTTP protocol error (client likely disconnected): {exc}")
        return None  # Don't try to send response
    
    # Handle connection/timeout errors
    if any(keyword in exc_str.lower() for keyword in ["connection", "timeout", "disconnect", "broken pipe"]):
        logger.warning(f"Connection error: {exc}")
        return None
    
    # Handle other exceptions normally
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    try:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "type": "internal_error",
                "status_code": 500
            }
        )
    except Exception as response_error:
        logger.warning(f"Could not send error response: {response_error}")
        return None


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "system": "Madagascar License System",
        "timestamp": time.time()
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with basic system information"""
    return {
        "message": "Madagascar Driver's License System API",
        "version": settings.VERSION,
        "docs_url": f"{settings.API_V1_STR}/docs",
        "redoc_url": f"{settings.API_V1_STR}/redoc",
        "api_base": settings.API_V1_STR
    }


# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


# Development/Admin endpoints for database management
@app.post("/admin/drop-tables", tags=["Admin"])
async def drop_all_tables():
    """Drop all database tables - DEVELOPMENT ONLY"""
    try:
        from app.core.database import drop_tables
        
        logger.warning("Dropping all database tables")
        drop_tables()
        
        return {
            "status": "success",
            "message": "All database tables dropped successfully",
            "warning": "All data has been lost",
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Failed to drop tables: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Failed to drop tables: {str(e)}",
                "timestamp": time.time()
            }
        )

@app.post("/admin/init-tables", tags=["Admin"])
async def initialize_tables():
    """Initialize database tables with latest schema"""
    try:
        from app.core.database import create_tables, engine
        from app.models.enums import LicenseCategory
        from sqlalchemy import text
        
        logger.info("Creating database tables with explicit enum creation")
        
        # Step 1: Explicitly create LicenseCategory enum first
        logger.info("Creating LicenseCategory enum with all values")
        enum_values = [category.value for category in LicenseCategory]
        logger.info(f"Enum values to create: {enum_values}")
        
        with engine.connect() as conn:
            # Drop existing enum if it exists
            try:
                conn.execute(text("DROP TYPE IF EXISTS licensecategory CASCADE"))
                logger.info("Dropped existing licensecategory enum")
            except Exception as e:
                logger.info(f"No existing enum to drop: {e}")
            
            # Create new enum with all values
            values_str = "', '".join(enum_values)
            create_enum_sql = f"CREATE TYPE licensecategory AS ENUM ('{values_str}')"
            conn.execute(text(create_enum_sql))
            logger.info(f"Created licensecategory enum: {create_enum_sql}")
            
            # Verify the enum was created correctly
            result = conn.execute(text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid 
                    FROM pg_type 
                    WHERE typname = 'licensecategory'
                )
                ORDER BY enumsortorder
            """))
            
            created_values = [row[0] for row in result.fetchall()]
            logger.info(f"Verified enum values in database: {created_values}")
            conn.commit()
        
        # Step 2: Now create all tables
        logger.info("Creating database tables")
        create_tables()
            
            return {
                "status": "success", 
                "message": "Database tables created successfully",
                "enum_values_created": created_values,
                "total_enum_values": len(created_values),
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Failed to create tables: {e}")
            return JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": f"Failed to create tables: {str(e)}",
                    "timestamp": time.time()
                }
            )


@app.post("/admin/fix-license-enum", tags=["Admin"])
async def fix_license_category_enum():
    """Fix LicenseCategory enum to include all values including '3'"""
    try:
        from app.core.database import engine
        from app.models.enums import LicenseCategory
        from sqlalchemy import text
        
        logger.info("Fixing LicenseCategory enum to include all values")
        
        # Get all enum values from the Python enum
        enum_values = [category.value for category in LicenseCategory]
        logger.info(f"LicenseCategory enum values to create: {enum_values}")
        
        with engine.connect() as conn:
            # Drop existing enum if it exists
            try:
                conn.execute(text("DROP TYPE IF EXISTS licensecategory CASCADE"))
                logger.info("Dropped existing licensecategory enum")
            except Exception as e:
                logger.info(f"No existing enum to drop: {e}")
            
            # Create new enum with all values
            values_str = "', '".join(enum_values)
            create_enum_sql = f"CREATE TYPE licensecategory AS ENUM ('{values_str}')"
            conn.execute(text(create_enum_sql))
            logger.info(f"Created licensecategory enum: {create_enum_sql}")
            
            # Verify the enum was created correctly
            result = conn.execute(text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid 
                    FROM pg_type 
                    WHERE typname = 'licensecategory'
                )
                ORDER BY enumsortorder
            """))
            
            created_values = [row[0] for row in result.fetchall()]
            logger.info(f"Verified enum values in database: {created_values}")
            conn.commit()
            
            # Check if all our values are present
            missing_values = set(enum_values) - set(created_values)
            if missing_values:
                logger.error(f"Missing values after enum creation: {missing_values}")
                return JSONResponse(
                    status_code=500,
                    content={
                        "status": "error",
                        "message": f"Missing enum values: {missing_values}",
                        "created_values": created_values,
                        "expected_values": enum_values,
                        "timestamp": time.time()
                    }
                )
            
            # Now recreate the applications table to use the new enum
            logger.info("Recreating applications table with fixed enum")
            conn.execute(text("DROP TABLE IF EXISTS applications CASCADE"))
            
            # Import and create just the applications table
            from app.models.application import Application
            from app.models.base import Base
            Application.__table__.create(bind=engine, checkfirst=True)
            logger.info("Recreated applications table")
            
            return {
                "status": "success",
                "message": "LicenseCategory enum fixed successfully",
                "enum_values_created": created_values,
                "total_enum_values": len(created_values),
                "includes_learners_3": "3" in created_values,
                "timestamp": time.time()
            }
            
    except Exception as e:
        logger.error(f"Failed to fix enum: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Failed to fix enum: {str(e)}",
                "timestamp": time.time()
            }
        )


@app.post("/admin/init-users", tags=["Admin"]) 
async def initialize_users():
    """Initialize default users, roles, and permissions for testing"""
    try:
        from app.core.database import get_db
        from app.models.user import User, Role, Permission
        from app.models.user import UserStatus, MadagascarIDType
        from app.models.enums import UserType
        from app.core.security import get_password_hash
        
        db = next(get_db())
        
        try:
            # Create permissions - Updated to include Person module permissions
            permissions_data = [
                # User Management Permissions
                ("users.create", "Create Users", "Create new user accounts", "users", "user", "create"),
                ("users.read", "View Users", "View user information", "users", "user", "read"),
                ("users.update", "Update Users", "Update user information", "users", "user", "update"),
                ("users.delete", "Delete Users", "Delete user accounts", "users", "user", "delete"),
                ("users.activate", "Activate Users", "Activate user accounts", "users", "user", "activate"),
                ("users.deactivate", "Deactivate Users", "Deactivate user accounts", "users", "user", "deactivate"),
                ("users.audit", "View User Audit", "View user audit logs", "users", "user", "audit"),
                ("users.bulk_create", "Bulk Create Users", "Create multiple users at once", "users", "user", "bulk_create"),
                ("users.manage_permissions", "Manage User Permissions", "Override individual user permissions", "users", "user", "manage_permissions"),
                ("users.view_statistics", "View User Statistics", "View user statistics and analytics", "users", "user", "view_statistics"),
                
                # Role Management Permissions
                ("roles.create", "Create Roles", "Create new roles", "roles", "role", "create"),
                ("roles.read", "View Roles", "View role information", "roles", "role", "read"),
                ("roles.update", "Update Roles", "Update role information", "roles", "role", "update"),
                ("roles.delete", "Delete Roles", "Delete roles", "roles", "role", "delete"),
                ("roles.assign_permissions", "Assign Role Permissions", "Assign permissions to roles", "roles", "role", "assign_permissions"),
                ("roles.view_hierarchy", "View Role Hierarchy", "View role hierarchy and relationships", "roles", "role", "view_hierarchy"),
                ("roles.view_statistics", "View Role Statistics", "View role usage statistics", "roles", "role", "view_statistics"),
                
                # Permission Management
                ("permissions.read", "View Permissions", "View permission information", "permissions", "permission", "read"),
                ("permissions.check_others", "Check Other User Permissions", "Check permissions for other users", "permissions", "permission", "check_others"),
                
                # Person Management Permissions
                ("persons.create", "Create Persons", "Create new person records", "persons", "person", "create"),
                ("persons.read", "View Persons", "View person information", "persons", "person", "read"),
                ("persons.update", "Update Persons", "Update person information", "persons", "person", "update"),
                ("persons.delete", "Delete Persons", "Delete person records", "persons", "person", "delete"),
                ("persons.search", "Search Persons", "Search and filter person records", "persons", "person", "search"),
                ("persons.check_duplicates", "Check Person Duplicates", "Check for potential duplicate persons", "persons", "person", "check_duplicates"),
                
                # Person Alias (Document) Management Permissions
                ("person_aliases.create", "Create Person Documents", "Add identification documents to persons", "persons", "person_alias", "create"),
                ("person_aliases.read", "View Person Documents", "View person identification documents", "persons", "person_alias", "read"),
                ("person_aliases.update", "Update Person Documents", "Update person identification documents", "persons", "person_alias", "update"),
                ("person_aliases.delete", "Delete Person Documents", "Delete person identification documents", "persons", "person_alias", "delete"),
                ("person_aliases.set_primary", "Set Primary Document", "Set primary identification document", "persons", "person_alias", "set_primary"),
                
                # Person Address Management Permissions
                ("person_addresses.create", "Create Person Addresses", "Add addresses to persons", "persons", "person_address", "create"),
                ("person_addresses.read", "View Person Addresses", "View person addresses", "persons", "person_address", "read"),
                ("person_addresses.update", "Update Person Addresses", "Update person addresses", "persons", "person_address", "update"),
                ("person_addresses.delete", "Delete Person Addresses", "Delete person addresses", "persons", "person_address", "delete"),
                ("person_addresses.set_primary", "Set Primary Address", "Set primary address per type", "persons", "person_address", "set_primary"),
                
                # License Application Permissions (placeholders for future modules)
                ("license_applications.create", "Create License Applications", "Create new license applications", "license_applications", "license_application", "create"),
                ("license_applications.read", "View License Applications", "View license applications", "license_applications", "license_application", "read"),
                ("license_applications.update", "Update License Applications", "Update license applications", "license_applications", "license_application", "update"),
                ("license_applications.delete", "Delete License Applications", "Delete license applications", "license_applications", "license_application", "delete"),
                ("license_applications.approve", "Approve License Applications", "Approve license applications", "license_applications", "license_application", "approve"),
                
                # Location Management Permissions
                ("locations.create", "Create Locations", "Create new office locations", "locations", "location", "create"),
                ("locations.read", "View Locations", "View location information", "locations", "location", "read"),
                ("locations.update", "Update Locations", "Update location information", "locations", "location", "update"),
                ("locations.delete", "Delete Locations", "Delete office locations", "locations", "location", "delete"),
                ("locations.view_statistics", "View Location Statistics", "View location statistics and analytics", "locations", "location", "view_statistics"),
                
                # Printing Permissions
                ("printing.local_print", "Local Printing", "Print at local location", "printing", "print_job", "local_print"),
                ("printing.cross_location_print", "Cross-Location Printing", "Print at other locations", "printing", "print_job", "cross_location_print"),
                ("printing.manage_queue", "Manage Print Queue", "Manage printing queue", "printing", "print_job", "manage_queue"),
                ("printing.monitor_status", "Monitor Printer Status", "Monitor printer status", "printing", "printer", "monitor_status"),
                
                # Provincial Management Permissions (NEW)
                ("provinces.manage_users", "Manage Provincial Users", "Manage users across entire province", "provinces", "province", "manage_users"),
                ("provinces.view_statistics", "View Provincial Statistics", "View statistics for entire province", "provinces", "province", "view_statistics"),
                ("provinces.view_audit_logs", "View Provincial Audit Logs", "View audit logs for entire province", "provinces", "province", "view_audit_logs"),
                
                # National Management Permissions (NEW)
                ("national.manage_all", "National Management", "Full national system management", "national", "system", "manage_all"),
                ("national.view_statistics", "View National Statistics", "View system-wide statistics", "national", "system", "view_statistics"),
                ("national.manage_provinces", "Manage All Provinces", "Manage users and settings across all provinces", "national", "system", "manage_provinces"),
                
                # Reports Permissions (NEW)
                ("reports.basic", "Basic Reports", "Generate basic reports", "reports", "report", "basic"),
                ("reports.advanced", "Advanced Reports", "Generate advanced reports", "reports", "report", "advanced"),
                ("reports.export", "Export Reports", "Export reports to various formats", "reports", "report", "export"),
                ("reports.provincial", "Provincial Reports", "Generate province-level reports", "reports", "report", "provincial"),
                ("reports.national", "National Reports", "Generate national-level reports", "reports", "report", "national"),
            ]
            
            permissions = {}
            for name, display_name, description, category, resource, action in permissions_data:
                existing = db.query(Permission).filter(Permission.name == name).first()
                if not existing:
                    perm = Permission(
                        name=name,
                        display_name=display_name,
                        description=description,
                        category=category,
                        resource=resource,
                        action=action,
                        is_system_permission=True
                    )
                    db.add(perm)
                    db.flush()
                    permissions[name] = perm
                else:
                    permissions[name] = existing
            
            # Define role permissions - Updated to include new features
            clerk_permissions = [
                "license_applications.create", "license_applications.read", "license_applications.update",
                "printing.local_print", "printing.monitor_status",
                # Person management (essential for license applications)
                "persons.create", "persons.read", "persons.update", "persons.search", "persons.check_duplicates",
                "person_aliases.create", "person_aliases.read", "person_aliases.update", "person_aliases.set_primary",
                "person_addresses.create", "person_addresses.read", "person_addresses.update", "person_addresses.set_primary",
                # Basic location viewing and reports for clerks
                "locations.read", "reports.basic",
                # Basic role viewing (needed for user interface)
                "roles.read", "users.read"
            ]
            
            supervisor_permissions = clerk_permissions + [
                "license_applications.approve",
                "users.read", "users.update", "users.view_statistics", "roles.read", "permissions.read",
                # Additional person management permissions for supervisors
                "persons.delete", "person_aliases.delete", "person_addresses.delete",
                # Location management for supervisors
                "locations.read", "locations.update", "locations.view_statistics",
                # Enhanced reporting for supervisors
                "reports.advanced", "reports.export"
            ]
            
            traffic_dept_head_permissions = supervisor_permissions + [
                # User management at provincial level
                "users.create", "users.update", "users.activate", "users.deactivate", "users.bulk_create",
                "users.manage_permissions", "users.view_statistics",
                # Role management
                "roles.read", "roles.view_hierarchy", "roles.view_statistics",
                # Provincial oversight
                "provinces.manage_users", "provinces.view_statistics", "provinces.view_audit_logs",
                # Advanced reporting
                "reports.provincial"
            ]
            
            printer_permissions = [
                "printing.local_print", "printing.cross_location_print",
                "printing.manage_queue", "printing.monitor_status",
                # Basic role viewing (needed for user interface)
                "roles.read", "users.read"
            ]
            
            # Define examiner permissions (authorization and review)
            examiner_permissions = [
                "applications.authorize", "applications.review_authorization",
                "license_applications.read", "license_applications.approve",
                # Basic permissions for interface
                "roles.read", "users.read"
            ]
            
            admin_permissions = [perm for perm in permissions.keys()]  # All permissions
            
            # Create roles with corrected structure - including EXAMINER role
            roles_data = [
                {
                    "name": "office_supervisor",
                    "display_name": "Office Supervisor",
                    "description": "Office level supervisor - can manage clerks and office operations",
                    "permissions": supervisor_permissions,
                    "hierarchy_level": 2,
                    "user_type_restriction": UserType.LOCATION_USER,
                    "scope_type": "location",
                    "is_system_role": True
                },
                {
                    "name": "examiner",
                    "display_name": "Examiner",
                    "description": "License examiner - can authorize applications and generate licenses",
                    "permissions": examiner_permissions,
                    "hierarchy_level": 1,
                    "user_type_restriction": UserType.LOCATION_USER,
                    "scope_type": "location",
                    "is_system_role": True
                },
                {
                    "name": "clerk",
                    "display_name": "Clerk",
                    "description": "License processing clerk with person management",
                    "permissions": clerk_permissions,
                    "hierarchy_level": 1,
                    "user_type_restriction": UserType.LOCATION_USER,
                    "scope_type": "location",
                    "is_system_role": True
                },
                {
                    "name": "printer",
                    "display_name": "Printer",
                    "description": "Card printing operator",
                    "permissions": printer_permissions,
                    "hierarchy_level": 1,
                    "user_type_restriction": UserType.LOCATION_USER,
                    "scope_type": "location",
                    "is_system_role": True
                }
            ]
            
            roles = {}
            for role_data in roles_data:
                existing = db.query(Role).filter(Role.name == role_data["name"]).first()
                if not existing:
                    role = Role(
                        name=role_data["name"],
                        display_name=role_data["display_name"],
                        description=role_data["description"],
                        is_system_role=role_data["is_system_role"],
                        level=0,  # Keep for backward compatibility
                        hierarchy_level=role_data["hierarchy_level"],
                        user_type_restriction=role_data["user_type_restriction"],
                        scope_type=role_data["scope_type"]
                    )
                    db.add(role)
                    db.flush()
                    
                    # Assign permissions to role
                    role_permission_objects = []
                    for perm_name in role_data["permissions"]:
                        if perm_name in permissions:
                            role_permission_objects.append(permissions[perm_name])
                    
                    role.permissions = role_permission_objects
                    roles[role_data["name"]] = role
                else:
                    # Update existing role with new hierarchy values
                    existing.hierarchy_level = role_data["hierarchy_level"]
                    existing.user_type_restriction = role_data["user_type_restriction"]
                    existing.scope_type = role_data["scope_type"]
                    existing.display_name = role_data["display_name"]
                    existing.description = role_data["description"]
                    
                    # Update permissions
                    role_permission_objects = []
                    for perm_name in role_data["permissions"]:
                        if perm_name in permissions:
                            role_permission_objects.append(permissions[perm_name])
                    
                    existing.permissions = role_permission_objects
                    roles[role_data["name"]] = existing
            
            # Create admin user
            admin = User(
                username="admin",
                email="admin@madagascar-license.gov.mg",
                password_hash=get_password_hash("Admin123"),
                first_name="System",
                last_name="Administrator",
                display_name="System Administrator",
                madagascar_id_number="ADM001",
                id_document_type=MadagascarIDType.MADAGASCAR_ID,
                phone_number="+261340000000",
                employee_id="ADM001",
                department="IT Administration",
                user_type=UserType.SYSTEM_USER,  # Changed to SYSTEM_USER
                can_create_roles=True,
                country_code="MG",
                province="Antananarivo",
                region="Analamanga",
                office_location="Central Office",
                language="en",
                timezone="Indian/Antananarivo",
                currency="MGA",
                status=UserStatus.ACTIVE,
                is_superuser=True,  # Superuser with no role needed - inherent full permissions
                is_verified=True
            )
            
            db.add(admin)
            db.flush()
            
            # Admin doesn't need role assignment - superuser has all permissions
            
            # Create test users
            test_users = [
                {
                    "username": "clerk1",
                    "email": "clerk1@madagascar-license.gov.mg",
                    "password": "Clerk123!",
                    "first_name": "Marie",
                    "last_name": "Razafy",
                    "madagascar_id_number": "CIN123456789",
                    "employee_id": "CLK001",
                    "department": "License Processing",
                    "user_type": UserType.LOCATION_USER,
                    "roles": ["clerk"]
                },
                {
                    "username": "supervisor1", 
                    "email": "supervisor1@madagascar-license.gov.mg",
                    "password": "Supervisor123!",
                    "first_name": "Jean",
                    "last_name": "Rakoto",
                    "madagascar_id_number": "CIN987654321",
                    "employee_id": "SUP001",
                    "department": "License Processing",
                    "user_type": UserType.LOCATION_USER,
                    "roles": ["office_supervisor"]
                },
                {
                    "username": "printer1",
                    "email": "printer1@madagascar-license.gov.mg", 
                    "password": "Printer123!",
                    "first_name": "Paul",
                    "last_name": "Andry",
                    "madagascar_id_number": "CIN456789123",
                    "employee_id": "PRT001",
                    "department": "Card Production",
                    "user_type": UserType.LOCATION_USER,
                    "roles": ["printer"]
                },
                {
                    "username": "examiner1",
                    "email": "examiner1@madagascar-license.gov.mg", 
                    "password": "Examiner123!",
                    "first_name": "Sarah",
                    "last_name": "Rasoarivelo",
                    "madagascar_id_number": "CIN789123456",
                    "employee_id": "EXM001",
                    "department": "License Authorization",
                    "user_type": UserType.LOCATION_USER,
                    "roles": ["examiner"]
                }
            ]
            
            created_users = []
            for user_data in test_users:
                existing = db.query(User).filter(User.username == user_data["username"]).first()
                if not existing:
                    user = User(
                        username=user_data["username"],
                        email=user_data["email"],
                        password_hash=get_password_hash(user_data["password"]),
                        first_name=user_data["first_name"],
                        last_name=user_data["last_name"],
                        madagascar_id_number=user_data["madagascar_id_number"],
                        id_document_type=MadagascarIDType.MADAGASCAR_ID,
                        employee_id=user_data["employee_id"],
                        department=user_data["department"],
                        user_type=user_data["user_type"],
                        phone_number="+261340000002",
                        country_code="MG",
                        province="Antananarivo",
                        region="Analamanga", 
                        office_location="Central Office",
                        language="en",
                        timezone="Indian/Antananarivo",
                        currency="MGA",
                        status=UserStatus.ACTIVE,
                        is_verified=True
                    )
                    
                    # Assign roles
                    user_roles = [roles[role_name] for role_name in user_data["roles"] if role_name in roles]
                    user.roles = user_roles
                    
                    db.add(user)
                    created_users.append(user_data["username"])
            
            db.commit()
            
            return {
                "status": "success",
                "message": "Users, roles, and permissions initialized successfully",
                "modules_initialized": ["users", "roles", "permissions", "persons"],
                "admin_credentials": {
                    "username": "admin",
                    "password": "Admin123",
                    "email": "admin@madagascar-license.gov.mg",
                    "role": "system_admin",
                    "note": "Technical system administrator with full superuser privileges"
                },
                "test_users": [
                    {"username": "clerk1", "password": "Clerk123!", "permissions": "person management + license processing"},
                    {"username": "supervisor1", "password": "Supervisor123!", "permissions": "all clerk permissions + deletions"},
                    {"username": "printer1", "password": "Printer123!", "permissions": "printing operations only"},
                    {"username": "examiner1", "password": "Examiner123!", "permissions": "application authorization + license generation"}
                ],
                "created_users": created_users,
                "permissions_created": len(permissions_data),
                "roles_created": len(roles_data),
                "note": "Person module is now fully integrated with permissions system. Admin = technical superuser",
                "timestamp": time.time()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to initialize users: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Failed to initialize users: {str(e)}",
                "timestamp": time.time()
            }
        )


@app.post("/admin/init-locations", tags=["Admin"])
async def initialize_locations():
    """Initialize Madagascar locations with all provinces and sample offices"""
    try:
        from app.core.database import get_db
        from app.models.user import Location
        from app.schemas.location import LocationCreate, ProvinceCodeEnum, OfficeTypeEnum
        from app.crud.crud_location import location as crud_location
        
        db = next(get_db())
        
        try:
            # Madagascar provinces and sample locations
            locations_data = [
                # Antananarivo Province (T)
                {
                    "name": "ANTANANARIVO CENTRAL OFFICE",
                    "province_code": ProvinceCodeEnum.ANTANANARIVO,
                    "office_number": "01",
                    "office_type": OfficeTypeEnum.MAIN,
                    "locality": "ANDRAVOAHANGY, ANTANANARIVO",  # Combined locality, town format
                    "street_address": "LOT II M 85 ANDRAVOAHANGY",
                    "postal_code": "101",
                    "phone_number": "+261 20 22 123 45",
                    "email": "antananarivo.central@gov.mg",
                    "manager_name": "RAKOTO JEAN MARIE",
                    "max_daily_capacity": 100,
                    "max_staff_capacity": 15,
                    "operational_schedule": [
                        {"day": "Monday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Tuesday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Wednesday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Thursday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Friday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Saturday", "is_open": True, "open_time": "08:00", "close_time": "12:00"},
                        {"day": "Sunday", "is_open": False, "open_time": "08:00", "close_time": "17:00"}
                    ],
                    "special_notes": "Main headquarters office with full services"
                },
                {
                    "name": "ANTANANARIVO BRANCH OFFICE",
                    "province_code": ProvinceCodeEnum.ANTANANARIVO,
                    "office_number": "02",
                    "office_type": OfficeTypeEnum.MAIN,
                    "locality": "BEHORIRIKA, ANTANANARIVO",  # Combined locality, town format
                    "street_address": "AVENUE DE L'INDEPENDENCE",
                    "postal_code": "101",
                    "phone_number": "+261 20 22 678 90",
                    "email": "antananarivo.branch@gov.mg",
                    "manager_name": "RABE MARIE CLAIRE",
                    "max_daily_capacity": 75,
                    "max_staff_capacity": 12,
                    "operational_schedule": [
                        {"day": "Monday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Tuesday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Wednesday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Thursday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Friday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Saturday", "is_open": False, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Sunday", "is_open": False, "open_time": "08:00", "close_time": "17:00"}
                    ]
                },
                
                # Fianarantsoa Province (F)
                {
                    "name": "FIANARANTSOA MAIN OFFICE",
                    "province_code": ProvinceCodeEnum.FIANARANTSOA,
                    "office_number": "01",
                    "office_type": OfficeTypeEnum.MAIN,
                    "locality": "TSIANOLONDROA, FIANARANTSOA",  # Combined locality, town format
                    "street_address": "RUE PRINCIPALE",
                    "phone_number": "+261 75 123 456",
                    "email": "fianarantsoa.main@gov.mg",
                    "manager_name": "ANDRY PAUL HENRI",
                    "max_daily_capacity": 60,
                    "max_staff_capacity": 10,
                    "operational_schedule": [
                        {"day": "Monday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Tuesday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Wednesday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Thursday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Friday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Saturday", "is_open": False, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Sunday", "is_open": False, "open_time": "08:00", "close_time": "17:00"}
                    ]
                },
                
                # Toamasina Province (A)
                {
                    "name": "TOAMASINA PORT OFFICE",
                    "province_code": ProvinceCodeEnum.TOAMASINA,
                    "office_number": "01",
                    "office_type": OfficeTypeEnum.MAIN,
                    "locality": "ANALAKININNY, TOAMASINA",  # Combined locality, town format
                    "street_address": "BOULEVARD JOFFRE",
                    "phone_number": "+261 53 123 789",
                    "email": "toamasina.port@gov.mg",
                    "manager_name": "RAZAFY LANTO",
                    "max_daily_capacity": 80,
                    "max_staff_capacity": 12,
                    "operational_schedule": [
                        {"day": "Monday", "is_open": True, "open_time": "07:30", "close_time": "17:30"},
                        {"day": "Tuesday", "is_open": True, "open_time": "07:30", "close_time": "17:30"},
                        {"day": "Wednesday", "is_open": True, "open_time": "07:30", "close_time": "17:30"},
                        {"day": "Thursday", "is_open": True, "open_time": "07:30", "close_time": "17:30"},
                        {"day": "Friday", "is_open": True, "open_time": "07:30", "close_time": "17:30"},
                        {"day": "Saturday", "is_open": True, "open_time": "08:00", "close_time": "12:00"},
                        {"day": "Sunday", "is_open": False, "open_time": "08:00", "close_time": "17:00"}
                    ]
                },
                
                # Mahajanga Province (M)
                {
                    "name": "MAHAJANGA COASTAL OFFICE",
                    "province_code": ProvinceCodeEnum.MAHAJANGA,
                    "office_number": "01",
                    "office_type": OfficeTypeEnum.MAIN,
                    "locality": "AMBOROVY, MAHAJANGA",  # Combined locality, town format
                    "street_address": "AVENUE DE LA REPUBLIQUE",
                    "phone_number": "+261 62 987 654",
                    "email": "mahajanga.coastal@gov.mg",
                    "manager_name": "RANDRIA SOLO",
                    "max_daily_capacity": 50,
                    "max_staff_capacity": 8,
                    "operational_schedule": [
                        {"day": "Monday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Tuesday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Wednesday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Thursday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Friday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Saturday", "is_open": False, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Sunday", "is_open": False, "open_time": "08:00", "close_time": "17:00"}
                    ]
                },
                
                # Antsiranana Province (D)
                {
                    "name": "ANTSIRANANA NORTHERN OFFICE",
                    "province_code": ProvinceCodeEnum.ANTSIRANANA,
                    "office_number": "01",
                    "office_type": OfficeTypeEnum.MAIN,
                    "locality": "TANAMBAO, ANTSIRANANA",  # Combined locality, town format
                    "street_address": "RUE COLBERT",
                    "phone_number": "+261 82 456 123",
                    "email": "antsiranana.north@gov.mg",
                    "manager_name": "RASOLOFO HERY",
                    "max_daily_capacity": 45,
                    "max_staff_capacity": 7,
                    "operational_schedule": [
                        {"day": "Monday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Tuesday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Wednesday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Thursday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Friday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Saturday", "is_open": False, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Sunday", "is_open": False, "open_time": "08:00", "close_time": "17:00"}
                    ]
                },
                
                # Toliara Province (U)
                {
                    "name": "TOLIARA SOUTHERN OFFICE",
                    "province_code": ProvinceCodeEnum.TOLIARA,
                    "office_number": "01",
                    "office_type": OfficeTypeEnum.MAIN,
                    "locality": "BETANIA, TOLIARA",  # Combined locality, town format
                    "street_address": "AVENUE DE LA LIBERATION",
                    "phone_number": "+261 94 321 987",
                    "email": "toliara.south@gov.mg",
                    "manager_name": "RABARY MIORA",
                    "max_daily_capacity": 40,
                    "max_staff_capacity": 6,
                    "operational_schedule": [
                        {"day": "Monday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Tuesday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Wednesday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Thursday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Friday", "is_open": True, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Saturday", "is_open": False, "open_time": "08:00", "close_time": "17:00"},
                        {"day": "Sunday", "is_open": False, "open_time": "08:00", "close_time": "17:00"}
                    ]
                },
                {
                    "name": "TOLIARA MOBILE UNIT",
                    "province_code": ProvinceCodeEnum.TOLIARA,
                    "office_number": "02",
                    "office_type": OfficeTypeEnum.MOBILE,
                    "locality": "ANKIEMBE, TOLIARA",  # Combined locality, town format
                    "manager_name": "RAHARISON DAVID",
                    "max_daily_capacity": 25,
                    "max_staff_capacity": 4,
                    "operational_schedule": [
                        {"day": "Monday", "is_open": True, "open_time": "09:00", "close_time": "16:00"},
                        {"day": "Tuesday", "is_open": True, "open_time": "09:00", "close_time": "16:00"},
                        {"day": "Wednesday", "is_open": True, "open_time": "09:00", "close_time": "16:00"},
                        {"day": "Thursday", "is_open": True, "open_time": "09:00", "close_time": "16:00"},
                        {"day": "Friday", "is_open": True, "open_time": "09:00", "close_time": "16:00"},
                        {"day": "Saturday", "is_open": False, "open_time": "09:00", "close_time": "16:00"},
                        {"day": "Sunday", "is_open": False, "open_time": "09:00", "close_time": "16:00"}
                    ],
                    "special_notes": "Mobile unit serving remote areas"
                }
            ]
            
            created_locations = []
            for loc_data in locations_data:
                # Check if location already exists
                existing = db.query(Location).filter(
                    Location.province_code == loc_data["province_code"].value,
                    Location.office_number == loc_data["office_number"]
                ).first()
                
                if not existing:
                    # Pass enum objects directly to LocationCreate - it will handle them properly
                    location_create = LocationCreate(**loc_data)
                    
                    # Use None for system initialization instead of string
                    location = crud_location.create_with_codes(
                        db=db,
                        obj_in=location_create,
                        created_by=None
                    )
                    created_locations.append({
                        "code": location.code,
                        "full_code": location.full_code,
                        "name": location.name,
                        "province": location.province_name,
                        "type": location.office_type
                    })
            
            # Get statistics
            stats = crud_location.get_location_statistics(db=db)
            
            return {
                "status": "success",
                "message": "Madagascar locations initialized successfully",
                "created_locations": created_locations,
                "total_locations": stats["total_locations"],
                "locations_by_province": stats["locations_by_province"],
                "locations_by_type": stats["locations_by_type"],
                "total_capacity": stats["total_staff_capacity"],
                "note": "All 6 Madagascar provinces represented with sample offices",
                "timestamp": time.time()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to initialize locations: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Failed to initialize locations: {str(e)}",
                "timestamp": time.time()
            }
        )


@app.post("/admin/init-location-users", tags=["Admin"])
async def initialize_location_users():
    """Initialize users for all operational locations"""
    try:
        from app.core.database import get_db
        from app.crud import user as crud_user
        from app.schemas import UserCreate
        from app.models.user import Role, Location
        
        db = next(get_db())
        
        try:
            # Get location-specific roles (these are the only roles needed for location users)
            supervisor_role = db.query(Role).filter(Role.name == "office_supervisor").first()
            clerk_role = db.query(Role).filter(Role.name == "clerk").first()  
            printer_role = db.query(Role).filter(Role.name == "printer").first()
            
            if not all([supervisor_role, clerk_role, printer_role]):
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "Required location roles not found. Please initialize roles first.",
                        "timestamp": time.time()
                    }
                )
            
            # Get operational locations  
            locations = db.query(Location).filter(Location.is_operational == True).all()
            
            if not locations:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "No operational locations found. Please initialize locations first.",
                        "timestamp": time.time()
                    }
                )
            
            # Test users data for each location
            user_templates = [
                {
                    "email_template": "clerk.{location}@gov.mg",
                    "first_name": "MARIE",
                    "last_name": "RAZAFY",
                    "madagascar_id_number_template": "1{province_num:02d}234567890",
                    "id_document_type": "MADAGASCAR_ID",
                    "password": "Clerk123!",
                    "employee_id_template": "CLK{location}001",
                    "department": "LICENSE PROCESSING",
                    "roles": [clerk_role.id]
                },
                {
                    "email_template": "supervisor.{location}@gov.mg",
                    "first_name": "JEAN",
                    "last_name": "RAKOTO",
                    "madagascar_id_number_template": "2{province_num:02d}987654321",
                    "id_document_type": "MADAGASCAR_ID",
                    "password": "Supervisor123!",
                    "employee_id_template": "SUP{location}001",
                    "department": "LICENSE PROCESSING",
                    "roles": [supervisor_role.id]
                },
                {
                    "email_template": "printer.{location}@gov.mg",
                    "first_name": "PAUL",
                    "last_name": "ANDRY",
                    "madagascar_id_number_template": "3{province_num:02d}456789123",
                    "id_document_type": "PASSPORT",
                    "password": "Printer123!",
                    "employee_id_template": "PRT{location}001",
                    "department": "CARD PRODUCTION",
                    "roles": [printer_role.id]
                }
            ]
            
            # Province number mapping for ID generation
            province_numbers = {"T": 1, "D": 2, "F": 3, "M": 4, "A": 5, "U": 6}
            
            created_users = []
            for location in locations:
                province_num = province_numbers.get(location.province_code, 0)
                
                for template in user_templates:
                    # Generate user data for this location
                    user_data = {
                        "username": f"temp_{location.code.lower()}_{template['first_name'].lower()}",  # Temporary, will be overridden
                        "email": template["email_template"].format(location=location.code.lower()),
                        "first_name": template["first_name"],
                        "last_name": template["last_name"],
                        "madagascar_id_number": template["madagascar_id_number_template"].format(province_num=province_num),
                        "id_document_type": template["id_document_type"],
                        "password": template["password"],
                        "confirm_password": template["password"],
                        "phone_number": f"+261 {30 + province_num} {location.office_number} {template['roles'][0].__hash__() % 1000:03d}",
                        "employee_id": template["employee_id_template"].format(location=location.code),
                        "department": template["department"],
                        "role_ids": template["roles"]
                    }
                    
                    # Check if user already exists
                    existing = crud_user.get_by_email(db=db, email=user_data["email"])
                    if not existing:
                        user_create = UserCreate(**user_data)
                        user = crud_user.create_with_location(
                            db=db,
                            obj_in=user_create,
                            location_id=location.id,
                            created_by=None
                        )
                        
                        created_users.append({
                            "username": user.username,
                            "email": user.email,
                            "full_name": user.full_name,
                            "location_code": user.assigned_location_code,
                            "location_name": location.name,
                            "roles": [role.name for role in user.roles],
                            "password": template["password"]
                        })
            
            # Update location staff counts
            for location in locations:
                location_users = crud_user.get_by_location(db=db, location_id=location.id)
                location.current_staff_count = len(location_users)
            
            db.commit()
            
            return {
                "status": "success",
                "message": "Location-based users created successfully",
                "created_users": created_users,
                "total_users_created": len(created_users),
                "locations_with_users": len(locations),
                "username_format": "Location-based usernames (e.g., T010001, F010002)",
                "note": "Each operational location now has clerk, supervisor, and printer users",
                "timestamp": time.time()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to initialize location users: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Failed to initialize location users: {str(e)}",
                "timestamp": time.time()
            }
        )


@app.post("/admin/init-fee-structures", tags=["Admin"])
async def initialize_fee_structures():
    """Initialize default fee structures for applications module"""
    try:
        from app.core.database import get_db
        from app.models.transaction import FeeStructure
        from app.models.enums import LicenseCategory, ApplicationType
        
        db = next(get_db())
        
        try:
            # Check if fee structures already exist
            existing_count = db.query(FeeStructure).count()
            if existing_count > 0:
                return {
                    "status": "success",
                    "message": f"Fee structures already exist ({existing_count} records)",
                    "skipped": True,
                    "timestamp": time.time()
                }
            
            # Madagascar Driver's License Fee Structure
            # Using FeeStructure model with proper field names
            fee_structures = [
                # Theory Test Fees for Light Categories (10,000 Ar)
                {
                    "fee_type": "theory_test_light",
                    "display_name": "Theory Test - Light Categories",
                    "description": "Theory test fee for A1/A2/A (Motorcycles), B1/B (Light Vehicles)",
                    "amount": 10000.0,
                    "applies_to_categories": ["A1", "A2", "A", "B1", "B"],
                    "applies_to_application_types": ["NEW_LICENSE", "LEARNERS_PERMIT"],
                    "is_mandatory": True,
                    "is_active": True
                },
                
                # Theory Test Fees for Heavy/Commercial Categories (15,000 Ar)
                {
                    "fee_type": "theory_test_heavy",
                    "display_name": "Theory Test - Heavy/Commercial Categories", 
                    "description": "Theory test fee for B2, BE, C1, C, C1E, CE, D1, D, D2 categories",
                    "amount": 15000.0,
                    "applies_to_categories": ["B2", "BE", "C1", "C", "C1E", "CE", "D1", "D", "D2"],
                    "applies_to_application_types": ["NEW_LICENSE", "LEARNERS_PERMIT"],
                    "is_mandatory": True,
                    "is_active": True
                },
                
                # Practical Test Fees for Light Categories (10,000 Ar)
                {
                    "fee_type": "practical_test_light",
                    "display_name": "Practical Test - Light Categories",
                    "description": "Practical test fee for A1/A2/A (Motorcycles), B1/B (Light Vehicles)",
                    "amount": 10000.0,
                    "applies_to_categories": ["A1", "A2", "A", "B1", "B"],
                    "applies_to_application_types": ["NEW_LICENSE"],
                    "is_mandatory": True,
                    "is_active": True
                },
                
                # Practical Test Fees for Heavy/Commercial Categories (15,000 Ar)
                {
                    "fee_type": "practical_test_heavy",
                    "display_name": "Practical Test - Heavy/Commercial Categories",
                    "description": "Practical test fee for B2, BE, C1, C, C1E, CE, D1, D, D2 categories",
                    "amount": 15000.0,
                    "applies_to_categories": ["B2", "BE", "C1", "C", "C1E", "CE", "D1", "D", "D2"],
                    "applies_to_application_types": ["NEW_LICENSE"],
                    "is_mandatory": True,
                    "is_active": True
                },
                
                # Card Production Fee (38,000 Ar - applies to all)
                {
                    "fee_type": "card_production",
                    "display_name": "License Card Production",
                    "description": "Card production fee for CIM-produced license cards (all SADC categories)",
                    "amount": 38000.0,
                    "applies_to_categories": ["A1", "A2", "A", "B1", "B", "B2", "BE", "C1", "C", "C1E", "CE", "D1", "D", "D2"],
                    "applies_to_application_types": ["NEW_LICENSE", "RENEWAL", "REPLACEMENT"],
                    "is_mandatory": True,
                    "is_active": True
                },
                
                # Temporary License Fees (urgency-based pricing)
                {
                    "fee_type": "temporary_license_standard",
                    "display_name": "Temporary License - Standard",
                    "description": "Standard temporary license fee (90-day A4 permit)",
                    "amount": 30000.0,
                    "applies_to_categories": ["A1", "A2", "A", "B1", "B", "B2", "BE", "C1", "C", "C1E", "CE", "D1", "D", "D2"],
                    "applies_to_application_types": ["TEMPORARY_LICENSE"],
                    "is_mandatory": True,
                    "is_active": True
                },
                {
                    "fee_type": "temporary_license_urgent",
                    "display_name": "Temporary License - Urgent",
                    "description": "Urgent temporary license fee (same-day processing)",
                    "amount": 100000.0,
                    "applies_to_categories": ["A1", "A2", "A", "B1", "B", "B2", "BE", "C1", "C", "C1E", "CE", "D1", "D", "D2"],
                    "applies_to_application_types": ["TEMPORARY_LICENSE"],
                    "is_mandatory": True,
                    "is_active": True
                },
                {
                    "fee_type": "temporary_license_emergency",
                    "display_name": "Temporary License - Emergency",
                    "description": "Emergency temporary license fee (immediate processing)",
                    "amount": 400000.0,
                    "applies_to_categories": ["A1", "A2", "A", "B1", "B", "B2", "BE", "C1", "C", "C1E", "CE", "D1", "D", "D2"],
                    "applies_to_application_types": ["TEMPORARY_LICENSE"],
                    "is_mandatory": True,
                    "is_active": True
                },
                
                # International Permit Fee (50,000 Ar)
                {
                    "fee_type": "international_permit",
                    "display_name": "International Driving Permit",
                    "description": "International driving permit fee (based on existing license)",
                    "amount": 50000.0,
                    "applies_to_categories": ["A1", "A2", "A", "B1", "B", "B2", "BE", "C1", "C", "C1E", "CE", "D1", "D", "D2"],
                    "applies_to_application_types": ["INTERNATIONAL_PERMIT"],
                    "is_mandatory": True,
                    "is_active": True
                },
                
                # License Renewal Fee (20,000 Ar)
                {
                    "fee_type": "license_renewal",
                    "display_name": "License Renewal",
                    "description": "License renewal fee (5-year validity for all categories)",
                    "amount": 20000.0,
                    "applies_to_categories": ["A1", "A2", "A", "B1", "B", "B2", "BE", "C1", "C", "C1E", "CE", "D1", "D", "D2"],
                    "applies_to_application_types": ["RENEWAL"],
                    "is_mandatory": True,
                    "is_active": True
                }
            ]
            
            # Get system user for created_by field
            from app.models.user import User
            from app.models.enums import UserType
            
            # Debug: Check what users exist
            all_users = db.query(User).all()
            logger.info(f"Fee structures init: Found {len(all_users)} users in database")
            for user in all_users[:5]:  # Log first 5 users
                logger.info(f"  User: {user.username}, type: {user.user_type}, id: {user.id}")
            
            # Try to find system user in order of preference
            system_user = (
                db.query(User).filter(User.username == "S001").first() or
                db.query(User).filter(User.user_type == UserType.SYSTEM_USER).first() or
                db.query(User).filter(User.user_type == UserType.NATIONAL_ADMIN).first() or
                db.query(User).order_by(User.created_at).first()
            )
            
            logger.info(f"Selected system user: {system_user.username if system_user else 'None'}")
            
            if not system_user:
                return JSONResponse(
                    status_code=400,
                    content={
                        "status": "error",
                        "message": "No users found in database. Please initialize users first.",
                        "timestamp": time.time()
                    }
                )
            
            created_fees = []
            for fee_data in fee_structures:
                # Add created_by field
                fee_data["created_by"] = system_user.id
                fee = FeeStructure(**fee_data)
                db.add(fee)
                db.flush()
                created_fees.append({
                    "fee_type": fee_data["fee_type"],
                    "display_name": fee_data["display_name"],
                    "amount": fee_data["amount"],
                    "description": fee_data["description"]
                })
            
            db.commit()
            
            return {
                "status": "success",
                "message": "Fee structures initialized successfully",
                "created_fee_structures": created_fees,
                "total_created": len(created_fees),
                "summary": {
                    "theory_test_fees": "Light (A1/A2/A/B1/B): 10,000 Ar, Heavy/Commercial (B2/BE/C1/C/C1E/CE/D1/D/D2): 15,000 Ar",
                    "practical_test_fees": "Same as theory test fees",
                    "card_production": "38,000 Ar (single fee)",
                    "temporary_licenses": "30,000-400,000 Ar (urgency-based)",
                    "international_permit": "50,000 Ar",
                    "renewals": "20,000 Ar"
                },
                "note": "Madagascar driver's license fee structure using SADC license codes",
                "timestamp": time.time()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to initialize fee structures: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Failed to initialize fee structures: {str(e)}",
                "timestamp": time.time()
            }
        )


async def cleanup_biometric_files():
    """
    Clean up all biometric files from storage
    Used during database reset to remove orphaned files
    """
    try:
        from app.core.config import get_settings
        from pathlib import Path
        import shutil
        
        settings = get_settings()
        storage_path = settings.get_file_storage_path()
        biometric_path = storage_path / "biometric"
        
        files_removed = 0
        folders_removed = 0
        
        if biometric_path.exists():
            logger.info(f"Cleaning biometric files from: {biometric_path}")
            
            # Remove all files and subdirectories in biometric folder
            for item in biometric_path.iterdir():
                try:
                    if item.is_file():
                        item.unlink()
                        files_removed += 1
                        logger.debug(f"Removed file: {item}")
                    elif item.is_dir():
                        shutil.rmtree(item)
                        folders_removed += 1
                        logger.debug(f"Removed directory: {item}")
                except Exception as item_error:
                    logger.warning(f"Could not remove {item}: {item_error}")
            
            logger.info(f"Biometric cleanup completed: {files_removed} files, {folders_removed} folders removed")
        else:
            logger.info(f"Biometric path does not exist: {biometric_path}")
        
        return {
            "files_removed": files_removed,
            "folders_removed": folders_removed,
            "storage_path": str(biometric_path)
        }
        
    except Exception as e:
        logger.error(f"Error during biometric file cleanup: {e}")
        return {
            "files_removed": 0,
            "folders_removed": 0,
            "error": str(e)
        }


@app.post("/admin/reset-database", tags=["Admin"])
async def reset_database():
    """
    DEVELOPMENT ONLY: Complete database reset
    Drops all tables, recreates them, and initializes with base data
    """
    try:
        from app.core.database import drop_tables, create_tables
        from app.models.enums import LicenseCategory
        
        logger.warning("Resetting entire database - all data will be lost")
        
        # Step 1: Drop and recreate all tables
        drop_tables()
        create_tables()
        
        # Step 1.5: Clean up orphaned biometric files
        logger.info("Cleaning up biometric files...")
        files_cleaned = await cleanup_biometric_files()
        
        # Verify enum values are properly created
        from app.core.database import get_db
        from sqlalchemy import text
        enum_values = []  # Initialize with default value
        db = next(get_db())
        try:
            # Check if enum is created with correct values
            result = db.execute(text("SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'licensecategory')"))
            enum_values = [row[0] for row in result.fetchall()]
            logger.info(f"Verified enum values in database: {enum_values}")
        except Exception as enum_error:
            logger.error(f"Error checking enum values: {enum_error}")
            # Set default enum values if query fails
            enum_values = ["A1", "A2", "A", "B1", "B", "B2", "BE", "C1", "C", "C1E", "CE", "D1", "D", "D2"]
        finally:
            db.close()
        
        # Step 2: Initialize all data automatically
        logger.info("Initializing users, roles, and permissions...")
        users_result = await initialize_users()
        if users_result.get("status") != "success":
            raise Exception(f"Failed to initialize users: {users_result.get('message', 'Unknown error')}")
        
        logger.info("Initializing locations...")
        locations_result = await initialize_locations()
        if locations_result.get("status") != "success":
            raise Exception(f"Failed to initialize locations: {locations_result.get('message', 'Unknown error')}")
        
        logger.info("Initializing location users...")
        location_users_result = await initialize_location_users()
        if location_users_result.get("status") != "success":
            raise Exception(f"Failed to initialize location users: {location_users_result.get('message', 'Unknown error')}")
        
        logger.info("Initializing fee structures...")
        fee_structures_result = await initialize_fee_structures()
        if fee_structures_result.get("status") != "success":
            raise Exception(f"Failed to initialize fee structures: {fee_structures_result.get('message', 'Unknown error')}")
        
        return {
            "status": "success",
            "message": "Complete database reset and initialization successful",
            "warning": "All previous data has been permanently deleted",
            "steps_completed": [
                "Tables dropped and recreated",
                "Biometric files cleaned up",
                "Base users and roles initialized (including EXAMINER role)",
                "Madagascar locations initialized",
                "Location-based users created",
                "Fee structures initialized"
            ],
            "summary": {
                "enum_values_created": len(enum_values),
                "biometric_files_removed": files_cleaned.get("files_removed", 0),
                "biometric_folders_removed": files_cleaned.get("folders_removed", 0),
                "permissions_created": users_result.get("permissions_created", 0),
                "roles_created": users_result.get("roles_created", 0),
                "locations_created": locations_result.get("locations_created", 0),
                "location_users_created": location_users_result.get("users_created", 0),
                "fee_structures_created": fee_structures_result.get("total_created", 0)
            },
            "admin_credentials": {
                "username": "admin",
                "password": "Admin123",
                "email": "admin@madagascar-license.gov.mg"
            },
            "test_users": [
                {"username": "clerk1", "password": "Clerk123!", "permissions": "person management + license processing"},
                {"username": "supervisor1", "password": "Supervisor123!", "permissions": "all clerk permissions + deletions"},
                {"username": "printer1", "password": "Printer123!", "permissions": "printing operations only"},
                {"username": "examiner1", "password": "Examiner123!", "permissions": "application authorization + license generation"}
            ],
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Failed to reset database: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Database reset failed: {str(e)}",
                "timestamp": time.time()
            }
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 