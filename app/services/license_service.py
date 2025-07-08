"""
License Service for Madagascar License System
Handles business logic for license creation, restriction management, and card workflow

This service provides high-level operations for:
1. Creating licenses from applications with restrictions
2. Managing the card lifecycle
3. Validating license restrictions
4. Coordinating between applications and license issuance
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.crud.crud_license import crud_license, crud_license_card
from app.crud.crud_application import crud_application
from app.models.user import User
from app.models.application import Application
from app.models.license import License, LicenseCard, LicenseStatus, CardStatus
from app.models.enums import (
    LicenseRestrictionCode, LicenseRestrictionCategory, 
    LICENSE_RESTRICTION_MAPPING, ProfessionalPermitCategory
)
from app.schemas.license import LicenseCreateFromApplication, CardCreate


class LicenseService:
    """Service class for license management business logic"""

    @staticmethod
    def create_license_from_authorized_application(
        db: Session,
        application_id: UUID,
        authorization_data: Dict[str, Any],
        current_user: User
    ) -> License:
        """
        Create license from authorized application with test results and restrictions
        
        This is called AFTER the application has been authorized (tests passed)
        and includes any additional restrictions determined during authorization.
        
        Args:
            application_id: ID of the approved application
            authorization_data: Data from authorization step including:
                - restrictions: List of restriction codes determined from tests
                - professional_permit: Professional permit info if applicable
                - medical_restrictions: Medical restrictions from assessment
                - captured_license_data: Any captured license data
        """
        # Validate application exists and is authorized
        application = crud_application.get(db, id=application_id)
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application {application_id} not found"
            )
        
        # Check application status allows license creation
        valid_statuses = ["APPROVED", "AUTHORIZED", "COMPLETED"]
        if application.status.value not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Application must be authorized to create license. Current status: {application.status}"
            )
        
        # Process restrictions from authorization
        license_restrictions = LicenseService._process_authorization_restrictions(
            authorization_data.get("restrictions", [])
        )
        
        # Extract license category from application data
        license_category = application.application_type.value.replace("_APPLICATION", "")
        
        # Prepare license creation data
        license_data = LicenseCreateFromApplication(
            application_id=application_id,
            license_category=license_category,
            restrictions=license_restrictions,
            medical_restrictions=authorization_data.get("medical_restrictions", []),
            has_professional_permit=authorization_data.get("has_professional_permit", False),
            professional_permit_categories=authorization_data.get("professional_permit_categories", []),
            professional_permit_expiry=authorization_data.get("professional_permit_expiry"),
            captured_from_license_number=authorization_data.get("captured_license_number"),
            order_card_immediately=True,  # Always order card for new licenses
            card_expiry_years=5
        )
        
        # Create the license
        license_obj = crud_license.create_from_application(
            db=db,
            obj_in=license_data,
            current_user=current_user
        )
        
        # Update application status to indicate license created
        crud_application.update_status(
            db=db,
            application_id=application_id,
            new_status="COMPLETED",
            notes=f"License {license_obj.license_number} created successfully",
            updated_by=current_user.id
        )
        
        return license_obj

    @staticmethod
    def _process_authorization_restrictions(restriction_codes: List[str]) -> List[str]:
        """
        Process and validate restriction codes from authorization step
        
        Args:
            restriction_codes: List of restriction codes (e.g., ["01", "03", "06"])
            
        Returns:
            List of validated restriction codes
        """
        validated_restrictions = []
        
        for code in restriction_codes:
            # Validate restriction code exists
            restriction_enum = None
            for restriction in LicenseRestrictionCode:
                if restriction.value == code:
                    restriction_enum = restriction
                    break
            
            if restriction_enum:
                validated_restrictions.append(code)
            else:
                # Log warning but don't fail - might be future restriction codes
                print(f"Warning: Unknown restriction code '{code}' - adding anyway")
                validated_restrictions.append(code)
        
        return validated_restrictions

    @staticmethod
    def get_restriction_details(restriction_codes: List[str]) -> List[Dict[str, Any]]:
        """
        Get detailed information about license restrictions
        
        Args:
            restriction_codes: List of restriction codes
            
        Returns:
            List of restriction details with descriptions and categories
        """
        details = []
        
        for code in restriction_codes:
            # Find matching restriction
            restriction_info = None
            for restriction, info in LICENSE_RESTRICTION_MAPPING.items():
                if info["code"] == code:
                    restriction_info = info
                    break
            
            if restriction_info:
                details.append({
                    "code": code,
                    "description": restriction_info["description"],
                    "category": restriction_info["category"].value,
                    "display_name": restriction_info["display_name"]
                })
            else:
                # Unknown restriction - provide basic info
                details.append({
                    "code": code,
                    "description": f"Restriction code {code}",
                    "category": "UNKNOWN",
                    "display_name": f"Restriction {code}"
                })
        
        return details

    @staticmethod
    def order_replacement_card(
        db: Session,
        license_id: UUID,
        replacement_reason: str,
        current_user: User
    ) -> LicenseCard:
        """
        Order a replacement card for an existing license
        
        Used when cards are lost, stolen, damaged, or expired
        """
        # Validate license exists
        license_obj = crud_license.get(db, id=license_id)
        if not license_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"License {license_id} not found"
            )
        
        # Check license is active
        if license_obj.status != LicenseStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot order card for {license_obj.status.value} license"
            )
        
        # Create replacement card
        card_data = CardCreate(
            license_id=license_id,
            card_type="REPLACEMENT",
            expiry_years=5,
            replacement_reason=replacement_reason
        )
        
        return crud_license_card.create_card(
            db=db,
            obj_in=card_data,
            current_user=current_user
        )

    @staticmethod
    def process_card_production_workflow(
        db: Session,
        card_id: UUID,
        new_status: CardStatus,
        current_user: User,
        notes: Optional[str] = None
    ) -> LicenseCard:
        """
        Process card through production workflow
        
        Workflow: PENDING_PRODUCTION → IN_PRODUCTION → READY_FOR_COLLECTION → COLLECTED
        """
        from app.schemas.license import CardStatusUpdate
        
        status_update = CardStatusUpdate(
            status=new_status,
            notes=notes
        )
        
        return crud_license_card.update_card_status(
            db=db,
            card_id=card_id,
            status_update=status_update,
            current_user=current_user
        )

    @staticmethod
    def get_cards_for_collection(
        db: Session,
        location_id: Optional[UUID] = None
    ) -> List[LicenseCard]:
        """
        Get cards ready for collection at a specific location
        
        Used by collection centers to see what cards are available
        """
        from sqlalchemy import and_
        
        query_filters = [LicenseCard.status == CardStatus.READY_FOR_COLLECTION]
        
        if location_id:
            query_filters.append(LicenseCard.collection_location_id == location_id)
        
        return db.query(LicenseCard).filter(and_(*query_filters)).all()

    @staticmethod
    def get_cards_near_expiry(
        db: Session,
        days_warning: int = 90
    ) -> List[LicenseCard]:
        """
        Get cards that are near expiry (for renewal notifications)
        """
        expiry_threshold = datetime.utcnow() + timedelta(days=days_warning)
        
        return db.query(LicenseCard).filter(
            and_(
                LicenseCard.is_current == True,
                LicenseCard.expiry_date <= expiry_threshold,
                LicenseCard.expiry_date > datetime.utcnow(),
                LicenseCard.status == CardStatus.COLLECTED
            )
        ).all()

    @staticmethod
    def validate_professional_permit_eligibility(
        db: Session,
        person_id: UUID,
        permit_categories: List[str]
    ) -> Dict[str, Any]:
        """
        Validate if person is eligible for professional permit categories
        
        Checks existing licenses and categories to ensure proper progression
        """
        existing_licenses = crud_license.get_by_person_id(
            db=db,
            person_id=person_id,
            active_only=True
        )
        
        existing_categories = [license.category.value for license in existing_licenses]
        
        # Professional permit eligibility rules
        eligibility = {
            "eligible": True,
            "reasons": [],
            "existing_categories": existing_categories,
            "requested_categories": permit_categories
        }
        
        # Check if person has required base licenses for professional permits
        required_base_categories = ["B", "C"]  # Typically need B or C for professional permits
        has_base_license = any(cat in existing_categories for cat in required_base_categories)
        
        if not has_base_license:
            eligibility["eligible"] = False
            eligibility["reasons"].append("Requires valid B or C category license for professional permit")
        
        return eligibility


# Card Workflow Integration Guide
"""
CARD WORKFLOW INTEGRATION GUIDE
===============================

The license system separates licenses (lifetime validity) from cards (5-year expiry).
Here's how the card workflow integrates with your application process:

1. LICENSE CREATION (From Application Authorization):
   ─────────────────────────────────────────────────
   
   Application Process:
   - Person submits application
   - Tests are conducted (eye test, driving test, medical)
   - Application is AUTHORIZED with test results
   
   → LICENSE CREATION happens here ←
   
   def authorize_application(application_id, test_results):
       # Process test results and determine restrictions
       restrictions = determine_restrictions_from_tests(test_results)
       
       # Create license with restrictions
       license = LicenseService.create_license_from_authorized_application(
           db=db,
           application_id=application_id,
           authorization_data={
               "restrictions": restrictions,  # ["01", "03"] for corrective lenses + automatic
               "medical_restrictions": test_results.medical_restrictions,
               "professional_permit_categories": ["P"] if qualified else []
           },
           current_user=current_user
       )
       
       # License created with Card in PENDING_PRODUCTION status
       return license

2. CARD PRODUCTION WORKFLOW:
   ──────────────────────────
   
   Card Status Flow:
   PENDING_PRODUCTION → IN_PRODUCTION → READY_FOR_COLLECTION → COLLECTED
   
   # When sending to printer
   LicenseService.process_card_production_workflow(
       db=db,
       card_id=card.id,
       new_status=CardStatus.IN_PRODUCTION,
       current_user=current_user
   )
   
   # When card is printed and ready
   LicenseService.process_card_production_workflow(
       db=db,
       card_id=card.id,
       new_status=CardStatus.READY_FOR_COLLECTION,
       current_user=current_user
   )
   
   # When person collects card
   LicenseService.process_card_production_workflow(
       db=db,
       card_id=card.id,
       new_status=CardStatus.COLLECTED,
       current_user=current_user,
       notes="Collected by license holder with ID verification"
   )

3. RESTRICTION HANDLING:
   ─────────────────────
   
   Restriction Codes:
   - "01": Corrective Lenses Required
   - "02": Prosthetics
   - "03": Automatic Transmission Only
   - "04": Electric Vehicles Only
   - "05": Disability Adapted Vehicles
   - "06": Tractor Vehicles Only
   - "07": Industrial/Agriculture Only
   
   Example Authorization with Restrictions:
   
   def process_eye_test_results(test_results):
       restrictions = []
       
       if test_results.vision_corrected_only:
           restrictions.append("01")  # Corrective lenses required
       
       if test_results.physical_disability:
           restrictions.append("05")  # Disability adapted vehicles
       
       return restrictions

4. CARD REPLACEMENT FLOW:
   ─────────────────────
   
   When cards are lost/stolen/damaged:
   
   replacement_card = LicenseService.order_replacement_card(
       db=db,
       license_id=license.id,
       replacement_reason="LOST",
       current_user=current_user
   )
   
   # New card enters production workflow
   # Old card is marked as not current

5. COLLECTION CENTER INTEGRATION:
   ──────────────────────────────
   
   # Get cards ready for collection at a location
   ready_cards = LicenseService.get_cards_for_collection(
       db=db,
       location_id=collection_center_id
   )
   
   # Show to collection center staff
   for card in ready_cards:
       print(f"Card {card.card_number} for License {card.license.license_number}")
       print(f"Person: {card.license.person.full_name}")
       print(f"Ready since: {card.ready_for_collection_date}")

6. RENEWAL NOTIFICATIONS:
   ─────────────────────
   
   # Check for cards expiring soon (90 days default)
   expiring_cards = LicenseService.get_cards_near_expiry(db=db, days_warning=90)
   
   # Send renewal notifications
   for card in expiring_cards:
       send_renewal_notification(card.license.person, card.expiry_date)

KEY POINTS:
-----------
✅ Licenses never expire (lifetime validity)
✅ Cards expire every 5 years and need replacement
✅ One license can have multiple cards over time
✅ Restrictions are applied at LICENSE level, inherited by all cards
✅ Card production is tracked separately from license status
✅ Professional permits are tracked at license level
✅ Complete audit trail for all status changes
""" 