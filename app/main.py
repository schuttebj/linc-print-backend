"""
Main FastAPI Application for Madagascar License System
Adapted from LINC Old with Madagascar-specific configuration
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
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "type": "internal_error",
            "status_code": 500
        }
    )


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
        from app.core.database import engine, Base
        
        logger.warning("Dropping all database tables")
        Base.metadata.drop_all(bind=engine)
        
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
        from app.core.database import engine, Base
        
        logger.info("Creating database tables")
        Base.metadata.create_all(bind=engine)
        
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
            # Create permissions
            permissions_data = [
                ("users.create", "Create Users", "Create new user accounts", "users", "user", "create"),
                ("users.read", "Read Users", "View user information", "users", "user", "read"), 
                ("users.update", "Update Users", "Modify user accounts", "users", "user", "update"),
                ("users.delete", "Delete Users", "Remove user accounts", "users", "user", "delete"),
                ("roles.create", "Create Roles", "Create new roles", "roles", "role", "create"),
                ("roles.read", "Read Roles", "View role information", "roles", "role", "read"),
                ("roles.update", "Update Roles", "Modify roles", "roles", "role", "update"),
                ("roles.delete", "Delete Roles", "Remove roles", "roles", "role", "delete"),
                ("permissions.read", "Read Permissions", "View permissions", "permissions", "permission", "read"),
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
                        action=action
                    )
                    db.add(perm)
                    db.flush()
                    permissions[name] = perm
                else:
                    permissions[name] = existing
            
            # Create roles
            roles_data = [
                ("admin", "Administrator", "Full system access", ["users.create", "users.read", "users.update", "users.delete", "roles.create", "roles.read", "roles.update", "roles.delete", "permissions.read"]),
                ("clerk", "Clerk", "License processing clerk", ["users.read", "roles.read", "permissions.read"]),
                ("supervisor", "Supervisor", "License processing supervisor", ["users.read", "users.update", "roles.read", "permissions.read"]),
                ("printer", "Printer", "Card printing operator", ["permissions.read"])
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
                "message": "Users initialized successfully",
                "admin_credentials": {
                    "username": "admin",
                    "password": "MadagascarAdmin2024!",
                    "email": "admin@madagascar-license.gov.mg"
                },
                "test_users": [
                    {"username": "clerk1", "password": "Clerk123!"},
                    {"username": "supervisor1", "password": "Supervisor123!"}
                ],
                "created_users": created_users,
                "note": "location_id parameter in login is optional - you can ignore it for testing",
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