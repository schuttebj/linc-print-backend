# Madagascar Driver's License Backend System

## Overview
Complete backend system for Madagascar's Driver's License management with person management, authentication, and role-based access control.

## Current Status ✅

- **Authentication System**: JWT-based with role-based access control
- **User Management**: Admin, Clerk, Supervisor, and Printer roles
- **Person Module**: Complete implementation with Madagascar-specific features
- **Permission System**: Granular access control with 43+ permissions
- **Database**: PostgreSQL with comprehensive audit trails
- **API Documentation**: Auto-generated OpenAPI/Swagger docs
- **Deployment**: Production-ready on Render.com

## Quick Start

### 1. System Initialization

Use admin endpoints to set up the complete system:

```bash
# Step 1: Create database tables
curl -X POST "https://linc-print-backend.onrender.com/admin/init-tables"

# Step 2: Initialize users, roles, and permissions (includes Person module)
curl -X POST "https://linc-print-backend.onrender.com/admin/init-users"
```

### 2. Authentication

```bash
# Login as clerk
curl -X POST "https://linc-print-backend.onrender.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "clerk1", "password": "Clerk123!"}'

# Use the returned access_token for subsequent requests
export TOKEN="your_access_token_here"
```

### 3. Test Person Management

```bash
# Create a person
curl -X POST "https://linc-print-backend.onrender.com/api/v1/persons/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "surname": "Rakoto",
    "first_name": "Jean",
    "person_nature": "01",
    "birth_date": "1990-05-15",
    "cell_phone": "+261341234567"
  }'
```

## System Architecture

### Core Modules

1. **Authentication & Authorization**
   - JWT token-based authentication
   - Role-based access control (RBAC)
   - Permission-based endpoint security

2. **User Management**
   - User CRUD operations
   - Role assignment and management
   - Permission system integration

3. **Person Management** 
   - Madagascar-specific person records
   - ID document management (Madagascar ID, Passport)
   - Address management with Madagascar postal codes
   - Duplicate detection with similarity scoring

### Database Schema

- **Users & Roles**: Authentication and authorization
- **Persons**: Natural person records with Madagascar specifics
- **Person Aliases**: ID documents with primary selection
- **Person Addresses**: Madagascar address format with postal codes
- **Audit Tables**: Comprehensive change tracking

## User Roles & Permissions

### Admin (admin/MadagascarAdmin2024!)
- Complete system access
- User and role management
- All person management operations

### Clerk (clerk1/Clerk123!)
- Person management (create, read, update, search)
- Document and address management
- Duplicate detection
- Essential for license application processing

### Supervisor (supervisor1/Supervisor123!)
- All clerk permissions
- Additional deletion capabilities
- User management permissions

### Printer (printer1/Printer123!)
- Printing operations only
- No person management access

## API Endpoints

### Authentication
- `POST /api/v1/auth/login` - User login
- `GET /api/v1/auth/me` - Current user info
- `POST /api/v1/auth/refresh` - Refresh token

### Person Management
- `POST /api/v1/persons/` - Create person
- `GET /api/v1/persons/{id}` - Get person details
- `PUT /api/v1/persons/{id}` - Update person
- `DELETE /api/v1/persons/{id}` - Delete person
- `GET /api/v1/persons/search` - Search persons
- `POST /api/v1/persons/check-duplicates` - Check duplicates

### Document Management
- `POST /api/v1/persons/{id}/aliases` - Add document
- `GET /api/v1/persons/{id}/aliases` - List documents
- `PUT /api/v1/persons/{id}/aliases/{alias_id}` - Update document
- `DELETE /api/v1/persons/{id}/aliases/{alias_id}` - Delete document
- `POST /api/v1/persons/{id}/aliases/{alias_id}/set-primary` - Set primary

### Address Management
- `POST /api/v1/persons/{id}/addresses` - Add address
- `GET /api/v1/persons/{id}/addresses` - List addresses
- `PUT /api/v1/persons/{id}/addresses/{addr_id}` - Update address
- `DELETE /api/v1/persons/{id}/addresses/{addr_id}` - Delete address
- `POST /api/v1/persons/{id}/addresses/{addr_id}/set-primary` - Set primary

### Admin Endpoints
- `POST /admin/init-tables` - Initialize database tables
- `POST /admin/init-users` - Initialize users, roles, permissions
- `POST /admin/drop-tables` - Drop all tables (development only)

## Madagascar-Specific Features

### ID Documents
- **Madagascar ID (MG_ID)**: National identity card (CIN/CNI)
- **Passport**: International travel document with expiry tracking

### Address Format
```json
{
  "street_line1": "Lot 67 Parcelle 1139",
  "street_line2": "Quartier Ambohipo",
  "locality": "Antananarivo", 
  "postal_code": "101",
  "town": "Antananarivo",
  "country": "MADAGASCAR"
}
```

### Phone Numbers
- Format: `0AA BB BB BBB` (local) or `+261 AA BB BB BBB` (international)
- Default country code: +261

### Duplicate Detection
Weighted similarity scoring:
- Birth date match: 30%
- Surname similarity: 25% (fuzzy)
- First name similarity: 20% (fuzzy)
- Phone number match: 15%
- Address similarity: 10%

## API Documentation

Access interactive documentation:
- **Swagger UI**: https://linc-print-backend.onrender.com/api/v1/docs
- **ReDoc**: https://linc-print-backend.onrender.com/api/v1/redoc

## Environment Configuration

Key environment variables:
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: JWT signing key
- `CORS_ORIGINS`: Allowed CORS origins
- `DEBUG`: Debug mode (development only)

## Development

### Local Setup
```bash
# Clone repository
git clone <repository-url>
cd linc-print-backend

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp env.example .env
# Edit .env with your configuration

# Run development server
python -m uvicorn app.main:app --reload
```

### Testing
```bash
# Test authentication
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "MadagascarAdmin2024!"}'

# Test person creation
curl -X POST "http://localhost:8000/api/v1/persons/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"surname": "Test", "first_name": "User", "person_nature": "01", "birth_date": "1990-01-01"}'
```

## Deployment

### Render.com Configuration
- **Python Version**: 3.11.0
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Environment Variables (Production)
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: Strong JWT signing key
- `CORS_ORIGINS`: Production frontend URLs
- `DEBUG`: False

## Future Modules

The system is designed for easy expansion:

1. **License Applications**: Process driver's license applications
2. **Printing System**: Distributed card printing management
3. **Document Management**: Scan and store supporting documents
4. **Reporting**: Compliance and operational reports
5. **Integration**: Connect with existing government systems

## Security Features

- JWT-based authentication with configurable expiration
- Role-based access control with granular permissions
- SQL injection protection via SQLAlchemy ORM
- CORS configuration for secure cross-origin requests
- Comprehensive audit trails for all operations
- Soft delete for data integrity

## Support

For technical support or questions:
1. Check API documentation at `/api/v1/docs`
2. Review server logs for error details
3. Verify user permissions with `/api/v1/auth/me`
4. Test with different user roles to isolate permission issues

## License

This project is developed for the Government of Madagascar's Driver's License modernization initiative.
