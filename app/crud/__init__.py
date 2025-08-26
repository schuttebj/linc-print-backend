"""
CRUD operations for Madagascar License System
Imports all CRUD classes for easy access
"""

from app.crud.base import CRUDBase
from app.crud.crud_person import CRUDPerson, CRUDPersonAlias, CRUDPersonAddress
from app.crud.crud_user import CRUDUser
from app.crud.crud_location import CRUDLocation
from app.crud.crud_license import CRUDLicense
from app.crud.crud_card import CRUDCard, CRUDCardProductionBatch
from app.crud.crud_transaction import CRUDTransaction, CRUDCardOrder, CRUDFeeStructure, TransactionCalculator
from app.crud.crud_issue import CRUDIssue, CRUDIssueComment, CRUDIssueAttachment

# Import CRUD instances
from app.crud.crud_person import person, person_alias, person_address
from app.crud.crud_user import user
from app.crud.crud_location import location
from app.crud.crud_license import crud_license
from app.crud.crud_card import crud_card, crud_card_production_batch
from app.crud.crud_transaction import crud_transaction, crud_card_order, crud_fee_structure, transaction_calculator
from app.crud.crud_issue import issue, issue_comment, issue_attachment

# TODO: Import other CRUD modules when implemented
# from app.crud.crud_audit import audit_log 