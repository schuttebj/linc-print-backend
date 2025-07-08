"""
CRUD operations for Madagascar License System
Imports all CRUD classes for easy access
"""

from app.crud.base import CRUDBase
from app.crud.crud_person import CRUDPerson, CRUDPersonAlias, CRUDPersonAddress
from app.crud.crud_user import CRUDUser
from app.crud.crud_location import CRUDLocation
from app.crud.crud_license import CRUDLicense, CRUDLicenseCard

# Import CRUD instances
from app.crud.crud_person import person, person_alias, person_address
from app.crud.crud_user import user
from app.crud.crud_location import location
from app.crud.crud_license import crud_license, crud_license_card

# TODO: Import other CRUD modules when implemented
# from app.crud.crud_audit import audit_log 