"""
Database models for Madagascar License System
"""

from app.models.base import BaseModel
from app.models.user import User, Role, Permission, UserAuditLog, Location, UserStatus, MadagascarIDType, ProvinceUserCounter, NationalUserCounter
from app.models.person import Person, PersonAlias, PersonAddress
from app.models.enums import UserType, RoleHierarchy 