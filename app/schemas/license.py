"""
License Management Schemas for Madagascar License System
Pydantic models for license API requests and responses with independent card system
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from uuid import UUID

from app.models.enums import LicenseCategory, LicenseRestrictionCode, ProfessionalPermitCategory
from app.models.license import LicenseStatus


# License creation schemas
class LicenseCreateFromApplication(BaseModel):
    """Schema for creating a license from a completed application"""
    application_id: UUID = Field(..., description="Application ID that creates this license")
    license_category: LicenseCategory = Field(..., description="License category")
    restrictions: Optional[List[str]] = Field(default_factory=list, description="License restriction codes (01-07)")
    medical_restrictions: Optional[List[str]] = Field(default_factory=list, description="Medical restrictions")
    
    # Professional permit data (if applicable)
    has_professional_permit: bool = Field(False, description="Has professional driving permit")
    professional_permit_categories: Optional[List[str]] = Field(default_factory=list, description="Professional permit categories (P, D, G)")
    professional_permit_expiry: Optional[datetime] = Field(None, description="Professional permit expiry date")
    
    # Captured license data (for capture applications)
    captured_from_license_number: Optional[str] = Field(None, description="Original license number if captured")
    
    # Card ordering - manual process, not automatic
    order_card_immediately: bool = Field(False, description="Order card immediately after license creation (default: manual)")
    card_order_reference: Optional[str] = Field(None, description="Card order reference if ordering immediately")

    @validator('restrictions')
    def validate_restriction_codes(cls, v):
        """Validate restriction codes are valid"""
        if not v:
            return v
        
        valid_codes = [code.value for code in LicenseRestrictionCode]
        for code in v:
            if code not in valid_codes:
                raise ValueError(f"Invalid restriction code: {code}. Valid codes are: {valid_codes}")
        return v

    @validator('professional_permit_categories')
    def validate_professional_permit_categories(cls, v):
        """Validate professional permit categories"""
        if not v:
            return v
            
        valid_categories = [cat.value for cat in ProfessionalPermitCategory]
        for category in v:
            if category not in valid_categories:
                raise ValueError(f"Invalid professional permit category: {category}. Valid categories are: {valid_categories}")
        return v


class LicenseCreate(BaseModel):
    """Schema for direct license creation (administrative)"""
    person_id: UUID = Field(..., description="Person ID")
    license_category: LicenseCategory = Field(..., description="License category")
    issuing_location_id: UUID = Field(..., description="Issuing location")
    
    # License details
    restrictions: Optional[List[str]] = Field(default_factory=list, description="License restrictions")
    medical_restrictions: Optional[List[str]] = Field(default_factory=list, description="Medical restrictions")
    
    # Professional permit
    has_professional_permit: bool = Field(False, description="Has professional driving permit")
    professional_permit_categories: Optional[List[str]] = Field(default_factory=list, description="Professional permit categories")
    professional_permit_expiry: Optional[datetime] = Field(None, description="Professional permit expiry date")
    
    # License history
    previous_license_id: Optional[UUID] = Field(None, description="Previous license (for upgrades)")
    is_upgrade: bool = Field(False, description="Is this an upgrade")
    upgrade_from_category: Optional[LicenseCategory] = Field(None, description="Previous category if upgrade")
    
    # External references
    legacy_license_number: Optional[str] = Field(None, description="Legacy license number")
    captured_from_license_number: Optional[str] = Field(None, description="Captured license number")


# License update schemas
class LicenseStatusUpdate(BaseModel):
    """Schema for updating license status"""
    status: LicenseStatus = Field(..., description="New license status")
    reason: Optional[str] = Field(None, description="Reason for status change")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    # Suspension specific fields
    suspension_start_date: Optional[datetime] = Field(None, description="Suspension start date")
    suspension_end_date: Optional[datetime] = Field(None, description="Suspension end date")


class LicenseRestrictionsUpdate(BaseModel):
    """Schema for updating license restrictions"""
    restrictions: List[str] = Field(..., description="Updated license restrictions")
    medical_restrictions: List[str] = Field(default_factory=list, description="Updated medical restrictions")
    reason: str = Field(..., description="Reason for restriction update")
    notes: Optional[str] = Field(None, description="Additional notes")

    @validator('restrictions')
    def validate_restrictions(cls, v):
        """Validate restriction codes"""
        if not v:
            return v
            
        valid_codes = [code.value for code in LicenseRestrictionCode]
        for code in v:
            if code not in valid_codes:
                raise ValueError(f"Invalid restriction code: {code}")
        return v


class LicenseProfessionalPermitUpdate(BaseModel):
    """Schema for updating professional permit information"""
    has_professional_permit: bool = Field(..., description="Has professional driving permit")
    professional_permit_categories: List[str] = Field(default_factory=list, description="Professional permit categories")
    professional_permit_expiry: Optional[datetime] = Field(None, description="Professional permit expiry date")
    reason: str = Field(..., description="Reason for permit update")
    notes: Optional[str] = Field(None, description="Additional notes")

    @validator('professional_permit_categories')
    def validate_categories(cls, v, values):
        """Validate professional permit categories"""
        if values.get('has_professional_permit') and not v:
            raise ValueError("Professional permit categories required when has_professional_permit is True")
            
        if v:
            valid_categories = [cat.value for cat in ProfessionalPermitCategory]
            for category in v:
                if category not in valid_categories:
                    raise ValueError(f"Invalid professional permit category: {category}")
        return v


# Card ordering schemas for licenses
class LicenseCardOrderRequest(BaseModel):
    """Schema for ordering a card for existing licenses"""
    license_ids: List[UUID] = Field(..., min_items=1, description="License IDs to include on card")
    card_type: str = Field("STANDARD", description="Type of card (STANDARD, REPLACEMENT, DUPLICATE)")
    valid_for_years: int = Field(5, ge=1, le=10, description="Card validity period in years")
    
    # Locations
    production_location_id: Optional[UUID] = Field(None, description="Production location")
    collection_location_id: Optional[UUID] = Field(None, description="Collection location")
    
    # Additional info
    primary_license_id: Optional[UUID] = Field(None, description="Primary license for the card")
    replacement_reason: Optional[str] = Field(None, description="Reason for replacement (if applicable)")
    notes: Optional[str] = Field(None, description="Additional notes")

    @validator('primary_license_id')
    def validate_primary_license(cls, v, values):
        """Ensure primary license is in the license list"""
        if v and 'license_ids' in values and v not in values['license_ids']:
            raise ValueError("Primary license must be in the license list")
        return v


# Search and filtering schemas
class LicenseSearchFilters(BaseModel):
    """Search filters for licenses"""
    # Pagination
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(50, ge=1, le=500, description="Page size")
    
    # Basic filters
    person_id: Optional[UUID] = Field(None, description="Filter by person")
    license_category: Optional[LicenseCategory] = Field(None, description="Filter by category")
    status: Optional[LicenseStatus] = Field(None, description="Filter by status")
    
    # Location filters
    issuing_location_id: Optional[UUID] = Field(None, description="Filter by issuing location")
    
    # Date filters
    issued_after: Optional[datetime] = Field(None, description="Issued after date")
    issued_before: Optional[datetime] = Field(None, description="Issued before date")
    
    # Card status filters
    has_card: Optional[bool] = Field(None, description="Filter by card availability")
    card_ordered: Optional[bool] = Field(None, description="Filter by card order status")
    needs_card: Optional[bool] = Field(None, description="Filter licenses that need cards")
    
    # Professional permit filters
    has_professional_permit: Optional[bool] = Field(None, description="Filter by professional permit")
    
    # Search terms
    license_number: Optional[str] = Field(None, description="Search by license number")
    person_name: Optional[str] = Field(None, description="Search by person name")


# Response schemas
class LicenseResponse(BaseModel):
    """Basic license response schema"""
    id: UUID
    license_number: str
    person_id: UUID
    category: LicenseCategory
    status: LicenseStatus
    
    # Issue information
    issue_date: datetime
    issuing_location_id: UUID
    issued_by_user_id: UUID
    
    # Restrictions
    restrictions: List[str] = Field(default_factory=list)
    medical_restrictions: List[str] = Field(default_factory=list)
    
    # Professional permit
    has_professional_permit: bool
    professional_permit_categories: List[str] = Field(default_factory=list)
    professional_permit_expiry: Optional[datetime]
    
    # Status information
    status_changed_date: Optional[datetime]
    suspension_start_date: Optional[datetime]
    suspension_end_date: Optional[datetime]
    cancellation_date: Optional[datetime]
    
    # Card relationship
    card_ordered: bool
    card_order_date: Optional[datetime]
    card_order_reference: Optional[str]
    
    # License history
    is_upgrade: bool
    upgrade_from_category: Optional[LicenseCategory]
    previous_license_id: Optional[UUID]
    
    # External references
    legacy_license_number: Optional[str]
    captured_from_license_number: Optional[str]
    
    # Metadata
    created_at: datetime
    updated_at: datetime

    @validator('restrictions', 'medical_restrictions', 'professional_permit_categories', pre=True)
    def convert_none_to_empty_list(cls, v):
        """Convert None values to empty lists"""
        return v if v is not None else []
    
    class Config:
        from_attributes = True


class LicenseCardInfo(BaseModel):
    """Card information for license response"""
    card_id: UUID
    card_number: str
    card_type: str
    status: str
    is_active: bool
    is_primary_license: bool
    valid_from: datetime
    valid_until: datetime
    collected_date: Optional[datetime]
    
    class Config:
        from_attributes = True


class LicenseDetailResponse(LicenseResponse):
    """Detailed license response with related information"""
    # Person information
    person_name: Optional[str] = Field(None, description="Person's full name")
    person_surname: Optional[str] = Field(None, description="Person's surname")
    person_id_number: Optional[str] = Field(None, description="Person's ID number")
    
    # Location information
    issuing_location_name: Optional[str] = Field(None, description="Issuing location name")
    issuing_location_code: Optional[str] = Field(None, description="Issuing location code")
    
    # User information
    issued_by_user_name: Optional[str] = Field(None, description="User who issued license")
    status_changed_by_user_name: Optional[str] = Field(None, description="User who changed status")
    
    # Card information
    cards: List[LicenseCardInfo] = Field(default_factory=list, description="Cards containing this license")
    current_card: Optional[LicenseCardInfo] = Field(None, description="Current active card")
    
    # Status history
    status_history: List['LicenseStatusHistoryResponse'] = Field(default_factory=list)
    
    # License chain information
    previous_license_number: Optional[str] = Field(None, description="Previous license number if upgrade")
    subsequent_licenses: List['LicenseResponse'] = Field(default_factory=list, description="Subsequent licenses (upgrades)")
    
    # Compliance information
    sadc_compliance_verified: bool
    international_validity: bool
    vienna_convention_compliant: bool


class LicenseStatusHistoryResponse(BaseModel):
    """License status history response"""
    id: UUID
    from_status: Optional[LicenseStatus]
    to_status: LicenseStatus
    changed_at: datetime
    changed_by_user_name: Optional[str]
    reason: Optional[str]
    notes: Optional[str]
    system_initiated: bool
    suspension_start_date: Optional[datetime]
    suspension_end_date: Optional[datetime]
    
    class Config:
        from_attributes = True


class LicenseListResponse(BaseModel):
    """Paginated list of licenses"""
    licenses: List[LicenseResponse]
    total: int
    page: int
    size: int
    pages: int


class PersonLicensesSummary(BaseModel):
    """Summary of all licenses for a person"""
    person_id: UUID
    person_name: str
    
    # License counts
    total_licenses: int
    active_licenses: int
    suspended_licenses: int
    cancelled_licenses: int
    
    # Categories
    categories: List[LicenseCategory]
    
    # Latest license
    latest_license_date: datetime
    latest_license_number: str
    
    # Card status
    cards_ready_for_collection: int
    cards_near_expiry: int
    licenses_needing_cards: int
    total_cards: int


# Validation and utility schemas
class LicenseNumberValidationResponse(BaseModel):
    """License number validation response"""
    license_number: str
    is_valid: bool
    check_digit_valid: bool
    format_valid: bool
    exists: bool
    license_id: Optional[UUID] = None
    error_message: Optional[str] = None


class AuthorizationData(BaseModel):
    """Authorization data for license creation"""
    practical_test_passed: bool = Field(..., description="Practical test result")
    practical_test_date: datetime = Field(..., description="Practical test date")
    practical_test_score: Optional[int] = Field(None, ge=0, le=100, description="Practical test score")
    examiner_id: UUID = Field(..., description="Examiner who conducted test")
    examiner_notes: Optional[str] = Field(None, description="Examiner notes")
    
    # Restrictions identified during test
    restrictions_identified: List[str] = Field(default_factory=list, description="Restrictions identified during test")
    medical_restrictions_identified: List[str] = Field(default_factory=list, description="Medical restrictions identified")
    
    # Authorization decision
    authorized: bool = Field(..., description="Application authorized for license")
    authorization_notes: Optional[str] = Field(None, description="Authorization notes")


class RestrictionDetail(BaseModel):
    """Detailed restriction information"""
    code: str
    description: str
    category: str  # VISION, MEDICAL, VEHICLE, CONDITION
    is_mandatory: bool
    applies_to_categories: List[LicenseCategory]


class AvailableRestrictionsResponse(BaseModel):
    """Available license restrictions"""
    vision_restrictions: List[RestrictionDetail]
    medical_restrictions: List[RestrictionDetail]
    vehicle_restrictions: List[RestrictionDetail]
    condition_restrictions: List[RestrictionDetail]


# Statistics schemas
class LicenseStatistics(BaseModel):
    """License statistics for reporting"""
    # Total counts
    total_licenses: int
    active_licenses: int
    suspended_licenses: int
    cancelled_licenses: int
    
    # Category breakdown
    licenses_by_category: Dict[str, int]
    
    # Card status
    licenses_with_cards: int
    licenses_without_cards: int
    licenses_needing_card_orders: int
    
    # Recent activity
    licenses_issued_today: int
    licenses_issued_this_week: int
    licenses_issued_this_month: int
    
    # Professional permits
    licenses_with_professional_permits: int
    professional_permits_expiring_soon: int
    
    # Location statistics
    licenses_by_issuing_location: Dict[str, int]
    
    # Upgrade statistics
    total_upgrades: int
    upgrades_this_month: int


# Bulk operations
class BulkLicenseStatusUpdate(BaseModel):
    """Schema for bulk license status updates"""
    license_ids: List[UUID] = Field(..., min_items=1, description="License IDs to update")
    status: LicenseStatus = Field(..., description="New status")
    reason: str = Field(..., description="Reason for bulk update")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    # Suspension specific (if applicable)
    suspension_start_date: Optional[datetime] = Field(None, description="Suspension start date")
    suspension_end_date: Optional[datetime] = Field(None, description="Suspension end date")


class BulkCardOrderRequest(BaseModel):
    """Schema for bulk card ordering for licenses"""
    person_license_groups: List[Dict[str, Any]] = Field(..., description="Groups of licenses per person for card ordering")
    card_type: str = Field("STANDARD", description="Type of cards to order")
    valid_for_years: int = Field(5, ge=1, le=10, description="Card validity period")
    production_location_id: Optional[UUID] = Field(None, description="Production location")
    collection_location_id: Optional[UUID] = Field(None, description="Collection location")
    notes: Optional[str] = Field(None, description="Bulk order notes")


class BulkOperationResponse(BaseModel):
    """Response for bulk operations"""
    total_requested: int
    successful: int
    failed: int
    error_details: List[Dict[str, str]] = Field(default_factory=list)


# Forward reference for recursive model
LicenseDetailResponse.model_rebuild() 