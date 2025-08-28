"""
Card Management API Endpoints for Madagascar License System
Independent card management with production workflow and license associations
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.core.audit_decorators import audit_create, audit_update, audit_delete
from app.crud.crud_card import crud_card, crud_card_production_batch
from app.models.user import User
from app.schemas.card import (
    CardCreate, CardUpdate, CardStatusUpdate, TemporaryCardCreate,
    CardResponse, CardDetailResponse, CardListResponse,
    CardSearchFilters, CardStatistics, ApplicationCardRequest
)

router = APIRouter()


def check_permission(user: User, permission: str) -> bool:
    """Check if user has specific permission"""
    if user.is_superuser:
        return True
    return user.has_permission(permission)


def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(current_user: User = Depends(get_current_user)):
        if not check_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}"
            )
        return current_user
    return decorator


# Card Creation Endpoints
@router.post("/", response_model=CardResponse, summary="Create New Card")
@audit_create(resource_type="CARD", screen_reference="CardManagement")
async def create_card(
    card_in: CardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.create"))
):
    """
    Create a new card with license associations
    
    This endpoint creates an independent card entity that can be associated
    with multiple licenses. The card has its own production workflow.
    """
    try:
        card = crud_card.create_with_licenses(
            db=db, 
            obj_in=card_in, 
            current_user=current_user
        )
        
        return CardResponse.from_orm(card)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create card: {str(e)}"
        )


@router.post("/from-application", response_model=CardResponse, summary="Create Card from Application")
async def create_card_from_application(
    request: ApplicationCardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.create"))
):
    """
    Create card from approved application
    
    This is called after application approval to order the physical card.
    The licenses associated with the application will be linked to the card.
    """
    try:
        card = crud_card.create_from_application(
            db=db,
            application_id=request.application_id,
            card_type=request.card_type,
            valid_for_years=request.valid_for_years,
            production_location_id=request.production_location_id,
            collection_location_id=request.collection_location_id,
            current_user=current_user
        )
        
        return CardResponse.from_orm(card)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create card from application: {str(e)}"
        )


@router.post("/test", response_model=CardResponse, summary="Create Test Card for License")
async def create_test_card(
    request: dict,  # Simple request with license_id
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.create"))
):
    """
    Create a test card for a license (for testing purposes)
    
    This endpoint creates a simple card containing a single license
    for testing the card system functionality.
    """
    try:
        license_id = request.get("license_id")
        if not license_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="license_id is required"
            )
        
        # Get the license to extract person and location info
        from app.crud.crud_license import license as crud_license
        license_obj = crud_license.get(db, id=license_id)
        if not license_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="License not found"
            )
        
        # Create card data
        card_data = CardCreate(
            person_id=license_obj.person_id,
            license_ids=[license_id],
            card_type="STANDARD",
            valid_for_years=5,
            production_location_id=license_obj.issuing_location_id,
            collection_location_id=license_obj.issuing_location_id,
            primary_license_id=license_id,
            production_notes="Test card creation"
        )
        
        # Create the card
        card = crud_card.create_with_licenses(
            db=db, 
            obj_in=card_data, 
            current_user=current_user
        )
        
        return CardResponse.from_orm(card)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating test card: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create test card: {str(e)}"
        )


@router.post("/temporary", response_model=CardResponse, summary="Create Temporary Card")
async def create_temporary_card(
    temp_card_in: TemporaryCardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.create_temporary"))
):
    """
    Create temporary card (for lost/stolen card replacements)
    
    Temporary cards are issued quickly while the permanent replacement
    is being produced. They have shorter validity periods.
    """
    try:
        card = crud_card.create_temporary_card(
            db=db,
            obj_in=temp_card_in,
            current_user=current_user
        )
        
        return CardResponse.from_orm(card)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create temporary card: {str(e)}"
        )


# Card Query Endpoints
@router.get("/search", response_model=CardListResponse, summary="Search Cards")
async def search_cards(
    # Pagination
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=500, description="Page size"),
    
    # Basic filters
    person_id: Optional[str] = Query(None, description="Filter by person"),
    card_type: Optional[str] = Query(None, description="Filter by card type"),
    status: Optional[List[str]] = Query(None, description="Filter by card status"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_temporary: Optional[bool] = Query(None, description="Filter temporary cards"),
    
    # Date filters
    created_after: Optional[str] = Query(None, description="Created after date"),
    created_before: Optional[str] = Query(None, description="Created before date"),
    ordered_after: Optional[str] = Query(None, description="Ordered after date"),
    ordered_before: Optional[str] = Query(None, description="Ordered before date"),
    expires_before: Optional[str] = Query(None, description="Expires before date"),
    
    # Location filters
    production_location_id: Optional[str] = Query(None, description="Filter by production location"),
    collection_location_id: Optional[str] = Query(None, description="Filter by collection location"),
    
    # Search terms
    card_number: Optional[str] = Query(None, description="Search by card number"),
    person_name: Optional[str] = Query(None, description="Search by person name"),
    collection_reference: Optional[str] = Query(None, description="Search by collection reference"),
    
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.read"))
):
    """
    Search cards with various filters and pagination
    """
    try:
        # Create search filters object
        filters = CardSearchFilters(
            page=page,
            size=size,
            person_id=person_id,
            card_type=card_type,
            status=status,
            is_active=is_active,
            is_temporary=is_temporary,
            created_after=created_after,
            created_before=created_before,
            ordered_after=ordered_after,
            ordered_before=ordered_before,
            expires_before=expires_before,
            production_location_id=production_location_id,
            collection_location_id=collection_location_id,
            card_number=card_number,
            person_name=person_name,
            collection_reference=collection_reference
        )
        
        # Search cards using CRUD
        cards, total = crud_card.search_cards(db=db, filters=filters)
        
        # Calculate pagination info
        pages = (total + size - 1) // size if total > 0 else 1
        
        return CardListResponse(
            cards=[CardResponse.from_orm(card) for card in cards],
            total=total,
            page=page,
            size=size,
            pages=pages
        )
    
    except Exception as e:
        logger.error(f"Error searching cards: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search cards: {str(e)}"
        )


@router.get("/{card_id}", response_model=CardDetailResponse, summary="Get Card Details")
async def get_card(
    card_id: UUID = Path(..., description="Card ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.read"))
):
    """
    Get detailed card information including licenses, production status, and history
    """
    card = crud_card.get_with_details(db, card_id=card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card {card_id} not found"
        )
    
    return CardDetailResponse.from_orm(card)


@router.get("/number/{card_number}", response_model=CardResponse, summary="Get Card by Number")
async def get_card_by_number(
    card_number: str = Path(..., description="Card number"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.read"))
):
    """
    Get card by card number
    """
    card = crud_card.get_by_card_number(db, card_number=card_number)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Card number {card_number} not found"
        )
    
    return CardResponse.from_orm(card)


@router.get("/person/{person_id}", response_model=List[CardResponse], summary="Get Person's Cards")
async def get_person_cards(
    person_id: UUID = Path(..., description="Person ID"),
    active_only: bool = Query(False, description="Return only active cards"),
    skip: int = Query(0, ge=0, description="Skip records"),
    limit: int = Query(100, ge=1, le=1000, description="Limit records"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.read"))
):
    """
    Get all cards for a specific person
    """
    cards = crud_card.get_by_person_id(
        db=db,
        person_id=person_id,
        active_only=active_only,
        skip=skip,
        limit=limit
    )
    
    return [CardResponse.from_orm(card) for card in cards]


@router.post("/search", response_model=CardListResponse, summary="Search Cards")
async def search_cards(
    filters: CardSearchFilters,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.read"))
):
    """
    Search cards with comprehensive filtering
    """
    cards, total = crud_card.search_cards(db=db, filters=filters)
    
    # Calculate pagination info
    pages = (total + filters.size - 1) // filters.size
    
    return CardListResponse(
        cards=[CardResponse.from_orm(card) for card in cards],
        total=total,
        page=filters.page,
        size=filters.size,
        pages=pages
    )


# Card Management Endpoints
@router.put("/{card_id}", response_model=CardResponse, summary="Update Card")
async def update_card(
    card_id: UUID = Path(..., description="Card ID"),
    card_update: CardUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.update"))
):
    """
    Update card information (license associations, validity, etc.)
    """
    card = crud_card.update_card(
        db=db,
        card_id=card_id,
        card_update=card_update,
        current_user=current_user
    )
    
    return CardResponse.from_orm(card)


@router.put("/{card_id}/status", response_model=CardResponse, summary="Update Card Status")
@audit_update(
    resource_type="CARD", 
    screen_reference="CardStatusUpdate",
    get_old_data=lambda db, card_id: db.query(crud_card.model).filter(crud_card.model.id == card_id).first()
)
async def update_card_status(
    card_id: UUID = Path(..., description="Card ID"),
    status_update: CardStatusUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.update_status"))
):
    """
    Update card status through production workflow
    
    Status transitions:
    PENDING_ORDER → ORDERED → PENDING_PRODUCTION → IN_PRODUCTION → 
    QUALITY_CONTROL → PRODUCTION_COMPLETED → READY_FOR_COLLECTION → COLLECTED
    """
    card = crud_card.update_status(
        db=db,
        card_id=card_id,
        status_update=status_update,
        current_user=current_user
    )
    
    return CardResponse.from_orm(card)


@router.post("/{card_id}/order", response_model=CardResponse, summary="Order Card for Production")
async def order_card_for_production(
    card_id: UUID = Path(..., description="Card ID"),
    production_priority: int = Query(1, ge=1, le=3, description="Production priority (1=normal, 2=urgent, 3=emergency)"),
    production_location_id: Optional[UUID] = Query(None, description="Override production location"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.order"))
):
    """
    Order card for production
    
    This moves the card from PENDING_ORDER to ORDERED status and
    schedules it for production.
    """
    card = crud_card.order_for_production(
        db=db,
        card_id=card_id,
        production_priority=production_priority,
        production_location_id=production_location_id,
        current_user=current_user
    )
    
    return CardResponse.from_orm(card)


@router.post("/{card_id}/collect", response_model=CardResponse, summary="Process Card Collection")
@audit_update(
    resource_type="CARD", 
    screen_reference="CardCollection",
    get_old_data=lambda db, card_id: db.query(crud_card.model).filter(crud_card.model.id == card_id).first()
)
async def collect_card(
    card_id: UUID = Path(..., description="Card ID"),
    collection_data: Dict[str, Any] = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.collect"))
):
    """
    Process card collection by person
    
    Validates identity and marks card as collected.
    """
    card = crud_card.process_collection(
        db=db,
        card_id=card_id,
        collection_data=collection_data,
        current_user=current_user
    )
    
    return CardResponse.from_orm(card)


# Production Management Endpoints
@router.get("/production/pending", response_model=List[CardResponse], summary="Get Cards Pending Production")
async def get_cards_pending_production(
    production_location_id: Optional[UUID] = Query(None, description="Filter by production location"),
    priority: Optional[int] = Query(None, description="Filter by priority"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.production.read"))
):
    """
    Get cards that are pending production (for production workflow)
    """
    cards = crud_card.get_pending_production(
        db=db,
        production_location_id=production_location_id,
        priority=priority
    )
    
    return [CardResponse.from_orm(card) for card in cards]


@router.get("/collection/ready", response_model=List[CardResponse], summary="Get Cards Ready for Collection")
async def get_cards_ready_for_collection(
    collection_location_id: Optional[UUID] = Query(None, description="Filter by collection location"),
    days_ready: Optional[int] = Query(None, description="Cards ready for X days"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.collection.read"))
):
    """
    Get cards that are ready for collection
    """
    cards = crud_card.get_ready_for_collection(
        db=db,
        collection_location_id=collection_location_id,
        days_ready=days_ready
    )
    
    return [CardResponse.from_orm(card) for card in cards]


@router.get("/expiring", response_model=List[CardResponse], summary="Get Cards Expiring Soon")
async def get_expiring_cards(
    days: int = Query(90, ge=1, le=365, description="Cards expiring within X days"),
    person_id: Optional[UUID] = Query(None, description="Filter by person"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.read"))
):
    """
    Get cards that are expiring soon (for renewal notifications)
    """
    cards = crud_card.get_expiring_cards(
        db=db,
        days=days,
        person_id=person_id
    )
    
    return [CardResponse.from_orm(card) for card in cards]


# License Association Management
@router.post("/{card_id}/licenses/{license_id}", response_model=CardResponse, summary="Add License to Card")
async def add_license_to_card(
    card_id: UUID = Path(..., description="Card ID"),
    license_id: UUID = Path(..., description="License ID"),
    is_primary: bool = Query(False, description="Set as primary license"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.manage_licenses"))
):
    """
    Associate a license with a card
    """
    card = crud_card.add_license_association(
        db=db,
        card_id=card_id,
        license_id=license_id,
        is_primary=is_primary,
        current_user=current_user
    )
    
    return CardResponse.from_orm(card)


@router.delete("/{card_id}/licenses/{license_id}", response_model=CardResponse, summary="Remove License from Card")
async def remove_license_from_card(
    card_id: UUID = Path(..., description="Card ID"),
    license_id: UUID = Path(..., description="License ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.manage_licenses"))
):
    """
    Remove license association from card
    """
    card = crud_card.remove_license_association(
        db=db,
        card_id=card_id,
        license_id=license_id,
        current_user=current_user
    )
    
    return CardResponse.from_orm(card)


# Statistics and Reporting
@router.get("/statistics/overview", response_model=CardStatistics, summary="Get Card Statistics")
async def get_card_statistics(
    location_id: Optional[UUID] = Query(None, description="Filter by location"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.view_statistics"))
):
    """
    Get comprehensive card statistics for reporting
    """
    stats = crud_card.get_statistics(db, location_id=location_id)
    
    return CardStatistics(**stats)


# Card Replacement and Duplicates
@router.post("/{card_id}/replace", response_model=CardResponse, summary="Request Card Replacement")
async def request_card_replacement(
    card_id: UUID = Path(..., description="Card ID to replace"),
    replacement_reason: str = Query(..., description="Reason for replacement"),
    urgent: bool = Query(False, description="Urgent replacement"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.replace"))
):
    """
    Request replacement for lost/stolen/damaged card
    """
    replacement_card = crud_card.create_replacement(
        db=db,
        original_card_id=card_id,
        replacement_reason=replacement_reason,
        urgent=urgent,
        current_user=current_user
    )
    
    return CardResponse.from_orm(replacement_card)


@router.post("/{card_id}/duplicate", response_model=CardResponse, summary="Create Card Duplicate")
async def create_card_duplicate(
    card_id: UUID = Path(..., description="Card ID to duplicate"),
    reason: str = Query(..., description="Reason for duplicate"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.duplicate"))
):
    """
    Create duplicate of existing card
    """
    duplicate_card = crud_card.create_duplicate(
        db=db,
        original_card_id=card_id,
        reason=reason,
        current_user=current_user
    )
    
    return CardResponse.from_orm(duplicate_card)


# Production Batch Management
@router.get("/production/batches", response_model=List[Dict[str, Any]], summary="Get Production Batches")
async def get_production_batches(
    production_location_id: Optional[UUID] = Query(None, description="Filter by production location"),
    status: Optional[str] = Query(None, description="Filter by batch status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.production.manage"))
):
    """
    Get production batches for management
    """
    batches = crud_card_production_batch.get_batches(
        db=db,
        production_location_id=production_location_id,
        status=status
    )
    
    return [batch.to_dict() for batch in batches]


@router.post("/production/batches", response_model=Dict[str, Any], summary="Create Production Batch")
async def create_production_batch(
    production_location_id: UUID = Query(..., description="Production location"),
    card_ids: List[UUID] = Query(..., description="Cards to include in batch"),
    batch_name: Optional[str] = Query(None, description="Batch name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("cards.production.manage"))
):
    """
    Create new production batch with selected cards
    """
    batch = crud_card_production_batch.create_batch(
        db=db,
        production_location_id=production_location_id,
        card_ids=card_ids,
        batch_name=batch_name,
        current_user=current_user
    )
    
    return batch.to_dict()


# Health Check
@router.get("/health", summary="Card Service Health Check")
async def health_check(
    db: Session = Depends(get_db)
):
    """
    Health check endpoint for card service
    """
    try:
        # Quick database connectivity test
        db.execute("SELECT 1")
        
        # Check if card tables exist and are accessible
        from app.models.card import Card
        card_count = db.query(Card).count()
        
        return {
            "status": "healthy",
            "service": "card_management",
            "database": "connected",
            "total_cards": card_count
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Card service unhealthy: {str(e)}"
        ) 