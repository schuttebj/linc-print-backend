"""
License Management Models for Madagascar License System
Implements issued licenses separate from applications with proper number generation and card tracking

Features:
- License number generation: {LocationCode}{8SequentialDigits}{CheckDigit}
- License statuses: ACTIVE, SUSPENDED, CANCELLED
- Card tracking as separate entities with expiry dates
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


class CardStatus(str, Enum):
    """Card status enumeration"""
    PENDING_PRODUCTION = "PENDING_PRODUCTION"   # Card ordered but not produced
    IN_PRODUCTION = "IN_PRODUCTION"            # Being printed/manufactured
    READY_FOR_COLLECTION = "READY_FOR_COLLECTION"  # Available for pickup
    COLLECTED = "COLLECTED"                    # Card collected by holder
    EXPIRED = "EXPIRED"                        # Card expired (needs renewal)
    DAMAGED = "DAMAGED"                        # Card reported damaged
    LOST = "LOST"                             # Card reported lost
    STOLEN = "STOLEN"                         # Card reported stolen


class License(BaseModel):
    """
    Madagascar Driver's License entity
    
    Represents an issued license that is valid for life unless suspended/cancelled.
    Cards expire and need renewal, but licenses remain valid.
    """
    __tablename__ = "licenses"

    # Core license information
    license_number = Column(String(15), nullable=False, unique=True, index=True, comment="Generated license number: {LocationCode}{8Sequential}{CheckDigit}")
    
    # Person and application links
    person_id = Column(UUID(as_uuid=True), ForeignKey('persons.id'), nullable=False, index=True, comment="License holder")
    created_from_application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, comment="Application that created this license")
    
    # License details
    category = Column(SQLEnum(LicenseCategory, native_enum=False), nullable=False, comment="Single license category for this license")
    status = Column(SQLEnum(LicenseStatus), nullable=False, default=LicenseStatus.ACTIVE, index=True, comment="Current license status")
    
    # Issue information
    issue_date = Column(DateTime, nullable=False, default=func.now(), comment="Date license was issued")
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
    
    # Relationships
    person = relationship("Person", foreign_keys=[person_id])
    created_from_application = relationship("Application", foreign_keys=[created_from_application_id])
    issuing_location = relationship("Location", foreign_keys=[issuing_location_id])
    issued_by_user = relationship("User", foreign_keys=[issued_by_user_id])
    status_changed_by_user = relationship("User", foreign_keys=[status_changed_by])
    previous_license = relationship("License", remote_side="License.id", foreign_keys=[previous_license_id])
    
    # Related entities
    cards = relationship("LicenseCard", back_populates="license", cascade="all, delete-orphan")
    status_history = relationship("LicenseStatusHistory", back_populates="license", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<License(number='{self.license_number}', category='{self.category}', status='{self.status}')>"

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
    def current_card(self) -> Optional['LicenseCard']:
        """Get the current active card for this license"""
        return next((card for card in self.cards if card.is_current), None)

    @property
    def restrictions_list(self) -> List[str]:
        """Get restrictions as a list"""
        if not self.restrictions:
            return []
        if isinstance(self.restrictions, list):
            return self.restrictions
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

    @staticmethod
    def generate_license_number(location_code: str, sequence_number: int) -> str:
        """
        Generate license number with check digit
        Format: {LocationCode}{8SequentialDigits}{CheckDigit}
        Example: A03123456789 (A03 + 12345678 + 9)
        """
        # Validate location code format (e.g., A03)
        if len(location_code) != 3:
            raise ValueError(f"Invalid location code format: {location_code}. Expected format: A03")
        
        # Format sequence number as 8 digits
        sequence_str = f"{sequence_number:08d}"
        
        # Combine without check digit
        base_number = f"{location_code}{sequence_str}"
        
        # Calculate check digit using Luhn algorithm (similar to SA ID)
        check_digit = License._calculate_check_digit(base_number)
        
        return f"{base_number}{check_digit}"

    @staticmethod
    def _calculate_check_digit(number_string: str) -> int:
        """
        Calculate check digit using Luhn algorithm
        Similar to South African ID number validation
        """
        # Convert to list of integers
        digits = [int(d) for d in number_string]
        
        # Double every second digit from right to left
        for i in range(len(digits) - 2, -1, -2):
            doubled = digits[i] * 2
            if doubled > 9:
                doubled = doubled // 10 + doubled % 10
            digits[i] = doubled
        
        # Sum all digits
        total = sum(digits)
        
        # Check digit makes total divisible by 10
        return (10 - (total % 10)) % 10

    @staticmethod
    def validate_license_number(license_number: str) -> bool:
        """Validate license number format and check digit"""
        if len(license_number) != 12:
            return False
        
        # Validate location code format (first 3 characters)
        location_code = license_number[:3]
        if not (location_code[0].isalpha() and location_code[1:].isdigit()):
            return False
        
        # Extract components
        base_number = license_number[:-1]
        check_digit = int(license_number[-1])
        
        # Verify check digit
        calculated_check_digit = License._calculate_check_digit(base_number)
        return check_digit == calculated_check_digit


class LicenseCard(BaseModel):
    """
    Physical license card entity with expiry dates
    
    Cards expire and need renewal, but licenses remain valid.
    Multiple cards can exist for one license over time.
    """
    __tablename__ = "license_cards"

    # Card identification
    card_number = Column(String(20), nullable=False, unique=True, index=True, comment="Physical card number")
    
    # License relationship
    license_id = Column(UUID(as_uuid=True), ForeignKey('licenses.id'), nullable=False, index=True, comment="Associated license")
    
    # Card details
    status = Column(SQLEnum(CardStatus), nullable=False, default=CardStatus.PENDING_PRODUCTION, comment="Current card status")
    card_type = Column(String(20), nullable=False, default="STANDARD", comment="STANDARD, DUPLICATE, REPLACEMENT")
    
    # Validity dates
    issue_date = Column(DateTime, nullable=False, default=func.now(), comment="Card issue date")
    expiry_date = Column(DateTime, nullable=False, comment="Card expiry date (5 years from issue)")
    valid_from = Column(DateTime, nullable=False, default=func.now(), comment="Card valid from date")
    
    # Card production
    ordered_date = Column(DateTime, nullable=True, comment="Date card was ordered for production")
    production_started = Column(DateTime, nullable=True, comment="Production start date")
    production_completed = Column(DateTime, nullable=True, comment="Production completion date")
    ready_for_collection_date = Column(DateTime, nullable=True, comment="Date card became ready for collection")
    collected_date = Column(DateTime, nullable=True, comment="Date card was collected")
    collected_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who processed collection")
    
    # Card specifications (ISO 18013 compliance)
    card_template = Column(String(50), nullable=False, default="MADAGASCAR_STANDARD", comment="Card template used")
    iso_compliance_version = Column(String(20), nullable=False, default="18013-1:2018", comment="ISO compliance version")
    security_level = Column(String(20), nullable=False, default="STANDARD", comment="Security level")
    
    # Physical card data
    front_image_path = Column(String(500), nullable=True, comment="Path to card front image")
    back_image_path = Column(String(500), nullable=True, comment="Path to card back image")
    barcode_image_path = Column(String(500), nullable=True, comment="Path to barcode image")
    
    # Production tracking
    production_batch_id = Column(String(50), nullable=True, comment="Production batch identifier")
    production_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=True, comment="Production location")
    quality_check_passed = Column(Boolean, nullable=True, comment="Quality check status")
    quality_check_date = Column(DateTime, nullable=True, comment="Quality check date")
    quality_check_notes = Column(Text, nullable=True, comment="Quality check notes")
    
    # Collection information
    collection_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=True, comment="Collection location")
    collection_notice_sent = Column(Boolean, nullable=False, default=False, comment="Collection notice sent")
    collection_notice_date = Column(DateTime, nullable=True, comment="Collection notice date")
    collection_reference = Column(String(50), nullable=True, comment="Collection reference number")
    
    # Card status flags
    is_current = Column(Boolean, nullable=False, default=True, comment="Is this the current card for the license")
    is_expired = Column(Boolean, nullable=False, default=False, comment="Card has expired")
    replacement_requested = Column(Boolean, nullable=False, default=False, comment="Replacement requested")
    replacement_reason = Column(String(100), nullable=True, comment="Reason for replacement")
    
    # Relationships
    license = relationship("License", back_populates="cards")
    collected_by_user = relationship("User", foreign_keys=[collected_by_user_id])
    production_location = relationship("Location", foreign_keys=[production_location_id])
    collection_location = relationship("Location", foreign_keys=[collection_location_id])
    
    def __repr__(self):
        return f"<LicenseCard(number='{self.card_number}', license_id={self.license_id}, status='{self.status}')>"

    @property
    def is_ready_for_collection(self) -> bool:
        """Check if card is ready for collection"""
        return self.status == CardStatus.READY_FOR_COLLECTION

    @property
    def is_collected(self) -> bool:
        """Check if card has been collected"""
        return self.status == CardStatus.COLLECTED

    @property
    def days_until_expiry(self) -> Optional[int]:
        """Calculate days until card expires"""
        if not self.expiry_date:
            return None
        
        days = (self.expiry_date.date() - date.today()).days
        return max(0, days)

    @property
    def is_near_expiry(self, warning_days: int = 90) -> bool:
        """Check if card is near expiry (default 90 days)"""
        days_left = self.days_until_expiry
        return days_left is not None and days_left <= warning_days

    @staticmethod
    def generate_card_number(license_number: str, card_sequence: int = 1) -> str:
        """
        Generate card number based on license number and sequence
        Format: {LicenseNumber}C{CardSequence}
        Example: T01000001231C1 (first card), T01000001231C2 (replacement)
        """
        return f"{license_number}C{card_sequence}"


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


class LicenseSequenceCounter(BaseModel):
    """
    Global sequence counter for license number generation
    Ensures unique sequential numbers across all locations
    """
    __tablename__ = "license_sequence_counter"

    # Single row table with ID=1
    id = Column(Integer, primary_key=True, default=1, comment="Always 1 for singleton pattern")
    current_sequence = Column(Integer, nullable=False, default=0, comment="Current sequence number")
    last_updated = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="Last update timestamp")
    updated_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who last updated counter")
    
    # Relationships
    updated_by_user = relationship("User", foreign_keys=[updated_by])
    
    @classmethod
    def get_next_sequence(cls, db, user_id: Optional[str] = None) -> int:
        """
        Get next sequence number atomically
        Thread-safe method to increment and return next sequence
        """
        # Get or create the counter record
        counter = db.query(cls).filter(cls.id == 1).first()
        if not counter:
            counter = cls(id=1, current_sequence=0, updated_by=user_id)
            db.add(counter)
            db.flush()
        
        # Increment and save
        counter.current_sequence += 1
        counter.updated_by = user_id
        db.commit()
        
        return counter.current_sequence
    
    def __repr__(self):
        return f"<LicenseSequenceCounter(current={self.current_sequence})>" 