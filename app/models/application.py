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
    LicenseCategory, ApplicationType, ApplicationStatus, TestResult,
    BiometricDataType, MedicalCertificateStatus, ParentalConsentStatus,
    TestAttemptType, PaymentStatus, ReplacementReason,
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
    
    # Test result (only for NEW_LICENSE and LEARNERS_PERMIT applications)
    test_result = Column(SQLEnum(TestResult), nullable=True, comment="Test result for new license applications (PASSED/FAILED/ABSENT)")
    
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
    
    # Approval tracking (New Simple Approval System)
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who approved/failed this application")
    approved_at_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=True, comment="Location where approval was processed")
    approval_date = Column(DateTime, nullable=True, comment="Date application was approved/failed/marked absent")
    approval_outcome = Column(SQLEnum(TestResult), nullable=True, comment="Approval outcome: PASSED, FAILED, ABSENT")
    identified_restrictions = Column(JSON, nullable=True, comment="License restrictions identified during approval process")
    
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
    
    # Payment stage tracking (NEW FIELDS FOR STAGED PAYMENTS)
    test_payment_completed = Column(Boolean, nullable=False, default=False, comment="Test fees have been paid")
    test_payment_date = Column(DateTime, nullable=True, comment="Date test payment was completed")
    card_payment_completed = Column(Boolean, nullable=False, default=False, comment="Card fees have been paid")
    card_payment_date = Column(DateTime, nullable=True, comment="Date card payment was completed")
    current_payment_stage = Column(String(50), nullable=True, comment="Current payment stage: TEST_PAYMENT, CARD_PAYMENT, COMPLETED")
    
    # Card ordering status
    card_ordered = Column(Boolean, nullable=False, default=False, comment="Physical card has been ordered")
    card_order_date = Column(DateTime, nullable=True, comment="Date card was ordered")
    card_order_id = Column(UUID(as_uuid=True), nullable=True, comment="Reference to card order")
    includes_temporary_license = Column(Boolean, nullable=False, default=False, comment="Card order includes temporary license")
    
    # Relationships
    person = relationship("Person", foreign_keys=[person_id])
    location = relationship("Location", foreign_keys=[location_id])
    assigned_to_user = relationship("User", foreign_keys=[assigned_to_user_id])
    medical_certificate_verified_by_user = relationship("User", foreign_keys=[medical_certificate_verified_by])
    approved_by_user = relationship("User", foreign_keys=[approved_by_user_id])
    approved_at_location = relationship("Location", foreign_keys=[approved_at_location_id])
    
    # Associated applications (self-referential)
    parent_application = relationship("Application", remote_side="Application.id", foreign_keys=[parent_application_id])
    child_applications = relationship("Application", foreign_keys=[parent_application_id], remote_side="Application.parent_application_id", overlaps="parent_application")
    
    # Related models
    biometric_data = relationship("ApplicationBiometricData", back_populates="application")
    test_attempts = relationship("ApplicationTestAttempt", back_populates="application") 
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

    @property
    def is_light_vehicle(self) -> bool:
        """Check if application is for light vehicle category"""
        light_categories = [
            LicenseCategory.A1, LicenseCategory.A2, LicenseCategory.A,
            LicenseCategory.B1, LicenseCategory.B
        ]
        return self.license_category in light_categories

    @property
    def is_heavy_vehicle(self) -> bool:
        """Check if application is for heavy vehicle category"""
        heavy_categories = [
            LicenseCategory.B2, LicenseCategory.BE,
            LicenseCategory.C1, LicenseCategory.C, LicenseCategory.C1E, LicenseCategory.CE,
            LicenseCategory.D1, LicenseCategory.D, LicenseCategory.D2
        ]
        return self.license_category in heavy_categories

    @property
    def requires_staged_payments(self) -> bool:
        """Check if application requires staged payments (test first, then card)"""
        return self.application_type in [ApplicationType.NEW_LICENSE, ApplicationType.LEARNERS_PERMIT]

    @property
    def requires_single_payment(self) -> bool:
        """Check if application requires single payment (application + card together)"""
        return self.application_type in [
            ApplicationType.RENEWAL, 
            ApplicationType.REPLACEMENT, 
            ApplicationType.TEMPORARY_LICENSE,
            ApplicationType.INTERNATIONAL_PERMIT,
            ApplicationType.PROFESSIONAL_LICENSE,
            ApplicationType.FOREIGN_CONVERSION
        ]

    @property
    def current_required_payment_type(self) -> str:
        """Determine what payment is currently required"""
        if self.requires_single_payment:
            if not self.card_payment_completed:
                return "CARD_AND_APPLICATION"
            else:
                return "COMPLETED"
        
        elif self.requires_staged_payments:
            if not self.test_payment_completed:
                return "TEST_PAYMENT"
            elif self.test_result == TestResult.PASSED and not self.card_payment_completed:
                return "CARD_PAYMENT"
            elif self.test_result in [TestResult.FAILED, TestResult.ABSENT]:
                return "TEST_FAILED"  # Need new application
            else:
                return "WAITING_FOR_TEST"
        
        return "NO_PAYMENT_REQUIRED"

    @property
    def can_order_card(self) -> bool:
        """Check if card can be ordered for this application"""
        if self.application_type == ApplicationType.RENEWAL:
            # Renewals: card can be ordered automatically with payment
            return self.card_payment_completed
        
        elif self.application_type == ApplicationType.NEW_LICENSE:
            # New licenses: card can only be ordered after passing test and paying
            return (self.test_payment_completed and 
                   self.test_result == TestResult.PASSED and 
                   self.card_payment_completed)
        
        elif self.application_type == ApplicationType.REPLACEMENT:
            # Replacements: card can be ordered with payment
            return self.card_payment_completed
        
        return False

    def get_required_fees(self) -> dict:
        """Get required fees based on current payment stage and application type"""
        from app.models.enums import MADAGASCAR_LICENSE_FEES
        
        fees = {"test_fees": [], "card_fees": [], "total": 0}
        
        payment_type = self.current_required_payment_type
        
        if payment_type == "TEST_PAYMENT":
            # Test fees based on application type:
            # - LEARNERS_PERMIT = theory test only
            # - NEW_LICENSE = practical test only (person already has learner's permit)
            
            if self.application_type == ApplicationType.LEARNERS_PERMIT:
                # Theory test for learner's permit
                if self.is_light_vehicle:
                    fees["test_fees"].append({
                        "type": "THEORY_TEST_LIGHT",
                        "amount": MADAGASCAR_LICENSE_FEES["THEORY_TEST_LIGHT"],
                        "description": "Theory Test (Light Vehicles)"
                    })
                else:  # Heavy vehicle
                    fees["test_fees"].append({
                        "type": "THEORY_TEST_HEAVY",
                        "amount": MADAGASCAR_LICENSE_FEES["THEORY_TEST_HEAVY"],
                        "description": "Theory Test (Heavy Vehicles)"
                    })
            elif self.application_type == ApplicationType.NEW_LICENSE:
                # Practical test for full license (theory already done in learner's permit)
                if self.is_light_vehicle:
                    fees["test_fees"].append({
                        "type": "PRACTICAL_TEST_LIGHT", 
                        "amount": MADAGASCAR_LICENSE_FEES["PRACTICAL_TEST_LIGHT"],
                        "description": "Practical Test (Light Vehicles)"
                    })
                else:  # Heavy vehicle
                    fees["test_fees"].append({
                        "type": "PRACTICAL_TEST_HEAVY",
                        "amount": MADAGASCAR_LICENSE_FEES["PRACTICAL_TEST_HEAVY"],
                        "description": "Practical Test (Heavy Vehicles)"
                    })
        
        elif payment_type == "CARD_PAYMENT":
            # Card fees for second stage of NEW_LICENSE
            fees["card_fees"].append({
                "type": "NEW_LICENSE_FEE",
                "amount": MADAGASCAR_LICENSE_FEES["NEW_LICENSE_FEE"],
                "description": "New License - Application + Card"
            })
        
        elif payment_type == "CARD_AND_APPLICATION":
            # Single payment for other application types
            if self.application_type == ApplicationType.RENEWAL:
                fees["card_fees"].append({
                    "type": "RENEWAL_FEE",
                    "amount": MADAGASCAR_LICENSE_FEES["RENEWAL_FEE"],
                    "description": "License Renewal"
                })
            elif self.application_type == ApplicationType.REPLACEMENT:
                fees["card_fees"].append({
                    "type": "REPLACEMENT_FEE",
                    "amount": MADAGASCAR_LICENSE_FEES["REPLACEMENT_FEE"],
                    "description": "License Replacement"
                })
            elif self.application_type == ApplicationType.TEMPORARY_LICENSE:
                fees["card_fees"].append({
                    "type": "TEMPORARY_LICENSE_FEE",
                    "amount": MADAGASCAR_LICENSE_FEES["TEMPORARY_LICENSE_FEE"],
                    "description": "Temporary License"
                })
            elif self.application_type == ApplicationType.INTERNATIONAL_PERMIT:
                fees["card_fees"].append({
                    "type": "INTERNATIONAL_PERMIT_FEE",
                    "amount": MADAGASCAR_LICENSE_FEES["INTERNATIONAL_PERMIT_FEE"],
                    "description": "International Driving Permit"
                })
            elif self.application_type == ApplicationType.PROFESSIONAL_LICENSE:
                fees["card_fees"].append({
                    "type": "PROFESSIONAL_LICENSE_FEE",
                    "amount": MADAGASCAR_LICENSE_FEES["PROFESSIONAL_LICENSE_FEE"],
                    "description": "Professional License"
                })
            elif self.application_type == ApplicationType.FOREIGN_CONVERSION:
                fees["card_fees"].append({
                    "type": "FOREIGN_CONVERSION_FEE",
                    "amount": MADAGASCAR_LICENSE_FEES["FOREIGN_CONVERSION_FEE"],
                    "description": "Foreign License Conversion"
                })
            elif self.application_type == ApplicationType.DRIVERS_LICENSE_CAPTURE:
                fees["card_fees"].append({
                    "type": "DRIVERS_LICENSE_CAPTURE_FEE",
                    "amount": MADAGASCAR_LICENSE_FEES["DRIVERS_LICENSE_CAPTURE_FEE"],
                    "description": "Driver's License Capture"
                })
            elif self.application_type == ApplicationType.LEARNERS_PERMIT_CAPTURE:
                fees["card_fees"].append({
                    "type": "LEARNERS_PERMIT_CAPTURE_FEE",
                    "amount": MADAGASCAR_LICENSE_FEES["LEARNERS_PERMIT_CAPTURE_FEE"],
                    "description": "Learner's Permit Capture"
                })
        
        # Calculate total
        fees["total"] = (
            sum(fee["amount"] for fee in fees["test_fees"]) +
            sum(fee["amount"] for fee in fees["card_fees"])
        )
        
        return fees 


class ApplicationBiometricData(BaseModel):
    """Biometric data captured for license applications"""
    __tablename__ = "application_biometric_data"

    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, index=True, comment="Application ID")
    data_type = Column(SQLEnum(BiometricDataType), nullable=False, comment="Type of biometric data")
    
    # File storage
    file_path = Column(String(500), nullable=True, comment="Path to stored biometric file")
    file_name = Column(String(255), nullable=True, comment="Original filename")
    file_size = Column(Integer, nullable=True, comment="File size in bytes")
    file_format = Column(String(10), nullable=True, comment="File format (jpg, png, etc.)")
    
    # Capture metadata
    capture_device = Column(String(100), nullable=True, comment="Device used for capture")
    capture_software = Column(String(100), nullable=True, comment="Software used for capture")
    capture_metadata = Column(JSON, nullable=True, comment="Additional capture metadata")
    
    # Quality metrics
    quality_score = Column(Numeric(3, 2), nullable=True, comment="Quality score (0.00-1.00)")
    quality_metrics = Column(JSON, nullable=True, comment="Detailed quality metrics")
    
    # Processing flags
    is_processed = Column(Boolean, nullable=False, default=False, comment="Data has been processed")
    is_verified = Column(Boolean, nullable=False, default=False, comment="Data has been verified")
    processing_notes = Column(Text, nullable=True, comment="Processing or verification notes")
    
    # Audit fields
    captured_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who captured the data")
    verified_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who verified the data")
    verified_at = Column(DateTime, nullable=True, comment="Verification timestamp")
    
    # Relationships
    application = relationship("Application", back_populates="biometric_data")
    captured_by_user = relationship("User", foreign_keys=[captured_by])
    verified_by_user = relationship("User", foreign_keys=[verified_by])

    def __repr__(self):
        return f"<ApplicationBiometricData(application_id={self.application_id}, type='{self.data_type}')>"


class ApplicationTestAttempt(BaseModel):
    """Test attempts for license applications"""
    __tablename__ = "application_test_attempts"

    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, index=True, comment="Application ID")
    test_type = Column(SQLEnum(TestAttemptType), nullable=False, comment="Type of test (theory/practical)")
    attempt_number = Column(Integer, nullable=False, default=1, comment="Attempt number (1, 2, 3, etc.)")
    
    # Test scheduling
    scheduled_date = Column(DateTime, nullable=True, comment="Scheduled test date and time")
    scheduled_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=True, comment="Scheduled test location")
    
    # Test execution
    test_date = Column(DateTime, nullable=True, comment="Actual test date and time")
    test_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=True, comment="Actual test location")
    examiner_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="Examiner who conducted the test")
    
    # Test results
    result = Column(SQLEnum(TestResult), nullable=True, comment="Test result (PASSED/FAILED/ABSENT)")
    score = Column(Numeric(5, 2), nullable=True, comment="Test score (if applicable)")
    max_score = Column(Numeric(5, 2), nullable=True, comment="Maximum possible score")
    pass_threshold = Column(Numeric(5, 2), nullable=True, comment="Minimum score to pass")
    
    # Test details
    test_duration_minutes = Column(Integer, nullable=True, comment="Test duration in minutes")
    test_questions_total = Column(Integer, nullable=True, comment="Total number of questions")
    test_questions_correct = Column(Integer, nullable=True, comment="Number of correct answers")
    
    # Test metadata
    test_metadata = Column(JSON, nullable=True, comment="Additional test metadata (questions, answers, etc.)")
    examiner_notes = Column(Text, nullable=True, comment="Examiner's notes and observations")
    
    # Relationships
    application = relationship("Application", back_populates="test_attempts")
    examiner = relationship("User", foreign_keys=[examiner_id])
    scheduled_location = relationship("Location", foreign_keys=[scheduled_location_id])
    test_location = relationship("Location", foreign_keys=[test_location_id])

    def __repr__(self):
        return f"<ApplicationTestAttempt(application_id={self.application_id}, type='{self.test_type}', attempt={self.attempt_number}, result='{self.result}')>"


class ApplicationStatusHistory(BaseModel):
    """Status change history for applications"""
    __tablename__ = "application_status_history"

    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, index=True, comment="Application ID")
    previous_status = Column(SQLEnum(ApplicationStatus), nullable=True, comment="Previous status")
    new_status = Column(SQLEnum(ApplicationStatus), nullable=False, comment="New status")
    
    # Change details
    change_reason = Column(String(500), nullable=True, comment="Reason for status change")
    change_notes = Column(Text, nullable=True, comment="Additional notes about the change")
    
    # Change metadata
    changed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who made the change")
    changed_at = Column(DateTime, nullable=False, default=func.now(), comment="When the change was made")
    system_generated = Column(Boolean, nullable=False, default=False, comment="Whether this was a system-generated change")
    
    # Additional context
    related_document_id = Column(UUID(as_uuid=True), nullable=True, comment="Related document or transaction ID")
    ip_address = Column(String(45), nullable=True, comment="IP address of user making change")
    user_agent = Column(String(500), nullable=True, comment="User agent of user making change")
    
    # Relationships
    application = relationship("Application", back_populates="status_history")
    changed_by_user = relationship("User", foreign_keys=[changed_by])

    def __repr__(self):
        return f"<ApplicationStatusHistory(application_id={self.application_id}, {self.previous_status} -> {self.new_status})>"


class ApplicationDocument(BaseModel):
    """Documents attached to applications"""
    __tablename__ = "application_documents"

    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, index=True, comment="Application ID")
    document_type = Column(String(50), nullable=False, comment="Type of document")
    document_name = Column(String(255), nullable=False, comment="Document name/title")
    
    # File information
    file_path = Column(String(500), nullable=False, comment="Path to stored document file")
    original_filename = Column(String(255), nullable=False, comment="Original filename")
    file_size = Column(Integer, nullable=False, comment="File size in bytes")
    file_format = Column(String(10), nullable=False, comment="File format (pdf, jpg, png, etc.)")
    mime_type = Column(String(100), nullable=True, comment="MIME type of the file")
    
    # Document metadata
    document_number = Column(String(100), nullable=True, comment="Document number (if applicable)")
    issue_date = Column(DateTime, nullable=True, comment="Document issue date")
    expiry_date = Column(DateTime, nullable=True, comment="Document expiry date")
    issuing_authority = Column(String(200), nullable=True, comment="Authority that issued the document")
    
    # Processing status
    is_verified = Column(Boolean, nullable=False, default=False, comment="Document has been verified")
    verification_status = Column(String(20), nullable=False, default="pending", comment="Verification status")
    verification_notes = Column(Text, nullable=True, comment="Verification notes")
    
    # Audit fields
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who uploaded the document")
    uploaded_at = Column(DateTime, nullable=False, default=func.now(), comment="Upload timestamp")
    verified_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who verified the document")
    verified_at = Column(DateTime, nullable=True, comment="Verification timestamp")
    
    # Relationships
    application = relationship("Application", back_populates="documents")
    uploaded_by_user = relationship("User", foreign_keys=[uploaded_by])
    verified_by_user = relationship("User", foreign_keys=[verified_by])

    def __repr__(self):
        return f"<ApplicationDocument(application_id={self.application_id}, type='{self.document_type}', name='{self.document_name}')>"


class ApplicationAuthorization(BaseModel):
    """Application authorization for license generation"""
    __tablename__ = "application_authorizations"

    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, unique=True, comment="Application ID (one authorization per application)")
    examiner_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="Examiner who conducted the authorization")
    infrastructure_number = Column(String(20), nullable=True, comment="Infrastructure number for the authorization")
    
    # Test results
    is_absent = Column(Boolean, nullable=False, default=False, comment="Applicant was absent for test")
    is_failed = Column(Boolean, nullable=False, default=False, comment="Applicant failed the test")
    eye_test_result = Column(String(10), nullable=True, comment="Eye test result (PASS/FAIL)")
    driving_test_result = Column(String(10), nullable=True, comment="Driving test result (PASS/FAIL)")
    driving_test_score = Column(Numeric(5, 2), nullable=True, comment="Driving test score")
    
    # Vehicle restrictions
    vehicle_restriction_none = Column(Boolean, nullable=False, default=True, comment="No vehicle restrictions")
    vehicle_restriction_automatic = Column(Boolean, nullable=False, default=False, comment="Automatic transmission only")
    vehicle_restriction_electric = Column(Boolean, nullable=False, default=False, comment="Electric vehicles only")
    vehicle_restriction_disabled = Column(Boolean, nullable=False, default=False, comment="Vehicles adapted for disabilities")
    
    # Driver restrictions  
    driver_restriction_none = Column(Boolean, nullable=False, default=True, comment="No driver restrictions")
    driver_restriction_glasses = Column(Boolean, nullable=False, default=False, comment="Must wear corrective lenses")
    driver_restriction_artificial_limb = Column(Boolean, nullable=False, default=False, comment="Uses artificial limb")
    driver_restriction_glasses_and_limb = Column(Boolean, nullable=False, default=False, comment="Glasses and artificial limb")
    
    # Authorization decision
    is_authorized = Column(Boolean, nullable=False, default=False, comment="Application is authorized for license generation")
    authorization_date = Column(DateTime, nullable=True, comment="Date authorization was granted")
    authorization_notes = Column(Text, nullable=True, comment="Authorization notes and comments")
    
    # Additional test details
    test_location = Column(String(200), nullable=True, comment="Location where test was conducted")
    test_vehicle_details = Column(String(500), nullable=True, comment="Details of test vehicle used")
    weather_conditions = Column(String(100), nullable=True, comment="Weather conditions during test")
    
    # Audit fields
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="Authorization creation timestamp")
    updated_at = Column(DateTime, nullable=True, onupdate=func.now(), comment="Last update timestamp")
    
    # Relationships
    application = relationship("Application", back_populates="authorization")
    examiner = relationship("User", foreign_keys=[examiner_id])

    @property
    def test_passed(self) -> bool:
        """Check if all tests were passed"""
        return (
            not self.is_absent and
            not self.is_failed and
            self.eye_test_result == "PASS" and
            self.driving_test_result == "PASS"
        )
    
    def get_restriction_codes(self) -> list:
        """Get list of applicable license restriction codes"""
        from app.models.enums import LicenseRestrictionCode
        
        codes = []
        
        # Driver restrictions
        if self.driver_restriction_glasses:
            codes.append(LicenseRestrictionCode.CORRECTIVE_LENSES)
        
        if self.driver_restriction_artificial_limb:
            codes.append(LicenseRestrictionCode.PROSTHETICS)
            
        if self.driver_restriction_glasses_and_limb:
            codes.append(LicenseRestrictionCode.CORRECTIVE_LENSES)
            codes.append(LicenseRestrictionCode.PROSTHETICS)
        
        # Vehicle restrictions
        if self.vehicle_restriction_automatic:
            codes.append(LicenseRestrictionCode.AUTOMATIC_TRANSMISSION)
            
        if self.vehicle_restriction_electric:
            codes.append(LicenseRestrictionCode.ELECTRIC_POWERED)
            
        if self.vehicle_restriction_disabled:
            codes.append(LicenseRestrictionCode.PHYSICAL_DISABLED)
        
        return list(set(codes))  # Remove duplicates
    
    def __repr__(self):
        return f"<ApplicationAuthorization(application_id={self.application_id}, examiner_id={self.examiner_id}, authorized={self.is_authorized})>" 