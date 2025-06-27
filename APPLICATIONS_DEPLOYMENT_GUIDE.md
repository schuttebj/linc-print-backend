# Applications Module Deployment Guide

## 🚀 Quick Deployment Steps

### 1. Database Migration
```bash
# Generate migration for the new applications tables
alembic revision --autogenerate -m "Add applications module with complete workflow support"

# Apply the migration
alembic upgrade head
```

### 2. Test API Endpoints
```bash
# Authenticate first
curl -X POST "https://your-backend-url/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "clerk1",
    "password": "Clerk123!"
  }'

# Use the returned access_token for subsequent requests
export TOKEN="your_access_token_here"

# Test applications endpoint
curl -X GET "https://your-backend-url/api/v1/applications/" \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Initialize Fee Structure (Optional)
```bash
# Create basic fee structures
curl -X POST "https://your-backend-url/api/v1/admin/init-fee-structures" \
  -H "Authorization: Bearer $TOKEN"
```

## 📊 Database Tables Created

The migration will create these new tables:

1. **applications** - Main application records
2. **application_biometric_data** - Photo, signature, fingerprint data
3. **application_test_attempts** - Theory and practical test records
4. **application_fees** - Fee tracking and payment records
5. **application_status_history** - Complete audit trail
6. **application_documents** - Document attachments
7. **fee_structures** - Configurable fee management

## 🔧 Integration Testing

### Test Person Integration
```python
# Create a test application
application_data = {
    "application_type": "NEW_LICENSE",
    "person_id": "existing-person-uuid",
    "license_categories": ["B"],
    "location_id": "location-uuid",
    "is_urgent": False
}

response = requests.post(
    "https://your-backend-url/api/v1/applications/",
    json=application_data,
    headers={"Authorization": f"Bearer {token}"}
)
```

### Test Associated Applications
```python
# Create temporary license linked to main application
temp_license_data = {
    "application_type": "TEMPORARY_LICENSE",
    "person_id": "same-person-uuid",
    "license_categories": ["B"],
    "location_id": "location-uuid",
    "parent_application_id": "main-application-uuid",
    "is_temporary_license": True,
    "temporary_license_reason": "Emergency travel",
    "priority": 3  # Emergency priority
}
```

### Test Status Workflow
```python
# Update application status
status_update = {
    "new_status": "SUBMITTED",
    "reason": "Application review complete",
    "notes": "All documents verified"
}

response = requests.post(
    f"https://your-backend-url/api/v1/applications/{app_id}/status",
    json=status_update,
    headers={"Authorization": f"Bearer {token}"}
)
```

## 🔐 Permission Verification

### Test Permission Enforcement
```bash
# Test as different user types
# 1. Location user - should only see own location's applications
# 2. Provincial admin - should see provincial applications  
# 3. National admin - should see all applications

# Test CRUD permissions
curl -X POST "https://your-backend-url/api/v1/applications/" \
  -H "Authorization: Bearer $CLERK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"application_type": "NEW_LICENSE", ...}'

curl -X DELETE "https://your-backend-url/api/v1/applications/uuid" \
  -H "Authorization: Bearer $CLERK_TOKEN"
# Should fail - clerks can't delete
```

## 📋 Checklist

### Backend Verification
- [ ] Database migration applied successfully
- [ ] All API endpoints return 200/201 for valid requests
- [ ] Permission system working correctly
- [ ] Person integration working
- [ ] Associated applications linking correctly
- [ ] Fee calculation accurate
- [ ] Status workflow validation working

### Frontend Ready Items
- [ ] PersonFormWrapper integration tested
- [ ] API client methods work with new endpoints
- [ ] Enums properly imported and used
- [ ] Error handling for validation failures

### Business Rules Verification
- [ ] Age validation: A′(16+), A/B(18+), C/D/E(21+)
- [ ] Medical certificate required for C/D/E and 60+
- [ ] Parental consent required for A′ applicants 16-17
- [ ] Existing license validation for C/D/E categories
- [ ] Fee calculation: 10k/15k for tests, 38k for cards
- [ ] Draft expiry after 30 days

## 🐛 Troubleshooting

### Common Issues

#### Migration Errors
```bash
# If migration fails, check for:
# 1. Enum conflicts
alembic downgrade -1
alembic upgrade head

# 2. Foreign key issues  
# Check that persons and locations tables exist
```

#### Permission Errors
```python
# Verify user has correct permissions
user = crud_user.get_by_username(db, username="clerk1")
print(user.has_permission("applications.create"))
print(user.roles)
```

#### Import Errors
```python
# Common import fixes
from app.models.application import Application, ApplicationStatus
from app.models.enums import LicenseCategory, ApplicationType
```

## 🎯 Next Steps After Deployment

1. **Frontend Development**: Start with ApplicationFormWrapper.tsx
2. **Testing**: Create test applications with various scenarios
3. **Fee Management**: Configure production fee structures
4. **Hardware Integration**: Plan biometric capture implementation
5. **Printing Integration**: Connect A4 confirmation printing
6. **User Training**: Prepare documentation for clerks and supervisors

## 📞 Support

If you encounter issues during deployment:

1. Check the APPLICATIONS_MODULE_SUMMARY.md for architecture details
2. Verify all imports are correct in models/__init__.py
3. Ensure API router includes applications endpoints
4. Test permissions with different user roles
5. Validate business rules with sample data

The applications module is designed to be non-disruptive to existing functionality while providing complete license application workflow management. 