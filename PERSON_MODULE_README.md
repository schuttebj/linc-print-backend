# Person Module Implementation Guide

## Overview
Complete implementation of the Person module for Madagascar Driver's License system, supporting natural persons only with Madagascar-specific requirements.

## Quick Start

### 1. Database Setup
Use the admin endpoints to initialize the system:

```bash
# Step 1: Drop existing tables (if needed)
curl -X POST "https://linc-print-backend.onrender.com/admin/drop-tables"

# Step 2: Create fresh database tables
curl -X POST "https://linc-print-backend.onrender.com/admin/init-tables"

# Step 3: Initialize users, roles, and permissions (includes Person module)
curl -X POST "https://linc-print-backend.onrender.com/admin/init-users"
```

### 2. Authentication
Login to get access token:

```bash
curl -X POST "https://linc-print-backend.onrender.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "clerk1",
    "password": "Clerk123!"
  }'
```

Use the returned `access_token` in subsequent requests:
```bash
export TOKEN="your_access_token_here"
```

## Madagascar-Specific Features

### ID Document Types
- **Madagascar ID (MG_ID)**: National identity card (CIN/CNI)
- **Passport**: International travel document with country of origin

### Address Format
Madagascar postal address structure:
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
- Types: Work phone and Cell phone only
- Default country code: +261

## API Usage Examples

### Create a Person
```bash
curl -X POST "https://linc-print-backend.onrender.com/api/v1/persons/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "surname": "Rakoto",
    "first_name": "Jean",
    "middle_name": "Paul",
    "person_nature": "01",
    "birth_date": "1990-05-15",
    "nationality_code": "MG",
    "preferred_language": "mg",
    "email": "jean.rakoto@email.mg",
    "work_phone": "+261 20 22 123 45",
    "cell_phone": "+261 34 12 345 67"
  }'
```

### Add Madagascar ID Document
```bash
curl -X POST "https://linc-print-backend.onrender.com/api/v1/persons/1/aliases" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "document_type": "MG_ID",
    "document_number": "CIN123456789",
    "is_primary": true
  }'
```

### Add Address
```bash
curl -X POST "https://linc-print-backend.onrender.com/api/v1/persons/1/addresses" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "address_type": "residential",
    "street_line1": "Lot 67 Parcelle 1139",
    "locality": "Antananarivo",
    "postal_code": "101",
    "town": "Antananarivo",
    "is_primary": true
  }'
```

### Search Persons
```bash
curl -X GET "https://linc-print-backend.onrender.com/api/v1/persons/search?surname=Rakoto&first_name=Jean" \
  -H "Authorization: Bearer $TOKEN"
```

### Check for Duplicates
```bash
curl -X POST "https://linc-print-backend.onrender.com/api/v1/persons/check-duplicates" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "surname": "Rakoto",
    "first_name": "Jean",
    "birth_date": "1990-05-15",
    "cell_phone": "+261341234567"
  }'
```

## Complete API Endpoints

### Person Management
- `POST /api/v1/persons/` - Create person
- `GET /api/v1/persons/{person_id}` - Get person details
- `PUT /api/v1/persons/{person_id}` - Update person
- `DELETE /api/v1/persons/{person_id}` - Delete person (soft delete)
- `GET /api/v1/persons/search` - Search persons
- `POST /api/v1/persons/check-duplicates` - Check duplicates

### Document Management
- `POST /api/v1/persons/{person_id}/aliases` - Add document
- `GET /api/v1/persons/{person_id}/aliases` - List documents
- `PUT /api/v1/persons/{person_id}/aliases/{alias_id}` - Update document
- `DELETE /api/v1/persons/{person_id}/aliases/{alias_id}` - Delete document
- `POST /api/v1/persons/{person_id}/aliases/{alias_id}/set-primary` - Set primary

### Address Management
- `POST /api/v1/persons/{person_id}/addresses` - Add address
- `GET /api/v1/persons/{person_id}/addresses` - List addresses
- `PUT /api/v1/persons/{person_id}/addresses/{address_id}` - Update address
- `DELETE /api/v1/persons/{person_id}/addresses/{address_id}` - Delete address
- `POST /api/v1/persons/{person_id}/addresses/{address_id}/set-primary` - Set primary

## Permission System

### User Roles & Permissions

**Clerk** (clerk1/Clerk123!):
- Full person management (create, read, update, search, check duplicates)
- Document and address management (create, read, update, set primary)
- Essential for license application processing

**Supervisor** (supervisor1/Supervisor123!):
- All clerk permissions
- Additional deletion capabilities (persons, documents, addresses)
- User management permissions

**Printer** (printer1/Printer123!):
- No person permissions (focused on printing operations)

## Duplicate Detection

The system uses weighted similarity scoring:
- Birth date match: 30% weight
- Surname similarity: 25% weight (fuzzy matching)
- First name similarity: 20% weight (fuzzy matching)
- Phone number match: 15% weight (exact match)
- Address similarity: 10% weight (locality match)

Default threshold: 70% similarity triggers duplicate flag.

## Database Schema

### Person Table
- Core person information with Madagascar defaults
- Audit trail (created_by, updated_by, created_at, updated_at)
- Soft delete support (deleted_at)

### PersonAlias Table
- ID documents (Madagascar ID, Passport)
- Primary document selection per person
- Document validation and expiry tracking

### PersonAddress Table
- Madagascar address format with 3-digit postal codes
- Multiple addresses per person with type classification
- Primary address selection per address type

## Testing

Access the interactive API documentation:
- **Swagger UI**: https://linc-print-backend.onrender.com/api/v1/docs
- **ReDoc**: https://linc-print-backend.onrender.com/api/v1/redoc

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure you're using the correct user role and have obtained a valid access token
2. **Validation Errors**: Check Madagascar-specific format requirements (postal codes, phone numbers)
3. **Duplicate Detection**: Review similarity scoring if duplicates aren't being detected properly

### Debug Steps
1. Check user permissions: `GET /api/v1/auth/me`
2. Verify token validity: Token expires after configured time
3. Check API documentation for exact request format
4. Review server logs for detailed error messages

## System Integration

The Person module is designed to integrate with:
- **License Applications**: Person records serve as applicant information
- **Audit System**: All operations are tracked with user attribution
- **Permission System**: Granular access control for different user roles
- **Future Modules**: Extensible design for additional functionality

## Production Considerations

- All endpoints require authentication and proper permissions
- Soft delete preserves data integrity while allowing "removal"
- Comprehensive audit trail for compliance requirements
- Optimized duplicate detection for large datasets
- Madagascar-specific validation ensures data quality 