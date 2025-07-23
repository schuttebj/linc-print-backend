"""
Pydantic schemas for Application Management in Madagascar License System
Handles validation and serialization for all application-related data structures
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime, date
from decimal import Decimal
import uuid

from app.models.enums import (
    LicenseCategory, ApplicationType, ApplicationStatus,
    BiometricDataType, MedicalCertificateStatus, ParentalConsentStatus,
    TestAttemptType, TestResult, PaymentStatus, ReplacementReason,
    ProfessionalPermitCategory, DriverRestrictionCode, VehicleRestrictionCode
)


# Medical Information Schemas for comprehensive health assessment
class VisionTestData(BaseModel):
    """Vision test data for driving fitness assessment"""
    visual_acuity_right_eye: str = Field(..., description="e.g., '20/20', '6/6'")
    visual_acuity_left_eye: str = Field(..., description="e.g., '20/20', '6/6'")
    visual_acuity_binocular: str = Field(..., description="e.g., '20/20', '6/6'")
    corrective_lenses_required: bool = False
    corrective_lenses_type: Optional[str] = Field(None, description="GLASSES, CONTACT_LENSES, BOTH")
    
    color_vision_normal: bool = True
    color_vision_deficiency_type: Optional[str] = Field(None, description="RED_GREEN, BLUE_YELLOW, COMPLETE, NONE")
    
    visual_field_normal: bool = True
    visual_field_horizontal_degrees: Optional[int] = None
    visual_field_vertical_degrees: Optional[int] = None
    visual_field_defects: Optional[str] = None
    
    night_vision_adequate: bool = True
    contrast_sensitivity_adequate: bool = True
    glare_sensitivity_issues: bool = False
    
    vision_meets_standards: bool = True
    vision_restrictions: List[str] = Field(default_factory=list)


class MedicalConditions(BaseModel):
    """Medical conditions assessment for driving fitness"""
    epilepsy: bool = False
    epilepsy_controlled: bool = False
    epilepsy_medication: Optional[str] = None
    seizures_last_occurrence: Optional[str] = None
    
    mental_illness: bool = False
    mental_illness_type: Optional[str] = None
    mental_illness_controlled: bool = False
    mental_illness_medication: Optional[str] = None
    
    heart_condition: bool = False
    heart_condition_type: Optional[str] = None
    blood_pressure_controlled: bool = True
    
    diabetes: bool = False
    diabetes_type: Optional[str] = Field(None, description="TYPE_1, TYPE_2, GESTATIONAL")
    diabetes_controlled: bool = False
    diabetes_medication: Optional[str] = None
    
    alcohol_dependency: bool = False
    drug_dependency: bool = False
    substance_treatment_program: bool = False
    
    fainting_episodes: bool = False
    dizziness_episodes: bool = False
    muscle_coordination_issues: bool = False
    
    medications_affecting_driving: bool = False
    current_medications: List[str] = Field(default_factory=list)
    
    medically_fit_to_drive: bool = True
    conditions_requiring_monitoring: List[str] = Field(default_factory=list)


class PhysicalAssessment(BaseModel):
    """Physical assessment for driving fitness"""
    hearing_adequate: bool = True
    hearing_aid_required: bool = False
    
    limb_disabilities: bool = False
    limb_disability_details: Optional[str] = None
    adaptive_equipment_required: bool = False
    adaptive_equipment_type: List[str] = Field(default_factory=list)
    
    mobility_impairment: bool = False
    mobility_aid_required: bool = False
    mobility_aid_type: Optional[str] = None
    
    reaction_time_adequate: bool = True
    
    physically_fit_to_drive: bool = True
    physical_restrictions: List[str] = Field(default_factory=list)


class MedicalInformation(BaseModel):
    """Comprehensive medical assessment for license application"""
    vision_test: VisionTestData
    medical_conditions: MedicalConditions
    physical_assessment: PhysicalAssessment
    
    medical_clearance: bool = Field(..., description="Overall medical clearance for driving")
    medical_restrictions: List[str] = Field(default_factory=list, description="Any restrictions to be placed on license")
    medical_notes: Optional[str] = None
    examined_by: Optional[str] = Field(None, description="Name of medical examiner")
    examination_date: Optional[date] = None


# License Capture Schemas for DRIVERS_LICENSE_CAPTURE and LEARNERS_PERMIT_CAPTURE
class CapturedLicense(BaseModel):
    """Individual captured license data"""
    id: str = Field(..., description="Temporary ID for form management")
    license_number: Optional[str] = Field(None, description="License number (optional)")
    license_category: str = Field(..., description="Single license category as string")
    issue_date: str = Field(..., description="License issue date")
    restrictions: Optional[Union[List[str], Dict[str, List[str]]]] = Field(default_factory=dict, description="License restrictions - new structured format: {'driver_restrictions': ['01'], 'vehicle_restrictions': ['00']} or old list format")
    verified: bool = Field(False, description="Whether license has been verified by clerk")
    verification_notes: Optional[str] = Field(None, description="Clerk verification notes")
    
    @validator('license_category')
    def validate_license_category(cls, v):
        """Validate that license_category is a valid LicenseCategory enum value"""
        if v not in [category.value for category in LicenseCategory]:
            raise ValueError(f"Invalid license category: {v}")
        return v
    
    @validator('restrictions')
    def validate_restriction_codes(cls, v):
        """Validate restriction codes in both old and new formats"""
        if not v:
            return {}
        
        # Handle both old format (list) and new format (dict) for backward compatibility
        if isinstance(v, list):
            # Old format - validate as combined codes
            valid_driver_codes = [code.value for code in DriverRestrictionCode]
            valid_vehicle_codes = [code.value for code in VehicleRestrictionCode]
            valid_codes = valid_driver_codes + valid_vehicle_codes
            
            for code in v:
                if code not in valid_codes:
                    raise ValueError(f"Invalid restriction code: {code}. Valid codes are: {valid_codes}")
                    
        elif isinstance(v, dict):
            # New format - validate separately
            driver_restrictions = v.get('driver_restrictions', [])
            vehicle_restrictions = v.get('vehicle_restrictions', [])
            
            valid_driver_codes = [code.value for code in DriverRestrictionCode]
            valid_vehicle_codes = [code.value for code in VehicleRestrictionCode]
            
            for code in driver_restrictions:
                if code not in valid_driver_codes:
                    raise ValueError(f"Invalid driver restriction code: {code}. Valid codes are: {valid_driver_codes}")
                    
            for code in vehicle_restrictions:
                if code not in valid_vehicle_codes:
                    raise ValueError(f"Invalid vehicle restriction code: {code}. Valid codes are: {valid_vehicle_codes}")
        
        return v


class LicenseCaptureData(BaseModel):
    """License capture data for capture applications"""
    captured_licenses: List[CapturedLicense] = Field(default_factory=list, description="List of captured licenses")
    application_type: str = Field(..., description="Must be DRIVERS_LICENSE_CAPTURE or LEARNERS_PERMIT_CAPTURE")
    
    @validator('application_type')
    def validate_capture_application_type(cls, v):
        # Convert to string if it's an enum
        if hasattr(v, 'value'):
            v = v.value
        # Validate that it's a valid capture application type
        valid_types = ['DRIVERS_LICENSE_CAPTURE', 'LEARNERS_PERMIT_CAPTURE']
        if v not in valid_types:
            raise ValueError(f'application_type must be one of {valid_types}')
        return v


# Base schemas
class ApplicationBase(BaseModel):
    """Base schema for Application"""
    application_type: ApplicationType
    person_id: uuid.UUID
    license_category: LicenseCategory = Field(..., description="Single license category for this application")
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
    is_on_hold: bool = False
    has_special_requirements: bool = False
    special_requirements_notes: Optional[str] = None
    
    # Replacement specific
    replacement_reason: Optional[ReplacementReason] = None
    
    # Professional permit specific
    professional_permit_categories: Optional[List[ProfessionalPermitCategory]] = Field(default_factory=list, description="Selected professional permit categories")
    professional_permit_previous_refusal: bool = False
    professional_permit_refusal_details: Optional[str] = None
    
    # Temporary license specific
    is_temporary_license: bool = False
    temporary_license_validity_days: Optional[int] = Field(default=90, ge=1, le=365)
    temporary_license_reason: Optional[str] = None

    @validator('replacement_reason')
    def validate_replacement_reason(cls, v, values):
        """Validate replacement reason is provided for REPLACEMENT applications"""
        if values.get('application_type') == ApplicationType.REPLACEMENT and not v:
            raise ValueError("Replacement reason required for REPLACEMENT applications")
        return v

    @validator('existing_license_number')
    def validate_existing_license_number(cls, v, values):
        """Validate existing license number is provided when required"""
        if values.get('requires_existing_license') and not v:
            raise ValueError("Existing license number required when requires_existing_license is True")
        return v

    @validator('license_category', pre=True)
    def validate_license_category(cls, v):
        """Convert string license category to LicenseCategory enum"""
        if isinstance(v, str):
            # Find the enum member by value
            for category in LicenseCategory:
                if category.value == v:
                    return category
            raise ValueError(f"Invalid license category value: {v}")
        elif isinstance(v, LicenseCategory):
            return v
        else:
            raise ValueError(f"license_category must be string or LicenseCategory enum, got {type(v)}")
        return v


class ApplicationCreate(ApplicationBase):
    """Schema for creating new applications"""
    # Medical information for comprehensive health assessment
    medical_information: Optional[MedicalInformation] = None
    # License capture data for DRIVERS_LICENSE_CAPTURE and LEARNERS_PERMIT_CAPTURE applications
    license_capture: Optional[LicenseCaptureData] = None


class ApplicationUpdate(BaseModel):
    """Schema for updating applications"""
    assigned_to_user_id: Optional[uuid.UUID] = None
    priority: Optional[int] = Field(None, ge=1, le=3)
    test_result: Optional[TestResult] = None  # Test result for NEW_LICENSE and LEARNERS_PERMIT applications
    medical_certificate_required: Optional[bool] = None
    parental_consent_required: Optional[bool] = None
    requires_existing_license: Optional[bool] = None
    existing_license_number: Optional[str] = None
    applicant_notes: Optional[str] = None
    processing_notes: Optional[str] = None
    is_urgent: Optional[bool] = None
    is_on_hold: Optional[bool] = None
    has_special_requirements: Optional[bool] = None
    special_requirements_notes: Optional[str] = None
    replacement_reason: Optional[ReplacementReason] = None
    
    # Professional permit specific
    professional_permit_categories: Optional[List[ProfessionalPermitCategory]] = None
    professional_permit_previous_refusal: Optional[bool] = None
    professional_permit_refusal_details: Optional[str] = None
    
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
    license_category: Optional[LicenseCategory] = None
    replacement_reason: Optional[ReplacementReason] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    is_urgent: Optional[bool] = None
    is_on_hold: Optional[bool] = None
    is_temporary_license: Optional[bool] = None
    
    # Sorting
    sort_by: Optional[str] = Field(default="application_date", description="Field to sort by")
    sort_order: Optional[str] = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")


class ApplicationInDBBase(ApplicationBase):
    """Base schema for application in database"""
    id: uuid.UUID
    application_number: str
    status: ApplicationStatus
    test_result: Optional[TestResult] = None  # Test result for NEW_LICENSE and LEARNERS_PERMIT applications
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
    
    # Approval tracking
    approved_by_user_id: Optional[uuid.UUID] = None
    approved_at_location_id: Optional[uuid.UUID] = None
    approval_date: Optional[datetime] = None
    approval_outcome: Optional[TestResult] = None
    identified_restrictions: Optional[Dict[str, Any]] = None
    
    # Biometric capture status
    photo_captured: bool = False
    signature_captured: bool = False
    fingerprint_captured: bool = False
    
    # Payment stage tracking (NEW FIELDS FOR STAGED PAYMENTS)
    test_payment_completed: bool = False
    test_payment_date: Optional[datetime] = None
    card_payment_completed: bool = False
    card_payment_date: Optional[datetime] = None
    current_payment_stage: Optional[str] = None
    
    # Card ordering status
    card_ordered: bool = False
    card_order_date: Optional[datetime] = None
    card_order_id: Optional[uuid.UUID] = None
    includes_temporary_license: bool = False
    
    # Medical information
    medical_information: Optional[Dict[str, Any]] = None
    
    # License capture data
    license_capture: Optional[Dict[str, Any]] = None
    
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
    
    # Computed fields
    can_order_card: bool = Field(default=False, description="Whether card can be ordered for this application")

    class Config:
        from_attributes = True
        
    @validator('can_order_card', always=True)
    def compute_can_order_card(cls, v, values):
        """Compute if card can be ordered for this application"""
        application_type = values.get('application_type')
        status = values.get('status') 
        test_result = values.get('test_result')
        card_payment_completed = values.get('card_payment_completed', False)
        
        if application_type == ApplicationType.RENEWAL:
            # Renewals: card can be ordered when application is approved (includes payment)
            return status == ApplicationStatus.APPROVED
        
        elif application_type == ApplicationType.NEW_LICENSE:
            # New licenses: card can only be ordered after passing test, paying card fee, and being approved
            return (test_result == TestResult.PASSED and 
                   status == ApplicationStatus.APPROVED and
                   card_payment_completed)
        
        elif application_type == ApplicationType.REPLACEMENT:
            # Replacements: card can be ordered when approved (includes payment)
            return status == ApplicationStatus.APPROVED
        
        elif application_type == ApplicationType.LEARNERS_PERMIT:
            # Learners permits: card can be ordered when approved
            return status == ApplicationStatus.APPROVED
        
        return False


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





# Statistics schemas
class ApplicationStatistics(BaseModel):
    """Schema for application statistics"""
    total_applications: int
    status_breakdown: Dict[str, int]
    type_breakdown: Dict[str, int]
    recent_applications_30_days: int


# Biometric Data schemas
class ApplicationBiometricDataBase(BaseModel):
    """Base schema for Application Biometric Data"""
    application_id: uuid.UUID
    data_type: BiometricDataType
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_format: Optional[str] = None
    capture_device: Optional[str] = None
    capture_software: Optional[str] = None
    capture_metadata: Optional[Dict[str, Any]] = None
    quality_score: Optional[Decimal] = None
    quality_metrics: Optional[Dict[str, Any]] = None
    is_processed: Optional[bool] = False
    is_verified: Optional[bool] = False
    processing_notes: Optional[str] = None
    captured_by: Optional[uuid.UUID] = None
    verified_by: Optional[uuid.UUID] = None
    verified_at: Optional[datetime] = None


class ApplicationBiometricDataCreate(ApplicationBiometricDataBase):
    """Schema for creating biometric data"""
    pass


class ApplicationBiometricDataUpdate(BaseModel):
    """Schema for updating biometric data"""
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    file_format: Optional[str] = None
    capture_device: Optional[str] = None
    capture_software: Optional[str] = None
    capture_metadata: Optional[Dict[str, Any]] = None
    quality_score: Optional[Decimal] = None
    quality_metrics: Optional[Dict[str, Any]] = None
    is_processed: Optional[bool] = None
    is_verified: Optional[bool] = None
    processing_notes: Optional[str] = None
    verified_by: Optional[uuid.UUID] = None
    verified_at: Optional[datetime] = None


class ApplicationBiometricDataInDB(ApplicationBiometricDataBase):
    """Schema for biometric data in database"""
    id: uuid.UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None
    is_active: Optional[bool] = True
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True


class ApplicationBiometricData(ApplicationBiometricDataInDB):
    """Schema for returning biometric data"""
    pass


# Test Attempt schemas
class ApplicationTestAttemptBase(BaseModel):
    """Base schema for Application Test Attempt"""
    application_id: uuid.UUID
    test_type: TestAttemptType
    attempt_number: int = 1
    scheduled_date: Optional[datetime] = None
    test_location_id: Optional[uuid.UUID] = None
    fee_amount: Decimal = Field(..., ge=0)


class ApplicationTestAttemptCreate(ApplicationTestAttemptBase):
    """Schema for creating test attempt"""
    pass


class ApplicationTestAttemptUpdate(BaseModel):
    """Schema for updating test attempt"""
    scheduled_date: Optional[datetime] = None
    actual_date: Optional[datetime] = None
    examiner_id: Optional[uuid.UUID] = None
    test_result: Optional[TestResult] = None
    score: Optional[Decimal] = None
    fee_paid: Optional[bool] = None
    payment_reference: Optional[str] = None
    test_duration_minutes: Optional[int] = None
    questions_total: Optional[int] = None
    questions_correct: Optional[int] = None
    result_notes: Optional[str] = None


class ApplicationTestAttemptInDB(ApplicationTestAttemptBase):
    """Schema for test attempt in database"""
    id: uuid.UUID
    actual_date: Optional[datetime] = None
    examiner_id: Optional[uuid.UUID] = None
    test_result: Optional[TestResult] = None
    score: Optional[Decimal] = None
    fee_paid: bool = False
    payment_reference: Optional[str] = None
    test_duration_minutes: Optional[int] = None
    questions_total: Optional[int] = None
    questions_correct: Optional[int] = None
    pass_threshold: Optional[Decimal] = None
    result_notes: Optional[str] = None
    failure_reasons: Optional[Dict[str, Any]] = None
    learners_permit_issued: bool = False
    learners_permit_number: Optional[str] = None
    learners_permit_expiry: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApplicationTestAttempt(ApplicationTestAttemptInDB):
    """Schema for returning test attempt data"""
    pass





# Application Document schemas
class ApplicationDocumentBase(BaseModel):
    """Base schema for Application Document"""
    application_id: uuid.UUID
    document_type: str
    document_name: str
    file_path: str
    file_size: Optional[int] = None
    mime_type: Optional[str] = None


class ApplicationDocumentCreate(ApplicationDocumentBase):
    """Schema for creating application document"""
    pass


class ApplicationDocumentUpdate(BaseModel):
    """Schema for updating application document"""
    document_name: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    is_verified: Optional[bool] = None
    verified_by: Optional[uuid.UUID] = None
    verification_notes: Optional[str] = None
    expiry_date: Optional[datetime] = None
    issuing_authority: Optional[str] = None
    document_number: Optional[str] = None


class ApplicationDocumentInDB(ApplicationDocumentBase):
    """Schema for application document in database"""
    id: uuid.UUID
    uploaded_by: uuid.UUID
    upload_date: datetime
    is_verified: bool = False
    verified_by: Optional[uuid.UUID] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None
    expiry_date: Optional[datetime] = None
    issuing_authority: Optional[str] = None
    document_number: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ApplicationDocument(ApplicationDocumentInDB):
    """Schema for returning application document data"""
    pass


# Fee Structure schemas
class FeeStructureBase(BaseModel):
    """Base schema for Fee Structure"""
    fee_type: str
    display_name: str
    description: Optional[str] = None
    amount: Decimal = Field(..., ge=0)
    currency: str = Field(default="MGA")
    applies_to_categories: Optional[List[str]] = None
    applies_to_application_types: Optional[List[str]] = None
    is_mandatory: bool = True
    is_active: bool = True


class FeeStructureCreate(FeeStructureBase):
    """Schema for creating fee structure"""
    pass


class FeeStructureUpdate(BaseModel):
    """Schema for updating fee structure"""
    display_name: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = Field(None, ge=0)
    applies_to_categories: Optional[List[str]] = None
    applies_to_application_types: Optional[List[str]] = None
    is_mandatory: Optional[bool] = None
    is_active: Optional[bool] = None
    effective_until: Optional[datetime] = None


class FeeStructureInDB(FeeStructureBase):
    """Schema for fee structure in database"""
    id: uuid.UUID
    effective_from: datetime
    effective_until: Optional[datetime] = None
    created_by: uuid.UUID
    last_updated_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class FeeStructure(FeeStructureInDB):
    """Schema for returning fee structure data"""
    pass