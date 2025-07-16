"""
License Management Models for Madagascar License System
Implements issued licenses with independent card tracking

Features:
- License number generation: {LocationCode}{8SequentialDigits}{CheckDigit}
- License statuses: ACTIVE, SUSPENDED, CANCELLED
- Independent card tracking with many-to-many relationship
- Restriction management per license
- History tracking for upgrades and changes
- ISO 18013 and SADC compliance fields
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Numeric, JSON, Enum as SQLEnum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum

from app.models.base import BaseModel
from app.models.enums import LicenseCategory


class LicenseStatus(str, Enum):
    """License status enumeration"""
    ACTIVE = "ACTIVE"           # Currently valid license
    SUSPENDED = "SUSPENDED"     # Temporarily suspended
    CANCELLED = "CANCELLED"     # Permanently cancelled/revoked


class License(BaseModel):
    """
    Madagascar Driver's License entity
    
    Represents an issued license that is valid for life unless suspended/cancelled.
    Cards are separate entities that can contain multiple licenses.
    """
    __tablename__ = "licenses"

    # Core license information (ID is the UUID primary key)
    
    # Person and application links
    person_id = Column(UUID(as_uuid=True), ForeignKey('persons.id'), nullable=False, index=True, comment="License holder")
    created_from_application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, comment="Application that created this license")
    
    # License details
    category = Column(SQLEnum(LicenseCategory, native_enum=False), nullable=False, comment="Single license category for this license")
    status = Column(SQLEnum(LicenseStatus), nullable=False, default=LicenseStatus.ACTIVE, index=True, comment="Current license status")
    
    # Issue information
    issue_date = Column(DateTime, nullable=False, default=func.now(), comment="Date license was issued")
    expiry_date = Column(DateTime, nullable=True, comment="Date license expires (only for learner's permits - 6 months from issue)")
    issuing_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=False, comment="Location that issued the license")
    issued_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who issued the license")
    
    # Restrictions and conditions
    restrictions = Column(JSON, nullable=True, comment="License restrictions (corrective lenses, etc.)")
    medical_restrictions = Column(JSON, nullable=True, comment="Medical restrictions from assessment")
    
    # Professional driving permit information (if applicable)
    has_professional_permit = Column(Boolean, nullable=False, default=False, comment="Has associated professional driving permit")
    professional_permit_categories = Column(JSON, nullable=True, comment="Professional permit categories (P, D, G)")
    professional_permit_expiry = Column(DateTime, nullable=True, comment="Professional permit expiry date")
    
    # Status management
    status_changed_date = Column(DateTime, nullable=True, comment="Date status was last changed")
    status_changed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who changed status")
    suspension_reason = Column(Text, nullable=True, comment="Reason for suspension (if applicable)")
    suspension_start_date = Column(DateTime, nullable=True, comment="Suspension start date")
    suspension_end_date = Column(DateTime, nullable=True, comment="Suspension end date (if temporary)")
    cancellation_reason = Column(Text, nullable=True, comment="Reason for cancellation")
    cancellation_date = Column(DateTime, nullable=True, comment="Date license was cancelled")
    
    # ISO 18013 compliance fields
    iso_compliance_data = Column(JSON, nullable=True, comment="ISO 18013-1:2018 compliance data")
    barcode_data = Column(Text, nullable=True, comment="PDF417 barcode data for card")
    security_features = Column(JSON, nullable=True, comment="Security features for card production")
    
    # SADC compliance
    sadc_compliance_verified = Column(Boolean, nullable=False, default=False, comment="SADC standards compliance verified")
    international_validity = Column(Boolean, nullable=False, default=True, comment="Valid for international use")
    vienna_convention_compliant = Column(Boolean, nullable=False, default=True, comment="Vienna Convention compliance")
    
    # Biometric links
    photo_file_path = Column(String(500), nullable=True, comment="Path to license photo file")
    signature_file_path = Column(String(500), nullable=True, comment="Path to signature file")
    biometric_template_id = Column(String(100), nullable=True, comment="Biometric template identifier")
    
    # License history tracking
    previous_license_id = Column(UUID(as_uuid=True), ForeignKey('licenses.id'), nullable=True, comment="Previous license (for upgrades)")
    is_upgrade = Column(Boolean, nullable=False, default=False, comment="Is this an upgrade from a lower category")
    upgrade_from_category = Column(SQLEnum(LicenseCategory, native_enum=False), nullable=True, comment="Previous category if upgrade")
    
    # External references
    legacy_license_number = Column(String(20), nullable=True, comment="Legacy license number (for imports)")
    captured_from_license_number = Column(String(20), nullable=True, comment="Original license number if captured")
    
    # Card relationship tracking
    card_ordered = Column(Boolean, nullable=False, default=False, comment="Has a card been ordered for this license")
    card_order_date = Column(DateTime, nullable=True, comment="Date card was ordered")
    card_order_reference = Column(String(50), nullable=True, comment="Card order reference number")
    
    # Relationships
    person = relationship("Person", foreign_keys=[person_id])
    created_from_application = relationship("Application", foreign_keys=[created_from_application_id])
    issuing_location = relationship("Location", foreign_keys=[issuing_location_id])
    issued_by_user = relationship("User", foreign_keys=[issued_by_user_id])
    status_changed_by_user = relationship("User", foreign_keys=[status_changed_by])
    previous_license = relationship("License", remote_side="License.id", foreign_keys=[previous_license_id])
    
    # Many-to-many relationship with cards through CardLicense association
    card_licenses = relationship("CardLicense", back_populates="license", cascade="all, delete-orphan")
    
    @property
    def cards(self):
        """Get all cards associated with this license"""
        return [cl.card for cl in self.card_licenses]
    
    # Related entities
    status_history = relationship("LicenseStatusHistory", back_populates="license", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<License(id='{self.id}', category='{self.category}', status='{self.status}')>"

    @property
    def is_active(self) -> bool:
        """Check if license is currently active"""
        return self.status == LicenseStatus.ACTIVE

    @property
    def is_suspended(self) -> bool:
        """Check if license is currently suspended"""
        return self.status == LicenseStatus.SUSPENDED

    @property
    def is_cancelled(self) -> bool:
        """Check if license is permanently cancelled"""
        return self.status == LicenseStatus.CANCELLED

    @property
    def current_card(self) -> Optional['Card']:
        """Get the current active card that contains this license"""
        from app.models.card import Card, CardStatus
        for card in self.cards:
            if card.is_active and card.status not in [CardStatus.CANCELLED, CardStatus.EXPIRED]:
                return card
        return None

    @property
    def active_card(self) -> Optional['Card']:
        """Get the active card for the person (may contain other licenses too)"""
        from app.models.card import Card
        if self.person:
            # Get the person's active card
            for card in self.person.cards if hasattr(self.person, 'cards') else []:
                if card.is_active:
                    return card
        return None

    @property
    def restrictions_list(self) -> List[str]:
        """Get restrictions as a list"""
        if not self.restrictions:
            return []
        if isinstance(self.restrictions, list):
            return self.restrictions
        return []

    @property
    def medical_restrictions_list(self) -> List[str]:
        """Get medical restrictions as a list"""
        if not self.medical_restrictions:
            return []
        if isinstance(self.medical_restrictions, list):
            return self.medical_restrictions
        return []

    @property
    def professional_permit_categories_list(self) -> List[str]:
        """Get professional permit categories as a list"""
        if not self.professional_permit_categories:
            return []
        if isinstance(self.professional_permit_categories, list):
            return self.professional_permit_categories
        return []

    def add_restriction(self, restriction: str) -> None:
        """Add a restriction to the license"""
        current_restrictions = self.restrictions_list
        if restriction not in current_restrictions:
            current_restrictions.append(restriction)
            self.restrictions = current_restrictions

    def remove_restriction(self, restriction: str) -> None:
        """Remove a restriction from the license"""
        current_restrictions = self.restrictions_list
        if restriction in current_restrictions:
            current_restrictions.remove(restriction)
            self.restrictions = current_restrictions

    def needs_card(self) -> bool:
        """Check if this license needs a card ordered"""
        return not self.card_ordered and self.is_active

    def can_be_added_to_card(self) -> bool:
        """Check if this license can be added to a card"""
        return self.is_active and not self.current_card








class LicenseStatusHistory(BaseModel):
    """Track license status changes for audit trail"""
    __tablename__ = "license_status_history"

    license_id = Column(UUID(as_uuid=True), ForeignKey('licenses.id'), nullable=False, index=True, comment="License ID")
    
    # Status change details
    from_status = Column(SQLEnum(LicenseStatus), nullable=True, comment="Previous status")
    to_status = Column(SQLEnum(LicenseStatus), nullable=False, comment="New status")
    changed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who made the change")
    changed_at = Column(DateTime, nullable=False, default=func.now(), comment="Timestamp of status change")
    
    # Change context
    reason = Column(String(200), nullable=True, comment="Reason for status change")
    notes = Column(Text, nullable=True, comment="Additional notes about the change")
    system_initiated = Column(Boolean, nullable=False, default=False, comment="Whether change was system-initiated")
    
    # Suspension specific fields
    suspension_start_date = Column(DateTime, nullable=True, comment="Suspension start date (if applicable)")
    suspension_end_date = Column(DateTime, nullable=True, comment="Suspension end date (if applicable)")
    
    # Relationships
    license = relationship("License", back_populates="status_history")
    changed_by_user = relationship("User", foreign_keys=[changed_by])
    
    def __repr__(self):
        return f"<LicenseStatusHistory(license_id={self.license_id}, from='{self.from_status}', to='{self.to_status}')>"

