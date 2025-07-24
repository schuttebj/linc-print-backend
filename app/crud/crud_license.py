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
from app.models.license import License, LicenseStatusHistory, LicenseStatus
from app.models.application import Application
from app.models.person import Person
from app.models.user import User, Location
from app.schemas.license import (
    LicenseCreateFromApplication, LicenseCreate, LicenseStatusUpdate,
    LicenseRestrictionsUpdate, LicenseProfessionalPermitUpdate,
    LicenseSearchFilters
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
        Note: Card ordering is now a separate manual process
        """
        # Get application
        application = db.query(Application).filter(Application.id == obj_in.application_id).first()
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application {obj_in.application_id} not found"
            )
        
        # Validate application status
        if application.status != "APPROVED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Application must be approved before license creation. Current status: {application.status}"
            )
        
        # Create license
        issue_date = datetime.utcnow()
        
        license_data = {
            "person_id": application.person_id,
            "created_from_application_id": obj_in.application_id,
            "category": obj_in.license_category,
            "status": LicenseStatus.ACTIVE,
            "issue_date": issue_date,
            "issuing_location_id": application.issuing_location_id,
            "issued_by_user_id": current_user.id,
            "restrictions": obj_in.restrictions,
            "medical_restrictions": obj_in.medical_restrictions,
            "has_professional_permit": obj_in.has_professional_permit,
            "professional_permit_categories": obj_in.professional_permit_categories,
            "professional_permit_expiry": obj_in.professional_permit_expiry,
            "captured_from_license_number": obj_in.captured_from_license_number,
            "sadc_compliance_verified": True,
            "international_validity": True,
            "vienna_convention_compliant": True,
            # Card ordering tracking
            "card_ordered": obj_in.order_card_immediately,
            "card_order_date": datetime.utcnow() if obj_in.order_card_immediately else None,
            "card_order_reference": obj_in.card_order_reference if obj_in.order_card_immediately else None
        }
        
        # Set expiry date for learner's permits (6 months from issue date)
        if obj_in.license_category.value in ['1', '2', '3']:  # LEARNERS_1, LEARNERS_2, LEARNERS_3
            from datetime import timedelta
            license_data["expiry_date"] = issue_date + timedelta(days=180)  # 6 months
        
        db_license = License(**license_data)
        db.add(db_license)
        db.flush()  # Get the ID
        
        # Create status history
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
        
        # Note: Card creation is now handled separately through the card ordering process
        # If order_card_immediately is True, the calling code should create a card order
        
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
        """Create a license manually (administrative use)"""
        # Create license
        license_data = {
            "person_id": obj_in.person_id,
            "category": obj_in.license_category,
            "status": LicenseStatus.ACTIVE,
            "issue_date": datetime.utcnow(),
            "issuing_location_id": obj_in.issuing_location_id,
            "issued_by_user_id": current_user.id,
            "restrictions": obj_in.restrictions,
            "medical_restrictions": obj_in.medical_restrictions,
            "has_professional_permit": obj_in.has_professional_permit,
            "professional_permit_categories": obj_in.professional_permit_categories,
            "professional_permit_expiry": obj_in.professional_permit_expiry,
            "previous_license_id": obj_in.previous_license_id,
            "is_upgrade": obj_in.is_upgrade,
            "upgrade_from_category": obj_in.upgrade_from_category,
            "legacy_license_number": obj_in.legacy_license_number,
            "captured_from_license_number": obj_in.captured_from_license_number,
            "sadc_compliance_verified": True,
            "international_validity": True,
            "vienna_convention_compliant": True,
            "card_ordered": False  # Manual card ordering required
        }
        
        db_license = License(**license_data)
        db.add(db_license)
        db.flush()
        
        # Create status history
        status_history = LicenseStatusHistory(
            license_id=db_license.id,
            from_status=None,
            to_status=LicenseStatus.ACTIVE,
            changed_by=current_user.id,
            changed_at=datetime.utcnow(),
            reason="Manual license creation",
            notes="License created manually by administrator",
            system_initiated=False
        )
        db.add(status_history)
        
        db.commit()
        db.refresh(db_license)
        
        return db_license

    def get_with_details(self, db: Session, *, license_id: UUID) -> Optional[License]:
        """Get license with all related data loaded"""
        return db.query(License).options(
            selectinload(License.person),
            selectinload(License.issuing_location),
            selectinload(License.issued_by_user),
            selectinload(License.card_licenses),  # Use card_licenses instead of cards property
            selectinload(License.status_history).selectinload(LicenseStatusHistory.changed_by_user),
            selectinload(License.previous_license),
            selectinload(License.created_from_application)
        ).filter(License.id == license_id).first()



    def get_by_person_id(
        self, 
        db: Session, 
        *, 
        person_id: UUID, 
        skip: int = 0, 
        limit: int = 100,
        active_only: bool = False
    ) -> List[License]:
        """Get all licenses for a person"""
        query = db.query(License).filter(License.person_id == person_id)
        
        if active_only:
            from app.models.license import LicenseStatus
            query = query.filter(License.status == LicenseStatus.ACTIVE)
            
        return query.order_by(desc(License.issue_date)).offset(skip).limit(limit).all()

    def search_licenses(
        self, 
        db: Session, 
        *, 
        filters: LicenseSearchFilters
    ) -> Tuple[List[License], int]:
        """Search licenses with comprehensive filtering"""
        query = db.query(License)
        
        # Basic filters
        if filters.person_id:
            query = query.filter(License.person_id == filters.person_id)
        
        if filters.license_category:
            query = query.filter(License.category == filters.license_category)
        
        if filters.status:
            query = query.filter(License.status == filters.status)
        
        if filters.issuing_location_id:
            query = query.filter(License.issuing_location_id == filters.issuing_location_id)
        
        # Date filters
        if filters.issued_after:
            query = query.filter(License.issue_date >= filters.issued_after)
        
        if filters.issued_before:
            query = query.filter(License.issue_date <= filters.issued_before)
        
        # Card status filters
        if filters.has_card is not None:
            if filters.has_card:
                # Has at least one active card association
                query = query.join(License.cards).filter(
                    and_(License.cards.any(), License.cards.any(lambda c: c.is_active))
                )
            else:
                # No active card associations
                query = query.filter(~License.cards.any(lambda c: c.is_active))
        
        if filters.card_ordered is not None:
            query = query.filter(License.card_ordered == filters.card_ordered)
        
        if filters.needs_card:
            # Active licenses without cards that haven't been ordered
            query = query.filter(
                and_(
                    License.status == LicenseStatus.ACTIVE,
                    License.card_ordered == False,
                    ~License.cards.any(lambda c: c.is_active)
                )
            )
        
        # Professional permit filters
        if filters.has_professional_permit is not None:
            query = query.filter(License.has_professional_permit == filters.has_professional_permit)
        
        # Search terms
        if filters.person_name:
            query = query.join(License.person).filter(
                or_(
                    Person.first_name.ilike(f"%{filters.person_name}%"),
                    Person.surname.ilike(f"%{filters.person_name}%")
                )
            )
        
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
        """Update license status with proper audit trail"""
        license_obj = self.get(db, id=license_id)
        if not license_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"License {license_id} not found"
            )
        
        old_status = license_obj.status
        
        # Update license status
        license_obj.status = status_update.status
        license_obj.status_changed_date = datetime.utcnow()
        license_obj.status_changed_by = current_user.id
        
        # Handle suspension specific fields
        if status_update.status == LicenseStatus.SUSPENDED:
            license_obj.suspension_start_date = status_update.suspension_start_date or datetime.utcnow()
            license_obj.suspension_end_date = status_update.suspension_end_date
            license_obj.suspension_reason = status_update.reason
        elif status_update.status == LicenseStatus.CANCELLED:
            license_obj.cancellation_date = datetime.utcnow()
            license_obj.cancellation_reason = status_update.reason
        
        # Create status history
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
        
        # Update restrictions
        license_obj.restrictions = restrictions_update.restrictions
        license_obj.medical_restrictions = restrictions_update.medical_restrictions
        license_obj.updated_at = datetime.utcnow()
        
        # Create audit trail in status history
        status_history = LicenseStatusHistory(
            license_id=license_id,
            from_status=license_obj.status,
            to_status=license_obj.status,
            changed_by=current_user.id,
            changed_at=datetime.utcnow(),
            reason=restrictions_update.reason,
            notes=f"Restrictions updated: {restrictions_update.notes}",
            system_initiated=False
        )
        db.add(status_history)
        
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
        
        # Update professional permit
        license_obj.has_professional_permit = permit_update.has_professional_permit
        license_obj.professional_permit_categories = permit_update.professional_permit_categories
        license_obj.professional_permit_expiry = permit_update.professional_permit_expiry
        license_obj.updated_at = datetime.utcnow()
        
        # Create audit trail
        status_history = LicenseStatusHistory(
            license_id=license_id,
            from_status=license_obj.status,
            to_status=license_obj.status,
            changed_by=current_user.id,
            changed_at=datetime.utcnow(),
            reason=permit_update.reason,
            notes=f"Professional permit updated: {permit_update.notes}",
            system_initiated=False
        )
        db.add(status_history)
        
        db.commit()
        db.refresh(license_obj)
        
        return license_obj

    def get_statistics(self, db: Session) -> Dict[str, Any]:
        """Get license statistics"""
        total_licenses = db.query(License).count()
        active_licenses = db.query(License).filter(License.status == LicenseStatus.ACTIVE).count()
        suspended_licenses = db.query(License).filter(License.status == LicenseStatus.SUSPENDED).count()
        cancelled_licenses = db.query(License).filter(License.status == LicenseStatus.CANCELLED).count()
        
        # Recent activity
        today = datetime.utcnow().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        licenses_issued_today = db.query(License).filter(
            func.date(License.issue_date) == today
        ).count()
        
        licenses_issued_this_week = db.query(License).filter(
            License.issue_date >= week_ago
        ).count()
        
        licenses_issued_this_month = db.query(License).filter(
            License.issue_date >= month_ago
        ).count()
        
        # Card statistics - now using new card system
        from app.models.card import Card, CardLicense
        licenses_with_cards = db.query(License).join(License.card_licenses).join(CardLicense.card).filter(
            Card.is_active == True
        ).count()
        
        licenses_without_cards = total_licenses - licenses_with_cards
        
        licenses_needing_card_orders = db.query(License).filter(
            and_(
                License.status == LicenseStatus.ACTIVE,
                License.card_ordered == False,
                ~License.card_licenses.any()
            )
        ).count()
        
        # Professional permits
        licenses_with_professional_permits = db.query(License).filter(
            License.has_professional_permit == True
        ).count()
        
        # Professional permits expiring soon (within 90 days)
        expiry_threshold = datetime.utcnow() + timedelta(days=90)
        professional_permits_expiring_soon = db.query(License).filter(
            and_(
                License.has_professional_permit == True,
                License.professional_permit_expiry <= expiry_threshold,
                License.professional_permit_expiry > datetime.utcnow()
            )
        ).count()
        
        # Category breakdown
        category_stats = db.query(
            License.category,
            func.count(License.id).label('count')
        ).group_by(License.category).all()
        licenses_by_category = {str(category): count for category, count in category_stats}
        
        # Location breakdown
        from app.models.user import Location
        location_stats = db.query(
            Location.name,
            func.count(License.id).label('count')
        ).join(License, License.issuing_location_id == Location.id).group_by(
            Location.id, Location.name
        ).all()
        licenses_by_issuing_location = {location_name: count for location_name, count in location_stats}
        
        # Upgrade statistics
        total_upgrades = db.query(License).filter(License.is_upgrade == True).count()
        upgrades_this_month = db.query(License).filter(
            and_(
                License.is_upgrade == True,
                License.issue_date >= month_ago
            )
        ).count()
        
        return {
            "total_licenses": total_licenses,
            "active_licenses": active_licenses,
            "suspended_licenses": suspended_licenses,
            "cancelled_licenses": cancelled_licenses,
            "licenses_by_category": licenses_by_category,
            "licenses_with_cards": licenses_with_cards,
            "licenses_without_cards": licenses_without_cards,
            "licenses_needing_card_orders": licenses_needing_card_orders,
            "licenses_issued_today": licenses_issued_today,
            "licenses_issued_this_week": licenses_issued_this_week,
            "licenses_issued_this_month": licenses_issued_this_month,
            "licenses_with_professional_permits": licenses_with_professional_permits,
            "professional_permits_expiring_soon": professional_permits_expiring_soon,
            "licenses_by_issuing_location": licenses_by_issuing_location,
            "total_upgrades": total_upgrades,
            "upgrades_this_month": upgrades_this_month
        }



    def get_by_application_id(self, db: Session, *, application_id: UUID) -> Optional[License]:
        """
        Get license by application ID
        
        Returns the license that was created from a specific application,
        or None if no license exists for that application.
        """
        return db.query(License).filter(License.created_from_application_id == application_id).first()


# Create instance
crud_license = CRUDLicense(License) 