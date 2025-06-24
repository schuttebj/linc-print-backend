# Madagascar License System - Admin Endpoints Documentation

## Overview
The Madagascar License System includes comprehensive admin endpoints for database management, initialization, and testing. These endpoints provide a complete solution for setting up and resetting the database with Madagascar-specific data.

## Security Notice
⚠️ **WARNING**: These endpoints are for development and testing only. In production environments, these endpoints should be:
- Removed or disabled
- Protected with proper authentication
- Restricted to admin users only
- Logged and audited

## Available Admin Endpoints

### 1. Drop All Tables
**Endpoint**: `POST /admin/drop-tables`
**Description**: Drops all database tables and destroys all data.

```bash
curl -X POST http://localhost:8000/admin/drop-tables
```

**Response**:
```json
{
  "status": "success",
  "message": "All database tables dropped successfully",
  "warning": "All data has been lost",
  "timestamp": 1703123456.789
}
```

### 2. Initialize Tables
**Endpoint**: `POST /admin/init-tables`
**Description**: Creates all database tables with the latest schema.

```bash
curl -X POST http://localhost:8000/admin/init-tables
```

**Response**:
```json
{
  "status": "success",
  "message": "Database tables created successfully",
  "timestamp": 1703123456.789
}
```

### 3. Initialize Users & Roles
**Endpoint**: `POST /admin/init-users`
**Description**: Creates default users, roles, and permissions for the system.

```bash
curl -X POST http://localhost:8000/admin/init-users
```

**Features**:
- Creates comprehensive permission system
- Sets up 4 default roles (admin, clerk, supervisor, printer)
- Creates admin user and test users
- Includes Madagascar-specific permissions

**Default Credentials**:
- **Admin**: username=`admin`, password=`MadagascarAdmin2024!`
- **Clerk**: username=`clerk1`, password=`Clerk123!`
- **Supervisor**: username=`supervisor1`, password=`Supervisor123!`
- **Printer**: username=`printer1`, password=`Printer123!`

### 4. Initialize Locations (NEW)
**Endpoint**: `POST /admin/init-locations`
**Description**: Creates Madagascar office locations for all 6 provinces.

```bash
curl -X POST http://localhost:8000/admin/init-locations
```

**Features**:
- Creates locations for all 6 Madagascar provinces
- Uses proper Madagascar province codes (T, D, F, M, A, U)
- Includes main offices and mobile units
- Sets up location codes (MG-T01, MG-F01, etc.)

**Sample Locations Created**:
- **MG-T01**: Antananarivo Central Office
- **MG-T02**: Antananarivo Branch Office  
- **MG-F01**: Fianarantsoa Main Office
- **MG-A01**: Toamasina Port Office
- **MG-M01**: Mahajanga Coastal Office
- **MG-D01**: Antsiranana Northern Office
- **MG-U01**: Toliara Southern Office
- **MG-U02**: Toliara Mobile Unit

### 5. Initialize Location Users (NEW)
**Endpoint**: `POST /admin/init-location-users`
**Description**: Creates location-based users with automatic username generation.

```bash
curl -X POST http://localhost:8000/admin/init-location-users
```

**Prerequisites**: 
- Must run `/admin/init-users` first (for roles)
- Must run `/admin/init-locations` first (for locations)

**Features**:
- Creates users for each operational location
- Generates location-based usernames (T010001, F010002, etc.)
- Creates clerk, supervisor, and printer for each location
- Uses Madagascar ID formats and phone numbers

**Username Format**: `{ProvinceCode}{OfficeNumber}{UserNumber}`
- Example: `T010001` = Antananarivo (T) + Office 01 + User 0001

### 6. Complete Database Reset (NEW)
**Endpoint**: `POST /admin/reset-database`
**Description**: Performs complete database reset and initialization in one step.

```bash
curl -X POST http://localhost:8000/admin/reset-database
```

**Process**:
1. Drop all tables
2. Recreate tables
3. Initialize users and roles
4. Initialize locations
5. Create location-based users

**Response**:
```json
{
  "status": "success",
  "message": "Complete database reset successful",
  "steps_completed": [
    "Tables dropped",
    "Tables recreated",
    "Base users and roles initialized", 
    "Madagascar locations initialized",
    "Location-based users created"
  ],
  "summary": {
    "permissions_created": 35,
    "roles_created": 4,
    "locations_created": 8,
    "location_users_created": 24
  },
  "admin_credentials": {
    "username": "admin",
    "password": "MadagascarAdmin2024!",
    "email": "admin@madagascar-license.gov.mg"
  }
}
```

## Permission System

### Permission Categories
1. **User Management**: Create, read, update, delete users
2. **Role Management**: Manage user roles and permissions
3. **Person Management**: Handle person records and documents
4. **Location Management**: Manage office locations (NEW)
5. **License Applications**: Process license applications
6. **Printing**: Handle card printing operations

### Role Permissions
- **Admin**: All permissions
- **Supervisor**: All clerk permissions + approvals + location management
- **Clerk**: Person management + license processing + location viewing
- **Printer**: Printing operations only

## Location System Details

### Province Codes (Madagascar ISO Standard)
- **T**: Antananarivo (MG-T)
- **D**: Antsiranana (MG-D) 
- **F**: Fianarantsoa (MG-F)
- **M**: Mahajanga (MG-M)
- **A**: Toamasina (MG-A)
- **U**: Toliara (MG-U)

### Location Code Format
- **Full Code**: `MG-{ProvinceCode}{OfficeNumber}` (e.g., MG-T01)
- **Short Code**: `{ProvinceCode}{OfficeNumber}` (e.g., T01)

### User Code Format
- **Username**: `{ProvinceCode}{OfficeNumber}{UserNumber}` (e.g., T010001)
- **Capacity**: 9999 users per location
- **No Reuse**: User numbers are never reused for audit purposes

## Testing

### Test Script
Use the provided test script to validate all endpoints:

```bash
python test_admin_endpoints.py
```

### Manual Testing
Test individual endpoints using curl or Postman:

```bash
# Complete reset (recommended for fresh start)
curl -X POST http://localhost:8000/admin/reset-database

# Or step by step:
curl -X POST http://localhost:8000/admin/drop-tables
curl -X POST http://localhost:8000/admin/init-tables
curl -X POST http://localhost:8000/admin/init-users
curl -X POST http://localhost:8000/admin/init-locations
curl -X POST http://localhost:8000/admin/init-location-users
```

## Error Handling
All endpoints include comprehensive error handling:
- Database connection errors
- Validation errors
- Dependency errors (missing roles/locations)
- Duplicate data handling

## Development Workflow

### Fresh Development Setup
```bash
# 1. Start the server
python -m uvicorn app.main:app --reload

# 2. Reset everything
curl -X POST http://localhost:8000/admin/reset-database

# 3. Verify with health check
curl http://localhost:8000/health
```

### Incremental Updates
```bash
# Add new locations only
curl -X POST http://localhost:8000/admin/init-locations

# Add location users only  
curl -X POST http://localhost:8000/admin/init-location-users
```

## Production Considerations

### Security
- Remove or secure admin endpoints in production
- Implement proper authentication and authorization
- Add rate limiting and request validation
- Enable audit logging for all admin actions

### Data Management
- Use proper database migrations instead of drop/create
- Implement backup and restore procedures
- Add data validation and integrity checks
- Consider read-only replicas for reporting

### Monitoring
- Add health checks for all dependencies
- Implement comprehensive logging
- Set up alerts for admin endpoint usage
- Monitor database performance and capacity

## API Documentation
Access the interactive API documentation at:
- **Swagger UI**: http://localhost:8000/api/v1/docs
- **ReDoc**: http://localhost:8000/api/v1/redoc

## Support
For issues or questions about the admin endpoints:
1. Check the server logs for detailed error messages
2. Verify all prerequisites are met (roles, locations)
3. Test with the provided test script
4. Review the permission system configuration 