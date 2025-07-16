"""
Application Management Models for Madagascar License System
Implements the complete driver's license application workflow based on ATT/CIM process

Features:
- 6 Application types: New, Learner's Permit, Renewal, Replacement, Temporary, IDP
- SADC License categories: A1/A2/A (Motorcycles), B1/B/B2/BE (Light Vehicles), C1/C/C1E/CE (Heavy Goods), D1/D/D2 (Passenger Transport)
- 17 Application statuses: From DRAFT to COMPLETED
- Biometric data capture: Photo, signature, fingerprint
- Progressive requirements: C/D/E require existing B license
- Fee management: Theory test, card production, temporary licenses
- Associated applications: Temporary licenses linked to main applications
- Age validation: A1/B1(16*), A2/A/B/BE(18), C/D categories(21+) with parental consent for minors
- Medical certificate requirements: C/D/E categories, age 60+, specific health conditions
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Numeric, JSON, Enum as SQLEnum, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from decimal import Decimal
from datetime import datetime, date

from app.models.base import BaseModel
from app.models.enums import (
    LicenseCategory, ApplicationType, ApplicationStatus,
    BiometricDataType, MedicalCertificateStatus, ParentalConsentStatus,
    TestAttemptType, TestResult, PaymentStatus, ReplacementReason,
    ProfessionalPermitCategory, LicenseRestrictionCode
)


class EnumValueType(TypeDecorator):
    """
    Custom type decorator that ensures enum values (not names) are sent to database
    This fixes the SQLAlchemy issue where enum names are sent instead of values
    even when native_enum=False is specified
    """
    impl = String
    
    def __init__(self, enum_class, *args, **kwargs):
        self.enum_class = enum_class
        super().__init__(*args, **kwargs)
    
    def process_bind_param(self, value, dialect):
        """Convert Python enum to database value"""
        if value is None:
            return value
        if isinstance(value, self.enum_class):
            return value.value  # Always return the enum value, not name
        if isinstance(value, str):
            # If it's already a string, check if it's a valid enum value
            try:
                enum_instance = self.enum_class(value)
                return enum_instance.value
            except ValueError:
                # If not a valid value, try to find by name
                for enum_member in self.enum_class:
                    if enum_member.name == value:
                        return enum_member.value
                raise ValueError(f"Invalid enum value: {value}")
        return value
    
    def process_result_value(self, value, dialect):
        """Convert database value back to Python enum"""
        if value is None:
            return value
        try:
            return self.enum_class(value)
        except ValueError:
            # If the database value doesn't match any enum value, return as-is
            return value


class Application(BaseModel):
    """
    Main application model for Madagascar driver's license system
    
    Supports all application types with complete workflow integration:
    - Person integration via foreign key
    - Single license category per application
    - Complete status workflow (17 stages)
    - Biometric data association
    - Fee management and payment tracking
    - Associated applications (temporary licenses)
    - Medical certificate and parental consent handling
    """
    __tablename__ = "applications"

    # Core application information
    application_number = Column(String(20), nullable=False, unique=True, index=True, comment="Unique application number")
    application_type = Column(SQLEnum(ApplicationType), nullable=False, index=True, comment="Type of application")
    
    # Person integration - links to existing Person module
    person_id = Column(UUID(as_uuid=True), ForeignKey('persons.id'), nullable=False, index=True, comment="Applicant person ID")
    
    # License category - Single category per application (changed from JSON array)
    license_category = Column(EnumValueType(LicenseCategory), nullable=False, comment="Single license category for this application")
    
    # Application status and workflow
    status = Column(SQLEnum(ApplicationStatus), nullable=False, default=ApplicationStatus.DRAFT, index=True, comment="Current application status")
    priority = Column(Integer, nullable=False, default=1, comment="Processing priority (1=normal, 2=urgent, 3=emergency)")
    
    # Dates and timing
    application_date = Column(DateTime, nullable=False, default=func.now(), comment="Date application was created")
    submitted_date = Column(DateTime, nullable=True, comment="Date application was submitted")
    target_completion_date = Column(DateTime, nullable=True, comment="Target completion date")
    actual_completion_date = Column(DateTime, nullable=True, comment="Actual completion date")
    
    # Location and processing
    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=False, index=True, comment="Processing location")
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User assigned to process application")
    
    # Requirements validation
    medical_certificate_required = Column(Boolean, nullable=False, default=False, comment="Medical certificate required for this application")
    medical_certificate_status = Column(SQLEnum(MedicalCertificateStatus), nullable=False, default=MedicalCertificateStatus.NOT_REQUIRED, comment="Medical certificate verification status")
    medical_certificate_file_path = Column(String(500), nullable=True, comment="Path to uploaded medical certificate file")
    medical_certificate_verified_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who verified medical certificate")
    medical_certificate_verified_at = Column(DateTime, nullable=True, comment="Date medical certificate was verified")
    
    parental_consent_required = Column(Boolean, nullable=False, default=False, comment="Parental consent required (ages 16-17)")
    parental_consent_status = Column(SQLEnum(ParentalConsentStatus), nullable=False, default=ParentalConsentStatus.NOT_REQUIRED, comment="Parental consent status")
    parental_consent_file_path = Column(String(500), nullable=True, comment="Path to parental consent document")
    
    # Existing license validation (for C/D/E categories)
    requires_existing_license = Column(Boolean, nullable=False, default=False, comment="Requires existing B license (for C/D/E)")
    existing_license_number = Column(String(20), nullable=True, comment="Existing license number for verification")
    existing_license_verified = Column(Boolean, nullable=False, default=False, comment="Existing license verified")
    
    # Associated applications (for temporary licenses, etc.)
    parent_application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=True, comment="Parent application (if this is associated)")
    
    # Application notes and processing details
    applicant_notes = Column(Text, nullable=True, comment="Notes from applicant")
    processing_notes = Column(Text, nullable=True, comment="Internal processing notes")
    rejection_reason = Column(Text, nullable=True, comment="Reason for rejection (if applicable)")
    
    # Document checklist - JSON object tracking required documents
    required_documents = Column(JSON, nullable=True, comment="JSON object of required documents and their status")
    
    # Medical information - comprehensive health assessment data
    medical_information = Column(JSON, nullable=True, comment="Comprehensive medical assessment data including vision tests, medical conditions, and physical assessments")
    
    # License capture data - for DRIVERS_LICENSE_CAPTURE and LEARNERS_PERMIT_CAPTURE applications
    license_capture = Column(JSON, nullable=True, comment="Captured existing license data for capture applications")
    
    # Biometric data capture status
    photo_captured = Column(Boolean, nullable=False, default=False, comment="ISO-compliant photo captured")
    signature_captured = Column(Boolean, nullable=False, default=False, comment="Digital signature captured")
    fingerprint_captured = Column(Boolean, nullable=False, default=False, comment="Fingerprint captured")
    
    # Special flags
    is_urgent = Column(Boolean, nullable=False, default=False, comment="Urgent processing flag")
    is_on_hold = Column(Boolean, nullable=False, default=False, comment="Application held (not sent to printer)")
    has_special_requirements = Column(Boolean, nullable=False, default=False, comment="Has special requirements")
    special_requirements_notes = Column(Text, nullable=True, comment="Special requirements details")
    
    # Replacement specific fields
    replacement_reason = Column(SQLEnum(ReplacementReason), nullable=True, comment="Reason for replacement (only for REPLACEMENT applications)")
    
    # Professional permit specific fields
    professional_permit_categories = Column(JSON, nullable=True, comment="Selected professional permit categories (P, D, G) - JSON array")
    professional_permit_previous_refusal = Column(Boolean, nullable=False, default=False, comment="Previous professional permit application refused")
    professional_permit_refusal_details = Column(Text, nullable=True, comment="Details of previous professional permit refusal")
    
    # Temporary license specific fields
    is_temporary_license = Column(Boolean, nullable=False, default=False, comment="Is this a temporary license application")
    temporary_license_validity_days = Column(Integer, nullable=True, default=90, comment="Temporary license validity period")
    temporary_license_reason = Column(String(200), nullable=True, comment="Reason for temporary license")
    
    # Draft persistence
    draft_data = Column(JSON, nullable=True, comment="Saved draft application data")
    draft_expires_at = Column(DateTime, nullable=True, comment="When draft expires (30 days from creation)")
    
    # Printing and collection
    print_ready = Column(Boolean, nullable=False, default=False, comment="Ready for printing")
    print_job_id = Column(UUID(as_uuid=True), nullable=True, comment="Associated print job ID")
    collection_notice_sent = Column(Boolean, nullable=False, default=False, comment="Collection notice sent to applicant")
    collection_notice_sent_at = Column(DateTime, nullable=True, comment="Date collection notice was sent")
    
    # Relationships
    person = relationship("Person", foreign_keys=[person_id])
    location = relationship("Location", foreign_keys=[location_id])
    assigned_to_user = relationship("User", foreign_keys=[assigned_to_user_id])
    medical_certificate_verified_by_user = relationship("User", foreign_keys=[medical_certificate_verified_by])
    
    # Associated applications (self-referential)
    parent_application = relationship("Application", remote_side="Application.id", foreign_keys=[parent_application_id])
    child_applications = relationship("Application", foreign_keys=[parent_application_id], remote_side="Application.parent_application_id", overlaps="parent_application")
    
    # Related models
    biometric_data = relationship("ApplicationBiometricData", back_populates="application")
    test_attempts = relationship("ApplicationTestAttempt", back_populates="application") 
    fees = relationship("ApplicationFee", back_populates="application")
    status_history = relationship("ApplicationStatusHistory", back_populates="application")
    documents = relationship("ApplicationDocument", back_populates="application")
    authorization = relationship("ApplicationAuthorization", back_populates="application", uselist=False)
    
    def __repr__(self):
        return f"<Application(id={self.id}, number='{self.application_number}', type='{self.application_type}', status='{self.status}')>"

    @property
    def is_draft_expired(self) -> bool:
        """Check if draft application has expired"""
        if self.status != ApplicationStatus.DRAFT or not self.draft_expires_at:
            return False
        return datetime.utcnow() > self.draft_expires_at

    @property
    def license_categories_list(self) -> list:
        """Get license categories as a list (backward compatibility)"""
        return [self.license_category.value] if self.license_category else []

    @property
    def requires_theory_test(self) -> bool:
        """Check if application requires theory test"""
        return self.application_type in [ApplicationType.NEW_LICENSE, ApplicationType.LEARNERS_PERMIT]

    @property
    def requires_practical_test(self) -> bool:
        """Check if application requires practical test"""
        return self.application_type in [ApplicationType.NEW_LICENSE]

    def has_license_category(self, category: LicenseCategory) -> bool:
        """Check if application includes specific license category"""
        return self.license_category == category

    def requires_medical_certificate_for_categories(self) -> bool:
        """Check if selected category requires medical certificate"""
        categories_requiring_medical = [
            LicenseCategory.C1, LicenseCategory.C, LicenseCategory.C1E, LicenseCategory.CE,
            LicenseCategory.D1, LicenseCategory.D, LicenseCategory.D2
        ]
        return self.license_category in categories_requiring_medical

    def get_theory_test_fee_amount(self) -> int:
        """Calculate theory test fee based on category (10,000 or 15,000 Ar)"""
        heavy_categories = [
            LicenseCategory.C1, LicenseCategory.C, LicenseCategory.C1E, LicenseCategory.CE,
            LicenseCategory.D1, LicenseCategory.D, LicenseCategory.D2
        ]
        if self.license_category in heavy_categories:
            return 15000  # Ar for heavy categories
        return 10000  # Ar for light categories


class ApplicationBiometricData(BaseModel):
    """Biometric data captured for license applications"""
    __tablename__ = "application_biometric_data"

    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, index=True, comment="Application ID")
    data_type = Column(SQLEnum(BiometricDataType), nullable=False, comment="Type of biometric data")
    
    # File storage
    file_path = Column(String(500), nullable=True, comment="Path to stored biometric file")
    file_size = Column(Integer, nullable=True, comment="File size in bytes")
    file_format = Column(String(10), nullable=True, comment="File format (jpg, png, etc.)")
    
    # Capture metadata
    capture_method = Column(String(50), nullable=True, comment="Capture method (webcam, scanner, etc.)")
    capture_device_id = Column(String(100), nullable=True, comment="Device used for capture")
    image_resolution = Column(String(20), nullable=True, comment="Image resolution (e.g., 1920x1080)")
    
    # Quality metrics
    quality_score = Column(Numeric(5, 2), nullable=True, comment="Quality score (0-100)")
    is_verified = Column(Boolean, nullable=False, default=False, comment="Biometric data verified")
    verified_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who verified the data")
    verified_at = Column(DateTime, nullable=True, comment="Verification timestamp")
    
    # Additional metadata
    capture_metadata = Column(JSON, nullable=True, comment="Additional capture metadata")
    notes = Column(Text, nullable=True, comment="Notes about the biometric capture")
    
    # Relationships
    application = relationship("Application", back_populates="biometric_data")
    verified_by_user = relationship("User", foreign_keys=[verified_by])
    
    def __repr__(self):
        return f"<ApplicationBiometricData(application_id={self.application_id}, type='{self.data_type}')>"


class ApplicationTestAttempt(BaseModel):
    """License test attempts (theory and practical)"""
    __tablename__ = "application_test_attempts"

    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, index=True, comment="Application ID")
    test_type = Column(SQLEnum(TestAttemptType), nullable=False, comment="Type of test")
    attempt_number = Column(Integer, nullable=False, default=1, comment="Attempt number (1, 2, 3, etc.)")
    
    # Test scheduling
    scheduled_date = Column(DateTime, nullable=True, comment="Scheduled test date")
    actual_date = Column(DateTime, nullable=True, comment="Actual test date")
    test_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=True, comment="Test location")
    
    # Test details
    examiner_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="Examiner user ID")
    test_result = Column(SQLEnum(TestResult), nullable=False, default=TestResult.PENDING, comment="Test result")
    score = Column(Numeric(5, 2), nullable=True, comment="Test score (percentage)")
    
    # Fee tracking
    fee_amount = Column(Numeric(10, 2), nullable=False, comment="Test fee amount (Ar)")
    fee_paid = Column(Boolean, nullable=False, default=False, comment="Fee payment status")
    payment_reference = Column(String(100), nullable=True, comment="Payment reference number")
    
    # Test metadata
    test_duration_minutes = Column(Integer, nullable=True, comment="Test duration in minutes")
    questions_total = Column(Integer, nullable=True, comment="Total questions (theory test)")
    questions_correct = Column(Integer, nullable=True, comment="Correct answers (theory test)")
    
    # Result details
    pass_threshold = Column(Numeric(5, 2), nullable=True, comment="Pass threshold percentage")
    result_notes = Column(Text, nullable=True, comment="Examiner notes about test result")
    failure_reasons = Column(JSON, nullable=True, comment="Reasons for failure (if applicable)")
    
    # Certificate issuance (for theory tests)
    learners_permit_issued = Column(Boolean, nullable=False, default=False, comment="Learner's permit issued after theory pass")
    learners_permit_number = Column(String(20), nullable=True, comment="Learner's permit number")
    learners_permit_expiry = Column(DateTime, nullable=True, comment="Learner's permit expiry date")
    
    # Relationships
    application = relationship("Application", back_populates="test_attempts")
    test_location = relationship("Location", foreign_keys=[test_location_id])
    examiner = relationship("User", foreign_keys=[examiner_id])
    
    def __repr__(self):
        return f"<ApplicationTestAttempt(application_id={self.application_id}, type='{self.test_type}', attempt={self.attempt_number}, result='{self.test_result}')>"


class ApplicationFee(BaseModel):
    """Fee structure and payment tracking for applications"""
    __tablename__ = "application_fees"

    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, index=True, comment="Application ID")
    
    # Fee details
    fee_type = Column(String(50), nullable=False, comment="Type of fee (theory_test, card_production, temporary_license)")
    amount = Column(Numeric(10, 2), nullable=False, comment="Fee amount in Ariary (Ar)")
    currency = Column(String(3), nullable=False, default='MGA', comment="Currency code (MGA = Madagascar Ariary)")
    
    # Payment status
    payment_status = Column(SQLEnum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING, comment="Payment status")
    payment_date = Column(DateTime, nullable=True, comment="Date payment was made")
    payment_method = Column(String(50), nullable=True, comment="Payment method (cash, mobile_money, etc.)")
    payment_reference = Column(String(100), nullable=True, comment="Payment reference/receipt number")
    
    # Processing
    processed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who processed payment")
    transaction_id = Column(UUID(as_uuid=True), nullable=True, comment="Transaction ID for accounting")
    
    # Fee metadata
    due_date = Column(DateTime, nullable=True, comment="Payment due date")
    discount_amount = Column(Numeric(10, 2), nullable=True, default=0, comment="Discount applied")
    discount_reason = Column(String(200), nullable=True, comment="Reason for discount")
    
    # Receipt and documentation
    receipt_number = Column(String(50), nullable=True, comment="Official receipt number")
    receipt_file_path = Column(String(500), nullable=True, comment="Path to receipt file")
    
    # Notes
    payment_notes = Column(Text, nullable=True, comment="Payment processing notes")
    
    # Relationships
    application = relationship("Application", back_populates="fees")
    processed_by_user = relationship("User", foreign_keys=[processed_by])
    
    def __repr__(self):
        return f"<ApplicationFee(application_id={self.application_id}, type='{self.fee_type}', amount={self.amount}, status='{self.payment_status}')>"


class ApplicationStatusHistory(BaseModel):
    """Track application status changes for audit trail"""
    __tablename__ = "application_status_history"

    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, index=True, comment="Application ID")
    
    # Status change details
    from_status = Column(SQLEnum(ApplicationStatus), nullable=True, comment="Previous status")
    to_status = Column(SQLEnum(ApplicationStatus), nullable=False, comment="New status")
    changed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who made the change")
    changed_at = Column(DateTime, nullable=False, default=func.now(), comment="Timestamp of status change")
    
    # Change context
    reason = Column(String(200), nullable=True, comment="Reason for status change")
    notes = Column(Text, nullable=True, comment="Additional notes about the change")
    system_initiated = Column(Boolean, nullable=False, default=False, comment="Whether change was system-initiated")
    
    # Relationships
    application = relationship("Application", back_populates="status_history")
    changed_by_user = relationship("User", foreign_keys=[changed_by])
    
    def __repr__(self):
        return f"<ApplicationStatusHistory(application_id={self.application_id}, from='{self.from_status}', to='{self.to_status}')>"


class ApplicationDocument(BaseModel):
    """Document attachments for applications"""
    __tablename__ = "application_documents"

    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, index=True, comment="Application ID")
    
    # Document details
    document_type = Column(String(50), nullable=False, comment="Type of document (medical_certificate, parental_consent, etc.)")
    document_name = Column(String(200), nullable=False, comment="Document file name")
    file_path = Column(String(500), nullable=False, comment="Path to stored document file")
    file_size = Column(Integer, nullable=True, comment="File size in bytes")
    mime_type = Column(String(100), nullable=True, comment="MIME type of file")
    
    # Upload details
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who uploaded document")
    upload_date = Column(DateTime, nullable=False, default=func.now(), comment="Upload timestamp")
    
    # Verification
    is_verified = Column(Boolean, nullable=False, default=False, comment="Document verified")
    verified_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who verified document")
    verified_at = Column(DateTime, nullable=True, comment="Verification timestamp")
    verification_notes = Column(Text, nullable=True, comment="Verification notes")
    
    # Document metadata
    expiry_date = Column(DateTime, nullable=True, comment="Document expiry date (if applicable)")
    issuing_authority = Column(String(200), nullable=True, comment="Document issuing authority")
    document_number = Column(String(100), nullable=True, comment="Document reference number")
    
    # Relationships
    application = relationship("Application", back_populates="documents")
    uploaded_by_user = relationship("User", foreign_keys=[uploaded_by])
    verified_by_user = relationship("User", foreign_keys=[verified_by])
    
    def __repr__(self):
        return f"<ApplicationDocument(application_id={self.application_id}, type='{self.document_type}', name='{self.document_name}')>"


class FeeStructure(BaseModel):
    """Configurable fee structure for Madagascar license system"""
    __tablename__ = "fee_structures"
    
    # Fee identification
    fee_type = Column(String(50), nullable=False, unique=True, comment="Type of fee (theory_test_ab, theory_test_cde, card_production, etc.)")
    display_name = Column(String(100), nullable=False, comment="Human-readable fee name")
    description = Column(Text, nullable=True, comment="Fee description")
    
    # Fee amount
    amount = Column(Numeric(10, 2), nullable=False, comment="Fee amount in Ariary (Ar)")
    currency = Column(String(3), nullable=False, default='MGA', comment="Currency code")
    
    # Fee applicability
    applies_to_categories = Column(JSON, nullable=True, comment="License categories this fee applies to")
    applies_to_application_types = Column(JSON, nullable=True, comment="Application types this fee applies to")
    
    # Fee settings
    is_mandatory = Column(Boolean, nullable=False, default=True, comment="Whether fee is mandatory")
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
    
    def __repr__(self):
        return f"<FeeStructure(type='{self.fee_type}', amount={self.amount}, active={self.is_active})>"

    @property
    def is_effective(self) -> bool:
        """Check if fee structure is currently effective"""
        now = datetime.utcnow()
        if not self.is_active:
            return False
        if self.effective_from > now:
            return False
        if self.effective_until and self.effective_until <= now:
            return False
        return True


# License category display names for frontend
LICENSE_CATEGORY_DISPLAY_NAMES = {
    # Motorcycles and Mopeds
    LicenseCategory.A1: "A1 - Small motorcycles and mopeds (<125cc)",
    LicenseCategory.A2: "A2 - Mid-range motorcycles (power limited, up to 35kW)",
    LicenseCategory.A: "A - Unlimited motorcycles (no power restriction)",
    
    # Light Vehicles
    LicenseCategory.B1: "B1 - Light quadricycles (motorized tricycles/quadricycles)",
    LicenseCategory.B: "B - Standard passenger cars and light vehicles (up to 3.5t)",
    LicenseCategory.B2: "B2 - Taxis or commercial passenger vehicles",
    LicenseCategory.BE: "BE - Category B with trailer exceeding 750kg",
    
    # Heavy Goods Vehicles
    LicenseCategory.C1: "C1 - Medium-sized goods vehicles (3.5-7.5t)",
    LicenseCategory.C: "C - Heavy goods vehicles (over 7.5t)",
    LicenseCategory.C1E: "C1E - C1 category vehicles with heavy trailer",
    LicenseCategory.CE: "CE - Full heavy combination vehicles",
    
    # Passenger Transport
    LicenseCategory.D1: "D1 - Small buses (up to 16 passengers)",
    LicenseCategory.D: "D - Standard buses and coaches (over 16 passengers)",
    LicenseCategory.D2: "D2 - Specialized public transport (articulated buses)",
    
    # Learner's Permits
    LicenseCategory.LEARNERS_1: "1 - Motor cycles, motor tricycles and motor quadricycles with engine of any capacity",
    LicenseCategory.LEARNERS_2: "2 - Light motor vehicles, other than motor cycles, motor tricycles or motor quadricycles",
    LicenseCategory.LEARNERS_3: "3 - Any motor vehicle other than motor cycles, motor tricycles or motor quadricycles",
}

# Application type display names for frontend
APPLICATION_TYPE_DISPLAY_NAMES = {
    ApplicationType.NEW_LICENSE: "New License Application",
    ApplicationType.LEARNERS_PERMIT: "Learner's Permit Application",
    ApplicationType.RENEWAL: "License Renewal",
    ApplicationType.REPLACEMENT: "Replacement License",
    ApplicationType.TEMPORARY_LICENSE: "Temporary License",
    ApplicationType.INTERNATIONAL_PERMIT: "International Driving Permit",
}

# Application status display names for frontend
APPLICATION_STATUS_DISPLAY_NAMES = {
    ApplicationStatus.DRAFT: "Draft",
    ApplicationStatus.SUBMITTED: "Submitted",
    ApplicationStatus.ON_HOLD: "On Hold",
    ApplicationStatus.DOCUMENTS_PENDING: "Documents Pending",
    ApplicationStatus.THEORY_TEST_REQUIRED: "Theory Test Required",
    ApplicationStatus.THEORY_PASSED: "Theory Test Passed",
    ApplicationStatus.THEORY_FAILED: "Theory Test Failed",
    ApplicationStatus.PRACTICAL_TEST_REQUIRED: "Practical Test Required",
    ApplicationStatus.PRACTICAL_PASSED: "Practical Test Passed",
    ApplicationStatus.PRACTICAL_FAILED: "Practical Test Failed",
    ApplicationStatus.APPROVED: "Approved",
    ApplicationStatus.SENT_TO_PRINTER: "Sent to Printer",
    ApplicationStatus.CARD_PRODUCTION: "Card Production",
    ApplicationStatus.READY_FOR_COLLECTION: "Ready for Collection",
    ApplicationStatus.COMPLETED: "Completed",
    ApplicationStatus.REJECTED: "Rejected",
    ApplicationStatus.CANCELLED: "Cancelled",
}

# Age requirements for license categories
LICENSE_CATEGORY_AGE_REQUIREMENTS = {
    # Motorcycles and Mopeds
    LicenseCategory.A1: 16,  # Requires parental consent for 16-17
    LicenseCategory.A2: 18,
    LicenseCategory.A: 18,
    
    # Light Vehicles
    LicenseCategory.B1: 16,  # Requires parental consent for 16-17
    LicenseCategory.B: 18,
    LicenseCategory.B2: 21,  # Plus existing B license
    LicenseCategory.BE: 18,  # Plus existing B license
    
    # Heavy Goods Vehicles
    LicenseCategory.C1: 18,  # Plus existing B license
    LicenseCategory.C: 21,   # Plus existing B license
    LicenseCategory.C1E: 18, # Plus existing C1 license
    LicenseCategory.CE: 21,  # Plus existing C license
    
    # Passenger Transport
    LicenseCategory.D1: 21,  # Plus existing B license
    LicenseCategory.D: 24,   # Plus existing B license
    LicenseCategory.D2: 24,  # Plus existing B license
    
    # Learner's Permits
    LicenseCategory.LEARNERS_1: 16,  # Requires parental consent for 16-17
    LicenseCategory.LEARNERS_2: 18,
    LicenseCategory.LEARNERS_3: 18,
}

# Categories requiring existing B license
CATEGORIES_REQUIRING_B_LICENSE = [
    LicenseCategory.B2,   # Commercial passenger vehicles
    LicenseCategory.BE,   # B with trailer
    LicenseCategory.C1,   # Medium goods vehicles
    LicenseCategory.C,    # Heavy goods vehicles
    LicenseCategory.C1E,  # C1 with trailer
    LicenseCategory.CE,   # C with trailer
    LicenseCategory.D1,   # Small buses
    LicenseCategory.D,    # Standard buses
    LicenseCategory.D2,   # Specialized transport
]

# Categories requiring medical certificate
CATEGORIES_REQUIRING_MEDICAL = [
    LicenseCategory.B2,   # Commercial passenger vehicles
    LicenseCategory.C1,   # Medium goods vehicles
    LicenseCategory.C,    # Heavy goods vehicles
    LicenseCategory.C1E,  # C1 with trailer
    LicenseCategory.CE,   # C with trailer
    LicenseCategory.D1,   # Small buses
    LicenseCategory.D,    # Standard buses
    LicenseCategory.D2,   # Specialized transport
]

# Replacement reason display names for frontend
REPLACEMENT_REASON_DISPLAY_NAMES = {
    ReplacementReason.LOST: "Lost License",
    ReplacementReason.STOLEN: "Stolen License (Police Report Required)",
    ReplacementReason.DAMAGED: "Damaged License",
    ReplacementReason.NAME_CHANGE: "Name Change",
    ReplacementReason.ADDRESS_CHANGE: "Address Change",
    ReplacementReason.OTHER: "Other Reason",
} 

class ApplicationAuthorization(BaseModel):
    """
    Authorization model for capturing test results and examiner decisions
    This model captures the test day form data including eye test results,
    driving test results, restrictions, and final authorization decision
    """
    __tablename__ = "application_authorizations"

    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, unique=True, index=True, comment="Application ID (one authorization per application)")
    
    # Examiner information
    examiner_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="Examiner user ID")
    infrastructure_number = Column(String(50), nullable=True, comment="Infrastructure number and name")
    examiner_signature_path = Column(String(500), nullable=True, comment="Path to examiner signature file")
    
    # Test attendance and basic result
    is_absent = Column(Boolean, nullable=False, default=False, comment="Applicant was absent for test")
    is_failed = Column(Boolean, nullable=False, default=False, comment="Applicant failed the test")
    absent_failed_reason = Column(Text, nullable=True, comment="Reason for absence or failure")
    
    # Eye test results (from medical information section)
    eye_test_result = Column(String(20), nullable=True, comment="Eye test result: PASS/FAIL")
    eye_test_notes = Column(Text, nullable=True, comment="Additional eye test notes")
    
    # Driving test results
    driving_test_result = Column(String(20), nullable=True, comment="Driving test result: PASS/FAIL")
    driving_test_score = Column(Numeric(5, 2), nullable=True, comment="Driving test score (percentage)")
    driving_test_notes = Column(Text, nullable=True, comment="Driving test examiner notes")
    
    # Vehicle restrictions (from test form)
    vehicle_restriction_none = Column(Boolean, nullable=False, default=True, comment="No vehicle restrictions")
    vehicle_restriction_automatic = Column(Boolean, nullable=False, default=False, comment="Automatic transmission only")
    vehicle_restriction_electric = Column(Boolean, nullable=False, default=False, comment="Electric powered vehicles only")
    vehicle_restriction_disabled = Column(Boolean, nullable=False, default=False, comment="Adapted for physically disabled person")
    
    # Driver restrictions (from test form)
    driver_restriction_none = Column(Boolean, nullable=False, default=True, comment="No driver restrictions")
    driver_restriction_glasses = Column(Boolean, nullable=False, default=False, comment="Glasses or contact lenses required")
    driver_restriction_artificial_limb = Column(Boolean, nullable=False, default=False, comment="Has artificial limb")
    driver_restriction_glasses_and_limb = Column(Boolean, nullable=False, default=False, comment="Glasses and artificial limb")
    
    # Applied restrictions (final restrictions applied to license)
    applied_restrictions = Column(JSON, nullable=True, comment="JSON array of applied LicenseRestrictionCode values")
    
    # Authorization decision
    is_authorized = Column(Boolean, nullable=False, default=False, comment="Application authorized for license generation")
    authorization_date = Column(DateTime, nullable=False, default=func.now(), comment="Date of authorization")
    authorization_notes = Column(Text, nullable=True, comment="Examiner authorization notes")
    
    # License generation tracking
    license_generated = Column(Boolean, nullable=False, default=False, comment="License generated from this authorization")
    license_id = Column(UUID(as_uuid=True), ForeignKey('licenses.id'), nullable=True, comment="Generated license ID")
    license_generated_at = Column(DateTime, nullable=True, comment="Date license was generated")
    
    # Quality assurance
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="Supervisor who reviewed authorization")
    reviewed_at = Column(DateTime, nullable=True, comment="Date authorization was reviewed")
    review_notes = Column(Text, nullable=True, comment="Review notes")
    
    # Relationships
    application = relationship("Application", back_populates="authorization", foreign_keys=[application_id])
    examiner = relationship("User", foreign_keys=[examiner_id])
    generated_license = relationship("License", foreign_keys=[license_id])
    reviewed_by_user = relationship("User", foreign_keys=[reviewed_by])
    
    def __repr__(self):
        return f"<ApplicationAuthorization(application_id={self.application_id}, examiner_id={self.examiner_id}, authorized={self.is_authorized})>"
    
    @property
    def has_vehicle_restrictions(self) -> bool:
        """Check if any vehicle restrictions are applied"""
        return not self.vehicle_restriction_none
    
    @property
    def has_driver_restrictions(self) -> bool:
        """Check if any driver restrictions are applied"""
        return not self.driver_restriction_none
    
    @property
    def test_passed(self) -> bool:
        """Check if both eye test and driving test passed"""
        return (
            not self.is_absent and 
            not self.is_failed and 
            self.eye_test_result == "PASS" and 
            self.driving_test_result == "PASS"
        )
    
    def get_restriction_codes(self) -> list:
        """Get list of restriction codes to apply to license"""
        restrictions = []
        
        # Driver restrictions
        if self.driver_restriction_glasses or self.driver_restriction_glasses_and_limb:
            restrictions.append(LicenseRestrictionCode.CORRECTIVE_LENSES)
        
        if self.driver_restriction_artificial_limb or self.driver_restriction_glasses_and_limb:
            restrictions.append(LicenseRestrictionCode.PROSTHETICS)
        
        # Vehicle restrictions
        if self.vehicle_restriction_automatic:
            restrictions.append(LicenseRestrictionCode.AUTOMATIC_TRANSMISSION)
        
        if self.vehicle_restriction_electric:
            restrictions.append(LicenseRestrictionCode.ELECTRIC_POWERED)
        
        if self.vehicle_restriction_disabled:
            restrictions.append(LicenseRestrictionCode.PHYSICAL_DISABLED)
        
        return restrictions 