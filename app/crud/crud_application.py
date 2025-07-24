"""
CRUD operations for Application Management in Madagascar License System
Handles all application-related database operations with comprehensive workflow support
"""

from typing import List, Optional, Dict, Any, Union
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, asc, func, cast, String, extract
from datetime import datetime, timedelta
import uuid
from uuid import UUID

from app.crud.base import CRUDBase
from app.models.application import (
    Application, ApplicationBiometricData, ApplicationTestAttempt, 
    ApplicationStatusHistory, ApplicationDocument
)
from app.models.enums import (
    LicenseCategory, ApplicationType, ApplicationStatus,
    TestAttemptType, TestResult, PaymentStatus, BiometricDataType,
    MedicalCertificateStatus, ParentalConsentStatus
)
from app.schemas.application import (
    ApplicationCreate, ApplicationUpdate, ApplicationSearch,
    ApplicationBiometricDataCreate, ApplicationBiometricDataUpdate,
    ApplicationTestAttemptCreate, ApplicationTestAttemptUpdate,
    ApplicationDocumentCreate, ApplicationDocumentUpdate
)


class CRUDApplication(CRUDBase[Application, ApplicationCreate, ApplicationUpdate]):
    """CRUD operations for Applications"""
    
    def create_with_details(
        self, 
        db: Session, 
        *, 
        obj_in: ApplicationCreate,
        created_by_user_id: uuid.UUID
    ) -> Application:
        """Create application with full details and initial status history"""
        
        # Generate unique application number
        application_number = self.generate_application_number(db, obj_in.application_type, obj_in.location_id)
        
        # Calculate draft expiry (30 days from now)
        draft_expires_at = datetime.utcnow() + timedelta(days=30)
        
        # Convert ApplicationCreate to dict and handle enum serialization
        obj_data = obj_in.dict(exclude={'application_number'})
        
        # Note: Enum conversion is handled by Pydantic validators in schemas
        # SQLAlchemy with native_enum=False will handle enum-to-string conversion automatically
        
        # Handle professional_permit_categories list
        if 'professional_permit_categories' in obj_data and obj_data['professional_permit_categories']:
            obj_data['professional_permit_categories'] = [
                category.value if hasattr(category, 'value') else str(category)
                for category in obj_data['professional_permit_categories']
            ]
        
        # Create application
        db_obj = Application(
            application_number=application_number,
            draft_expires_at=draft_expires_at,
            **obj_data
        )
        
        # Set audit fields
        db_obj.created_by = created_by_user_id
        db_obj.updated_by = created_by_user_id
        
        db.add(db_obj)
        db.flush()  # Get the ID
        
        # Create initial status history
        status_history = ApplicationStatusHistory(
            application_id=db_obj.id,
            previous_status=None,
            new_status=ApplicationStatus.DRAFT,
            changed_by=created_by_user_id,
            change_reason="Application created",
            change_notes="Initial application creation"
        )
        db.add(status_history)
        
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def generate_application_number(
        self, 
        db: Session, 
        application_type: ApplicationType, 
        location_id: uuid.UUID
    ) -> str:
        """Generate unique application number: {LOCATION_CODE}-{TYPE_CODE}-{YEAR}-{SEQUENCE}"""
        from app.models.user import Location
        
        # Get location code
        location = db.query(Location).filter(Location.id == location_id).first()
        if not location:
            raise ValueError("Location not found")
        
        # Type codes mapping
        type_codes = {
            ApplicationType.NEW_LICENSE: "NL",
            ApplicationType.LEARNERS_PERMIT: "LP", 
            ApplicationType.RENEWAL: "RN",
            ApplicationType.REPLACEMENT: "RP",
            ApplicationType.TEMPORARY_LICENSE: "TL",
            ApplicationType.INTERNATIONAL_PERMIT: "IP"
        }
        
        type_code = type_codes.get(application_type, "XX")
        current_year = datetime.utcnow().year
        
        # Get next sequence number for this location, type, and year
        prefix = f"{location.code}-{type_code}-{current_year}"
        
        last_app = db.query(Application).filter(
            Application.application_number.like(f"{prefix}-%")
        ).order_by(desc(Application.application_number)).first()
        
        if last_app:
            try:
                last_sequence = int(last_app.application_number.split('-')[-1])
                next_sequence = last_sequence + 1
            except (ValueError, IndexError):
                next_sequence = 1
        else:
            next_sequence = 1
        
        return f"{prefix}-{next_sequence:04d}"
    
    def get_by_person_id(
        self,
        db: Session,
        *,
        person_id: UUID,
        status_filter: Optional[List[ApplicationStatus]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Application]:
        """Get applications for a person with optional status filtering"""
        query = db.query(Application).options(
            joinedload(Application.person),
            joinedload(Application.location),
            joinedload(Application.assigned_to_user)
        ).filter(Application.person_id == person_id)
        
        if status_filter:
            query = query.filter(Application.status.in_(status_filter))
        
        return query.order_by(desc(Application.application_date)).offset(skip).limit(limit).all()
    
    def search_applications(
        self, 
        db: Session, 
        *, 
        search_params: ApplicationSearch,
        skip: int = 0,
        limit: int = 100
    ) -> List[Application]:
        """Advanced application search with multiple criteria"""
        
        query = db.query(Application).options(
            joinedload(Application.person),
            joinedload(Application.location),
            joinedload(Application.assigned_to_user)
        )
        
        # Apply search filters
        if search_params.application_number:
            query = query.filter(Application.application_number.ilike(f"%{search_params.application_number}%"))
        
        if search_params.person_id:
            query = query.filter(Application.person_id == search_params.person_id)
        
        if search_params.application_type:
            query = query.filter(Application.application_type == search_params.application_type)
        
        if search_params.status:
            query = query.filter(Application.status == search_params.status)
        
        if search_params.location_id:
            query = query.filter(Application.location_id == search_params.location_id)
        
        if search_params.assigned_to_user_id:
            query = query.filter(Application.assigned_to_user_id == search_params.assigned_to_user_id)
        
        if search_params.license_category:
            query = query.filter(Application.license_category == search_params.license_category)
        
        if search_params.replacement_reason:
            query = query.filter(Application.replacement_reason == search_params.replacement_reason)
        
        if search_params.date_from:
            query = query.filter(Application.application_date >= search_params.date_from)
        
        if search_params.date_to:
            query = query.filter(Application.application_date <= search_params.date_to)
        
        if search_params.is_urgent is not None:
            query = query.filter(Application.is_urgent == search_params.is_urgent)
        
        if search_params.is_on_hold is not None:
            query = query.filter(Application.is_on_hold == search_params.is_on_hold)
        
        if search_params.is_temporary_license is not None:
            query = query.filter(Application.is_temporary_license == search_params.is_temporary_license)
        
        # Apply sorting
        if search_params.sort_by:
            if search_params.sort_order == "desc":
                query = query.order_by(desc(getattr(Application, search_params.sort_by)))
            else:
                query = query.order_by(asc(getattr(Application, search_params.sort_by)))
        else:
            # Default sort by application date descending
            query = query.order_by(desc(Application.application_date))
        
        return query.offset(skip).limit(limit).all()
    
    def get_by_application_number(self, db: Session, *, application_number: str) -> Optional[Application]:
        """Get application by application number"""
        return db.query(Application).filter(Application.application_number == application_number).first()
    
    def get_applications_by_person(self, db: Session, *, person_id: uuid.UUID) -> List[Application]:
        """Get all applications for a specific person"""
        return db.query(Application).filter(Application.person_id == person_id).order_by(desc(Application.application_date)).all()
    
    def get_associated_applications(self, db: Session, *, parent_application_id: uuid.UUID) -> List[Application]:
        """Get all applications associated with a parent application"""
        return db.query(Application).filter(Application.parent_application_id == parent_application_id).all()
    
    def update_status(
        self, 
        db: Session, 
        *, 
        application_id: uuid.UUID,
        new_status: ApplicationStatus,
        changed_by: uuid.UUID,
        reason: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Application:
        """Update application status with history tracking"""
        
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            raise ValueError("Application not found")
        
        old_status = application.status
        
        # Update application
        application.status = new_status  
        application.updated_by = changed_by
        application.updated_at = datetime.utcnow()
        
        # Handle status-specific updates
        if new_status == ApplicationStatus.SUBMITTED:
            application.submitted_date = datetime.utcnow()
        elif new_status == ApplicationStatus.COMPLETED:
            application.actual_completion_date = datetime.utcnow()
        
        # Create status history entry
        status_history = ApplicationStatusHistory(
            application_id=application_id,
            previous_status=old_status,
            new_status=new_status,
            changed_by=changed_by,
            change_reason=reason,
            change_notes=notes
        )
        db.add(status_history)
        
        db.commit()
        db.refresh(application)
        return application
    
    def get_applications_by_status(self, db: Session, *, status: ApplicationStatus) -> List[Application]:
        """Get all applications with specific status"""
        return db.query(Application).filter(Application.status == status).all()
    
    def get_expired_drafts(self, db: Session) -> List[Application]:
        """Get all expired draft applications for cleanup"""
        return db.query(Application).filter(
            and_(
                Application.status == ApplicationStatus.DRAFT,
                Application.draft_expires_at < datetime.utcnow()
            )
        ).all()
    
    def delete_expired_drafts(self, db: Session) -> int:
        """Delete expired draft applications and return count"""
        expired_drafts = self.get_expired_drafts(db)
        count = len(expired_drafts)
        
        for draft in expired_drafts:
            db.delete(draft)
        
        db.commit()
        return count
    
    def get_application_statistics(self, db: Session, *, location_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        """Get application statistics"""
        query = db.query(Application)
        
        if location_id:
            query = query.filter(Application.location_id == location_id)
        
        total_applications = query.count()
        
        # Status breakdown
        status_stats = {}
        for status in ApplicationStatus:
            count = query.filter(Application.status == status).count()
            status_stats[status.value] = count
        
        # Type breakdown
        type_stats = {}
        for app_type in ApplicationType:
            count = query.filter(Application.application_type == app_type).count()
            type_stats[app_type.value] = count
        
        # Recent activity (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_applications = query.filter(Application.application_date >= thirty_days_ago).count()
        
        return {
            "total_applications": total_applications,
            "status_breakdown": status_stats,
            "type_breakdown": type_stats,
            "recent_applications_30_days": recent_applications
        }


class CRUDApplicationBiometricData(CRUDBase[ApplicationBiometricData, ApplicationBiometricDataCreate, ApplicationBiometricDataUpdate]):
    """CRUD operations for Application Biometric Data"""
    
    def create_biometric_data(
        self, 
        db: Session, 
        *, 
        obj_in: ApplicationBiometricDataCreate,
        created_by_user_id: uuid.UUID
    ) -> ApplicationBiometricData:
        """Create biometric data entry"""
        import logging
        logger = logging.getLogger(__name__)
        
        obj_dict = obj_in.dict()
        logger.info(f"=== CRUD CREATE DEBUG ===")
        logger.info(f"Input metadata type: {type(obj_dict.get('capture_metadata'))}")
        logger.info(f"Input metadata value: {obj_dict.get('capture_metadata')}")
        
        db_obj = ApplicationBiometricData(**obj_dict)
        logger.info(f"DB object metadata type: {type(db_obj.capture_metadata)}")
        logger.info(f"DB object metadata value: {db_obj.capture_metadata}")
        
        db_obj.created_by = created_by_user_id
        db_obj.updated_by = created_by_user_id
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        
        logger.info(f"After commit metadata type: {type(db_obj.capture_metadata)}")
        logger.info(f"After commit metadata value: {db_obj.capture_metadata}")
        
        return db_obj
    
    def get_by_application(self, db: Session, *, application_id: uuid.UUID) -> List[ApplicationBiometricData]:
        """Get all biometric data for an application"""
        return db.query(ApplicationBiometricData).filter(ApplicationBiometricData.application_id == application_id).all()
    
    def get_by_application_and_type(self, db: Session, *, application_id: uuid.UUID, data_type: str) -> Optional[ApplicationBiometricData]:
        """Get specific biometric data by application and data type"""
        from app.models.enums import BiometricDataType
        
        # Convert string to enum
        try:
            data_type_enum = BiometricDataType(data_type.upper())
        except ValueError:
            return None
        
        return db.query(ApplicationBiometricData).filter(
            ApplicationBiometricData.application_id == application_id,
            ApplicationBiometricData.data_type == data_type_enum
        ).first()
    
    def verify_biometric_data(
        self, 
        db: Session, 
        *, 
        biometric_id: uuid.UUID,
        verified_by: uuid.UUID,
        quality_score: Optional[float] = None,
        notes: Optional[str] = None
    ) -> ApplicationBiometricData:
        """Mark biometric data as verified"""
        biometric = db.query(ApplicationBiometricData).filter(ApplicationBiometricData.id == biometric_id).first()
        if not biometric:
            raise ValueError("Biometric data not found")
        
        biometric.is_verified = True
        biometric.verified_by = verified_by
        biometric.verified_at = datetime.utcnow()
        if quality_score is not None:
            biometric.quality_score = quality_score
        if notes:
            biometric.notes = notes
        
        db.commit()
        db.refresh(biometric)
        return biometric


class CRUDApplicationTestAttempt(CRUDBase[ApplicationTestAttempt, ApplicationTestAttemptCreate, ApplicationTestAttemptUpdate]):
    """CRUD operations for Application Test Attempts"""
    
    def create_test_attempt(
        self, 
        db: Session, 
        *, 
        obj_in: ApplicationTestAttemptCreate,
        created_by_user_id: uuid.UUID
    ) -> ApplicationTestAttempt:
        """Create test attempt with auto-generated attempt number"""
        
        # Get the next attempt number for this application and test type
        last_attempt = db.query(ApplicationTestAttempt).filter(
            and_(
                ApplicationTestAttempt.application_id == obj_in.application_id,
                ApplicationTestAttempt.test_type == obj_in.test_type
            )
        ).order_by(desc(ApplicationTestAttempt.attempt_number)).first()
        
        attempt_number = 1 if not last_attempt else last_attempt.attempt_number + 1
        
        db_obj = ApplicationTestAttempt(
            attempt_number=attempt_number,
            **obj_in.dict()
        )
        db_obj.created_by = created_by_user_id
        db_obj.updated_by = created_by_user_id
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_by_application(self, db: Session, *, application_id: uuid.UUID) -> List[ApplicationTestAttempt]:
        """Get all test attempts for an application"""
        return db.query(ApplicationTestAttempt).filter(
            ApplicationTestAttempt.application_id == application_id
        ).order_by(ApplicationTestAttempt.test_type, ApplicationTestAttempt.attempt_number).all()
    
    def get_latest_attempt(
        self, 
        db: Session, 
        *, 
        application_id: uuid.UUID, 
        test_type: TestAttemptType
    ) -> Optional[ApplicationTestAttempt]:
        """Get the latest test attempt for specific type"""
        return db.query(ApplicationTestAttempt).filter(
            and_(
                ApplicationTestAttempt.application_id == application_id,
                ApplicationTestAttempt.test_type == test_type
            )
        ).order_by(desc(ApplicationTestAttempt.attempt_number)).first()
    
    def record_test_result(
        self, 
        db: Session, 
        *, 
        test_attempt_id: uuid.UUID,
        result: TestResult,
        score: Optional[float] = None,
        examiner_id: Optional[uuid.UUID] = None,
        result_notes: Optional[str] = None
    ) -> ApplicationTestAttempt:
        """Record test result"""
        test_attempt = db.query(ApplicationTestAttempt).filter(ApplicationTestAttempt.id == test_attempt_id).first()
        if not test_attempt:
            raise ValueError("Test attempt not found")
        
        test_attempt.test_result = result
        test_attempt.actual_date = datetime.utcnow()
        
        if score is not None:
            test_attempt.score = score
        if examiner_id:
            test_attempt.examiner_id = examiner_id
        if result_notes:
            test_attempt.result_notes = result_notes
        
        # Issue learner's permit for passed theory tests
        if (test_attempt.test_type == TestAttemptType.THEORY and 
            result == TestResult.PASSED and 
            not test_attempt.learners_permit_issued):
            test_attempt.learners_permit_issued = True
            test_attempt.learners_permit_number = self._generate_learners_permit_number(db)
            test_attempt.learners_permit_expiry = datetime.utcnow() + timedelta(days=180)  # 6 months
        
        db.commit()
        db.refresh(test_attempt)
        return test_attempt
    
    def _generate_learners_permit_number(self, db: Session) -> str:
        """Generate unique learner's permit number"""
        current_year = datetime.utcnow().year
        
        # Get the last permit number for this year
        last_permit = db.query(ApplicationTestAttempt).filter(
            and_(
                ApplicationTestAttempt.learners_permit_number.is_not(None),
                ApplicationTestAttempt.learners_permit_number.like(f"LP{current_year}%")
            )
        ).order_by(desc(ApplicationTestAttempt.learners_permit_number)).first()
        
        if last_permit:
            try:
                last_sequence = int(last_permit.learners_permit_number[-4:])
                next_sequence = last_sequence + 1
            except ValueError:
                next_sequence = 1
        else:
            next_sequence = 1
        
        return f"LP{current_year}{next_sequence:04d}"





class CRUDApplicationDocument(CRUDBase[ApplicationDocument, ApplicationDocumentCreate, ApplicationDocumentUpdate]):
    """CRUD operations for Application Documents"""
    
    def get_by_application(self, db: Session, *, application_id: uuid.UUID) -> List[ApplicationDocument]:
        """Get all documents for an application"""
        return db.query(ApplicationDocument).filter(ApplicationDocument.application_id == application_id).all()
    
    def verify_document(
        self, 
        db: Session, 
        *, 
        document_id: uuid.UUID,
        verified_by: uuid.UUID,
        verification_notes: Optional[str] = None
    ) -> ApplicationDocument:
        """Mark document as verified"""
        document = db.query(ApplicationDocument).filter(ApplicationDocument.id == document_id).first()
        if not document:
            raise ValueError("Document not found")
        
        document.is_verified = True
        document.verified_by = verified_by
        document.verified_at = datetime.utcnow()
        if verification_notes:
            document.verification_notes = verification_notes
        
        db.commit()
        db.refresh(document)
        return document





# Create CRUD instances
crud_application = CRUDApplication(Application)
crud_application_biometric_data = CRUDApplicationBiometricData(ApplicationBiometricData)
crud_application_test_attempt = CRUDApplicationTestAttempt(ApplicationTestAttempt)
crud_application_document = CRUDApplicationDocument(ApplicationDocument) 