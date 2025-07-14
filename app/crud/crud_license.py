"""
CRUD operations for License Management in Madagascar License System
Handles license creation, updates, queries, and status management
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import and_, or_, desc, func, text
from fastapi import HTTPException, status

from app.crud.base import CRUDBase
from app.models.license import License, LicenseCard, LicenseStatusHistory, LicenseSequenceCounter, LicenseStatus, CardStatus
from app.models.application import Application
from app.models.person import Person
from app.models.user import User, Location
from app.schemas.license import (
    LicenseCreateFromApplication, LicenseCreate, LicenseStatusUpdate,
    LicenseRestrictionsUpdate, LicenseProfessionalPermitUpdate,
    LicenseSearchFilters, CardCreate, CardStatusUpdate
)


class CRUDLicense(CRUDBase[License, LicenseCreate, dict]):
    """CRUD operations for License model"""

    def create_from_application(
        self,
        db: Session,
        *,
        obj_in: LicenseCreateFromApplication,
        current_user: User
    ) -> License:
        """
        Create a license from a completed application
        This is the primary method for license creation
        """
        # Get the application and validate it exists and is completed
        application = db.query(Application).filter(Application.id == obj_in.application_id).first()
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application {obj_in.application_id} not found"
            )
        
        # Validate application is in appropriate status for license creation
        valid_statuses = ["APPROVED", "COMPLETED", "SENT_TO_PRINTER"]
        if application.status.value not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Application must be approved/completed to create license. Current status: {application.status}"
            )
        
        # Check if license already exists for this application
        existing_license = self.get_by_application_id(db, application_id=obj_in.application_id)
        if existing_license:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"License already exists for application {obj_in.application_id}"
            )
        
        # Get person from application
        person = db.query(Person).filter(Person.id == application.person_id).first()
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Person {application.person_id} not found"
            )
        
        # Get location for license number generation
        location = db.query(Location).filter(Location.id == application.location_id).first()
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location {application.location_id} not found"
            )
        
        # Generate license number
        sequence_number = LicenseSequenceCounter.get_next_sequence(db, user_id=str(current_user.id))
        license_number = License.generate_license_number(location.code, sequence_number)
        
        # Prepare license data
        license_data = {
            "license_number": license_number,
            "person_id": application.person_id,
            "created_from_application_id": obj_in.application_id,
            "category": obj_in.license_category,
            "status": LicenseStatus.ACTIVE,
            "issue_date": datetime.utcnow(),
            "issuing_location_id": application.location_id,
            "issued_by_user_id": current_user.id,
            "restrictions": obj_in.restrictions or [],
            "medical_restrictions": obj_in.medical_restrictions or [],
            "has_professional_permit": obj_in.has_professional_permit,
            "professional_permit_categories": obj_in.professional_permit_categories or [],
            "professional_permit_expiry": obj_in.professional_permit_expiry,
            "captured_from_license_number": obj_in.captured_from_license_number,
            "sadc_compliance_verified": True,
            "international_validity": True,
            "vienna_convention_compliant": True
        }
        
        # Create license
        db_license = License(**license_data)
        db.add(db_license)
        db.flush()  # Get the ID for relationships
        
        # Create initial status history
        status_history = LicenseStatusHistory(
            license_id=db_license.id,
            from_status=None,
            to_status=LicenseStatus.ACTIVE,
            changed_by=current_user.id,
            changed_at=datetime.utcnow(),
            reason="License issued",
            notes=f"License created from application {obj_in.application_id}",
            system_initiated=True
        )
        db.add(status_history)
        
        # Create card if requested
        if obj_in.order_card_immediately:
            card_expiry = datetime.utcnow() + timedelta(days=obj_in.card_expiry_years * 365)
            card_number = LicenseCard.generate_card_number(license_number, 1)
            
            card_data = {
                "card_number": card_number,
                "license_id": db_license.id,
                "status": CardStatus.PENDING_PRODUCTION,
                "card_type": "STANDARD",
                "issue_date": datetime.utcnow(),
                "expiry_date": card_expiry,
                "valid_from": datetime.utcnow(),
                "ordered_date": datetime.utcnow(),
                "card_template": "MADAGASCAR_STANDARD",
                "iso_compliance_version": "18013-1:2018",
                "is_current": True
            }
            
            db_card = LicenseCard(**card_data)
            db.add(db_card)
        
        db.commit()
        db.refresh(db_license)
        
        return db_license

    def create_manual(
        self,
        db: Session,
        *,
        obj_in: LicenseCreate,
        current_user: User
    ) -> License:
        """
        Create a license manually (for admin/special cases)
        """
        # Validate person exists
        person = db.query(Person).filter(Person.id == obj_in.person_id).first()
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Person {obj_in.person_id} not found"
            )
        
        # Validate location exists
        location = db.query(Location).filter(Location.id == obj_in.issuing_location_id).first()
        if not location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Location {obj_in.issuing_location_id} not found"
            )
        
        # Generate license number
        sequence_number = LicenseSequenceCounter.get_next_sequence(db, user_id=str(current_user.id))
        license_number = License.generate_license_number(location.code, sequence_number)
        
        # Prepare license data
        license_data = {
            "license_number": license_number,
            "person_id": obj_in.person_id,
            "category": obj_in.license_category,
            "status": LicenseStatus.ACTIVE,
            "issue_date": datetime.utcnow(),
            "issuing_location_id": obj_in.issuing_location_id,
            "issued_by_user_id": current_user.id,
            "restrictions": obj_in.restrictions or [],
            "medical_restrictions": obj_in.medical_restrictions or [],
            "has_professional_permit": obj_in.has_professional_permit,
            "professional_permit_categories": obj_in.professional_permit_categories or [],
            "professional_permit_expiry": obj_in.professional_permit_expiry,
            "captured_from_license_number": obj_in.captured_from_license_number,
            "sadc_compliance_verified": True,
            "international_validity": True,
            "vienna_convention_compliant": True
        }
        
        # Create license
        db_license = License(**license_data)
        db.add(db_license)
        db.flush()
        
        # Create initial status history
        status_history = LicenseStatusHistory(
            license_id=db_license.id,
            from_status=None,
            to_status=LicenseStatus.ACTIVE,
            changed_by=current_user.id,
            changed_at=datetime.utcnow(),
            reason="Manual license creation",
            system_initiated=False
        )
        db.add(status_history)
        
        db.commit()
        db.refresh(db_license)
        
        return db_license

    def get_by_license_number(self, db: Session, *, license_number: str) -> Optional[License]:
        """Get license by license number"""
        return db.query(License).filter(License.license_number == license_number.upper()).first()

    def get_by_application_id(self, db: Session, *, application_id: UUID) -> Optional[License]:
        """Get license by application ID"""
        return db.query(License).filter(License.created_from_application_id == application_id).first()

    def get_by_person_id(
        self,
        db: Session,
        *,
        person_id: UUID,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[License]:
        """Get all licenses for a person"""
        query = db.query(License).filter(License.person_id == person_id)
        
        if active_only:
            query = query.filter(License.status == LicenseStatus.ACTIVE)
        
        return query.order_by(desc(License.issue_date)).offset(skip).limit(limit).all()

    def search_licenses(
        self,
        db: Session,
        *,
        filters: LicenseSearchFilters
    ) -> Tuple[List[License], int]:
        """Search licenses with filters and pagination"""
        query = db.query(License)
        
        # Apply filters
        if filters.license_number:
            query = query.filter(License.license_number.ilike(f"%{filters.license_number}%"))
        
        if filters.person_id:
            query = query.filter(License.person_id == filters.person_id)
        
        if filters.category:
            query = query.filter(License.category == filters.category)
        
        if filters.status:
            query = query.filter(License.status == filters.status)
        
        if filters.issuing_location_id:
            query = query.filter(License.issuing_location_id == filters.issuing_location_id)
        
        if filters.issued_after:
            query = query.filter(func.date(License.issue_date) >= filters.issued_after)
        
        if filters.issued_before:
            query = query.filter(func.date(License.issue_date) <= filters.issued_before)
        
        if filters.has_professional_permit is not None:
            query = query.filter(License.has_professional_permit == filters.has_professional_permit)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        licenses = query.order_by(desc(License.issue_date)).offset(
            (filters.page - 1) * filters.size
        ).limit(filters.size).all()
        
        return licenses, total

    def update_status(
        self,
        db: Session,
        *,
        license_id: UUID,
        status_update: LicenseStatusUpdate,
        current_user: User
    ) -> License:
        """Update license status with history tracking"""
        license_obj = self.get(db, id=license_id)
        if not license_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"License {license_id} not found"
            )
        
        old_status = license_obj.status
        
        # Update license
        license_obj.status = status_update.status
        license_obj.status_changed_date = datetime.utcnow()
        license_obj.status_changed_by = current_user.id
        
        # Handle suspension
        if status_update.status == LicenseStatus.SUSPENDED:
            license_obj.suspension_reason = status_update.reason
            license_obj.suspension_start_date = status_update.suspension_start_date or datetime.utcnow()
            license_obj.suspension_end_date = status_update.suspension_end_date
        
        # Handle cancellation
        if status_update.status == LicenseStatus.CANCELLED:
            license_obj.cancellation_reason = status_update.reason
            license_obj.cancellation_date = datetime.utcnow()
        
        # Create status history record
        status_history = LicenseStatusHistory(
            license_id=license_id,
            from_status=old_status,
            to_status=status_update.status,
            changed_by=current_user.id,
            changed_at=datetime.utcnow(),
            reason=status_update.reason,
            notes=status_update.notes,
            suspension_start_date=status_update.suspension_start_date,
            suspension_end_date=status_update.suspension_end_date,
            system_initiated=False
        )
        db.add(status_history)
        
        db.commit()
        db.refresh(license_obj)
        
        return license_obj

    def update_restrictions(
        self,
        db: Session,
        *,
        license_id: UUID,
        restrictions_update: LicenseRestrictionsUpdate,
        current_user: User
    ) -> License:
        """Update license restrictions"""
        license_obj = self.get(db, id=license_id)
        if not license_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"License {license_id} not found"
            )
        
        license_obj.restrictions = restrictions_update.restrictions
        license_obj.medical_restrictions = restrictions_update.medical_restrictions or []
        license_obj.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(license_obj)
        
        return license_obj

    def update_professional_permit(
        self,
        db: Session,
        *,
        license_id: UUID,
        permit_update: LicenseProfessionalPermitUpdate,
        current_user: User
    ) -> License:
        """Update professional permit information"""
        license_obj = self.get(db, id=license_id)
        if not license_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"License {license_id} not found"
            )
        
        license_obj.has_professional_permit = permit_update.has_professional_permit
        license_obj.professional_permit_categories = permit_update.professional_permit_categories
        license_obj.professional_permit_expiry = permit_update.professional_permit_expiry
        license_obj.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(license_obj)
        
        return license_obj

    def get_with_details(self, db: Session, *, license_id: UUID) -> Optional[License]:
        """Get license with all related data loaded"""
        return db.query(License).options(
            selectinload(License.cards),
            selectinload(License.status_history),
            selectinload(License.person),
            selectinload(License.issuing_location),
            selectinload(License.issued_by_user)
        ).filter(License.id == license_id).first()

    def get_statistics(self, db: Session) -> Dict[str, Any]:
        """Get license statistics"""
        # Basic counts
        total_licenses = db.query(License).count()
        active_licenses = db.query(License).filter(License.status == LicenseStatus.ACTIVE).count()
        suspended_licenses = db.query(License).filter(License.status == LicenseStatus.SUSPENDED).count()
        cancelled_licenses = db.query(License).filter(License.status == LicenseStatus.CANCELLED).count()
        
        # By category
        category_stats = db.query(
            License.category,
            func.count(License.id)
        ).group_by(License.category).all()
        
        by_category = {cat.value: count for cat, count in category_stats}
        
        # By location
        location_stats = db.query(
            Location.name,
            func.count(License.id)
        ).join(Location, License.issuing_location_id == Location.id).group_by(Location.name).all()
        
        by_location = {name: count for name, count in location_stats}
        
        # Recent activity
        this_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_year_start = datetime.utcnow().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        
        issued_this_month = db.query(License).filter(License.issue_date >= this_month_start).count()
        issued_this_year = db.query(License).filter(License.issue_date >= this_year_start).count()
        
        # Card statistics
        cards_pending_collection = db.query(LicenseCard).filter(
            LicenseCard.status == CardStatus.READY_FOR_COLLECTION
        ).count()
        
        expiry_threshold = datetime.utcnow() + timedelta(days=90)
        cards_near_expiry = db.query(LicenseCard).filter(
            and_(
                LicenseCard.is_current == True,
                LicenseCard.expiry_date <= expiry_threshold,
                LicenseCard.expiry_date > datetime.utcnow()
            )
        ).count()
        
        return {
            "total_licenses": total_licenses,
            "active_licenses": active_licenses,
            "suspended_licenses": suspended_licenses,
            "cancelled_licenses": cancelled_licenses,
            "by_category": by_category,
            "by_location": by_location,
            "issued_this_month": issued_this_month,
            "issued_this_year": issued_this_year,
            "cards_pending_collection": cards_pending_collection,
            "cards_near_expiry": cards_near_expiry
        }

    def validate_license_number(self, license_number: str) -> Dict[str, Any]:
        """Validate license number format and return breakdown"""
        try:
            is_valid = License.validate_license_number(license_number)
            
            if is_valid and len(license_number) == 12:
                location_code = license_number[:3]
                sequence_str = license_number[3:11]
                check_digit = int(license_number[11])
                
                return {
                    "license_number": license_number,
                    "is_valid": True,
                    "error_message": None,
                    "location_code": location_code,
                    "sequence_number": int(sequence_str),
                    "check_digit": check_digit
                }
            else:
                return {
                    "license_number": license_number,
                    "is_valid": False,
                    "error_message": "Invalid license number format or check digit",
                    "location_code": None,
                    "sequence_number": None,
                    "check_digit": None
                }
        
        except Exception as e:
            return {
                "license_number": license_number,
                "is_valid": False,
                "error_message": str(e),
                "location_code": None,
                "sequence_number": None,
                "check_digit": None
            }


class CRUDLicenseCard(CRUDBase[LicenseCard, CardCreate, dict]):
    """CRUD operations for License Card model"""

    def create_card(
        self,
        db: Session,
        *,
        obj_in: CardCreate,
        current_user: User
    ) -> LicenseCard:
        """Create a new card for existing license"""
        # Get license
        license_obj = db.query(License).filter(License.id == obj_in.license_id).first()
        if not license_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"License {obj_in.license_id} not found"
            )
        
        # Mark previous cards as not current
        db.query(LicenseCard).filter(
            and_(
                LicenseCard.license_id == obj_in.license_id,
                LicenseCard.is_current == True
            )
        ).update({"is_current": False})
        
        # Get next card sequence
        existing_cards = db.query(LicenseCard).filter(LicenseCard.license_id == obj_in.license_id).count()
        card_sequence = existing_cards + 1
        
        # Generate card number
        card_number = LicenseCard.generate_card_number(license_obj.license_number, card_sequence)
        
        # Calculate expiry date
        expiry_date = datetime.utcnow() + timedelta(days=obj_in.expiry_years * 365)
        
        # Create card
        card_data = {
            "card_number": card_number,
            "license_id": obj_in.license_id,
            "status": CardStatus.PENDING_PRODUCTION,
            "card_type": obj_in.card_type,
            "issue_date": datetime.utcnow(),
            "expiry_date": expiry_date,
            "valid_from": datetime.utcnow(),
            "ordered_date": datetime.utcnow(),
            "card_template": "MADAGASCAR_STANDARD",
            "iso_compliance_version": "18013-1:2018",
            "is_current": True,
            "replacement_reason": obj_in.replacement_reason
        }
        
        db_card = LicenseCard(**card_data)
        db.add(db_card)
        db.commit()
        db.refresh(db_card)
        
        return db_card

    def update_card_status(
        self,
        db: Session,
        *,
        card_id: UUID,
        status_update: CardStatusUpdate,
        current_user: User
    ) -> LicenseCard:
        """Update card status"""
        card = self.get(db, id=card_id)
        if not card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Card {card_id} not found"
            )
        
        # Update status and related fields
        card.status = status_update.status
        
        if status_update.status == CardStatus.READY_FOR_COLLECTION:
            card.ready_for_collection_date = datetime.utcnow()
        elif status_update.status == CardStatus.COLLECTED:
            card.collected_date = datetime.utcnow()
            card.collected_by_user_id = current_user.id
            card.collection_reference = status_update.collection_reference
        elif status_update.status == CardStatus.IN_PRODUCTION:
            card.production_started = datetime.utcnow()
        
        card.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(card)
        
        return card

    def get_cards_for_license(self, db: Session, *, license_id: UUID) -> List[LicenseCard]:
        """Get all cards for a license"""
        return db.query(LicenseCard).filter(
            LicenseCard.license_id == license_id
        ).order_by(desc(LicenseCard.issue_date)).all()

    def get_current_card(self, db: Session, *, license_id: UUID) -> Optional[LicenseCard]:
        """Get current active card for a license"""
        return db.query(LicenseCard).filter(
            and_(
                LicenseCard.license_id == license_id,
                LicenseCard.is_current == True
            )
        ).first()


# Create instances
crud_license = CRUDLicense(License)
crud_license_card = CRUDLicenseCard(LicenseCard) 