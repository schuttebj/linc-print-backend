"""
License Management API Endpoints for Madagascar License System
Comprehensive REST API for license creation, management, and card handling

Features:
- License creation from applications
- License status management (ACTIVE, SUSPENDED, CANCELLED)
- Card management with expiry tracking
- Search and filtering capabilities
- ISO 18013 and SADC compliance
- License number validation
- Statistics and reporting
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
from app.crud.crud_license import crud_license
from app.crud.crud_application import crud_application
from app.models.user import User
from app.schemas.license import (
    LicenseCreateFromApplication, LicenseCreate, LicenseStatusUpdate,
    LicenseRestrictionsUpdate, LicenseProfessionalPermitUpdate,
    LicenseSearchFilters,
    LicenseResponse, LicenseDetailResponse, LicenseListResponse,
    LicenseStatusHistoryResponse, PersonLicensesSummary,
    LicenseStatistics, BulkLicenseStatusUpdate, BulkOperationResponse,
    AuthorizationData, AvailableRestrictionsResponse, RestrictionDetail
)


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


router = APIRouter()


# License Creation Endpoints
@router.post("/from-application", response_model=LicenseResponse, summary="Create License from Application")
@audit_create(resource_type="LICENSE", screen_reference="LicenseCreation")
async def create_license_from_application(
    license_in: LicenseCreateFromApplication,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("licenses.create"))
):
    """
    Create a license from a completed application
    
    This is the primary endpoint for license creation after application approval.
    - Validates application status and eligibility
    - Generates unique license number with check digit
    - Creates license with proper ISO/SADC compliance
    - Optionally orders card immediately
    """
    try:
        license_obj = crud_license.create_from_application(
            db=db, 
            obj_in=license_in, 
            current_user=current_user
        )
        
        return LicenseResponse.from_orm(license_obj)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create license: {str(e)}"
        )


@router.post("/from-authorized-application", response_model=LicenseResponse, summary="Create License from Authorized Application with Restrictions")
@audit_create(resource_type="LICENSE", screen_reference="LicenseAuthorization")
async def create_license_from_authorized_application(
    application_id: UUID = Path(..., description="Application ID"),
    authorization_data: AuthorizationData = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("licenses.create"))
):
    """
    Create license from authorized application with test results and restrictions
    
    This endpoint is called AFTER the application authorization step where:
    - Tests have been completed (eye test, driving test, medical assessment)
    - Restrictions have been determined from test results
    - Professional permit eligibility has been assessed
    
    Expected authorization_data format:
    {
        "restrictions": ["01", "03"],  // Restriction codes from test results
        "medical_restrictions": ["High blood pressure monitored"],
        "professional_permit": {
            "eligible": true,
            "categories": ["P"],
            "expiry_years": 5
        },
        "captured_license_data": {
            "original_license_number": "OLD123456789"  // If license capture application
        },
        "test_results": {
            "eye_test": {...},
            "driving_test": {...},
            "medical_assessment": {...}
        }
    }
    """
    try:
        # Get application to determine license category
        application = crud_application.get(db, id=application_id)
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application {application_id} not found"
            )
        
        # Extract license category from application type
        app_type = application.application_type.value
        if app_type.endswith("_APPLICATION"):
            license_category = app_type.replace("_APPLICATION", "")
        else:
            license_category = app_type
        
        # Process professional permit data
        professional_permit = authorization_data.get("professional_permit", {})
        has_professional_permit = professional_permit.get("eligible", False)
        professional_permit_categories = professional_permit.get("categories", [])
        professional_permit_expiry = None
        
        if has_professional_permit and professional_permit.get("expiry_years"):
            from datetime import datetime, timedelta
            expiry_years = professional_permit.get("expiry_years", 5)
            professional_permit_expiry = datetime.utcnow() + timedelta(days=expiry_years * 365)
        
        # Extract captured license data if applicable
        captured_license_data = authorization_data.get("captured_license_data", {})
        captured_from_license_number = captured_license_data.get("original_license_number")
        
        # Create license data
        license_data = LicenseCreateFromApplication(
            application_id=application_id,
            license_category=license_category,
            restrictions=authorization_data.get("restrictions", []),
            medical_restrictions=authorization_data.get("medical_restrictions", []),
            has_professional_permit=has_professional_permit,
            professional_permit_categories=professional_permit_categories,
            professional_permit_expiry=professional_permit_expiry,
            captured_from_license_number=captured_from_license_number,
            order_card_immediately=True,  # Always order card for new licenses
            card_expiry_years=5
        )
        
        # Create the license
        license_obj = crud_license.create_from_application(
            db=db,
            obj_in=license_data,
            current_user=current_user
        )
        
        # Update application status to completed
        try:
            crud_application.update_status(
                db=db,
                application_id=application_id,
                new_status="COMPLETED",
                notes=f"License {license_obj.license_number} created successfully",
                updated_by=current_user.id
            )
        except Exception as e:
            # Log the error but don't fail license creation
            logger.warning(f"Failed to update application status: {e}")
        
        return LicenseResponse.from_orm(license_obj)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create license from authorized application: {str(e)}"
        )


@router.post("/manual", response_model=LicenseResponse, summary="Create License Manually")
@audit_create(resource_type="LICENSE", screen_reference="ManualLicenseCreation")
async def create_license_manual(
    license_in: LicenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("licenses.create_manual"))
):
    """
    Create a license manually (for admin/special cases)
    
    Allows direct license creation without an application.
    Requires elevated permissions.
    """
    try:
        license_obj = crud_license.create_manual(
            db=db,
            obj_in=license_in, 
            current_user=current_user
        )
        
        return LicenseResponse.from_orm(license_obj)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create license manually: {str(e)}"
        )


@router.get("/restrictions/available", response_model=AvailableRestrictionsResponse, summary="Get Available Restriction Codes")
async def get_available_restriction_codes(
    current_user: User = Depends(require_permission("licenses.read"))
):
    """
    Get all available restriction codes with descriptions
    
    Used by authorization frontend to show available restrictions
    """
    from app.models.enums import LICENSE_RESTRICTION_MAPPING
    
    restrictions = []
    for restriction_enum, info in LICENSE_RESTRICTION_MAPPING.items():
        restrictions.append(RestrictionDetail(
            code=info["code"],
            description=info["description"],
            category=info["category"].value,
            display_name=info["display_name"]
        ))
    
    # Sort by code
    restrictions.sort(key=lambda x: x.code)
    
    return AvailableRestrictionsResponse(
        restrictions=restrictions,
        total=len(restrictions)
    )


# License Query Endpoints
@router.get("/{license_id}", response_model=LicenseDetailResponse, summary="Get License Details")
async def get_license(
    license_id: UUID = Path(..., description="License ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("licenses.read"))
):
    """
    Get detailed license information including cards and history
    """
    license_obj = crud_license.get_with_details(db, license_id=license_id)
    if not license_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"License {license_id} not found"
        )
    
    # Build the response manually to handle all required fields
    # Convert license to basic response first
    base_license_data = LicenseResponse.from_orm(license_obj).dict()
    
    # Add person information
    person_name = None
    person_surname = None
    if license_obj.person:
        person_name = license_obj.person.first_name
        person_surname = license_obj.person.surname
    
    # Add location information
    issuing_location_name = None
    issuing_location_code = None
    if license_obj.issuing_location:
        issuing_location_name = license_obj.issuing_location.name
        issuing_location_code = license_obj.issuing_location.code
    
    # Convert cards - TODO: Implement when card CRUD is ready
    cards = []
    # Note: Temporarily disabled until new card system is fully implemented
    # if license_obj.cards:
    #     cards = [LicenseCardInfo.from_orm(card) for card in license_obj.cards]
    
    # Convert status history
    status_history = []
    if license_obj.status_history:
        status_history = [LicenseStatusHistoryResponse.from_orm(history) for history in license_obj.status_history]
    
    # Build the detailed response
    response_data = LicenseDetailResponse(
        **base_license_data,
        cards=cards,
        status_history=status_history,
        person_name=person_name,
        person_surname=person_surname,
        issuing_location_name=issuing_location_name,
        issuing_location_code=issuing_location_code,
        # Add compliance fields
        sadc_compliance_verified=license_obj.sadc_compliance_verified,
        international_validity=license_obj.international_validity,
        vienna_convention_compliant=license_obj.vienna_convention_compliant
    )
    
    return response_data


@router.get("/person/{person_id}", response_model=List[LicenseResponse], summary="Get Person's Licenses")
async def get_person_licenses(
    person_id: UUID = Path(..., description="Person ID"),
    active_only: bool = Query(False, description="Return only active licenses"),
    skip: int = Query(0, ge=0, description="Skip records"),
    limit: int = Query(100, ge=1, le=1000, description="Limit records"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("licenses.read"))
):
    """
    Get all licenses for a specific person
    """
    licenses = crud_license.get_by_person_id(
        db=db,
        person_id=person_id,
        active_only=active_only,
        skip=skip,
        limit=limit
    )
    
    return [LicenseResponse.from_orm(license_obj) for license_obj in licenses]


@router.get("/person/{person_id}/summary", response_model=PersonLicensesSummary, summary="Get Person's License Summary")
async def get_person_licenses_summary(
    person_id: UUID = Path(..., description="Person ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("licenses.read"))
):
    """
    Get summary of all licenses for a person
    """
    licenses = crud_license.get_by_person_id(db=db, person_id=person_id, limit=1000, active_only=False)
    
    if not licenses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No licenses found for person {person_id}"
        )
    
    # Calculate summary statistics
    total_licenses = len(licenses)
    active_licenses = sum(1 for l in licenses if l.is_active)
    suspended_licenses = sum(1 for l in licenses if l.is_suspended)
    cancelled_licenses = sum(1 for l in licenses if l.is_cancelled)
    
    # Get unique categories
    categories = list(set(license.category for license in licenses))
    
    # Latest license info
    latest_license = max(licenses, key=lambda l: l.issue_date)
    
    # Card statistics
    all_cards = []
    for license_obj in licenses:
        all_cards.extend(license_obj.cards)
    
    cards_ready_for_collection = sum(1 for card in all_cards if card.is_ready_for_collection)
    cards_near_expiry = sum(1 for card in all_cards if card.is_current and card.is_near_expiry)
    
    # Get person name
    person_name = f"{latest_license.person.first_name} {latest_license.person.surname}"
    
    return PersonLicensesSummary(
        person_id=person_id,
        person_name=person_name,
        total_licenses=total_licenses,
        active_licenses=active_licenses,
        suspended_licenses=suspended_licenses,
        cancelled_licenses=cancelled_licenses,
        categories=categories,
        latest_license_date=latest_license.issue_date,
        latest_license_id=latest_license.id,
        cards_ready_for_collection=cards_ready_for_collection,
        cards_near_expiry=cards_near_expiry
    )


@router.post("/search", response_model=LicenseListResponse, summary="Search Licenses")
async def search_licenses(
    filters: LicenseSearchFilters,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("licenses.read"))
):
    """
    Search licenses with comprehensive filtering
    """
    licenses, total = crud_license.search_licenses(db=db, filters=filters)
    
    # Calculate pagination info
    pages = (total + filters.size - 1) // filters.size
    
    return LicenseListResponse(
        licenses=[LicenseResponse.from_orm(license_obj) for license_obj in licenses],
        total=total,
        page=filters.page,
        size=filters.size,
        pages=pages
    )


# License Management Endpoints
@router.put("/{license_id}/status", response_model=LicenseResponse, summary="Update License Status")
@audit_update(
    resource_type="LICENSE", 
    screen_reference="LicenseStatusUpdate",
    get_old_data=lambda db, license_id: db.query(crud_license.model).filter(crud_license.model.id == license_id).first()
)
async def update_license_status(
    license_id: UUID = Path(..., description="License ID"),
    status_update: LicenseStatusUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("licenses.update_status"))
):
    """
    Update license status (ACTIVE, SUSPENDED, CANCELLED)
    
    Includes proper audit trail and status history tracking.
    """
    license_obj = crud_license.update_status(
        db=db,
        license_id=license_id,
        status_update=status_update,
        current_user=current_user
    )
    
    return LicenseResponse.from_orm(license_obj)


@router.put("/{license_id}/restrictions", response_model=LicenseResponse, summary="Update License Restrictions")
@audit_update(
    resource_type="LICENSE", 
    screen_reference="LicenseRestrictions",
    get_old_data=lambda db, license_id: db.query(crud_license.model).filter(crud_license.model.id == license_id).first()
)
async def update_license_restrictions(
    license_id: UUID = Path(..., description="License ID"),
    restrictions_update: LicenseRestrictionsUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("licenses.update"))
):
    """
    Update license restrictions (corrective lenses, medical restrictions, etc.)
    """
    license_obj = crud_license.update_restrictions(
        db=db,
        license_id=license_id,
        restrictions_update=restrictions_update,
        current_user=current_user
    )
    
    return LicenseResponse.from_orm(license_obj)


@router.put("/{license_id}/professional-permit", response_model=LicenseResponse, summary="Update Professional Permit")
@audit_update(
    resource_type="LICENSE", 
    screen_reference="ProfessionalPermit",
    get_old_data=lambda db, license_id: db.query(crud_license.model).filter(crud_license.model.id == license_id).first()
)
async def update_professional_permit(
    license_id: UUID = Path(..., description="License ID"),
    permit_update: LicenseProfessionalPermitUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("licenses.update"))
):
    """
    Update professional driving permit information
    """
    license_obj = crud_license.update_professional_permit(
        db=db,
        license_id=license_id,
        permit_update=permit_update,
        current_user=current_user
    )
    
    return LicenseResponse.from_orm(license_obj)


# NOTE: Card management endpoints are now handled by the dedicated /api/v1/cards/ router
# This provides better separation of concerns and supports the new independent card system


# Utility Endpoints
@router.get("/statistics/overview", response_model=LicenseStatistics, summary="Get License Statistics")
async def get_license_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("licenses.read"))
):
    """
    Get comprehensive license statistics for reporting
    """
    stats = crud_license.get_statistics(db)
    
    return LicenseStatistics(**stats)


# Bulk Operations
@router.post("/bulk/status-update", response_model=BulkOperationResponse, summary="Bulk Status Update")
async def bulk_status_update(
    bulk_update: BulkLicenseStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("licenses.bulk_update"))
):
    """
    Update status for multiple licenses in bulk
    
    Useful for administrative actions like bulk suspensions.
    """
    successful = 0
    failed = 0
    error_details = []
    
    for license_id in bulk_update.license_ids:
        try:
            status_update = LicenseStatusUpdate(
                status=bulk_update.status,
                reason=bulk_update.reason,
                notes=bulk_update.notes
            )
            
            crud_license.update_status(
                db=db,
                license_id=license_id,
                status_update=status_update,
                current_user=current_user
            )
            successful += 1
            
        except Exception as e:
            failed += 1
            error_details.append({
                "license_id": str(license_id),
                "error": str(e)
            })
    
    return BulkOperationResponse(
        total_requested=len(bulk_update.license_ids),
        successful=successful,
        failed=failed,
        error_details=error_details
    )


# Health Check
@router.get("/health", summary="License Service Health Check")
async def health_check(
    db: Session = Depends(get_db)
):
    """
    Health check endpoint for license service
    """
    try:
        # Quick database connectivity test
        db.execute("SELECT 1")
        
        # Check if sequence counter table exists and is accessible
        from app.models.license import LicenseSequenceCounter
        counter = db.query(LicenseSequenceCounter).first()
        
        return {
            "status": "healthy",
            "service": "license_management",
            "database": "connected",
            "sequence_counter": "accessible",
            "current_sequence": counter.current_sequence if counter else 0
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"License service unhealthy: {str(e)}"
        ) 