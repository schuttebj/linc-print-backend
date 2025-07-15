"""
Database models for Madagascar License System
"""

from app.models.base import BaseModel
from app.models.user import User, Role, Permission, UserAuditLog, UserPermissionOverride, Location, UserStatus, MadagascarIDType, ProvinceUserCounter, NationalUserCounter
from app.models.person import Person, PersonAlias, PersonAddress
from app.models.application import (
    Application, ApplicationBiometricData, ApplicationTestAttempt, 
    ApplicationFee, ApplicationStatusHistory, ApplicationDocument, FeeStructure
)
from app.models.license import (
    License, LicenseStatusHistory, LicenseSequenceCounter
)
from app.models.card import (
    Card, CardLicense, CardStatusHistory, CardProductionBatch, CardSequenceCounter
)
from app.models.enums import (
    UserType, RoleHierarchy, LicenseCategory, ApplicationType, ApplicationStatus, PaymentStatus
) 