"""
License Management Schemas for Madagascar License System
Pydantic models for license API requests and responses
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date
from uuid import UUID

from app.models.enums import LicenseCategory, LicenseRestrictionCode, ProfessionalPermitCategory
from app.models.license import LicenseStatus, CardStatus


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
    
    # Card ordering
    order_card_immediately: bool = Field(True, description="Order card immediately after license creation")
    card_expiry_years: int = Field(5, ge=1, le=10, description="Card validity period in years")

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

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class LicenseCreate(BaseModel):
    """Schema for direct license creation (for manual/admin use)"""
    person_id: UUID = Field(..., description="License holder person ID")
    license_category: LicenseCategory = Field(..., description="License category")
    issuing_location_id: UUID = Field(..., description="Issuing location ID")
    
    # Optional fields
    restrictions: Optional[List[str]] = Field(default_factory=list, description="License restrictions")
    medical_restrictions: Optional[List[str]] = Field(default_factory=list, description="Medical restrictions")
    captured_from_license_number: Optional[str] = Field(None, description="Original license number if captured")
    
    # Professional permit
    has_professional_permit: bool = Field(False, description="Has professional driving permit")
    professional_permit_categories: Optional[List[str]] = Field(default_factory=list, description="Professional permit categories")
    professional_permit_expiry: Optional[datetime] = Field(None, description="Professional permit expiry date")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# License update schemas
class LicenseStatusUpdate(BaseModel):
    """Schema for updating license status"""
    status: LicenseStatus = Field(..., description="New license status")
    reason: Optional[str] = Field(None, max_length=200, description="Reason for status change")
    notes: Optional[str] = Field(None, description="Additional notes")
    
    # Suspension specific fields
    suspension_start_date: Optional[datetime] = Field(None, description="Suspension start date")
    suspension_end_date: Optional[datetime] = Field(None, description="Suspension end date")

    @validator('suspension_start_date', 'suspension_end_date')
    def validate_suspension_dates(cls, v, values):
        """Validate suspension dates are provided when status is SUSPENDED"""
        if values.get('status') == LicenseStatus.SUSPENDED:
            if 'suspension_start_date' in values and not values.get('suspension_start_date'):
                raise ValueError("Suspension start date required when suspending license")
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class LicenseRestrictionsUpdate(BaseModel):
    """Schema for updating license restrictions"""
    restrictions: List[str] = Field(..., description="Updated license restrictions")
    medical_restrictions: Optional[List[str]] = Field(default_factory=list, description="Updated medical restrictions")
    reason: Optional[str] = Field(None, description="Reason for restriction changes")


class LicenseProfessionalPermitUpdate(BaseModel):
    """Schema for updating professional permit information"""
    has_professional_permit: bool = Field(..., description="Has professional driving permit")
    professional_permit_categories: List[str] = Field(..., description="Professional permit categories")
    professional_permit_expiry: datetime = Field(..., description="Professional permit expiry date")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# Card management schemas
class CardCreate(BaseModel):
    """Schema for creating a new card for existing license"""
    license_id: UUID = Field(..., description="License ID")
    card_type: str = Field("STANDARD", description="Card type (STANDARD, DUPLICATE, REPLACEMENT)")
    expiry_years: int = Field(5, ge=1, le=10, description="Card validity period in years")
    replacement_reason: Optional[str] = Field(None, description="Reason for replacement (if applicable)")


class CardStatusUpdate(BaseModel):
    """Schema for updating card status"""
    status: CardStatus = Field(..., description="New card status")
    notes: Optional[str] = Field(None, description="Status update notes")
    collection_reference: Optional[str] = Field(None, description="Collection reference number")


# Response schemas
class LicenseCardResponse(BaseModel):
    """Response schema for license card information"""
    id: UUID
    card_number: str
    status: CardStatus
    card_type: str
    issue_date: datetime
    expiry_date: datetime
    valid_from: datetime
    is_current: bool
    is_expired: bool
    
    # Collection information
    ready_for_collection_date: Optional[datetime]
    collected_date: Optional[datetime]
    collection_reference: Optional[str]
    
    # Production information
    ordered_date: Optional[datetime]
    production_started: Optional[datetime]
    production_completed: Optional[datetime]
    
    # Card specifications
    card_template: str
    iso_compliance_version: str
    days_until_expiry: Optional[int]
    is_near_expiry: bool

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class LicenseStatusHistoryResponse(BaseModel):
    """Response schema for license status history"""
    id: UUID
    from_status: Optional[LicenseStatus]
    to_status: LicenseStatus
    changed_at: datetime
    reason: Optional[str]
    notes: Optional[str]
    system_initiated: bool
    
    # Suspension details
    suspension_start_date: Optional[datetime]
    suspension_end_date: Optional[datetime]

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class LicenseResponse(BaseModel):
    """Response schema for license information"""
    id: UUID
    license_number: str
    person_id: UUID
    created_from_application_id: UUID
    
    # License details
    category: LicenseCategory
    status: LicenseStatus
    issue_date: datetime
    issuing_location_id: UUID
    issued_by_user_id: UUID
    
    # Restrictions and conditions
    restrictions: List[str]
    medical_restrictions: List[str]
    
    # Professional permit
    has_professional_permit: bool
    professional_permit_categories: List[str]
    professional_permit_expiry: Optional[datetime]
    
    @validator('restrictions', pre=True)
    def validate_restrictions(cls, v):
        """Convert None to empty list for restrictions"""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return []
    
    @validator('medical_restrictions', pre=True)
    def validate_medical_restrictions(cls, v):
        """Convert None to empty list for medical restrictions"""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return []
    
    @validator('professional_permit_categories', pre=True)
    def validate_professional_permit_categories(cls, v):
        """Convert None to empty list for professional permit categories"""
        if v is None:
            return []
        if isinstance(v, list):
            return v
        return []
    
    # Status information
    status_changed_date: Optional[datetime]
    suspension_reason: Optional[str]
    suspension_start_date: Optional[datetime]
    suspension_end_date: Optional[datetime]
    cancellation_reason: Optional[str]
    cancellation_date: Optional[datetime]
    
    # History and references
    previous_license_id: Optional[UUID]
    is_upgrade: bool
    upgrade_from_category: Optional[LicenseCategory]
    captured_from_license_number: Optional[str]
    
    # Compliance
    sadc_compliance_verified: bool
    international_validity: bool
    vienna_convention_compliant: bool
    
    # Computed properties
    is_active: bool
    is_suspended: bool
    is_cancelled: bool
    
    # Current card information
    current_card: Optional[LicenseCardResponse]
    
    # Audit fields
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class LicenseDetailResponse(LicenseResponse):
    """Detailed license response with related data"""
    # All cards for this license
    cards: List[LicenseCardResponse]
    
    # Status history
    status_history: List[LicenseStatusHistoryResponse]
    
    # Person information (basic)
    person_name: Optional[str]
    person_surname: Optional[str]
    
    # Location information
    issuing_location_name: Optional[str]
    issuing_location_code: Optional[str]

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class LicenseListResponse(BaseModel):
    """Response schema for license list with pagination"""
    licenses: List[LicenseResponse]
    total: int
    page: int
    size: int
    pages: int

    class Config:
        from_attributes = True


class PersonLicensesSummary(BaseModel):
    """Summary of all licenses for a person"""
    person_id: UUID
    person_name: str
    total_licenses: int
    active_licenses: int
    suspended_licenses: int
    cancelled_licenses: int
    
    # License categories held
    categories: List[LicenseCategory]
    
    # Recent activity
    latest_license_date: Optional[datetime]
    latest_license_number: Optional[str]
    
    # Current cards
    cards_ready_for_collection: int
    cards_near_expiry: int

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


# License number validation
class LicenseNumberValidation(BaseModel):
    """Schema for license number validation"""
    license_number: str = Field(..., min_length=11, max_length=15, description="License number to validate")


class LicenseNumberValidationResponse(BaseModel):
    """Response for license number validation"""
    license_number: str
    is_valid: bool
    error_message: Optional[str]
    
    # Breakdown if valid
    province_code: Optional[str]
    location_code: Optional[str]
    sequence_number: Optional[int]
    check_digit: Optional[int]


# Search and filter schemas
class LicenseSearchFilters(BaseModel):
    """Schema for license search filters"""
    license_number: Optional[str] = Field(None, description="Partial license number search")
    person_id: Optional[UUID] = Field(None, description="Filter by person ID")
    category: Optional[LicenseCategory] = Field(None, description="Filter by license category")
    status: Optional[LicenseStatus] = Field(None, description="Filter by license status")
    issuing_location_id: Optional[UUID] = Field(None, description="Filter by issuing location")
    
    # Date filters
    issued_after: Optional[date] = Field(None, description="Filter by issue date (after)")
    issued_before: Optional[date] = Field(None, description="Filter by issue date (before)")
    
    # Professional permit filters
    has_professional_permit: Optional[bool] = Field(None, description="Filter by professional permit")
    
    # Pagination
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Page size")

    class Config:
        json_encoders = {
            date: lambda v: v.isoformat() if v else None
        }


# Bulk operations
class BulkLicenseStatusUpdate(BaseModel):
    """Schema for bulk license status updates"""
    license_ids: List[UUID] = Field(..., min_items=1, max_items=100, description="License IDs to update")
    status: LicenseStatus = Field(..., description="New status for all licenses")
    reason: str = Field(..., min_length=3, max_length=200, description="Reason for bulk update")
    notes: Optional[str] = Field(None, description="Additional notes")


class BulkOperationResponse(BaseModel):
    """Response schema for bulk operations"""
    total_requested: int
    successful: int
    failed: int
    error_details: List[Dict[str, Any]]


# Statistics and reports
class LicenseStatistics(BaseModel):
    """License statistics response"""
    total_licenses: int
    active_licenses: int
    suspended_licenses: int
    cancelled_licenses: int
    
    # By category
    by_category: Dict[str, int]
    
    # By location
    by_location: Dict[str, int]
    
    # Recent activity
    issued_this_month: int
    issued_this_year: int
    
    # Card statistics
    cards_pending_collection: int
    cards_near_expiry: int


# Restriction management schemas
class RestrictionDetail(BaseModel):
    """Detailed information about a license restriction"""
    code: str = Field(..., description="Restriction code (01-07)")
    description: str = Field(..., description="Full description of restriction")
    category: str = Field(..., description="Category: DRIVER or VEHICLE")
    display_name: str = Field(..., description="Short display name")


class AvailableRestrictionsResponse(BaseModel):
    """Response for available restriction codes"""
    restrictions: List[RestrictionDetail]
    total: int
    
    
class AuthorizationData(BaseModel):
    """Schema for authorization data when creating license from authorized application"""
    restrictions: List[str] = Field(default_factory=list, description="Restriction codes from test results")
    medical_restrictions: List[str] = Field(default_factory=list, description="Medical restrictions")
    professional_permit: Dict[str, Any] = Field(default_factory=dict, description="Professional permit data")
    captured_license_data: Dict[str, Any] = Field(default_factory=dict, description="Captured license data if applicable")
    test_results: Dict[str, Any] = Field(default_factory=dict, description="Test results data")

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