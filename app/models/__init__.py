"""
Database models for Madagascar License System
"""

from app.models.base import BaseModel
from app.models.user import User, Role, Permission, UserAuditLog, UserPermissionOverride, Location, UserStatus, MadagascarIDType, ProvinceUserCounter, NationalUserCounter
from app.models.person import Person, PersonAlias, PersonAddress
from app.models.application import (
    Application, ApplicationBiometricData, ApplicationTestAttempt, 
    ApplicationStatusHistory, ApplicationDocument, ApplicationAuthorization
)
from app.models.transaction import (
    Transaction, TransactionItem, CardOrder, FeeStructure
)
from app.models.license import (
    License, LicenseStatusHistory
)
from app.models.card import (
    Card, CardLicense, CardStatusHistory, CardProductionBatch, CardSequenceCounter
)
from app.models.printing import (
    PrintJob, PrintJobApplication, PrintJobStatusHistory, PrintQueue,
    PrintJobStatus, PrintJobPriority, QualityCheckResult
)
from app.models.enums import (
    UserType, RoleHierarchy, LicenseCategory, ApplicationType, ApplicationStatus, PaymentStatus
) 