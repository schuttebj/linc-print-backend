"""
Pydantic schemas for Application Management in Madagascar License System
Handles validation and serialization for all application-related data structures
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime, date
from decimal import Decimal
import uuid

from app.models.application import (
    ApplicationType, ApplicationStatus, LicenseCategory, 
    BiometricDataType, MedicalCertificateStatus, ParentalConsentStatus,
    TestAttemptType, TestResult, PaymentStatus
)


# Base schemas
class ApplicationBase(BaseModel):
    """Base schema for Application"""
    application_type: ApplicationType
    person_id: uuid.UUID
    license_categories: List[str] = Field(..., description="Array of license categories (e.g., ['A', 'B'])")
    location_id: uuid.UUID
    assigned_to_user_id: Optional[uuid.UUID] = None
    priority: int = Field(default=1, ge=1, le=3, description="Processing priority (1=normal, 2=urgent, 3=emergency)")
    
    # Requirements
    medical_certificate_required: bool = False
    parental_consent_required: bool = False
    requires_existing_license: bool = False
    existing_license_number: Optional[str] = None
    
    # Associated applications
    parent_application_id: Optional[uuid.UUID] = None
    
    # Notes
    applicant_notes: Optional[str] = None
    
    # Special flags
    is_urgent: bool = False
    has_special_requirements: bool = False
    special_requirements_notes: Optional[str] = None
    
    # Temporary license specific
    is_temporary_license: bool = False
    temporary_license_validity_days: Optional[int] = Field(default=90, ge=1, le=365)
    temporary_license_reason: Optional[str] = None

    @validator('license_categories')
    def validate_license_categories(cls, v):
        """Validate license categories"""
        valid_categories = [cat.value for cat in LicenseCategory]
        for category in v:
            if category not in valid_categories:
                raise ValueError(f"Invalid license category: {category}")
        return v

    @validator('existing_license_number')
    def validate_existing_license_number(cls, v, values):
        """Validate existing license number is provided when required"""
        if values.get('requires_existing_license') and not v:
            raise ValueError("Existing license number required when requires_existing_license is True")
        return v


class ApplicationCreate(ApplicationBase):
    """Schema for creating new applications"""
    pass


class ApplicationUpdate(BaseModel):
    """Schema for updating applications"""
    assigned_to_user_id: Optional[uuid.UUID] = None
    priority: Optional[int] = Field(None, ge=1, le=3)
    medical_certificate_required: Optional[bool] = None
    parental_consent_required: Optional[bool] = None
    requires_existing_license: Optional[bool] = None
    existing_license_number: Optional[str] = None
    applicant_notes: Optional[str] = None
    processing_notes: Optional[str] = None
    is_urgent: Optional[bool] = None
    has_special_requirements: Optional[bool] = None
    special_requirements_notes: Optional[str] = None
    temporary_license_reason: Optional[str] = None
    
    # Biometric capture status
    photo_captured: Optional[bool] = None
    signature_captured: Optional[bool] = None
    fingerprint_captured: Optional[bool] = None


class ApplicationSearch(BaseModel):
    """Schema for application search parameters"""
    application_number: Optional[str] = None
    person_id: Optional[uuid.UUID] = None
    application_type: Optional[ApplicationType] = None
    status: Optional[ApplicationStatus] = None
    location_id: Optional[uuid.UUID] = None
    assigned_to_user_id: Optional[uuid.UUID] = None
    license_categories: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    is_urgent: Optional[bool] = None
    is_temporary_license: Optional[bool] = None
    
    # Sorting
    sort_by: Optional[str] = Field(default="application_date", description="Field to sort by")
    sort_order: Optional[str] = Field(default="desc", regex="^(asc|desc)$", description="Sort order")


class ApplicationInDBBase(ApplicationBase):
    """Base schema for application in database"""
    id: uuid.UUID
    application_number: str
    status: ApplicationStatus
    application_date: datetime
    submitted_date: Optional[datetime] = None
    target_completion_date: Optional[datetime] = None
    actual_completion_date: Optional[datetime] = None
    
    # Requirements status
    medical_certificate_status: MedicalCertificateStatus
    medical_certificate_file_path: Optional[str] = None
    medical_certificate_verified_by: Optional[uuid.UUID] = None
    medical_certificate_verified_at: Optional[datetime] = None
    
    parental_consent_status: ParentalConsentStatus
    parental_consent_file_path: Optional[str] = None
    
    existing_license_verified: bool = False
    
    # Processing details
    processing_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
    required_documents: Optional[Dict[str, Any]] = None
    
    # Biometric capture status
    photo_captured: bool = False
    signature_captured: bool = False
    fingerprint_captured: bool = False
    
    # Draft handling
    draft_data: Optional[Dict[str, Any]] = None
    draft_expires_at: Optional[datetime] = None
    
    # Printing and collection
    print_ready: bool = False
    print_job_id: Optional[uuid.UUID] = None
    collection_notice_sent: bool = False
    collection_notice_sent_at: Optional[datetime] = None
    
    # Audit fields
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None

    class Config:
        orm_mode = True


class Application(ApplicationInDBBase):
    """Schema for returning application data"""
    pass


class ApplicationWithDetails(Application):
    """Schema for application with related data"""
    person: Optional[Dict[str, Any]] = None
    location: Optional[Dict[str, Any]] = None
    assigned_to_user: Optional[Dict[str, Any]] = None
    biometric_data: Optional[List[Dict[str, Any]]] = None
    test_attempts: Optional[List[Dict[str, Any]]] = None
    fees: Optional[List[Dict[str, Any]]] = None
    documents: Optional[List[Dict[str, Any]]] = None
    status_history: Optional[List[Dict[str, Any]]] = None
    child_applications: Optional[List[Dict[str, Any]]] = None


# Application Fee schemas
class ApplicationFeeBase(BaseModel):
    """Base schema for Application Fee"""
    application_id: uuid.UUID
    fee_type: str
    amount: Decimal = Field(..., ge=0)
    currency: str = Field(default="MGA")


class ApplicationFeeCreate(ApplicationFeeBase):
    """Schema for creating application fee"""
    pass


class ApplicationFeeInDB(ApplicationFeeBase):
    """Schema for application fee in database"""
    id: uuid.UUID
    payment_status: PaymentStatus = PaymentStatus.PENDING
    payment_date: Optional[datetime] = None
    payment_method: Optional[str] = None
    payment_reference: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class ApplicationFee(ApplicationFeeInDB):
    """Schema for returning application fee data"""
    pass


# Statistics schemas
class ApplicationStatistics(BaseModel):
    """Schema for application statistics"""
    total_applications: int
    status_breakdown: Dict[str, int]
    type_breakdown: Dict[str, int]
    recent_applications_30_days: int