"""
Base Database Model for Madagascar License System
Compatible with SQLAlchemy 1.4 for Render.com deployment
"""

from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr, declarative_base
from datetime import datetime, timezone
import uuid

# Create base for SQLAlchemy 1.4
Base = declarative_base()


class BaseModel(Base):
    """Base model with common fields and functionality for Madagascar License System"""
    __abstract__ = True
    
    @declared_attr
    def __tablename__(cls):
        """Generate table name from class name"""
        import re
        name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', cls.__name__)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()
    
    # Primary key - using UUID for all records
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    
    # Audit fields - who and when
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, comment="Record creation timestamp")
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, comment="Last update timestamp")
    created_by = Column(UUID(as_uuid=True), nullable=True, comment="User ID who created the record")
    updated_by = Column(UUID(as_uuid=True), nullable=True, comment="User ID who last updated the record")
    
    # Soft delete support for data retention compliance
    is_active = Column(Boolean, default=True, nullable=False, comment="Active status - false for soft deleted")
    deleted_at = Column(DateTime(timezone=True), nullable=True, comment="Soft deletion timestamp")
    deleted_by = Column(UUID(as_uuid=True), nullable=True, comment="User ID who soft deleted the record")
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"
    
    def to_dict(self):
        """Convert model to dictionary for JSON serialization"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, uuid.UUID):
                value = str(value)
            result[column.name] = value
        return result
    
    def soft_delete(self, deleted_by_user_id: uuid.UUID = None):
        """
        Soft delete the record - maintains data for audit trail
        Used for compliance with Madagascar data retention requirements
        """
        self.is_active = False
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = deleted_by_user_id
    
    def restore(self):
        """Restore a soft-deleted record"""
        self.is_active = True
        self.deleted_at = None
        self.deleted_by = None
    
    @classmethod
    def get_active_query(cls, session):
        """Get query for only active (non-soft-deleted) records"""
        return session.query(cls).filter(cls.is_active == True) 