# Person Module Permissions Update

## Overview

The Person module has been fully integrated with the Madagascar License System's permission framework. All endpoints now require appropriate permissions, maintaining the clean and simple permission structure you appreciated.

## New Permissions Added

### Person Management Permissions (Category: `persons`)

| Permission | Display Name | Description | Resource | Action |
|------------|--------------|-------------|----------|--------|
| `persons.create` | Create Persons | Create new person records | person | create |
| `persons.read` | View Persons | View person information | person | read |
| `persons.update` | Update Persons | Update person information | person | update |
| `persons.delete` | Delete Persons | Delete person records | person | delete |
| `persons.search` | Search Persons | Search and filter person records | person | search |
| `persons.check_duplicates` | Check Person Duplicates | Check for potential duplicate persons | person | check_duplicates |

### Person Alias (Document) Permissions (Category: `persons`)

| Permission | Display Name | Description | Resource | Action |
|------------|--------------|-------------|----------|--------|
| `person_aliases.create` | Create Person Documents | Add identification documents to persons | person_alias | create |
| `person_aliases.read` | View Person Documents | View person identification documents | person_alias | read |
| `person_aliases.update` | Update Person Documents | Update person identification documents | person_alias | update |
| `person_aliases.delete` | Delete Person Documents | Delete person identification documents | person_alias | delete |
| `person_aliases.set_primary` | Set Primary Document | Set primary identification document | person_alias | set_primary |

### Person Address Permissions (Category: `persons`)

| Permission | Display Name | Description | Resource | Action |
|------------|--------------|-------------|----------|--------|
| `person_addresses.create` | Create Person Addresses | Add addresses to persons | person_address | create |
| `person_addresses.read` | View Person Addresses | View person addresses | person_address | read |
| `person_addresses.update` | Update Person Addresses | Update person addresses | person_address | update |
| `person_addresses.delete` | Delete Person Addresses | Delete person addresses | person_address | delete |
| `person_addresses.set_primary` | Set Primary Address | Set primary address per type | person_address | set_primary |

## Role Assignments

### Clerk Role
**Essential person management for license applications:**
- ✅ `persons.create` - Create new person records
- ✅ `persons.read` - View person information
- ✅ `persons.update` - Update person information
- ✅ `persons.search` - Search and filter persons
- ✅ `persons.check_duplicates` - Check for duplicates
- ✅ `person_aliases.create` - Add ID documents
- ✅ `person_aliases.read` - View ID documents
- ✅ `person_aliases.update` - Update ID documents
- ✅ `person_aliases.set_primary` - Set primary document
- ✅ `person_addresses.create` - Add addresses
- ✅ `person_addresses.read` - View addresses
- ✅ `person_addresses.update` - Update addresses
- ✅ `person_addresses.set_primary` - Set primary address

### Supervisor Role
**All clerk permissions PLUS deletion capabilities:**
- ✅ All Clerk permissions
- ✅ `persons.delete` - Delete person records
- ✅ `person_aliases.delete` - Delete ID documents
- ✅ `person_addresses.delete` - Delete addresses

### Printer Role
**No person management permissions** - Focused only on printing operations

## API Endpoint Security

All Person module endpoints now enforce permissions:

### Person CRUD
- `POST /api/v1/persons/` → Requires `persons.create`
- `GET /api/v1/persons/search` → Requires `persons.search`
- `GET /api/v1/persons/{person_id}` → Requires `persons.read`
- `PUT /api/v1/persons/{person_id}` → Requires `persons.update`
- `DELETE /api/v1/persons/{person_id}` → Requires `persons.delete` (Supervisor+)

### Duplicate Detection
- `GET /api/v1/persons/{person_id}/duplicates` → Requires `persons.check_duplicates`

### Document Management
- `POST /api/v1/persons/{person_id}/aliases` → Requires `person_aliases.create`
- `GET /api/v1/persons/{person_id}/aliases` → Requires `person_aliases.read`
- `PUT /api/v1/persons/{person_id}/aliases/{alias_id}` → Requires `person_aliases.update`
- `PUT /api/v1/persons/{person_id}/aliases/{alias_id}/set-primary` → Requires `person_aliases.set_primary`
- `DELETE /api/v1/persons/{person_id}/aliases/{alias_id}` → Requires `person_aliases.delete` (Supervisor+)

### Address Management
- `POST /api/v1/persons/{person_id}/addresses` → Requires `person_addresses.create`
- `GET /api/v1/persons/{person_id}/addresses` → Requires `person_addresses.read`
- `PUT /api/v1/persons/{person_id}/addresses/{address_id}` → Requires `person_addresses.update`
- `PUT /api/v1/persons/{person_id}/addresses/{address_id}/set-primary` → Requires `person_addresses.set_primary`
- `DELETE /api/v1/persons/{person_id}/addresses/{address_id}` → Requires `person_addresses.delete` (Supervisor+)

## Permission Hierarchy

```
Admin (Superuser)
├── All permissions automatically granted
│
Supervisor
├── All Clerk permissions
├── Plus deletion capabilities
│   ├── persons.delete
│   ├── person_aliases.delete
│   └── person_addresses.delete
│
Clerk
├── Core person management
│   ├── persons.create, read, update, search, check_duplicates
│   ├── person_aliases.create, read, update, set_primary
│   └── person_addresses.create, read, update, set_primary
│
Printer
└── No person management permissions
```

## Benefits of This Structure

1. **Granular Control**: Each operation has its own permission
2. **Role-Based**: Permissions align with job responsibilities
3. **Secure by Default**: All endpoints require explicit permissions
4. **Audit-Ready**: Permission checks are logged
5. **Scalable**: Easy to add new permissions for future features

## Future Enhancements (TODOs)

When new person-related features are added, follow this pattern:

```python
# Add to init_madagascar_system.py permissions_data
("persons.new_feature", "New Feature", "Description", "persons", "person", "new_feature")

# Add to appropriate role permissions
clerk_permissions = [..., "persons.new_feature"]

# Use in endpoint
@router.post("/new-feature")
def new_feature(
    current_user: User = Depends(require_permission("persons.new_feature"))
):
    pass
```

## Testing Permissions

You can test permissions using the existing endpoints:

```bash
# Check if user has permission
GET /api/v1/permissions/check/persons.create

# View user's effective permissions
GET /api/v1/permissions/user/{user_id}/effective

# View permissions by category
GET /api/v1/permissions/by-category
```

## Deployment Notes

1. **Database Update**: Run `python init_madagascar_system.py` to create new permissions
2. **Existing Users**: Will automatically inherit permissions based on their roles
3. **API Compatibility**: All endpoints now require authentication + appropriate permissions
4. **Error Handling**: Users without permissions receive `403 Forbidden` with clear error messages

The permission system maintains the clean, simple structure while providing comprehensive security for the Person module! 