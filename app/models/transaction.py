"""
Transaction Management Models for Madagascar License System
Handles all payment processing for applications and card orders

Features:
- Centralized payment processing for applications and card orders
- Point of sale system support
- Receipt generation and audit trail
- Configurable fee structures
- Support for multiple applications per transaction
- Card order management with separate payment tracking
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Numeric, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from decimal import Decimal
from datetime import datetime
from enum import Enum as PythonEnum

from app.models.base import BaseModel


class TransactionType(PythonEnum):
    """Types of transactions"""
    APPLICATION_PAYMENT = "APPLICATION_PAYMENT"     # Payment for application processing
    CARD_ORDER_PAYMENT = "CARD_ORDER_PAYMENT"       # Payment for card production
    MIXED_PAYMENT = "MIXED_PAYMENT"                 # Payment for both applications and cards


class TransactionStatus(PythonEnum):
    """Transaction status"""
    PENDING = "PENDING"           # Transaction created but not paid
    PAID = "PAID"                # Payment completed successfully  
    CANCELLED = "CANCELLED"       # Transaction cancelled
    REFUNDED = "REFUNDED"         # Payment refunded


class PaymentMethod(PythonEnum):
    """Payment methods available"""
    CASH = "CASH"                 # Cash payment
    MOBILE_MONEY = "MOBILE_MONEY" # Mobile money (Airtel, Orange, etc.)
    BANK_TRANSFER = "BANK_TRANSFER" # Bank transfer
    CARD = "CARD"                 # Credit/debit card
    CHEQUE = "CHEQUE"             # Bank cheque


class FeeType(PythonEnum):
    """Types of fees in the system - Application-type specific"""
    # Test fees (used across multiple application types)
    THEORY_TEST_LIGHT = "THEORY_TEST_LIGHT"         # Theory test for light vehicles (10,000 Ar)
    THEORY_TEST_HEAVY = "THEORY_TEST_HEAVY"         # Theory test for heavy vehicles (15,000 Ar)
    PRACTICAL_TEST_LIGHT = "PRACTICAL_TEST_LIGHT"   # Practical test for light vehicles (10,000 Ar)
    PRACTICAL_TEST_HEAVY = "PRACTICAL_TEST_HEAVY"   # Practical test for heavy vehicles (15,000 Ar)
    
    # Application-type-specific fees (adjustable)
    NEW_LICENSE_FEE = "NEW_LICENSE_FEE"             # New license application + card (38,000 Ar)
    LEARNERS_PERMIT_FEE = "LEARNERS_PERMIT_FEE"     # Learners permit (test fees only)
    RENEWAL_FEE = "RENEWAL_FEE"                     # License renewal (38,000 Ar)
    REPLACEMENT_FEE = "REPLACEMENT_FEE"             # License replacement (38,000 Ar)
    TEMPORARY_LICENSE_FEE = "TEMPORARY_LICENSE_FEE" # Temporary license (10,000 Ar)
    INTERNATIONAL_PERMIT_FEE = "INTERNATIONAL_PERMIT_FEE" # International permit (38,000 Ar)
    PROFESSIONAL_LICENSE_FEE = "PROFESSIONAL_LICENSE_FEE" # Professional license (38,000 Ar)
    FOREIGN_CONVERSION_FEE = "FOREIGN_CONVERSION_FEE"     # Foreign license conversion (38,000 Ar)
    DRIVERS_LICENSE_CAPTURE_FEE = "DRIVERS_LICENSE_CAPTURE_FEE" # License capture (38,000 Ar)
    LEARNERS_PERMIT_CAPTURE_FEE = "LEARNERS_PERMIT_CAPTURE_FEE" # Learners capture (38,000 Ar)
    
    # Legacy fees (keep for backward compatibility)
    APPLICATION_PROCESSING = "APPLICATION_PROCESSING" # Deprecated - use application-specific fees
    CARD_PRODUCTION = "CARD_PRODUCTION"             # Deprecated - use application-specific fees


class CardOrderStatus(PythonEnum):
    """Card order status tracking"""
    PENDING_PAYMENT = "PENDING_PAYMENT"             # Waiting for payment
    PAID = "PAID"                                   # Payment completed, ready to order
    ORDERED = "ORDERED"                             # Order sent to production
    IN_PRODUCTION = "IN_PRODUCTION"                 # Card being produced
    READY_FOR_COLLECTION = "READY_FOR_COLLECTION"   # Card ready for pickup
    COLLECTED = "COLLECTED"                         # Card collected by applicant
    CANCELLED = "CANCELLED"                         # Order cancelled


class FeeStructure(BaseModel):
    """Configurable fee structure for all transaction types"""
    __tablename__ = "fee_structures"
    
    # Fee identification
    fee_type = Column(SQLEnum(FeeType), nullable=False, unique=True, comment="Type of fee")
    display_name = Column(String(100), nullable=False, comment="Human-readable fee name")
    description = Column(Text, nullable=True, comment="Fee description")
    
    # Fee amount
    amount = Column(Numeric(10, 2), nullable=False, comment="Fee amount in Ariary (Ar)")
    currency = Column(String(3), nullable=False, default='MGA', comment="Currency code")
    
    # Fee settings
    is_active = Column(Boolean, nullable=False, default=True, comment="Whether fee is currently active")
    
    # Date ranges
    effective_from = Column(DateTime, nullable=False, default=func.now(), comment="When fee becomes effective")
    effective_until = Column(DateTime, nullable=True, comment="When fee expires (null = indefinite)")
    
    # Management
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who created this fee structure")
    last_updated_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who last updated this fee")
    
    # Relationships
    created_by_user = relationship("User", foreign_keys=[created_by])
    last_updated_by_user = relationship("User", foreign_keys=[last_updated_by])
    
    def is_effective(self, date: datetime = None) -> bool:
        """Check if fee is effective on given date (defaults to now)"""
        if date is None:
            date = datetime.utcnow()
        
        if not self.is_active:
            return False
            
        if date < self.effective_from:
            return False
            
        if self.effective_until and date > self.effective_until:
            return False
            
        return True
    
    def __repr__(self):
        return f"<FeeStructure(type='{self.fee_type.value}', amount={self.amount}, active={self.is_active})>"


class Transaction(BaseModel):
    """Main transaction record for payment processing"""
    __tablename__ = "transactions"
    
    # Transaction identification
    transaction_number = Column(String(20), nullable=False, unique=True, index=True, comment="Unique transaction number")
    transaction_type = Column(SQLEnum(TransactionType), nullable=False, comment="Type of transaction")
    status = Column(SQLEnum(TransactionStatus), nullable=False, default=TransactionStatus.PENDING, comment="Transaction status")
    
    # Person and location
    person_id = Column(UUID(as_uuid=True), ForeignKey('persons.id'), nullable=False, index=True, comment="Person making payment")
    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=False, comment="Location where payment is made")
    
    # Payment details
    total_amount = Column(Numeric(10, 2), nullable=False, comment="Total transaction amount")
    payment_method = Column(SQLEnum(PaymentMethod), nullable=True, comment="Payment method used")
    payment_reference = Column(String(100), nullable=True, comment="Payment reference number")
    
    # Processing details
    processed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who processed payment")
    processed_at = Column(DateTime, nullable=True, comment="When payment was processed")
    
    # Receipt and documentation
    receipt_number = Column(String(50), nullable=True, comment="Official receipt number")
    receipt_printed = Column(Boolean, nullable=False, default=False, comment="Whether receipt was printed")
    receipt_printed_at = Column(DateTime, nullable=True, comment="When receipt was printed")
    
    # Notes and metadata
    notes = Column(Text, nullable=True, comment="Transaction notes")
    transaction_metadata = Column(JSON, nullable=True, comment="Additional transaction metadata")
    
    # Relationships
    person = relationship("Person", back_populates="transactions")
    location = relationship("Location")
    processed_by_user = relationship("User", foreign_keys=[processed_by])
    items = relationship("TransactionItem", back_populates="transaction", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Transaction(number='{self.transaction_number}', amount={self.total_amount}, status='{self.status.value}')>"


class TransactionItem(BaseModel):
    """Individual items within a transaction"""
    __tablename__ = "transaction_items"
    
    # Transaction reference
    transaction_id = Column(UUID(as_uuid=True), ForeignKey('transactions.id'), nullable=False, index=True, comment="Parent transaction")
    
    # Item details
    item_type = Column(String(50), nullable=False, comment="Type of item (application_fee, card_order, etc.)")
    description = Column(String(200), nullable=False, comment="Human-readable description")
    amount = Column(Numeric(10, 2), nullable=False, comment="Item amount")
    
    # References to related entities
    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=True, comment="Related application (if applicable)")
    card_order_id = Column(UUID(as_uuid=True), ForeignKey('card_orders.id'), nullable=True, comment="Related card order (if applicable)")
    fee_structure_id = Column(UUID(as_uuid=True), ForeignKey('fee_structures.id'), nullable=True, comment="Fee structure used")
    
    # Item metadata
    item_metadata = Column(JSON, nullable=True, comment="Additional item metadata")
    
    # Relationships
    transaction = relationship("Transaction", back_populates="items")
    application = relationship("Application")
    card_order = relationship("CardOrder", back_populates="transaction_item")
    fee_structure = relationship("FeeStructure")
    
    def __repr__(self):
        return f"<TransactionItem(type='{self.item_type}', amount={self.amount}, description='{self.description}')>"


class CardOrder(BaseModel):
    """Card order management with payment tracking"""
    __tablename__ = "card_orders"
    
    # Order identification
    order_number = Column(String(20), nullable=False, unique=True, index=True, comment="Unique card order number")
    status = Column(SQLEnum(CardOrderStatus), nullable=False, default=CardOrderStatus.PENDING_PAYMENT, comment="Order status")
    
    # Application and person
    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, index=True, comment="Application for card")
    person_id = Column(UUID(as_uuid=True), ForeignKey('persons.id'), nullable=False, comment="Person ordering card")
    
    # Card details
    card_type = Column(String(50), nullable=False, comment="Type of card (license, permit, etc.)")
    urgency_level = Column(Integer, nullable=False, default=1, comment="Urgency level (1=normal, 2=urgent, 3=emergency)")
    
    # Payment tracking
    fee_amount = Column(Numeric(10, 2), nullable=False, comment="Card production fee")
    payment_required = Column(Boolean, nullable=False, default=True, comment="Whether payment is required")
    
    # Order processing
    ordered_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who created order")
    ordered_at = Column(DateTime, nullable=False, default=func.now(), comment="When order was created")
    payment_deadline = Column(DateTime, nullable=True, comment="Payment deadline")
    
    # Production tracking
    production_started_at = Column(DateTime, nullable=True, comment="When production started")
    production_completed_at = Column(DateTime, nullable=True, comment="When production completed")
    ready_for_collection_at = Column(DateTime, nullable=True, comment="When card became ready for collection")
    collected_at = Column(DateTime, nullable=True, comment="When card was collected")
    collected_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who processed collection")
    
    # Card metadata
    card_data = Column(JSON, nullable=True, comment="Card production data (photo, license details, etc.)")
    production_metadata = Column(JSON, nullable=True, comment="Production tracking metadata")
    
    # Notes
    order_notes = Column(Text, nullable=True, comment="Order processing notes")
    collection_notes = Column(Text, nullable=True, comment="Collection notes")
    
    # Relationships
    application = relationship("Application")
    person = relationship("Person")
    ordered_by_user = relationship("User", foreign_keys=[ordered_by])
    collected_by_user = relationship("User", foreign_keys=[collected_by])
    transaction_item = relationship("TransactionItem", back_populates="card_order", uselist=False)
    
    def can_be_ordered(self) -> bool:
        """Check if card can be ordered (application requirements met)"""
        if not self.application:
            return False
            
        # For new licenses, must pass tests first
        if self.application.application_type in ['NEW_LICENSE'] and self.application.status != 'PASSED':
            return False
            
        # For renewals, etc., can order immediately after payment
        return True
    
    def __repr__(self):
        return f"<CardOrder(number='{self.order_number}', status='{self.status.value}', amount={self.fee_amount})>"


# Madagascar License Fee Structure (Application-Type Specific)
DEFAULT_FEE_STRUCTURE = {
    # Test Fees
    FeeType.THEORY_TEST_LIGHT: {
        "display_name": "Theory Test (Light Vehicles)",
        "description": "Theory test for light vehicle categories (A1, A2, A, B1, B)",
        "amount": Decimal("10000.00")
    },
    FeeType.THEORY_TEST_HEAVY: {
        "display_name": "Theory Test (Heavy Vehicles)", 
        "description": "Theory test for heavy vehicle categories (B2, BE, C1, C, C1E, CE, D1, D, D2)",
        "amount": Decimal("15000.00")
    },
    FeeType.PRACTICAL_TEST_LIGHT: {
        "display_name": "Practical Test (Light Vehicles)",
        "description": "Practical test for light vehicle categories",
        "amount": Decimal("10000.00")
    },
    FeeType.PRACTICAL_TEST_HEAVY: {
        "display_name": "Practical Test (Heavy Vehicles)",
        "description": "Practical test for heavy vehicle categories",
        "amount": Decimal("15000.00")
    },
    
    # Application-Type-Specific Fees (adjustable)
    FeeType.NEW_LICENSE_FEE: {
        "display_name": "New License - Application + Card",
        "description": "Complete new license application processing and card production",
        "amount": Decimal("38000.00")
    },
    FeeType.LEARNERS_PERMIT_FEE: {
        "display_name": "Learners Permit - Additional Fee",
        "description": "Additional fee for learners permit (test fees separate)",
        "amount": Decimal("0.00")
    },
    FeeType.RENEWAL_FEE: {
        "display_name": "License Renewal",
        "description": "License renewal processing and new card production",
        "amount": Decimal("38000.00")
    },
    FeeType.REPLACEMENT_FEE: {
        "display_name": "License Replacement",
        "description": "License replacement for lost/stolen/damaged cards",
        "amount": Decimal("38000.00")
    },
    FeeType.TEMPORARY_LICENSE_FEE: {
        "display_name": "Temporary License",
        "description": "Temporary license (90-day validity)",
        "amount": Decimal("10000.00")
    },
    FeeType.INTERNATIONAL_PERMIT_FEE: {
        "display_name": "International Driving Permit",
        "description": "International driving permit application",
        "amount": Decimal("38000.00")
    },
    FeeType.PROFESSIONAL_LICENSE_FEE: {
        "display_name": "Professional License",
        "description": "Professional driving license application",
        "amount": Decimal("38000.00")
    },
    FeeType.FOREIGN_CONVERSION_FEE: {
        "display_name": "Foreign License Conversion",
        "description": "Foreign license conversion to Madagascar license",
        "amount": Decimal("38000.00")
    },
    FeeType.DRIVERS_LICENSE_CAPTURE_FEE: {
        "display_name": "Driver's License Capture",
        "description": "Capture existing driver's license into system",
        "amount": Decimal("38000.00")
    },
    FeeType.LEARNERS_PERMIT_CAPTURE_FEE: {
        "display_name": "Learner's Permit Capture",
        "description": "Capture existing learner's permit into system",
        "amount": Decimal("38000.00")
    },
    
    # Legacy fees (for backward compatibility)
    FeeType.APPLICATION_PROCESSING: {
        "display_name": "Application Processing (Legacy)",
        "description": "Legacy application processing fee",
        "amount": Decimal("38000.00")
    },
    FeeType.CARD_PRODUCTION: {
        "display_name": "Card Production (Legacy)",
        "description": "Legacy card production fee",
        "amount": Decimal("38000.00")
    }
} 