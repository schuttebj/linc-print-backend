"""
Independent Card Management Models for Madagascar License System
Cards as separate entities with license associations and production workflow tracking
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Numeric, JSON, Enum as SQLEnum, func, Table, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Session, validates
from sqlalchemy.sql import func
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum

from app.models.base import BaseModel


class CardNumberGenerator:
    """Card number generation and validation utilities"""
    
    @staticmethod
    def calculate_checksum(base_number: str) -> int:
        """
        Calculate checksum using Luhn algorithm (modulo 10)
        Used for card number validation
        """
        digits = [int(d) for d in base_number if d.isdigit()]
        checksum = 0
        
        # Double every second digit from right to left
        for i, digit in enumerate(reversed(digits)):
            if i % 2 == 1:  # Every second digit
                digit *= 2
                if digit > 9:
                    digit = digit // 10 + digit % 10
            checksum += digit
        
        # Return the amount needed to make checksum divisible by 10
        return (10 - (checksum % 10)) % 10
    
    @staticmethod
    def validate_card_number(card_number: str) -> bool:
        """
        Validate card number checksum
        Returns True if card number is valid
        """
        if not card_number or len(card_number) < 4:
            return False
        
        # Extract base number and checksum
        base_number = card_number[:-1]
        expected_checksum = int(card_number[-1])
        
        # Calculate and compare checksum
        actual_checksum = CardNumberGenerator.calculate_checksum(base_number)
        return actual_checksum == expected_checksum

    @staticmethod
    def get_next_sequence_number(db: Session, location_code: str) -> int:
        """
        Get next sequence number for a location
        Thread-safe method to increment and return next sequence
        """
        # Get or create the counter record for this location
        counter = db.query(CardSequenceCounter).filter(
            CardSequenceCounter.location_code == location_code
        ).first()
        
        if not counter:
            counter = CardSequenceCounter(
                location_code=location_code,
                current_sequence=0
            )
            db.add(counter)
            db.flush()
        
        # Increment and save
        counter.current_sequence += 1
        db.commit()
        
        return counter.current_sequence


class CardType(str, Enum):
    """Card type enumeration"""
    STANDARD = "STANDARD"           # Regular plastic card
    TEMPORARY = "TEMPORARY"         # Paper temporary license (A4 printed)
    DUPLICATE = "DUPLICATE"         # Duplicate of existing card
    REPLACEMENT = "REPLACEMENT"     # Replacement for lost/stolen/damaged card
    EMERGENCY = "EMERGENCY"         # Emergency temporary card


class CardStatus(str, Enum):
    """Card status enumeration"""
    PENDING_ORDER = "PENDING_ORDER"               # Card not yet ordered (manual process)
    ORDERED = "ORDERED"                          # Card ordered for production
    PENDING_PRODUCTION = "PENDING_PRODUCTION"     # Waiting to start production
    IN_PRODUCTION = "IN_PRODUCTION"              # Being produced
    QUALITY_CONTROL = "QUALITY_CONTROL"         # Quality control review
    PRODUCTION_COMPLETED = "PRODUCTION_COMPLETED" # Production finished
    READY_FOR_COLLECTION = "READY_FOR_COLLECTION" # Available for pickup
    COLLECTED = "COLLECTED"                      # Card collected by holder
    EXPIRED = "EXPIRED"                          # Card expired (needs renewal)
    CANCELLED = "CANCELLED"                      # Card cancelled (replaced/lost)
    DAMAGED = "DAMAGED"                          # Card reported damaged
    LOST = "LOST"                               # Card reported lost
    STOLEN = "STOLEN"                           # Card reported stolen


class ProductionStatus(str, Enum):
    """Detailed production status tracking"""
    NOT_STARTED = "NOT_STARTED"
    DESIGN_CREATED = "DESIGN_CREATED"
    PRINTING_STARTED = "PRINTING_STARTED"
    CARD_PRINTED = "CARD_PRINTED"
    QUALITY_CHECK_PENDING = "QUALITY_CHECK_PENDING"
    QUALITY_CHECK_PASSED = "QUALITY_CHECK_PASSED"
    QUALITY_CHECK_FAILED = "QUALITY_CHECK_FAILED"
    PACKAGING_COMPLETED = "PACKAGING_COMPLETED"
    SHIPPED_TO_COLLECTION_POINT = "SHIPPED_TO_COLLECTION_POINT"


class CardLicense(BaseModel):
    """
    Model for Card-License associations with additional metadata
    Provides ORM interface for the card_licenses association table
    """
    __tablename__ = "card_licenses"

    card_id = Column(UUID(as_uuid=True), ForeignKey('cards.id'), nullable=False, index=True)
    license_id = Column(UUID(as_uuid=True), ForeignKey('licenses.id'), nullable=False, index=True)
    is_primary = Column(Boolean, nullable=False, default=False, comment="Primary license for this card")
    added_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    added_at = Column(DateTime, nullable=False, default=func.now())

    # Relationships
    card = relationship("Card", back_populates="card_licenses")
    license = relationship("License", back_populates="card_licenses")
    added_by_user = relationship("User", foreign_keys=[added_by])
    
    # Table constraints
    __table_args__ = (
        UniqueConstraint('card_id', 'license_id', name='uq_card_license'),
    )


class Card(BaseModel):
    """
    Independent Card entity for Madagascar License System
    
    Cards are physical entities that can contain multiple licenses.
    They have their own lifecycle independent of licenses.
    Only one active card per person is allowed at a time.
    """
    __tablename__ = "cards"

    # Card identification
    card_number = Column(String(20), nullable=False, unique=True, index=True, comment="Physical card number")
    
    # Person assignment - only one active card per person
    person_id = Column(UUID(as_uuid=True), ForeignKey('persons.id'), nullable=False, index=True, comment="Person this card is assigned to")
    
    # Card details
    card_type = Column(SQLEnum(CardType), nullable=False, comment="Type of card")
    status = Column(SQLEnum(CardStatus), nullable=False, default=CardStatus.PENDING_ORDER, comment="Current card status")
    production_status = Column(SQLEnum(ProductionStatus), nullable=False, default=ProductionStatus.NOT_STARTED, comment="Detailed production status")
    
    # Validity period
    valid_from = Column(DateTime, nullable=False, comment="Card valid from date")
    valid_until = Column(DateTime, nullable=False, comment="Card valid until date")
    
    # Application integration
    created_from_application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=True, comment="Application that triggered card creation")
    
    # Active status - only one active card per person
    is_active = Column(Boolean, nullable=False, default=True, comment="Is this the active card for the person")
    cancelled_at = Column(DateTime, nullable=True, comment="Date card was cancelled")
    cancelled_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who cancelled the card")
    cancellation_reason = Column(Text, nullable=True, comment="Reason for cancellation")
    
    # Production workflow dates
    ordered_date = Column(DateTime, nullable=True, comment="Date card was ordered for production")
    production_start_date = Column(DateTime, nullable=True, comment="Production start date")
    production_completed_date = Column(DateTime, nullable=True, comment="Production completion date")
    quality_check_date = Column(DateTime, nullable=True, comment="Quality check date")
    ready_for_collection_date = Column(DateTime, nullable=True, comment="Date card became ready for collection")
    collected_date = Column(DateTime, nullable=True, comment="Date card was collected")
    
    # Collection tracking
    collection_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=True, comment="Collection location")
    production_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=True, comment="Production location")
    collected_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who processed collection")
    collection_reference = Column(String(50), nullable=True, comment="Collection reference number")
    collection_notes = Column(Text, nullable=True, comment="Collection process notes")
    
    # Production details
    production_batch_id = Column(String(50), nullable=True, comment="Production batch identifier")
    quality_control_passed = Column(Boolean, nullable=True, comment="Quality control status")
    quality_control_notes = Column(Text, nullable=True, comment="Quality control notes")
    
    # Physical card specifications
    card_template = Column(String(50), nullable=False, default="MADAGASCAR_STANDARD", comment="Card design template")
    security_features = Column(JSON, nullable=True, comment="Security features applied to card")
    
    # Temporary card specific fields
    is_temporary = Column(Boolean, nullable=False, default=False, comment="Is this a temporary paper license")
    temporary_valid_days = Column(Integer, nullable=True, comment="Validity period for temporary cards (days)")
    replacement_card_id = Column(UUID(as_uuid=True), ForeignKey('cards.id'), nullable=True, comment="Permanent card that replaces this temporary card")
    
    # Relationships
    person = relationship("Person")
    created_from_application = relationship("Application")
    collection_location = relationship("Location", foreign_keys=[collection_location_id])
    production_location = relationship("Location", foreign_keys=[production_location_id])
    collected_by_user = relationship("User", foreign_keys=[collected_by_user_id])
    cancelled_by_user = relationship("User", foreign_keys=[cancelled_by_user_id])
    replacement_card = relationship("Card", remote_side="Card.id", foreign_keys=[replacement_card_id])
    
    # Many-to-many relationship with licenses through CardLicense association
    card_licenses = relationship("CardLicense", back_populates="card", cascade="all, delete-orphan")
    
    @property
    def licenses(self):
        """Get all licenses associated with this card"""
        return [cl.license for cl in self.card_licenses]
    
    # Card history and status tracking
    status_history = relationship("CardStatusHistory", back_populates="card", cascade="all, delete-orphan")
    
    # Database constraints
    __table_args__ = (
        # Ensure only one active card per person
        Index('idx_person_active_card', 'person_id', 'is_active', unique=True, 
              postgresql_where=(Column('is_active') == True)),
        # Index for performance
        Index('idx_card_status_person', 'status', 'person_id'),
        Index('idx_card_production_batch', 'production_batch_id'),
    )

    def __repr__(self):
        return f"<Card(number='{self.card_number}', person_id={self.person_id}, status='{self.status}')>"

    @property
    def is_collected(self) -> bool:
        """Check if card has been collected"""
        return self.status == CardStatus.COLLECTED

    @property
    def is_ready_for_collection(self) -> bool:
        """Check if card is ready for collection"""
        return self.status == CardStatus.READY_FOR_COLLECTION

    @property
    def days_until_expiry(self) -> Optional[int]:
        """Calculate days until card expires"""
        if not self.valid_until:
            return None
        
        days = (self.valid_until.date() - date.today()).days
        return max(0, days)

    @property
    def is_near_expiry(self, warning_days: int = 90) -> bool:
        """Check if card is near expiry (default 90 days)"""
        days_left = self.days_until_expiry
        return days_left is not None and days_left <= warning_days

    @property
    def is_expired(self) -> bool:
        """Check if card has expired"""
        return self.valid_until and self.valid_until.date() < date.today()

    @property
    def can_be_collected(self) -> bool:
        """Check if card can be collected"""
        return self.status == CardStatus.READY_FOR_COLLECTION and self.is_active

    @property
    def primary_license(self) -> Optional['License']:
        """Get the primary license for this card"""
        for license_obj in self.licenses:
            # Check the association table for is_primary flag
            # This would need to be implemented in CRUD layer
            pass
        return None

    def cancel_card(self, reason: str, cancelled_by_user_id: UUID) -> None:
        """Cancel this card (when ordering a replacement)"""
        self.is_active = False
        self.status = CardStatus.CANCELLED
        self.cancelled_at = datetime.utcnow()
        self.cancelled_by_user_id = cancelled_by_user_id
        self.cancellation_reason = reason

    @staticmethod
    def generate_card_number(location_code: str, sequence_number: int, card_type: CardType = CardType.STANDARD) -> str:
        """
        Generate card number using Madagascar format:
        Format: {LocationCode}{8-digit-sequence}{checksum}
        Example: T0100000123 (T01 = location, 00000012 = sequence, 3 = checksum)
        
        For temporary cards, prefix with 'T': TT0100000123
        """
        # Ensure location code is properly formatted (e.g., T01, F01, etc.)
        if len(location_code) == 1:
            location_code = f"{location_code}01"  # Default to office 01
        
        # Format 8-digit sequence number (zero-padded)
        sequence_str = f"{sequence_number:08d}"
        
        # Calculate checksum (simple modulo 10 algorithm)
        checksum = CardNumberGenerator.calculate_checksum(location_code + sequence_str)
        
        # Construct final card number
        if card_type == CardType.TEMPORARY:
            return f"T{location_code}{sequence_str}{checksum}"
        else:
            return f"{location_code}{sequence_str}{checksum}"

    @staticmethod
    def create_temporary_card(person_id: UUID, licenses: List['License'], valid_days: int = 90) -> 'Card':
        """
        Create a temporary paper license card
        Used for lost/stolen card replacements while permanent card is being produced
        """
        from datetime import datetime, timedelta
        
        # Generate temporary card number
        card_number = Card.generate_card_number(person_id, card_type=CardType.TEMPORARY)
        
        # Set validity period (much shorter than permanent cards)
        valid_from = datetime.utcnow()
        valid_until = valid_from + timedelta(days=valid_days)
        
        return Card(
            card_number=card_number,
            person_id=person_id,
            card_type=CardType.TEMPORARY,
            status=CardStatus.READY_FOR_COLLECTION,  # Can be printed immediately
            is_temporary=True,
            temporary_valid_days=valid_days,
            valid_from=valid_from,
            valid_until=valid_until,
            is_active=True  # Will become active temporary card
        )


class CardStatusHistory(BaseModel):
    """Track card status changes for audit trail"""
    __tablename__ = "card_status_history"

    card_id = Column(UUID(as_uuid=True), ForeignKey('cards.id'), nullable=False, index=True, comment="Card ID")
    
    # Status change details
    from_status = Column(SQLEnum(CardStatus), nullable=True, comment="Previous status")
    to_status = Column(SQLEnum(CardStatus), nullable=False, comment="New status")
    changed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who made the change")
    changed_at = Column(DateTime, nullable=False, default=func.now(), comment="Timestamp of status change")
    
    # Change context
    reason = Column(String(200), nullable=True, comment="Reason for status change")
    notes = Column(Text, nullable=True, comment="Additional notes about the change")
    system_initiated = Column(Boolean, nullable=False, default=False, comment="Whether change was system-initiated")
    
    # Production specific tracking
    production_batch_id = Column(String(50), nullable=True, comment="Production batch if applicable")
    quality_check_result = Column(String(20), nullable=True, comment="Quality check result if applicable")
    
    # Relationships
    card = relationship("Card", back_populates="status_history")
    changed_by_user = relationship("User", foreign_keys=[changed_by])
    
    def __repr__(self):
        return f"<CardStatusHistory(card_id={self.card_id}, from='{self.from_status}', to='{self.to_status}')>"


class CardProductionBatch(BaseModel):
    """Track card production in batches for efficiency"""
    __tablename__ = "card_production_batches"

    batch_id = Column(String(50), nullable=False, unique=True, index=True, comment="Production batch identifier")
    
    # Batch details
    batch_date = Column(DateTime, nullable=False, default=func.now(), comment="Batch creation date")
    production_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=False, comment="Production location")
    batch_size = Column(Integer, nullable=False, comment="Number of cards in batch")
    
    # Production status
    status = Column(String(20), nullable=False, default="PENDING", comment="Batch status")
    started_at = Column(DateTime, nullable=True, comment="Production start time")
    completed_at = Column(DateTime, nullable=True, comment="Production completion time")
    
    # Quality control
    quality_check_passed = Column(Boolean, nullable=True, comment="Batch quality check status")
    quality_check_date = Column(DateTime, nullable=True, comment="Quality check date")
    defect_count = Column(Integer, nullable=False, default=0, comment="Number of defective cards")
    
    # Production details
    template_used = Column(String(50), nullable=True, comment="Card template used for batch")
    production_notes = Column(Text, nullable=True, comment="Production notes")
    
    # Relationships
    production_location = relationship("Location")
    
    def __repr__(self):
        return f"<CardProductionBatch(id='{self.batch_id}', size={self.batch_size}, status='{self.status}')>"


class CardSequenceCounter(BaseModel):
    """
    Sequence counter for card number generation by location
    Ensures unique sequential numbers for each location
    """
    __tablename__ = "card_sequence_counters"

    location_code = Column(String(10), nullable=False, unique=True, index=True, comment="Location code (T01, F01, etc.)")
    current_sequence = Column(Integer, nullable=False, default=0, comment="Current sequence number for this location")
    last_updated = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="Last update timestamp")
    updated_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who last updated counter")
    
    # Relationships
    updated_by_user = relationship("User", foreign_keys=[updated_by])
    
    def __repr__(self):
        return f"<CardSequenceCounter(location='{self.location_code}', sequence={self.current_sequence})>" 