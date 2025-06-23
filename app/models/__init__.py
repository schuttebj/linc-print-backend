"""
Database models for Madagascar License System
"""

from app.models.base import BaseModel
from app.models.user import User, Role, Permission, UserRole, RolePermission
from app.models.person import Person, PersonAlias, PersonAddress 