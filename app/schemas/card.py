"""
Card Management Schemas for Madagascar License System
Pydantic models for independent card system with manual ordering workflow
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from uuid import UUID

from app.models.card import CardType, CardStatus, ProductionStatus
from app.models.enums import LicenseCategory


# Card Creation Schemas
class CardCreate(BaseModel):
    """Schema for creating a new card (manual ordering process)"""
    person_id: UUID = Field(..., description="Person ID for card assignment")
    license_ids: List[UUID] = Field(..., min_items=1, description="License IDs to include on card")
    card_type: CardType = Field(CardType.STANDARD, description="Type of card")
    
    # Card validity
    valid_for_years: int = Field(5, ge=1, le=10, description="Card validity period in years")
    
    # Production and collection locations
    production_location_id: Optional[UUID] = Field(None, description="Production location")
    collection_location_id: Optional[UUID] = Field(None, description="Collection location")
    
    # Additional information
    primary_license_id: Optional[UUID] = Field(None, description="Primary license for the card")
    replacement_reason: Optional[str] = Field(None, description="Reason for replacement (if applicable)")
    production_notes: Optional[str] = Field(None, description="Production notes")

    @validator('license_ids')
    def validate_license_ids(cls, v):
        """Ensure at least one license is provided"""
        if not v or len(v) == 0:
            raise ValueError("At least one license ID is required")
        return v

    @validator('primary_license_id')
    def validate_primary_license(cls, v, values):
        """Ensure primary license is in the license list"""
        if v and 'license_ids' in values and v not in values['license_ids']:
            raise ValueError("Primary license must be in the license list")
        return v


class TemporaryCardCreate(BaseModel):
    """Schema for creating temporary paper licenses"""
    person_id: UUID = Field(..., description="Person ID")
    license_ids: List[UUID] = Field(..., min_items=1, description="License IDs for temporary card")
    reason: str = Field(..., description="Reason for temporary card (lost, stolen, damaged)")
    valid_days: int = Field(90, ge=1, le=365, description="Validity period in days (default 90)")
    replacement_card_reference: Optional[str] = Field(None, description="Reference to permanent replacement card order")


class ApplicationCardRequest(BaseModel):
    """Schema for creating card from approved application"""
    application_id: UUID = Field(..., description="Application ID")
    card_type: CardType = Field(CardType.STANDARD, description="Type of card")
    valid_for_years: int = Field(5, ge=1, le=10, description="Card validity period in years")
    production_location_id: Optional[UUID] = Field(None, description="Production location")
    collection_location_id: Optional[UUID] = Field(None, description="Collection location")


# Card Update Schemas
class CardUpdate(BaseModel):
    """Schema for updating card information"""
    production_location_id: Optional[UUID] = Field(None, description="Production location")
    collection_location_id: Optional[UUID] = Field(None, description="Collection location")
    valid_until: Optional[datetime] = Field(None, description="Update validity period")
    production_notes: Optional[str] = Field(None, description="Production notes")
    collection_notes: Optional[str] = Field(None, description="Collection notes")


class CardStatusUpdate(BaseModel):
    """Schema for updating card status"""
    status: CardStatus = Field(..., description="New card status")
    production_status: Optional[ProductionStatus] = Field(None, description="Detailed production status")
    
    # Context information
    reason: Optional[str] = Field(None, description="Reason for status change")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    # Status-specific fields
    collection_reference: Optional[str] = Field(None, description="Collection reference (for COLLECTED status)")
    production_batch_id: Optional[str] = Field(None, description="Production batch ID")
    quality_check_passed: Optional[bool] = Field(None, description="Quality check result")
    quality_check_notes: Optional[str] = Field(None, description="Quality check notes")


class CardCancelRequest(BaseModel):
    """Schema for cancelling a card (when ordering replacement)"""
    reason: str = Field(..., description="Reason for cancellation")
    replacement_ordered: bool = Field(False, description="Is replacement already ordered")
    notes: Optional[str] = Field(None, description="Additional notes")


# License Association Management
class LicenseAssociation(BaseModel):
    """Schema for managing license-card associations"""
    license_id: UUID = Field(..., description="License ID")
    is_primary: bool = Field(False, description="Is this the primary license on the card")


class AddLicenseToCard(BaseModel):
    """Schema for adding license to existing card"""
    license_id: UUID = Field(..., description="License ID to add")
    is_primary: bool = Field(False, description="Set as primary license")
    reason: Optional[str] = Field(None, description="Reason for adding license")


# Card Search and Filtering
class CardSearchFilters(BaseModel):
    """Search filters for cards"""
    # Pagination
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(50, ge=1, le=500, description="Page size")
    
    # Basic filters
    person_id: Optional[UUID] = Field(None, description="Filter by person")
    card_type: Optional[CardType] = Field(None, description="Filter by card type")
    status: Optional[List[CardStatus]] = Field(None, description="Filter by card status")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    is_temporary: Optional[bool] = Field(None, description="Filter temporary cards")
    
    # Date filters
    created_after: Optional[datetime] = Field(None, description="Created after date")
    created_before: Optional[datetime] = Field(None, description="Created before date")
    ordered_after: Optional[datetime] = Field(None, description="Ordered after date")
    ordered_before: Optional[datetime] = Field(None, description="Ordered before date")
    expires_before: Optional[datetime] = Field(None, description="Expires before date")
    
    # Location filters
    production_location_id: Optional[UUID] = Field(None, description="Filter by production location")
    collection_location_id: Optional[UUID] = Field(None, description="Filter by collection location")
    
    # Production filters
    production_batch_id: Optional[str] = Field(None, description="Filter by production batch")
    production_status: Optional[List[ProductionStatus]] = Field(None, description="Filter by production status")
    quality_check_passed: Optional[bool] = Field(None, description="Filter by quality check result")
    
    # Search terms
    card_number: Optional[str] = Field(None, description="Search by card number")
    person_name: Optional[str] = Field(None, description="Search by person name")
    collection_reference: Optional[str] = Field(None, description="Search by collection reference")


# Response Schemas
class LicenseAssociationResponse(BaseModel):
    """Response schema for license associations"""
    license_id: UUID
    license_number: str
    category: LicenseCategory
    is_primary: bool
    added_at: datetime
    
    class Config:
        from_attributes = True


class CardResponse(BaseModel):
    """Basic card response schema"""
    id: UUID
    card_number: str
    person_id: UUID
    person_name: Optional[str] = Field(None, description="Person's full name")
    card_type: CardType
    status: CardStatus
    production_status: ProductionStatus
    
    # Validity
    valid_from: datetime
    valid_until: datetime
    is_active: bool
    is_temporary: bool
    
    # Production info
    ordered_date: Optional[datetime]
    production_start_date: Optional[datetime]
    production_completed_date: Optional[datetime]
    ready_for_collection_date: Optional[datetime]
    collected_date: Optional[datetime]
    
    # Locations
    production_location_id: Optional[UUID]
    collection_location_id: Optional[UUID]
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CardDetailResponse(CardResponse):
    """Detailed card response with license associations"""
    # Person information
    person_name: Optional[str] = Field(None, description="Person's full name")
    person_id_number: Optional[str] = Field(None, description="Person's ID number")
    
    # License associations
    licenses: List[LicenseAssociationResponse] = Field(default_factory=list)
    primary_license: Optional[LicenseAssociationResponse] = None
    
    # Production details
    production_batch_id: Optional[str]
    quality_control_passed: Optional[bool]
    quality_control_notes: Optional[str]
    
    # Collection details
    collection_reference: Optional[str]
    collection_notes: Optional[str]
    collected_by_user_id: Optional[UUID]
    
    # Location details
    production_location_name: Optional[str]
    collection_location_name: Optional[str]
    
    # Card details
    card_template: str
    security_features: Optional[Dict[str, Any]]
    
    # Temporary card specifics
    temporary_valid_days: Optional[int]
    replacement_card_id: Optional[UUID]
    
    # Cancellation info (if applicable)
    cancelled_at: Optional[datetime]
    cancellation_reason: Optional[str]
    cancelled_by_user_id: Optional[UUID]


class CardListResponse(BaseModel):
    """Paginated list of cards"""
    cards: List[CardResponse]
    total: int
    page: int
    size: int
    pages: int


class CardStatistics(BaseModel):
    """Card statistics response"""
    # Total counts
    total_cards: int
    active_cards: int
    inactive_cards: int
    temporary_cards: int
    
    # Status breakdown
    cards_by_status: Dict[str, int]
    cards_by_type: Dict[str, int]
    
    # Production statistics
    cards_in_production: int
    cards_ready_for_collection: int
    cards_collected_today: int
    cards_collected_this_week: int
    cards_collected_this_month: int
    
    # Quality metrics
    average_production_days: Optional[float]
    quality_check_pass_rate: Optional[float]
    
    # Upcoming expirations
    cards_expiring_soon: int  # Within 90 days
    cards_expiring_this_month: int


# Production and Collection Schemas
class ProductionBatchCreate(BaseModel):
    """Schema for creating production batch"""
    batch_id: str = Field(..., description="Batch identifier")
    production_location_id: UUID = Field(..., description="Production location")
    card_ids: List[UUID] = Field(..., description="Cards to include in batch")
    template_used: Optional[str] = Field(None, description="Card template")
    notes: Optional[str] = Field(None, description="Production notes")


class ProductionBatchUpdate(BaseModel):
    """Schema for updating production batch"""
    status: str = Field(..., description="Batch status")
    quality_check_passed: Optional[bool] = Field(None, description="Quality check result")
    quality_check_notes: Optional[str] = Field(None, description="Quality check notes")
    defect_count: int = Field(0, ge=0, description="Number of defective cards")
    notes: Optional[str] = Field(None, description="Production notes")


class CollectionRequest(BaseModel):
    """Schema for card collection process"""
    collection_reference: str = Field(..., description="Collection reference number")
    collected_by_person_name: str = Field(..., description="Name of person collecting")
    id_document_type: str = Field(..., description="ID document type")
    id_document_number: str = Field(..., description="ID document number")
    notes: Optional[str] = Field(None, description="Collection notes")


# Bulk Operations
class BulkCardStatusUpdate(BaseModel):
    """Schema for bulk card status updates"""
    card_ids: List[UUID] = Field(..., min_items=1, description="Card IDs to update")
    status: CardStatus = Field(..., description="New status")
    production_status: Optional[ProductionStatus] = Field(None, description="Production status")
    reason: Optional[str] = Field(None, description="Reason for update")
    notes: Optional[str] = Field(None, description="Update notes")
    production_batch_id: Optional[str] = Field(None, description="Production batch ID")


class BulkOperationResponse(BaseModel):
    """Response for bulk operations"""
    total_requested: int
    successful: int
    failed: int
    error_details: List[Dict[str, str]] = Field(default_factory=list)


# Validation Schemas
class CardNumberValidation(BaseModel):
    """Card number validation request"""
    card_number: str = Field(..., description="Card number to validate")


class CardNumberValidationResponse(BaseModel):
    """Card number validation response"""
    card_number: str
    is_valid: bool
    exists: bool
    card_id: Optional[UUID] = None
    error_message: Optional[str] = None


# Person Card Summary
class PersonCardSummary(BaseModel):
    """Summary of cards for a person"""
    person_id: UUID
    person_name: str
    
    # Card counts
    total_cards: int
    active_cards: int
    expired_cards: int
    cancelled_cards: int
    
    # Current status
    current_card_id: Optional[UUID]
    current_card_number: Optional[str]
    current_card_status: Optional[CardStatus]
    current_card_expires: Optional[datetime]
    
    # License information
    total_licenses_on_cards: int
    license_categories: List[str]
    
    # Collection status
    cards_ready_for_collection: int
    cards_near_expiry: int  # Within 90 days 