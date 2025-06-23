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

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import logging

from app.core.config import get_settings
from app.core.database import create_tables
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
        from app.core.database import create_tables
        
        logger.info("Creating database tables")
        create_tables()
        
        return {
            "status": "success", 
            "message": "Database tables created successfully",
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


@app.post("/admin/init-users", tags=["Admin"]) 
async def initialize_users():
    """Initialize default users, roles, and permissions for testing"""
    try:
        from app.core.database import get_db
        from app.models.user import User, Role, Permission
        from app.models.user import UserStatus, MadagascarIDType
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
                
                # Role Management Permissions
                ("roles.create", "Create Roles", "Create new roles", "roles", "role", "create"),
                ("roles.read", "View Roles", "View role information", "roles", "role", "read"),
                ("roles.update", "Update Roles", "Update role information", "roles", "role", "update"),
                ("roles.delete", "Delete Roles", "Delete roles", "roles", "role", "delete"),
                ("roles.assign_permissions", "Assign Role Permissions", "Assign permissions to roles", "roles", "role", "assign_permissions"),
                
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
                
                # Printing Permissions
                ("printing.local_print", "Local Printing", "Print at local location", "printing", "print_job", "local_print"),
                ("printing.cross_location_print", "Cross-Location Printing", "Print at other locations", "printing", "print_job", "cross_location_print"),
                ("printing.manage_queue", "Manage Print Queue", "Manage printing queue", "printing", "print_job", "manage_queue"),
                ("printing.monitor_status", "Monitor Printer Status", "Monitor printer status", "printing", "printer", "monitor_status"),
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
            
            # Define role permissions - Updated to include Person module
            clerk_permissions = [
                "license_applications.create", "license_applications.read", "license_applications.update",
                "printing.local_print", "printing.monitor_status",
                # Person management (essential for license applications)
                "persons.create", "persons.read", "persons.update", "persons.search", "persons.check_duplicates",
                "person_aliases.create", "person_aliases.read", "person_aliases.update", "person_aliases.set_primary",
                "person_addresses.create", "person_addresses.read", "person_addresses.update", "person_addresses.set_primary"
            ]
            
            supervisor_permissions = clerk_permissions + [
                "license_applications.approve",
                "users.read", "users.update", "roles.read", "permissions.read",
                # Additional person management permissions for supervisors
                "persons.delete", "person_aliases.delete", "person_addresses.delete"
            ]
            
            printer_permissions = [
                "printing.local_print", "printing.cross_location_print",
                "printing.manage_queue", "printing.monitor_status"
            ]
            
            admin_permissions = [perm for perm in permissions.keys()]  # All permissions
            
            # Create roles
            roles_data = [
                ("admin", "Administrator", "Full system access", admin_permissions),
                ("clerk", "Clerk", "License processing clerk with person management", clerk_permissions),
                ("supervisor", "Supervisor", "License processing supervisor with additional permissions", supervisor_permissions),
                ("printer", "Printer", "Card printing operator", printer_permissions)
            ]
            
            roles = {}
            for role_name, display_name, description, role_permissions in roles_data:
                existing = db.query(Role).filter(Role.name == role_name).first()
                if not existing:
                    role = Role(
                        name=role_name,
                        display_name=display_name,
                        description=description,
                        is_system_role=True,
                        level=0
                    )
                    db.add(role)
                    db.flush()
                    
                    # Assign permissions to role
                    role_permission_objects = []
                    for perm_name in role_permissions:
                        if perm_name in permissions:
                            role_permission_objects.append(permissions[perm_name])
                    
                    role.permissions = role_permission_objects
                    roles[role_name] = role
                else:
                    roles[role_name] = existing
            
            # Create admin user
            admin = db.query(User).filter(User.username == "admin").first()
            if not admin:
                admin = User(
                    username="admin",
                    email="admin@madagascar-license.gov.mg",
                    password_hash=get_password_hash("MadagascarAdmin2024!"),
                    first_name="System",
                    last_name="Administrator",
                    display_name="System Administrator",
                    madagascar_id_number="ADM001",
                    id_document_type=MadagascarIDType.CIN,
                    phone_number="+261340000000",
                    employee_id="ADM001",
                    department="IT Administration",
                    country_code="MG",
                    province="Antananarivo",
                    region="Analamanga",
                    office_location="Central Office",
                    language="en",
                    timezone="Indian/Antananarivo",
                    currency="MGA",
                    status=UserStatus.ACTIVE,
                    is_superuser=True,
                    is_verified=True
                )
                
                db.add(admin)
                db.flush()
                
                # Assign admin role
                admin.roles = [roles["admin"]]
            
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
                    "roles": ["supervisor"]
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
                    "roles": ["printer"]
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
                        id_document_type=MadagascarIDType.CIN,
                        employee_id=user_data["employee_id"],
                        department=user_data["department"],
                        country_code="MG",
                        province="Antananarivo",
                        region="Analamanga",
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
                    "password": "MadagascarAdmin2024!",
                    "email": "admin@madagascar-license.gov.mg"
                },
                "test_users": [
                    {"username": "clerk1", "password": "Clerk123!", "permissions": "person management + license processing"},
                    {"username": "supervisor1", "password": "Supervisor123!", "permissions": "all clerk permissions + deletions"},
                    {"username": "printer1", "password": "Printer123!", "permissions": "printing operations only"}
                ],
                "created_users": created_users,
                "permissions_created": len(permissions_data),
                "roles_created": len(roles_data),
                "note": "Person module is now fully integrated with permissions system",
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    ) 