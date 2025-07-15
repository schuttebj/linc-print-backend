"""
CRUD operations for Card Management in Madagascar License System
Handles independent card entities with production workflow and license associations
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session, selectinload, joinedload
from sqlalchemy import and_, or_, desc, func, text
from fastapi import HTTPException, status

from app.crud.base import CRUDBase
from app.models.card import Card, CardLicense, CardSequenceCounter, CardProductionBatch
from app.models.license import License
from app.models.application import Application
from app.models.person import Person
from app.models.user import User, Location
from app.schemas.card import (
    CardCreate, CardUpdate, CardStatusUpdate, TemporaryCardCreate,
    CardSearchFilters
)


class CRUDCard(CRUDBase[Card, CardCreate, CardUpdate]):
    """CRUD operations for Card model"""

    def create_with_licenses(
        self,
        db: Session,
        *,
        obj_in: CardCreate,
        current_user: User
    ) -> Card:
        """
        Create a new card with license associations
        """
        try:
            # Generate card number
            card_number = self._generate_card_number(
                db, 
                obj_in.production_location_id,
                is_temporary=obj_in.card_type == "TEMPORARY"
            )
            
            # Create card
            card_data = obj_in.dict(exclude={"license_ids"})
            card_data["card_number"] = card_number
            card_data["created_by"] = current_user.id
            card_data["created_at"] = datetime.utcnow()
            card_data["status"] = "PENDING_ORDER"
            
            db_card = Card(**card_data)
            db.add(db_card)
            db.flush()  # Get card ID
            
            # Associate licenses
            if obj_in.license_ids:
                for license_id in obj_in.license_ids:
                    license_assoc = CardLicense(
                        card_id=db_card.id,
                        license_id=license_id,
                        is_primary=(license_id == obj_in.primary_license_id),
                        added_by=current_user.id,
                        added_at=datetime.utcnow()
                    )
                    db.add(license_assoc)
            
            db.commit()
            db.refresh(db_card)
            
            return db_card
            
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create card: {str(e)}"
            )

    def create_from_application(
        self,
        db: Session,
        *,
        application_id: UUID,
        card_type: str = "STANDARD",
        valid_for_years: int = 5,
        production_location_id: UUID,
        collection_location_id: UUID,
        current_user: User
    ) -> Card:
        """
        Create card from approved application
        """
        # Get application with licenses
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Get application licenses
        licenses = db.query(License).filter(License.application_id == application_id).all()
        if not licenses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No licenses found for application"
            )
        
        # Create card data
        card_data = CardCreate(
            person_id=application.person_id,
            license_ids=[license.id for license in licenses],
            card_type=card_type,
            valid_for_years=valid_for_years,
            production_location_id=production_location_id,
            collection_location_id=collection_location_id,
            primary_license_id=licenses[0].id,  # First license as primary
            production_notes=f"Created from application {application_id}"
        )
        
        return self.create_with_licenses(db=db, obj_in=card_data, current_user=current_user)

    def create_temporary_card(
        self,
        db: Session,
        *,
        obj_in: TemporaryCardCreate,
        current_user: User
    ) -> Card:
        """
        Create temporary card (for A4 printing)
        """
        card_data = CardCreate(
            person_id=obj_in.person_id,
            license_ids=obj_in.license_ids,
            card_type="TEMPORARY",
            valid_for_years=1,  # Temporary cards valid for 1 year
            production_location_id=obj_in.production_location_id,
            collection_location_id=obj_in.production_location_id,  # Same location
            primary_license_id=obj_in.primary_license_id,
            production_notes="Temporary card for A4 printing"
        )
        
        return self.create_with_licenses(db=db, obj_in=card_data, current_user=current_user)

    def get_with_details(self, db: Session, *, card_id: UUID) -> Optional[Card]:
        """
        Get card with all related details (licenses, person, etc.)
        """
        return db.query(Card).options(
            selectinload(Card.card_licenses).selectinload(CardLicense.license),
            selectinload(Card.person),
            selectinload(Card.production_location),
            selectinload(Card.collection_location)
        ).filter(Card.id == card_id).first()

    def get_by_card_number(self, db: Session, *, card_number: str) -> Optional[Card]:
        """
        Get card by card number
        """
        return db.query(Card).filter(Card.card_number == card_number).first()

    def get_by_person_id(
        self,
        db: Session,
        *,
        person_id: UUID,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[Card]:
        """
        Get cards for a person
        """
        query = db.query(Card).filter(Card.person_id == person_id)
        
        if active_only:
            query = query.filter(Card.is_active == True)
        
        return query.offset(skip).limit(limit).all()

    def search_cards(
        self,
        db: Session,
        *,
        filters: CardSearchFilters
    ) -> Tuple[List[Card], int]:
        """
        Search cards with comprehensive filtering
        """
        query = db.query(Card)
        
        # Apply filters
        if filters.person_id:
            query = query.filter(Card.person_id == filters.person_id)
        
        if filters.card_type:
            query = query.filter(Card.card_type == filters.card_type)
        
        if filters.status:
            query = query.filter(Card.status.in_(filters.status))
        
        if filters.is_active is not None:
            query = query.filter(Card.is_active == filters.is_active)
        
        if filters.card_number:
            query = query.filter(Card.card_number.ilike(f"%{filters.card_number}%"))
        
        if filters.production_location_id:
            query = query.filter(Card.production_location_id == filters.production_location_id)
        
        if filters.collection_location_id:
            query = query.filter(Card.collection_location_id == filters.collection_location_id)
        
        # Date filters
        if filters.created_after:
            query = query.filter(Card.created_at >= filters.created_after)
        
        if filters.created_before:
            query = query.filter(Card.created_at <= filters.created_before)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        cards = query.offset((filters.page - 1) * filters.size).limit(filters.size).all()
        
        return cards, total

    def update_card(
        self,
        db: Session,
        *,
        card_id: UUID,
        card_update: CardUpdate,
        current_user: User
    ) -> Card:
        """
        Update card information
        """
        card = self.get(db, id=card_id)
        if not card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Card not found"
            )
        
        update_data = card_update.dict(exclude_unset=True)
        update_data["updated_by"] = current_user.id
        update_data["updated_at"] = datetime.utcnow()
        
        for field, value in update_data.items():
            setattr(card, field, value)
        
        db.commit()
        db.refresh(card)
        
        return card

    def update_status(
        self,
        db: Session,
        *,
        card_id: UUID,
        status_update: CardStatusUpdate,
        current_user: User
    ) -> Card:
        """
        Update card status through production workflow
        """
        card = self.get(db, id=card_id)
        if not card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Card not found"
            )
        
        # Update status
        card.status = status_update.new_status
        card.status_updated_by = current_user.id
        card.status_updated_at = datetime.utcnow()
        
        if status_update.notes:
            card.production_notes = status_update.notes
        
        # Update specific workflow fields
        if status_update.new_status == "ORDERED":
            card.ordered_at = datetime.utcnow()
            card.ordered_by = current_user.id
        elif status_update.new_status == "COLLECTED":
            card.collected_at = datetime.utcnow()
            card.collected_by = current_user.id
        
        db.commit()
        db.refresh(card)
        
        return card

    def order_for_production(
        self,
        db: Session,
        *,
        card_id: UUID,
        production_priority: int = 1,
        production_location_id: Optional[UUID] = None,
        current_user: User
    ) -> Card:
        """
        Order card for production
        """
        card = self.get(db, id=card_id)
        if not card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Card not found"
            )
        
        if card.status != "PENDING_ORDER":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Card status must be PENDING_ORDER, currently {card.status}"
            )
        
        # Update card
        card.status = "ORDERED"
        card.production_priority = production_priority
        card.ordered_at = datetime.utcnow()
        card.ordered_by = current_user.id
        
        if production_location_id:
            card.production_location_id = production_location_id
        
        db.commit()
        db.refresh(card)
        
        return card

    def process_collection(
        self,
        db: Session,
        *,
        card_id: UUID,
        collection_data: Dict[str, Any],
        current_user: User
    ) -> Card:
        """
        Process card collection
        """
        card = self.get(db, id=card_id)
        if not card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Card not found"
            )
        
        if card.status != "READY_FOR_COLLECTION":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Card not ready for collection, currently {card.status}"
            )
        
        # Update card
        card.status = "COLLECTED"
        card.collected_at = datetime.utcnow()
        card.collected_by = current_user.id
        card.collection_reference = collection_data.get("collection_reference")
        
        db.commit()
        db.refresh(card)
        
        return card

    def get_pending_production(
        self,
        db: Session,
        *,
        production_location_id: Optional[UUID] = None,
        priority: Optional[int] = None
    ) -> List[Card]:
        """
        Get cards pending production
        """
        query = db.query(Card).filter(
            Card.status.in_(["ORDERED", "PENDING_PRODUCTION", "IN_PRODUCTION"])
        )
        
        if production_location_id:
            query = query.filter(Card.production_location_id == production_location_id)
        
        if priority:
            query = query.filter(Card.production_priority == priority)
        
        return query.order_by(Card.production_priority.desc(), Card.ordered_at).all()

    def get_ready_for_collection(
        self,
        db: Session,
        *,
        collection_location_id: Optional[UUID] = None,
        days_ready: Optional[int] = None
    ) -> List[Card]:
        """
        Get cards ready for collection
        """
        query = db.query(Card).filter(Card.status == "READY_FOR_COLLECTION")
        
        if collection_location_id:
            query = query.filter(Card.collection_location_id == collection_location_id)
        
        if days_ready:
            cutoff_date = datetime.utcnow() - timedelta(days=days_ready)
            query = query.filter(Card.production_completed_at <= cutoff_date)
        
        return query.order_by(Card.production_completed_at).all()

    def get_expiring_cards(
        self,
        db: Session,
        *,
        days: int = 90,
        person_id: Optional[UUID] = None
    ) -> List[Card]:
        """
        Get cards expiring soon
        """
        cutoff_date = datetime.utcnow() + timedelta(days=days)
        
        query = db.query(Card).filter(
            Card.expires_at <= cutoff_date,
            Card.is_active == True
        )
        
        if person_id:
            query = query.filter(Card.person_id == person_id)
        
        return query.order_by(Card.expires_at).all()

    def add_license_association(
        self,
        db: Session,
        *,
        card_id: UUID,
        license_id: UUID,
        is_primary: bool = False,
        current_user: User
    ) -> Card:
        """
        Add license to card
        """
        # Check if association already exists
        existing = db.query(CardLicense).filter(
            CardLicense.card_id == card_id,
            CardLicense.license_id == license_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="License already associated with card"
            )
        
        # Create association
        association = CardLicense(
            card_id=card_id,
            license_id=license_id,
            is_primary=is_primary,
            added_by=current_user.id,
            added_at=datetime.utcnow()
        )
        
        db.add(association)
        
        # If this is primary, remove primary flag from others
        if is_primary:
            db.query(CardLicense).filter(
                CardLicense.card_id == card_id,
                CardLicense.license_id != license_id
            ).update({"is_primary": False})
        
        db.commit()
        
        return self.get(db, id=card_id)

    def remove_license_association(
        self,
        db: Session,
        *,
        card_id: UUID,
        license_id: UUID,
        current_user: User
    ) -> Card:
        """
        Remove license from card
        """
        association = db.query(CardLicense).filter(
            CardLicense.card_id == card_id,
            CardLicense.license_id == license_id
        ).first()
        
        if not association:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="License association not found"
            )
        
        db.delete(association)
        db.commit()
        
        return self.get(db, id=card_id)

    def get_statistics(self, db: Session, *, location_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Get card statistics
        """
        query = db.query(Card)
        
        if location_id:
            query = query.filter(
                or_(
                    Card.production_location_id == location_id,
                    Card.collection_location_id == location_id
                )
            )
        
        total_cards = query.count()
        active_cards = query.filter(Card.is_active == True).count()
        
        # Status breakdown
        status_counts = {}
        status_results = db.query(Card.status, func.count(Card.id)).group_by(Card.status).all()
        for status, count in status_results:
            status_counts[status] = count
        
        return {
            "total_cards": total_cards,
            "active_cards": active_cards,
            "status_counts": status_counts
        }

    def create_replacement(
        self,
        db: Session,
        *,
        original_card_id: UUID,
        replacement_reason: str,
        urgent: bool = False,
        current_user: User
    ) -> Card:
        """
        Create replacement for lost/stolen/damaged card
        """
        original_card = self.get(db, id=original_card_id)
        if not original_card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original card not found"
            )
        
        # Deactivate original card
        original_card.is_active = False
        original_card.deactivated_at = datetime.utcnow()
        original_card.deactivated_by = current_user.id
        original_card.deactivation_reason = replacement_reason
        
        # Get license IDs from original card
        license_ids = [cl.license_id for cl in original_card.card_licenses]
        primary_license_id = next(
            (cl.license_id for cl in original_card.card_licenses if cl.is_primary),
            license_ids[0] if license_ids else None
        )
        
        # Create replacement card
        replacement_data = CardCreate(
            person_id=original_card.person_id,
            license_ids=license_ids,
            card_type="REPLACEMENT",
            valid_for_years=original_card.valid_for_years,
            production_location_id=original_card.production_location_id,
            collection_location_id=original_card.collection_location_id,
            primary_license_id=primary_license_id,
            production_notes=f"Replacement for card {original_card.card_number}: {replacement_reason}",
            production_priority=2 if urgent else 1
        )
        
        replacement_card = self.create_with_licenses(
            db=db, 
            obj_in=replacement_data, 
            current_user=current_user
        )
        
        db.commit()
        
        return replacement_card

    def create_duplicate(
        self,
        db: Session,
        *,
        original_card_id: UUID,
        reason: str,
        current_user: User
    ) -> Card:
        """
        Create duplicate of existing card
        """
        original_card = self.get(db, id=original_card_id)
        if not original_card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original card not found"
            )
        
        # Get license IDs from original card
        license_ids = [cl.license_id for cl in original_card.card_licenses]
        primary_license_id = next(
            (cl.license_id for cl in original_card.card_licenses if cl.is_primary),
            license_ids[0] if license_ids else None
        )
        
        # Create duplicate card
        duplicate_data = CardCreate(
            person_id=original_card.person_id,
            license_ids=license_ids,
            card_type="DUPLICATE",
            valid_for_years=original_card.valid_for_years,
            production_location_id=original_card.production_location_id,
            collection_location_id=original_card.collection_location_id,
            primary_license_id=primary_license_id,
            production_notes=f"Duplicate of card {original_card.card_number}: {reason}"
        )
        
        return self.create_with_licenses(
            db=db, 
            obj_in=duplicate_data, 
            current_user=current_user
        )

    def _generate_card_number(
        self,
        db: Session,
        location_id: UUID,
        is_temporary: bool = False
    ) -> str:
        """
        Generate card number: LocationCode + 8-digit sequence + checksum
        """
        try:
            # Get location code
            location = db.query(Location).filter(Location.id == location_id).first()
            if not location:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Location not found"
                )
            
            location_code = location.code
            
            # Get next sequence number for this location
            sequence_counter = db.query(CardSequenceCounter).filter(
                CardSequenceCounter.location_id == location_id
            ).first()
            
            if not sequence_counter:
                # Create new sequence counter
                sequence_counter = CardSequenceCounter(
                    location_id=location_id,
                    current_sequence=1
                )
                db.add(sequence_counter)
                db.flush()
                sequence_num = 1
            else:
                # Increment sequence
                sequence_counter.current_sequence += 1
                sequence_num = sequence_counter.current_sequence
            
            # Format as 8-digit number
            sequence_str = f"{sequence_num:08d}"
            
            # Calculate checksum using Luhn algorithm
            card_base = location_code + sequence_str
            checksum = self._calculate_checksum(card_base)
            
            # Build final card number
            if is_temporary:
                card_number = f"T{location_code}{sequence_str}{checksum}"
            else:
                card_number = f"{location_code}{sequence_str}{checksum}"
            
            return card_number
            
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate card number: {str(e)}"
            )

    def _calculate_checksum(self, card_base: str) -> str:
        """
        Calculate Luhn algorithm checksum
        """
        def luhn_checksum(card_num):
            def digits_of(n):
                return [int(d) for d in str(n)]
            
            digits = digits_of(card_num)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d*2))
            
            return (10 - (checksum % 10)) % 10
        
        return str(luhn_checksum(card_base))


class CRUDCardProductionBatch(CRUDBase[CardProductionBatch, dict, dict]):
    """CRUD operations for Card Production Batch management"""

    def get_batches(
        self,
        db: Session,
        *,
        production_location_id: Optional[UUID] = None,
        status: Optional[str] = None
    ) -> List[CardProductionBatch]:
        """
        Get production batches
        """
        query = db.query(CardProductionBatch)
        
        if production_location_id:
            query = query.filter(CardProductionBatch.production_location_id == production_location_id)
        
        if status:
            query = query.filter(CardProductionBatch.status == status)
        
        return query.order_by(desc(CardProductionBatch.created_at)).all()

    def create_batch(
        self,
        db: Session,
        *,
        production_location_id: UUID,
        card_ids: List[UUID],
        batch_name: Optional[str] = None,
        current_user: User
    ) -> CardProductionBatch:
        """
        Create production batch with cards
        """
        # Generate batch name if not provided
        if not batch_name:
            batch_date = datetime.utcnow().strftime("%Y%m%d")
            batch_count = db.query(CardProductionBatch).filter(
                func.date(CardProductionBatch.created_at) == datetime.utcnow().date()
            ).count()
            batch_name = f"BATCH_{batch_date}_{batch_count + 1:03d}"
        
        # Create batch
        batch = CardProductionBatch(
            name=batch_name,
            production_location_id=production_location_id,
            status="PENDING",
            created_by=current_user.id,
            created_at=datetime.utcnow()
        )
        
        db.add(batch)
        db.flush()  # Get batch ID
        
        # Update cards to belong to this batch
        db.query(Card).filter(Card.id.in_(card_ids)).update(
            {"production_batch_id": batch.id},
            synchronize_session=False
        )
        
        db.commit()
        db.refresh(batch)
        
        return batch


# Create instances
crud_card = CRUDCard(Card)
crud_card_production_batch = CRUDCardProductionBatch(CardProductionBatch) 