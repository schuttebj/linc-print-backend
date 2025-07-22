"""
Pydantic schemas for Transaction Management
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from decimal import Decimal
from datetime import datetime
import uuid

from app.models.transaction import (
    TransactionType, TransactionStatus, PaymentMethod, FeeType, CardOrderStatus
)


# Fee Structure schemas
class FeeStructureBase(BaseModel):
    """Base schema for Fee Structure"""
    fee_type: FeeType
    display_name: str = Field(..., max_length=100)
    description: Optional[str] = None
    amount: Decimal = Field(..., ge=0)
    currency: str = Field(default="MGA", max_length=3)
    is_active: bool = True
    effective_from: datetime
    effective_until: Optional[datetime] = None

class FeeStructureCreate(FeeStructureBase):
    """Schema for creating Fee Structure"""
    pass

class FeeStructureUpdate(BaseModel):
    """Schema for updating Fee Structure"""
    display_name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    amount: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None
    effective_until: Optional[datetime] = None

class FeeStructure(FeeStructureBase):
    """Schema for Fee Structure response"""
    id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: uuid.UUID
    last_updated_by: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True


# Transaction Item schemas
class TransactionItemBase(BaseModel):
    """Base schema for Transaction Item"""
    item_type: str = Field(..., max_length=50)
    description: str = Field(..., max_length=200)
    amount: Decimal = Field(..., ge=0)
    application_id: Optional[uuid.UUID] = None
    card_order_id: Optional[uuid.UUID] = None
    fee_structure_id: Optional[uuid.UUID] = None
    metadata: Optional[Dict[str, Any]] = None

class TransactionItemCreate(TransactionItemBase):
    """Schema for creating Transaction Item"""
    pass

class TransactionItem(TransactionItemBase):
    """Schema for Transaction Item response"""
    id: uuid.UUID
    transaction_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True


# Card Order schemas
class CardOrderBase(BaseModel):
    """Base schema for Card Order"""
    application_id: uuid.UUID
    card_type: str = Field(default="license", max_length=50)
    urgency_level: int = Field(default=1, ge=1, le=3)
    payment_required: bool = True
    payment_deadline: Optional[datetime] = None
    order_notes: Optional[str] = None

class CardOrderCreate(CardOrderBase):
    """Schema for creating Card Order"""
    pass

class CardOrderUpdate(BaseModel):
    """Schema for updating Card Order"""
    status: Optional[CardOrderStatus] = None
    urgency_level: Optional[int] = Field(None, ge=1, le=3)
    payment_deadline: Optional[datetime] = None
    order_notes: Optional[str] = None
    production_metadata: Optional[Dict[str, Any]] = None
    collection_notes: Optional[str] = None

class CardOrder(CardOrderBase):
    """Schema for Card Order response"""
    id: uuid.UUID
    order_number: str
    status: CardOrderStatus
    person_id: uuid.UUID
    fee_amount: Decimal
    ordered_by: uuid.UUID
    ordered_at: datetime
    production_started_at: Optional[datetime] = None
    production_completed_at: Optional[datetime] = None
    ready_for_collection_at: Optional[datetime] = None
    collected_at: Optional[datetime] = None
    collected_by: Optional[uuid.UUID] = None
    card_data: Optional[Dict[str, Any]] = None
    production_metadata: Optional[Dict[str, Any]] = None
    collection_notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Transaction schemas
class TransactionBase(BaseModel):
    """Base schema for Transaction"""
    person_id: uuid.UUID
    location_id: uuid.UUID
    payment_method: Optional[PaymentMethod] = None
    payment_reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None

class TransactionCreate(TransactionBase):
    """Schema for creating Transaction"""
    items: List[TransactionItemCreate] = Field(..., min_items=1)

class TransactionUpdate(BaseModel):
    """Schema for updating Transaction"""
    status: Optional[TransactionStatus] = None
    payment_method: Optional[PaymentMethod] = None
    payment_reference: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None

class Transaction(TransactionBase):
    """Schema for Transaction response"""
    id: uuid.UUID
    transaction_number: str
    transaction_type: TransactionType
    status: TransactionStatus
    total_amount: Decimal
    processed_by: uuid.UUID
    processed_at: Optional[datetime] = None
    receipt_number: Optional[str] = None
    receipt_printed: bool = False
    receipt_printed_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Relationships
    items: List[TransactionItem] = []

    class Config:
        from_attributes = True


# POS System specific schemas
class PayableApplicationItem(BaseModel):
    """Schema for applications that can be paid"""
    id: uuid.UUID
    application_number: str
    application_type: str
    license_category: str
    status: str
    fees: List[Dict[str, Any]]
    total_amount: Decimal
    
    class Config:
        from_attributes = True

class PayableCardOrderItem(BaseModel):
    """Schema for card orders that can be paid"""
    id: uuid.UUID
    order_number: str
    card_type: str
    urgency_level: int
    fee_amount: Decimal
    application_number: str
    application_type: str
    
    class Config:
        from_attributes = True

class PersonPaymentSummary(BaseModel):
    """Summary of payable items for a person"""
    person_id: uuid.UUID
    person_name: str
    person_id_number: str
    payable_applications: List[PayableApplicationItem] = []
    payable_card_orders: List[PayableCardOrderItem] = []
    total_applications_amount: Decimal = Decimal('0.00')
    total_card_orders_amount: Decimal = Decimal('0.00')
    grand_total_amount: Decimal = Decimal('0.00')

class PaymentRequest(BaseModel):
    """Schema for processing payment"""
    person_id: uuid.UUID
    location_id: uuid.UUID
    application_ids: List[uuid.UUID] = []
    card_order_ids: List[uuid.UUID] = []
    payment_method: PaymentMethod
    payment_reference: Optional[str] = None
    notes: Optional[str] = None
    
    @validator('application_ids', 'card_order_ids')
    def at_least_one_item(cls, v, values):
        """Ensure at least one application or card order is selected"""
        application_ids = values.get('application_ids', [])
        if not v and not application_ids:
            raise ValueError('At least one application or card order must be selected for payment')
        return v

class PaymentResponse(BaseModel):
    """Response after processing payment"""
    transaction: Transaction
    receipt_url: Optional[str] = None
    updated_applications: List[uuid.UUID] = []
    updated_card_orders: List[uuid.UUID] = []
    success_message: str

class TransactionSummary(BaseModel):
    """Daily transaction summary"""
    date: datetime
    location_id: uuid.UUID
    total_transactions: int
    total_amount: Decimal
    payment_methods: Dict[str, Dict[str, Any]]

class ReceiptData(BaseModel):
    """Receipt data for printing"""
    transaction: Transaction
    person_name: str
    person_id_number: str
    location_name: str
    items_breakdown: List[Dict[str, Any]]
    payment_method_display: str
    receipt_footer: str = "Thank you for your payment. Keep this receipt as proof of payment." 