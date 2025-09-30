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
import os
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import create_tables, get_db
from app.core.audit_middleware import setup_audit_middleware
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
    
    # Check critical tables and create if needed
    await check_and_create_critical_tables()
    
    # Note: Main table creation disabled during startup to prevent schema conflicts
    # Use /admin/reset-database or /admin/init-tables endpoints for database management
    logger.info("Database table auto-creation disabled - use admin endpoints for database management")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Madagascar License System...")


async def check_and_create_critical_tables():
    """
    Check if critical tables exist and create them if needed
    Safe to run on deployment - only creates missing tables
    """
    try:
        from app.core.database import engine
        from sqlalchemy import text, inspect
        
        # Check what tables exist
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        # Define critical tables that must exist for the system to function
        critical_tables = [
            'users',
            'roles', 
            'permissions',
            'user_roles',
            'locations',
            'user_audit_logs',
            'api_request_logs'
        ]
        
        missing_tables = [table for table in critical_tables if table not in existing_tables]
        
        if not missing_tables:
            logger.info("✅ All critical tables exist")
            return
            
        logger.info(f"🔧 Missing critical tables: {missing_tables}")
        
        # If core tables are missing, suggest using full initialization
        core_tables = ['users', 'roles', 'permissions', 'locations']
        missing_core = [table for table in core_tables if table in missing_tables]
        
        if missing_core:
            logger.warning(f"⚠️ Core system tables missing: {missing_core}")
            logger.warning("⚠️ This indicates a fresh database or corruption")
            logger.warning("⚠️ Use /admin/reset-database or /admin/init-tables for full initialization")
            logger.warning("⚠️ Continuing startup - some features may not work until tables are created")
            return
            
        # Only create audit tables if core system exists
        if 'api_request_logs' in missing_tables:
            await create_api_request_logs_table()
            
    except Exception as e:
        logger.error(f"❌ Failed to check critical tables: {e}")
        logger.info("⚠️ Continuing startup - use manual endpoints if needed")


async def create_api_request_logs_table():
    """Create the API request logs table with indexes"""
    try:
        from app.core.database import engine
        from sqlalchemy import text
        
        logger.info("🔧 Creating API request logs table...")
        
        with engine.connect() as conn:
            # Create the api_request_logs table
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS api_request_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                created_by UUID REFERENCES users(id) ON DELETE SET NULL,
                updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                deleted_at TIMESTAMPTZ,
                deleted_by UUID REFERENCES users(id) ON DELETE SET NULL,
                
                -- Request identification
                request_id VARCHAR(36) NOT NULL UNIQUE,
                
                -- Request details
                method VARCHAR(10) NOT NULL,
                endpoint VARCHAR(500) NOT NULL,
                query_params TEXT,
                
                -- User context
                user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                ip_address VARCHAR(45),
                user_agent TEXT,
                
                -- Response details
                status_code INTEGER NOT NULL,
                response_size_bytes INTEGER,
                
                -- Performance metrics
                duration_ms INTEGER NOT NULL,
                
                -- Location context
                location_id UUID REFERENCES locations(id) ON DELETE SET NULL,
                
                -- Error tracking
                error_message TEXT
            );
            """
            
            conn.execute(text(create_table_sql))
            
            # Create indexes for better query performance
            index_sql = [
                "CREATE INDEX IF NOT EXISTS idx_api_request_logs_created_at ON api_request_logs(created_at DESC);",
                "CREATE INDEX IF NOT EXISTS idx_api_request_logs_user_id ON api_request_logs(user_id);",
                "CREATE INDEX IF NOT EXISTS idx_api_request_logs_endpoint ON api_request_logs(endpoint);",
                "CREATE INDEX IF NOT EXISTS idx_api_request_logs_status_code ON api_request_logs(status_code);",
                "CREATE INDEX IF NOT EXISTS idx_api_request_logs_duration ON api_request_logs(duration_ms);",
                "CREATE INDEX IF NOT EXISTS idx_api_request_logs_method ON api_request_logs(method);"
            ]
            
            for index in index_sql:
                conn.execute(text(index))
                
            conn.commit()
            logger.info("✅ API request logs table created successfully with indexes")
            
    except Exception as e:
        logger.error(f"❌ Failed to create API request logs table: {e}")
        logger.info("⚠️ Use /admin/init-audit-middleware-table to create manually")


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
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add audit middleware for API request logging (can be disabled)
if not os.getenv("DISABLE_AUDIT_MIDDLEWARE", "").lower() in ["true", "1", "yes"]:
    setup_audit_middleware(app)
    logger.info("✅ Audit middleware enabled")
else:
    logger.info("⚠️ Audit middleware disabled via DISABLE_AUDIT_MIDDLEWARE environment variable")



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
    """
    Health check endpoint with database connection test
    Useful for debugging Render PostgreSQL connection issues
    """
    from app.core.database import test_database_connection
    
    # Test database connection
    db_connected, db_message = test_database_connection()
    
    health_status = {
        "status": "healthy" if db_connected else "unhealthy",
        "version": settings.VERSION,
        "system": "Madagascar License System",
        "timestamp": time.time(),
        "database": {
            "connected": db_connected,
            "message": db_message
        }
    }
    
    # Return 503 if database is not connected
    if not db_connected:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=health_status)
    
    return health_status


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

"""
==============================================================================
ADMIN ENDPOINTS - DATABASE MANAGEMENT
==============================================================================

Database Management Workflow:
1. For fresh setup: POST /admin/init-tables (creates tables with correct schema)
2. For complete reset: POST /admin/reset-database (drops all tables, recreates, initializes data)
3. For schema fixes: POST /admin/fix-fee-structures-schema (adds missing columns)

IMPORTANT: Auto table creation on deployment is DISABLED to prevent schema conflicts.
Always use the above endpoints for database management.

Available Admin Endpoints:
- /admin/drop-tables: Drop all database tables
- /admin/init-tables: Create tables with latest schema
- /admin/reset-database: Complete database reset with data initialization
- /admin/fix-license-enum: Fix LicenseCategory enum values
- /admin/fix-fee-structures-schema: Fix fee_structures table schema
- /admin/init-audit-middleware-table: Create api_request_logs table for audit middleware
- /admin/init-users: Initialize default users and roles
- /admin/init-locations: Initialize Madagascar locations
- /admin/init-location-users: Initialize location-based users
- /admin/init-fee-structures: Initialize fee structures
- /admin/inspect-database: Inspect current database schema

==============================================================================
"""

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


@app.post("/admin/init-audit-middleware-table", tags=["Admin"]) 
async def init_audit_middleware_table():
    """
    Manual: Initialize API Request Logs Table
    
    Creates the api_request_logs table with indexes for the audit middleware system.
    This table stores comprehensive API request monitoring data including:
    - Request details (method, endpoint, query parameters)
    - User context (user ID, IP address, user agent)
    - Performance metrics (response time, response size)
    - Status tracking (HTTP status codes, error messages)
    
    📋 **When to use this endpoint:**
    - If the automatic startup check failed
    - If you want to manually control table creation
    - If you need to recreate the table after corruption
    
    ✅ **Automatic alternative:** The system checks for this table on startup
    and creates it automatically if missing (recommended for most users).
    
    🔄 **Full reset alternative:** /admin/reset-database includes this table creation.
    """
    try:
        from app.core.database import engine
        from sqlalchemy import text
        
        logger.info("Creating api_request_logs table for audit middleware")
        
        with engine.connect() as conn:
            # Create the api_request_logs table
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS api_request_logs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                created_by UUID REFERENCES users(id) ON DELETE SET NULL,
                updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                deleted_at TIMESTAMPTZ,
                deleted_by UUID REFERENCES users(id) ON DELETE SET NULL,
                
                -- Request identification
                request_id VARCHAR(36) NOT NULL UNIQUE,
                
                -- Request details
                method VARCHAR(10) NOT NULL,
                endpoint VARCHAR(500) NOT NULL,
                query_params TEXT,
                
                -- User context
                user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                ip_address VARCHAR(45),
                user_agent TEXT,
                
                -- Response details
                status_code INTEGER NOT NULL,
                response_size_bytes INTEGER,
                
                -- Performance metrics
                duration_ms INTEGER NOT NULL,
                
                -- Location context
                location_id UUID REFERENCES locations(id) ON DELETE SET NULL,
                
                -- Error tracking
                error_message TEXT
            );
            """
            
            conn.execute(text(create_table_sql))
            
            # Create indexes for better query performance
            index_sql = [
                "CREATE INDEX IF NOT EXISTS idx_api_request_logs_created_at ON api_request_logs(created_at DESC);",
                "CREATE INDEX IF NOT EXISTS idx_api_request_logs_user_id ON api_request_logs(user_id);",
                "CREATE INDEX IF NOT EXISTS idx_api_request_logs_endpoint ON api_request_logs(endpoint);",
                "CREATE INDEX IF NOT EXISTS idx_api_request_logs_status_code ON api_request_logs(status_code);",
                "CREATE INDEX IF NOT EXISTS idx_api_request_logs_duration ON api_request_logs(duration_ms);",
                "CREATE INDEX IF NOT EXISTS idx_api_request_logs_method ON api_request_logs(method);"
            ]
            
            for index in index_sql:
                conn.execute(text(index))
                
            conn.commit()
            logger.info("Successfully created api_request_logs table and indexes")
        
        return {
            "status": "success",
            "message": "api_request_logs table created successfully with performance indexes",
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Failed to create api_request_logs table: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Failed to create api_request_logs table: {str(e)}",
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
                "includes_category_3": "3" in created_values,
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
                
                # Applications Management Permissions (main application module)
                ("applications.create", "Create Applications", "Create new applications", "applications", "application", "create"),
                ("applications.read", "View Applications", "View applications", "applications", "application", "read"),
                ("applications.update", "Update Applications", "Update applications", "applications", "application", "update"),
                ("applications.delete", "Delete Applications", "Delete applications", "applications", "application", "delete"),
                ("applications.approve", "Approve Applications", "Approve applications", "applications", "application", "approve"),
                ("applications.authorize", "Authorize Applications", "Authorize applications", "applications", "application", "authorize"),
                ("applications.review_authorization", "Review Authorization", "Review application authorization", "applications", "application", "review_authorization"),
                ("applications.bulk_process", "Bulk Process Applications", "Process multiple applications", "applications", "application", "bulk_process"),
                ("applications.change_status", "Change Application Status", "Change application status through workflow", "applications", "application", "change_status"),
                ("applications.submit", "Submit Applications", "Submit applications for processing", "applications", "application", "submit"),
                ("applications.test_results", "Record Test Results", "Record test results (PASSED/FAILED/ABSENT)", "applications", "application", "test_results"),
                ("applications.view_errors", "View Error Applications", "View applications with processing errors", "applications", "application", "view_errors"),
                ("applications.fix_errors", "Fix Error Applications", "Fix and retry failed application processing", "applications", "application", "fix_errors"),
                
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
                
                # Enhanced Printing and Card Management Permissions
                ("printing.create", "Create Print Jobs", "Create new print jobs for card ordering", "printing", "print_job", "create"),
                ("printing.read", "View Print Jobs", "View print job details and queue", "printing", "print_job", "read"),
                ("printing.update", "Update Print Jobs", "Update print job information", "printing", "print_job", "update"),
                ("printing.delete", "Delete Print Jobs", "Cancel or delete print jobs", "printing", "print_job", "delete"),
                ("printing.assign", "Assign Print Jobs", "Assign print jobs to operators", "printing", "print_job", "assign"),
                ("printing.start", "Start Printing", "Begin printing process for jobs", "printing", "print_job", "start"),
                ("printing.complete", "Complete Printing", "Mark print jobs as completed", "printing", "print_job", "complete"),
                ("printing.quality_check", "Quality Assurance", "Perform quality checks on printed cards", "printing", "print_job", "quality_check"),
                ("printing.move_to_top", "Priority Queue Management", "Move jobs to top of queue", "printing", "print_job", "move_to_top"),
                ("printing.regenerate_files", "Regenerate Card Files", "Regenerate PDF files for print jobs", "printing", "print_job", "regenerate_files"),
                ("printing.view_statistics", "View Print Statistics", "View printing performance and statistics", "printing", "print_job", "view_statistics"),
                
                # Card Management Permissions
                ("cards.create", "Create Cards", "Create new card records", "cards", "card", "create"),
                ("cards.read", "View Cards", "View card information and status", "cards", "card", "read"),
                ("cards.update", "Update Cards", "Update card information", "cards", "card", "update"),
                ("cards.delete", "Delete Cards", "Delete card records", "cards", "card", "delete"),
                ("cards.order", "Order Cards", "Order cards for printing", "cards", "card", "order"),
                ("cards.track_status", "Track Card Status", "Monitor card production status", "cards", "card", "track_status"),
                ("cards.collect", "Collect Cards", "Complete card collection process", "cards", "card", "collect"),
                ("cards.collection.read", "View Collection Queue", "View cards ready for collection", "cards", "card", "collection_read"),
                ("cards.update_status", "Update Card Status", "Update card status through production workflow", "cards", "card", "update_status"),
                
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
                
                # Transaction Permissions (NEW)
                ("transactions.create", "Create Transactions", "Process payments and create transactions", "transactions", "transaction", "create"),
                ("transactions.read", "View Transactions", "View transaction history and details", "transactions", "transaction", "read"),
                ("transactions.update", "Update Transactions", "Update transaction information", "transactions", "transaction", "update"),
                ("transactions.delete", "Delete Transactions", "Delete or cancel transactions", "transactions", "transaction", "delete"),
                ("transactions.manage", "Manage Transactions", "Full transaction management access", "transactions", "transaction", "manage"),
                ("transactions.manage_fees", "Manage Fee Structures", "Update application fee amounts", "transactions", "fee_structure", "manage_fees"),
                
                # Issue Tracking Permissions (NEW)
                ("admin.issues.read", "View Issues", "View all reported issues and bug reports", "admin", "issue", "read"),
                ("admin.issues.write", "Manage Issues", "Update, assign, and manage issue reports", "admin", "issue", "write"),
                ("admin.issues.delete", "Delete Issues", "Delete issue reports", "admin", "issue", "delete"),
                ("admin.issues.stats", "Issue Statistics", "View issue tracking statistics and analytics", "admin", "issue", "stats"),
                ("issues.create", "Report Issues", "Create new issue reports", "issues", "issue", "create"),
                ("issues.comment", "Comment on Issues", "Add comments to issue reports", "issues", "issue", "comment"),
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
            
            # Define role permissions - Updated to match frontend expectations
            clerk_permissions = [
                # Applications management (essential for clerks) - refined for security
                "applications.create", "applications.read", "applications.update", "applications.submit",
                "license_applications.create", "license_applications.read", "license_applications.update",
                # Licenses management
                "licenses.read",
                # Printing permissions
                "printing.local_print", "printing.monitor_status",
                "printing.create", "printing.read", "cards.order", "cards.read", "cards.track_status",
                # Card collection permissions for clerks
                "cards.collect", "cards.collection.read",
                # Person management (essential for license applications)
                "persons.create", "persons.read", "persons.update", "persons.search", "persons.check_duplicates",
                "person_aliases.create", "person_aliases.read", "person_aliases.update", "person_aliases.set_primary",
                # Basic audit access for dashboard statistics
                "audit.read",
                "person_addresses.create", "person_addresses.read", "person_addresses.update", "person_addresses.set_primary",
                # Transaction management (for processing payments)
                "transactions.create", "transactions.read",
                # Basic location viewing and reports for clerks
                "locations.read", "reports.basic",
                # Basic role viewing (needed for user interface)
                "roles.read", "users.read",
                # Issue tracking - all users can report issues
                "issues.create", "issues.comment"
            ]
            
            supervisor_permissions = clerk_permissions + [
                # Application management for supervisors - full control
                "applications.change_status", "applications.approve", "applications.delete", "applications.bulk_process",
                "applications.view_errors", "applications.fix_errors",
                "license_applications.approve",
                "users.read", "users.update", "users.view_statistics", "roles.read", "permissions.read",
                # Additional person management permissions for supervisors
                "persons.delete", "person_aliases.delete", "person_addresses.delete",
                # Additional transaction management for supervisors
                "transactions.update", "transactions.manage",
                # Enhanced printing and card management for supervisors
                "printing.update", "printing.delete", "printing.move_to_top", "printing.view_statistics",
                "cards.create", "cards.update", "cards.delete",
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
                # Fee management (provincial and national admins can manage fees)
                "transactions.manage_fees",
                # Advanced reporting
                "reports.provincial",
                # Issue management for traffic department heads
                "admin.issues.read", "admin.issues.write", "admin.issues.stats",
                # Applications full access for department heads
                "applications.authorize", "applications.bulk_process"
            ]
            
            printer_permissions = [
                "printing.local_print", "printing.cross_location_print",
                "printing.manage_queue", "printing.monitor_status",
                # Enhanced printer permissions for full print workflow
                "printing.read", "printing.assign", "printing.start", "printing.complete",
                "printing.quality_check", "printing.regenerate_files", "printing.view_statistics",
                "cards.read", "cards.track_status", "cards.update", "cards.update_status",
                # Application status management for printing workflow
                "applications.read", "applications.change_status",
                # Basic role viewing (needed for user interface)
                "roles.read", "users.read",
                # Issue tracking - all users can report issues
                "issues.create", "issues.comment"
            ]
            
            # Define examiner permissions (test results and authorization)
            examiner_permissions = [
                # Applications access for examiners - focused on test results
                "applications.read", "applications.test_results",
                "license_applications.read", "license_applications.approve",
                # Basic permissions for interface
                "roles.read", "users.read",
                # Issue tracking - all users can report issues
                "issues.create", "issues.comment"
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
            
            # Find default location (Antananarivo Central Office) for test users
            from app.models.user import Location
            default_location = db.query(Location).filter(
                Location.province_code == "T",  # Antananarivo province
                Location.office_number == "01"  # Central office
            ).first()
            
            if default_location:
                logger.info(f"Found default location: {default_location.name} (ID: {default_location.id}) - will assign to users")
            else:
                logger.warning("No default location found. Please initialize locations first using /admin/init-locations")
                # Also check if any locations exist at all
                location_count = db.query(Location).count()
                logger.info(f"Total locations in database: {location_count}")
            
            created_users = []
            updated_users = []
            for user_data in test_users:
                existing = db.query(User).filter(User.username == user_data["username"]).first()
                if not existing:
                    # Create new user
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
                        is_verified=True,
                        primary_location_id=default_location.id if default_location else None
                    )
                    
                    # Assign roles to new user
                    user_roles = [roles[role_name] for role_name in user_data["roles"] if role_name in roles]
                    user.roles = user_roles
                    
                    db.add(user)
                    created_users.append(user_data["username"])
                else:
                    # Update existing user's roles and location
                    user_roles = [roles[role_name] for role_name in user_data["roles"] if role_name in roles]
                    existing.roles = user_roles
                    if default_location and not existing.primary_location_id:
                        existing.primary_location_id = default_location.id
                    updated_users.append(user_data["username"])
            
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
                "updated_users": updated_users,
                "default_location_assigned": default_location.name if default_location else "No location assigned - initialize locations first",
                "permissions_created": len(permissions_data),
                "roles_created": len(roles_data),
                "note": "Person module is now fully integrated with permissions system. Admin = technical superuser. Existing users updated with correct roles and default location.",
                "timestamp": time.time()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to initialize users: {e}")
        return {
            "status": "error",
            "message": f"Failed to initialize users: {str(e)}",
            "permissions_created": 0,
            "roles_created": 0,
            "timestamp": time.time()
        }


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
        return {
            "status": "error",
            "message": f"Failed to initialize locations: {str(e)}",
            "total_locations": 0,
            "timestamp": time.time()
        }


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
                return {
                    "status": "error",
                    "message": "Required location roles not found. Please initialize roles first.",
                    "users_created": 0,
                    "total_users_created": 0,
                    "timestamp": time.time()
                }
            
            # Get operational locations  
            locations = db.query(Location).filter(Location.is_operational == True).all()
            
            if not locations:
                return {
                    "status": "error",
                    "message": "No operational locations found. Please initialize locations first.",
                    "users_created": 0,
                    "total_users_created": 0,
                    "timestamp": time.time()
                }
            
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
        return {
            "status": "error",
            "message": f"Failed to initialize location users: {str(e)}",
            "users_created": 0,
            "total_users_created": 0,
            "timestamp": time.time()
        }


@app.post("/admin/init-fee-structures", tags=["Admin"])
async def initialize_fee_structures():
    """Initialize default fee structures for applications module"""
    try:
        from app.core.database import get_db
        from app.models.transaction import FeeStructure, DEFAULT_FEE_STRUCTURE, FeeType
        from app.models.enums import LicenseCategory, ApplicationType
        from app.models.user import User
        from app.models.enums import UserType
        
        db = next(get_db())
        
        try:
            # Check if fee structures already exist
            existing_count = db.query(FeeStructure).count()
            if existing_count > 0:
                return {
                    "status": "success",
                    "message": f"Fee structures already exist ({existing_count} records)",
                    "skipped": True,
                    "total_created": 0,
                    "timestamp": time.time()
                }
            
            # Get all users for debugging
            all_users = db.query(User).all()
            logger.info(f"Fee structures init: Found {len(all_users)} users in database")
            for user in all_users:
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
                return {
                    "status": "error",
                    "message": "No users found in database. Please initialize users first.",
                    "total_created": 0,
                    "timestamp": time.time()
                }
            
            created_fees = []
            for fee_type, fee_data in DEFAULT_FEE_STRUCTURE.items():
                # Create FeeStructure with only the fields that exist in the model
                fee = FeeStructure(
                    fee_type=fee_type,
                    display_name=fee_data["display_name"],
                    description=fee_data["description"],
                    amount=fee_data["amount"],
                    created_by=system_user.id,
                    is_active=True
                )
                db.add(fee)
                db.flush()
                created_fees.append({
                    "fee_type": fee_type.value,
                    "display_name": fee_data["display_name"],
                    "amount": str(fee_data["amount"]),
                    "description": fee_data["description"]
                })
            
            db.commit()
            
            return {
                "status": "success",
                "message": "Fee structures initialized successfully",
                "created_fee_structures": created_fees,
                "total_created": len(created_fees),
                "summary": {
                    "theory_test_fees": "Light (10,000 Ar), Heavy (15,000 Ar)",
                    "practical_test_fees": "Light (10,000 Ar), Heavy (15,000 Ar)",
                    "card_production": "38,000 Ar (standard)",
                    "card_urgent": "100,000 Ar",
                    "card_emergency": "400,000 Ar",
                    "application_processing": "5,000 Ar"
                },
                "note": "Madagascar driver's license fee structure",
                "timestamp": time.time()
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to initialize fee structures: {e}")
        return {
            "status": "error",
            "message": f"Failed to initialize fee structures: {str(e)}",
            "total_created": 0,
            "timestamp": time.time()
        }


@app.post("/admin/fix-fee-structures-schema", tags=["Admin"])
async def fix_fee_structures_schema():
    """Fix the fee_structures table schema by cleaning duplicates and adding constraints"""
    try:
        from app.core.database import engine
        from sqlalchemy import text
        from app.models.transaction import FeeType
        
        with engine.connect() as conn:
            # Check current state
            check_column = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'fee_structures' 
                AND column_name = 'fee_type'
            """)).fetchone()
            
            check_constraint = conn.execute(text("""
                SELECT constraint_name 
                FROM information_schema.table_constraints 
                WHERE table_name = 'fee_structures' 
                AND constraint_name = 'fee_structures_fee_type_unique'
            """)).fetchone()
            
            step_results = []
            
            # Step 1: Add column if missing
            if not check_column:
                step_results.append("🔧 Adding fee_type column...")
                conn.execute(text("""
                    ALTER TABLE fee_structures 
                    ADD COLUMN fee_type feetype NOT NULL DEFAULT 'APPLICATION_PROCESSING'
                """))
                conn.execute(text("""
                    ALTER TABLE fee_structures 
                    ALTER COLUMN fee_type DROP DEFAULT
                """))
                step_results.append("✅ fee_type column added")
            else:
                step_results.append("✅ fee_type column already exists")
            
            # Step 2: Check for and clean duplicates
            duplicates = conn.execute(text("""
                SELECT fee_type, COUNT(*) as count
                FROM fee_structures 
                GROUP BY fee_type 
                HAVING COUNT(*) > 1
            """)).fetchall()
            
            if duplicates:
                step_results.append(f"🔧 Found {len(duplicates)} duplicate fee_type groups")
                
                for fee_type, count in duplicates:
                    step_results.append(f"🧹 Cleaning {count} duplicates for fee_type: {fee_type}")
                    
                    # Keep the oldest record, delete the rest
                    conn.execute(text("""
                        DELETE FROM fee_structures 
                        WHERE fee_type = :fee_type 
                        AND id NOT IN (
                            SELECT id FROM fee_structures 
                            WHERE fee_type = :fee_type 
                            ORDER BY created_at ASC 
                            LIMIT 1
                        )
                    """), {"fee_type": fee_type})
                
                step_results.append("✅ Duplicates cleaned")
            else:
                step_results.append("✅ No duplicates found")
            
            # Step 3: Add unique constraint if missing
            if not check_constraint:
                step_results.append("🔧 Adding unique constraint...")
                conn.execute(text("""
                    ALTER TABLE fee_structures 
                    ADD CONSTRAINT fee_structures_fee_type_unique UNIQUE (fee_type)
                """))
                step_results.append("✅ Unique constraint added")
            else:
                step_results.append("✅ Unique constraint already exists")
            
            conn.commit()
            
            # Verify final state
            final_count = conn.execute(text("SELECT COUNT(*) FROM fee_structures")).scalar()
            fee_types = conn.execute(text("SELECT fee_type FROM fee_structures ORDER BY fee_type")).fetchall()
            
            return {
                "status": "success",
                "message": "Fee structures schema fixed successfully",
                "steps_completed": step_results,
                "final_state": {
                    "total_records": final_count,
                    "fee_types": [row[0] for row in fee_types]
                }
            }
            
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to fix fee_structures schema: {str(e)}",
            "error_type": type(e).__name__
        }


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
    Complete Database Reset and Initialization
    
    ⚠️ DEVELOPMENT ONLY: This will permanently delete ALL data!
    
    Performs a complete database reset including:
    1. Drop all existing tables
    2. Recreate tables with latest schema
    3. Create API request logs table (audit middleware)
    4. Clean up orphaned biometric files
    5. Initialize base users, roles, and permissions
    6. Initialize Madagascar locations
    7. Create location-based users
    8. Initialize fee structures
    
    After completion, you can use these credentials:
    - Admin: admin / Admin123
    - Test users: clerk1, supervisor1, printer1, examiner1 (see response for passwords)
    
    ⚠️ Warning: All previous data will be permanently deleted!
    """
    try:
        from app.core.database import drop_tables, create_tables, engine
        from app.models.enums import LicenseCategory
        
        logger.warning("Resetting entire database - all data will be lost")
        
        # Step 1: Drop and recreate all tables
        drop_tables()
        create_tables()
        
        # Step 1.2: Create API request logs table (audit middleware)
        logger.info("Creating API request logs table...")
        from sqlalchemy import text
        audit_table_result = None
        try:
            with engine.connect() as conn:
                # Create the api_request_logs table
                create_table_sql = """
                CREATE TABLE IF NOT EXISTS api_request_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
                    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    deleted_at TIMESTAMPTZ,
                    deleted_by UUID REFERENCES users(id) ON DELETE SET NULL,
                    
                    -- Request identification
                    request_id VARCHAR(36) NOT NULL UNIQUE,
                    
                    -- Request details
                    method VARCHAR(10) NOT NULL,
                    endpoint VARCHAR(500) NOT NULL,
                    query_params TEXT,
                    
                    -- User context
                    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
                    ip_address VARCHAR(45),
                    user_agent TEXT,
                    
                    -- Response details
                    status_code INTEGER NOT NULL,
                    response_size_bytes INTEGER,
                    
                    -- Performance metrics
                    duration_ms INTEGER NOT NULL,
                    
                    -- Location context
                    location_id UUID REFERENCES locations(id) ON DELETE SET NULL,
                    
                    -- Error tracking
                    error_message TEXT
                );
                """
                
                conn.execute(text(create_table_sql))
                
                # Create indexes for better query performance
                index_sql = [
                    "CREATE INDEX IF NOT EXISTS idx_api_request_logs_created_at ON api_request_logs(created_at DESC);",
                    "CREATE INDEX IF NOT EXISTS idx_api_request_logs_user_id ON api_request_logs(user_id);",
                    "CREATE INDEX IF NOT EXISTS idx_api_request_logs_endpoint ON api_request_logs(endpoint);",
                    "CREATE INDEX IF NOT EXISTS idx_api_request_logs_status_code ON api_request_logs(status_code);",
                    "CREATE INDEX IF NOT EXISTS idx_api_request_logs_duration ON api_request_logs(duration_ms);",
                    "CREATE INDEX IF NOT EXISTS idx_api_request_logs_method ON api_request_logs(method);"
                ]
                
                for index in index_sql:
                    conn.execute(text(index))
                    
                conn.commit()
                audit_table_result = {"status": "success", "message": "API request logs table created successfully"}
                logger.info("API request logs table and indexes created successfully")
                
        except Exception as audit_error:
            logger.error(f"Failed to create API request logs table: {audit_error}")
            audit_table_result = {"status": "error", "message": str(audit_error)}
        
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
        
        # Step 2: Initialize all data automatically (locations FIRST, then users)
        logger.info("Initializing locations...")
        locations_result = await initialize_locations()
        if not isinstance(locations_result, dict) or locations_result.get("status") != "success":
            raise Exception(f"Failed to initialize locations: {locations_result.get('message', 'Unknown error') if isinstance(locations_result, dict) else 'JSONResponse returned'}")
        
        logger.info("Initializing users, roles, and permissions...")
        users_result = await initialize_users()
        if not isinstance(users_result, dict) or users_result.get("status") != "success":
            raise Exception(f"Failed to initialize users: {users_result.get('message', 'Unknown error') if isinstance(users_result, dict) else 'JSONResponse returned'}")
        
        logger.info("Initializing location users...")
        location_users_result = await initialize_location_users()
        if not isinstance(location_users_result, dict) or location_users_result.get("status") != "success":
            raise Exception(f"Failed to initialize location users: {location_users_result.get('message', 'Unknown error') if isinstance(location_users_result, dict) else 'JSONResponse returned'}")
        
        logger.info("Initializing fee structures...")
        fee_structures_result = await initialize_fee_structures()
        if not isinstance(fee_structures_result, dict) or fee_structures_result.get("status") != "success":
            raise Exception(f"Failed to initialize fee structures: {fee_structures_result.get('message', 'Unknown error') if isinstance(fee_structures_result, dict) else 'JSONResponse returned'}")
        
        return {
            "status": "success",
            "message": "Complete database reset and initialization successful",
            "warning": "All previous data has been permanently deleted",
            "steps_completed": [
                "Tables dropped and recreated",
                "API request logs table created with indexes",
                "Biometric files cleaned up",
                "Madagascar locations initialized",
                "Base users and roles initialized (including EXAMINER role)",
                "Users assigned to default location (Antananarivo Central Office)",
                "Location-based users created",
                "Fee structures initialized"
            ],
            "summary": {
                "enum_values_created": len(enum_values),
                "api_request_logs_table": audit_table_result.get("status", "unknown") if audit_table_result else "not_attempted",
                "biometric_files_removed": files_cleaned.get("files_removed", 0),
                "biometric_folders_removed": files_cleaned.get("folders_removed", 0),
                "permissions_created": users_result.get("permissions_created", 0) if isinstance(users_result, dict) else 0,
                "roles_created": users_result.get("roles_created", 0) if isinstance(users_result, dict) else 0,
                "locations_created": locations_result.get("total_locations", 0) if isinstance(locations_result, dict) else 0,
                "location_users_created": location_users_result.get("total_users_created", 0) if isinstance(location_users_result, dict) else 0,
                "fee_structures_created": fee_structures_result.get("total_created", 0) if isinstance(fee_structures_result, dict) else 0
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


@app.get("/admin/inspect-database", tags=["Admin"])
async def inspect_database():
    """Inspect database schema - for debugging"""
    try:
        from app.core.database import engine
        from sqlalchemy import text, inspect
        
        inspector = inspect(engine)
        
        # Get all tables
        tables = inspector.get_table_names()
        
        table_info = {}
        for table_name in tables:
            columns = inspector.get_columns(table_name)
            table_info[table_name] = {
                "columns": [{"name": col["name"], "type": str(col["type"])} for col in columns],
                "column_count": len(columns)
            }
        
        # Specifically check fee_structures
        fee_structures_info = None
        if "fee_structures" in tables:
            fee_columns = inspector.get_columns("fee_structures")
            fee_structures_info = {
                "exists": True,
                "columns": [col["name"] for col in fee_columns],
                "has_fee_type": "fee_type" in [col["name"] for col in fee_columns]
            }
        else:
            fee_structures_info = {"exists": False}
        
        return {
            "status": "success",
            "total_tables": len(tables),
            "tables": list(tables),
            "fee_structures_analysis": fee_structures_info,
            "table_details": table_info
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Database inspection failed: {str(e)}",
            "error_type": type(e).__name__
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 