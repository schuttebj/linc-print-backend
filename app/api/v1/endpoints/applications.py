"""
Application Management API Endpoints for Madagascar License System
Comprehensive REST API for driver's license applications with complete workflow support
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from pathlib import Path
import uuid
import logging
from datetime import datetime, timedelta

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.application import Application, ApplicationAuthorization
from app.models.enums import ApplicationStatus, ApplicationType, LicenseCategory, RoleHierarchy
from app.schemas.application import (
    Application as ApplicationSchema,
    ApplicationCreate,
    ApplicationUpdate, 
    ApplicationSearch,
    ApplicationWithDetails,
    ApplicationFee,
    ApplicationFeeCreate,
    ApplicationStatistics
)
from app.crud.crud_application import (
    crud_application,
    crud_application_fee,
    crud_application_biometric_data,
    crud_application_test_attempt,
    crud_application_document
)
from app.crud.crud_license import crud_license
from app.services.image_service import ImageProcessingService
from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/", response_model=List[ApplicationSchema])
def get_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[ApplicationStatus] = None,
    application_type: Optional[ApplicationType] = None,
    location_id: Optional[uuid.UUID] = None,
    is_urgent: Optional[bool] = None
) -> List[ApplicationSchema]:
    """
    Get applications with optional filtering
    
    Requires: applications.read permission
    """
    if not current_user.has_permission("applications.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to read applications"
        )
    
    # Build search parameters
    search_params = ApplicationSearch()
    if status:
        search_params.status = status
    if application_type:
        search_params.application_type = application_type
    if location_id:
        search_params.location_id = location_id
    if is_urgent is not None:
        search_params.is_urgent = is_urgent
    
    # Apply location filtering for location users
    if current_user.user_type.value == "LOCATION_USER":
        if not current_user.can_access_location(location_id or current_user.primary_location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access applications for this location"
            )
        search_params.location_id = current_user.primary_location_id
    
    applications = crud_application.search_applications(
        db=db, search_params=search_params, skip=skip, limit=limit
    )
    
    return applications


@router.get("/search/person/{person_id}", response_model=List[ApplicationSchema])
def get_applications_by_person(
    person_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[ApplicationSchema]:
    """
    Get all applications for a specific person (for quick continuation)
    
    Requires: applications.read permission
    """
    if not current_user.has_permission("applications.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to read applications"
        )
    
    # Apply location filtering for location users
    location_filter = None
    if current_user.user_type.value == "LOCATION_USER":
        location_filter = current_user.primary_location_id
    
    applications = crud_application.get_applications_by_person(
        db=db, person_id=person_id
    )
    
    return applications


@router.get("/in-progress", response_model=List[ApplicationSchema])
def get_in_progress_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    date: Optional[str] = Query("today", description="Date filter (today, week, month)"),
    stage: Optional[str] = Query(None, description="Workflow stage filter")
) -> List[ApplicationSchema]:
    """
    Get applications that are ready for next stage processing
    
    Requires: applications.read permission
    """
    if not current_user.has_permission("applications.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to read applications"
        )
    
    # Apply location filtering for location users
    location_filter = None
    if current_user.user_type.value == "LOCATION_USER":
        location_filter = current_user.primary_location_id
    
    # Get applications ready for next stage
    applications = crud_application.get_in_progress_applications(
        db=db, 
        location_id=location_filter,
        date_filter=date,
        stage_filter=stage
    )
    
    return applications





@router.post("/", response_model=ApplicationSchema)
def create_application(
    *,
    db: Session = Depends(get_db),
    application_in: ApplicationCreate,
    current_user: User = Depends(get_current_user)
) -> ApplicationSchema:
    """
    Create new license application
    
    Requires: applications.create permission
    """
    if not current_user.has_permission("applications.create"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to create applications"
        )
    
    # Validate person exists
    from app.crud.crud_person import person as crud_person
    person = crud_person.get(db=db, id=application_in.person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found"
        )
    
    # Validate location access
    if not current_user.can_access_location(application_in.location_id):
        # For provincial admins, do additional province check
        if current_user.user_type.value == "PROVINCIAL_ADMIN":
            from app.crud.crud_location import crud_location
            location = crud_location.get(db=db, id=application_in.location_id)
            if not location or location.province_code != current_user.scope_province:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to create applications for locations outside {current_user.scope_province} province"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to create applications for this location"
            )
    
    # Validate age requirements and set flags
    validated_application = _validate_and_enhance_application(db, application_in, person)
    
    # Create application with audit trail
    application = crud_application.create_with_details(
        db=db, obj_in=validated_application, created_by_user_id=current_user.id
    )
    
    # Create required fees
    if application.status != ApplicationStatus.DRAFT:
        crud_application_fee.create_application_fees(
            db=db, application_id=application.id, created_by_user_id=current_user.id
        )
    
    return application


@router.get("/search", response_model=List[ApplicationSchema])
def search_applications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    application_number: Optional[str] = None,
    person_id: Optional[uuid.UUID] = None,
    application_type: Optional[ApplicationType] = None,
    status: Optional[ApplicationStatus] = None,
    location_id: Optional[uuid.UUID] = None,
    license_categories: Optional[List[str]] = Query(None),
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    is_urgent: Optional[bool] = None,
    is_temporary_license: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500)
) -> List[ApplicationSchema]:
    """
    Advanced application search
    
    Requires: applications.read permission
    """
    if not current_user.has_permission("applications.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to search applications"
        )
    
    # Build search parameters
    search_params = ApplicationSearch(
        application_number=application_number,
        person_id=person_id,
        application_type=application_type,
        status=status,
        location_id=location_id,
        license_categories=license_categories,
        date_from=date_from,
        date_to=date_to,
        is_urgent=is_urgent,
        is_temporary_license=is_temporary_license
    )
    
    # Apply location filtering for location users
    if current_user.user_type.value == "LOCATION_USER":
        search_params.location_id = current_user.primary_location_id
    
    applications = crud_application.search_applications(
        db=db, search_params=search_params, skip=skip, limit=limit
    )
    
    return applications


@router.get("/pending-authorization", response_model=List[ApplicationSchema])
def get_applications_pending_authorization(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    location_id: Optional[uuid.UUID] = None
) -> List[ApplicationSchema]:
    """
    Get applications that are pending authorization by examiners
    
    Requires: applications.authorize permission or EXAMINER role
    """
    # Check if user has authorization permissions
    if not (current_user.has_permission("applications.authorize") or 
            current_user.role_hierarchy == RoleHierarchy.EXAMINER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view applications pending authorization"
        )
    
    # Apply location filtering for location users
    if current_user.user_type.value == "LOCATION_USER":
        location_id = current_user.primary_location_id
    
    # Get applications with PASSED status (ready for authorization)
    search_params = ApplicationSearch()
    search_params.status = ApplicationStatus.PASSED
    if location_id:
        search_params.location_id = location_id
    
    applications = crud_application.search_applications(
        db=db, search_params=search_params, skip=skip, limit=limit
    )
    
    return applications


@router.get("/{application_id}", response_model=ApplicationWithDetails)
def get_application(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApplicationWithDetails:
    """
    Get application by ID with full details
    
    Requires: applications.read permission
    """
    if not current_user.has_permission("applications.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to read applications"
        )
    
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check location access
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this application"
        )
    
    # Build detailed response with related data
    application_dict = ApplicationSchema.from_orm(application).dict()
    
    # Add related data
    application_dict["biometric_data"] = crud_application_biometric_data.get_by_application(
        db=db, application_id=application_id
    )
    application_dict["fees"] = crud_application_fee.get_by_application(
        db=db, application_id=application_id
    )
    application_dict["test_attempts"] = crud_application_test_attempt.get_by_application(
        db=db, application_id=application_id
    )
    application_dict["documents"] = crud_application_document.get_by_application(
        db=db, application_id=application_id
    )
    application_dict["child_applications"] = crud_application.get_associated_applications(
        db=db, parent_application_id=application_id
    )
    
    return ApplicationWithDetails(**application_dict)


@router.put("/{application_id}", response_model=ApplicationSchema)
def update_application(
    *,
    db: Session = Depends(get_db),
    application_id: uuid.UUID,
    application_in: ApplicationUpdate,
    current_user: User = Depends(get_current_user)
) -> ApplicationSchema:
    """
    Update application
    
    Requires: applications.update permission
    """
    if not current_user.has_permission("applications.update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update applications"
        )
    
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check location access
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this application"
        )
    
    # Prevent updates to completed applications
    if application.status in [ApplicationStatus.COMPLETED, ApplicationStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update completed or cancelled applications"
        )
    
    updated_application = crud_application.update(
        db=db, db_obj=application, obj_in=application_in
    )
    
    return updated_application


@router.post("/{application_id}/status", response_model=ApplicationSchema)
def update_application_status(
    *,
    db: Session = Depends(get_db),
    application_id: uuid.UUID,
    new_status: ApplicationStatus,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_user)
) -> ApplicationSchema:
    """
    Update application status with history tracking
    
    Requires: applications.change_status permission
    """
    if not current_user.has_permission("applications.change_status"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to change application status"
        )
    
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check location access
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this application"
        )
    
    # Validate status transition
    if not _is_valid_status_transition(application.status, new_status, application):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition from {application.status} to {new_status}"
        )
    
    updated_application = crud_application.update_status(
        db=db,
        application_id=application_id,
        new_status=new_status,
        changed_by=current_user.id,
        reason=reason,
        notes=notes
    )
    
    # Auto-generate license when moving to APPROVED status (for capture applications)
    if (new_status == ApplicationStatus.APPROVED and 
        application.application_type in [ApplicationType.DRIVERS_LICENSE_CAPTURE, ApplicationType.LEARNERS_PERMIT_CAPTURE]):
        
        try:
            # Check if license doesn't already exist
            from app.crud.crud_license import crud_license
            existing_license = crud_license.get_by_application_id(db, application_id=application_id)
            
            if not existing_license:
                # Generate license automatically
                license = _generate_license_from_application_status(db, updated_application, current_user)
                logger.info(f"Auto-generated license {license.id} for application {application_id}")
        except Exception as e:
            # Log error but don't fail status update
            logger.error(f"Failed to auto-generate license for application {application_id}: {str(e)}")
    
    return updated_application


@router.post("/{application_id}/submit-async", response_model=Dict[str, Any])
def submit_application_async(
    *,
    db: Session = Depends(get_db),
    application_id: uuid.UUID,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Submit application with async license generation
    
    Optimized endpoint for frontend:
    - Immediately changes status to SUBMITTED
    - Returns success response quickly
    - Triggers license generation in background (when moving to APPROVED)
    - Frontend doesn't wait for complete processing
    """
    if not current_user.has_permission("applications.change_status"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to submit application"
        )
    
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check location access
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to submit this application"
        )
    
    # Validate current status allows submission
    if application.status not in [ApplicationStatus.DRAFT, ApplicationStatus.ON_HOLD]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Application cannot be submitted from status {application.status}"
        )
    
    # Update to SUBMITTED status
    updated_application = crud_application.update_status(
        db=db,
        application_id=application_id,
        new_status=ApplicationStatus.SUBMITTED,
        changed_by=current_user.id,
        reason=reason or "Application submitted for processing",
        notes=notes
    )
    
    return {
        "status": "success",
        "message": "Application submitted successfully",
        "application_id": str(application_id),
        "application_number": updated_application.application_number,
        "current_status": updated_application.status.value,
        "submitted_at": updated_application.submitted_date.isoformat() if updated_application.submitted_date else None,
        "processing_note": "Application is being processed. License will be generated automatically upon approval."
    }


@router.post("/{application_id}/approve-and-generate-license", response_model=Dict[str, Any])
def approve_and_generate_license(
    *,
    db: Session = Depends(get_db),
    application_id: uuid.UUID,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Approve application and generate license in one operation
    
    Optimized for examiner workflow:
    - Validates application can be approved
    - Moves status to APPROVED
    - Generates license immediately
    - Returns both application and license info
    """
    if not current_user.has_permission("applications.authorize"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to approve application"
        )
    
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check location access
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to approve this application"
        )
    
    # Validate current status allows approval
    if application.status not in [ApplicationStatus.SUBMITTED, ApplicationStatus.PASSED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Application cannot be approved from status {application.status}"
        )
    
    # Update to APPROVED status
    updated_application = crud_application.update_status(
        db=db,
        application_id=application_id,
        new_status=ApplicationStatus.APPROVED,
        changed_by=current_user.id,
        reason=reason or "Application approved by examiner",
        notes=notes
    )
    
    # Generate license immediately
    license = None
    license_error = None
    
    try:
        # Check if license doesn't already exist
        from app.crud.crud_license import crud_license
        existing_license = crud_license.get_by_application_id(db, application_id=application_id)
        
        if existing_license:
            license = existing_license
        else:
            license = _generate_license_from_application_status(db, updated_application, current_user)
            
    except Exception as e:
        license_error = str(e)
        logger.error(f"Failed to generate license for application {application_id}: {license_error}")
    
    return {
        "status": "success",
        "message": "Application approved successfully",
        "application": {
            "id": str(updated_application.id),
            "number": updated_application.application_number,
            "status": updated_application.status.value,
            "person_id": str(updated_application.person_id),
            "license_category": updated_application.license_category.value
        },
        "license": {
            "id": str(license.id) if license else None,
            "status": license.status.value if license else None,
            "issue_date": license.issue_date.isoformat() if license else None,
            "category": license.category.value if license else None
        } if license else None,
        "license_generation_error": license_error,
        "next_steps": [
            "License has been generated" if license else "License generation failed - check logs",
            "Application can now be moved to COMPLETED status",
            "Card production can be initiated"
        ]
    }


@router.get("/{application_id}/license", response_model=Dict[str, Any])
def get_application_license(
    *,
    db: Session = Depends(get_db),
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get license generated from application
    
    Quick check endpoint to see if license was generated
    """
    if not current_user.has_permission("applications.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view application"
        )
    
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check location access
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this application"
        )
    
    # Get license if it exists
    from app.crud.crud_license import crud_license
    license = crud_license.get_by_application_id(db, application_id=application_id)
    
    return {
        "application_id": str(application_id),
        "application_number": application.application_number,
        "application_status": application.status.value,
        "license_generated": license is not None,
        "license": {
            "id": str(license.id),
            "status": license.status.value,
            "issue_date": license.issue_date.isoformat(),
            "category": license.category.value,
            "restrictions": license.restrictions
        } if license else None
    }


@router.get("/{application_id}/fees", response_model=List[ApplicationFee])
def get_application_fees(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[ApplicationFee]:
    """
    Get fees for an application
    
    Requires: applications.read permission
    """
    if not current_user.has_permission("applications.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to read application fees"
        )
    
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check location access
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this application"
        )
    
    fees = crud_application_fee.get_by_application(db=db, application_id=application_id)
    return fees


@router.post("/{application_id}/fees/{fee_id}/pay", response_model=ApplicationFee)
def process_fee_payment(
    *,
    db: Session = Depends(get_db),
    application_id: uuid.UUID,
    fee_id: uuid.UUID,
    payment_method: str,
    payment_reference: Optional[str] = None,
    current_user: User = Depends(get_current_user)
) -> ApplicationFee:
    """
    Process fee payment
    
    Requires: fee_payments.process permission
    """
    if not current_user.has_permission("fee_payments.process"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to process payments"
        )
    
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check location access
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to process payments for this application"
        )
    
    fee = crud_application_fee.process_payment(
        db=db,
        fee_id=fee_id,
        processed_by=current_user.id,
        payment_method=payment_method,
        payment_reference=payment_reference
    )
    
    return fee


@router.get("/{application_id}/associated", response_model=List[ApplicationSchema])
def get_associated_applications(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[ApplicationSchema]:
    """
    Get applications associated with a parent application (e.g., temporary licenses)
    
    Requires: applications.read permission
    """
    if not current_user.has_permission("applications.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to read applications"
        )
    
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check location access
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this application"
        )
    
    associated_applications = crud_application.get_associated_applications(
        db=db, parent_application_id=application_id
    )
    
    return associated_applications


@router.get("/statistics", response_model=ApplicationStatistics)
def get_application_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    location_id: Optional[uuid.UUID] = None
) -> ApplicationStatistics:
    """
    Get application statistics
    
    Requires: applications.view_statistics permission
    """
    if not current_user.has_permission("applications.view_statistics"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view application statistics"
        )
    
    # Apply location filtering for location users
    if current_user.user_type.value == "LOCATION_USER":
        location_id = current_user.primary_location_id
    elif location_id and not current_user.can_access_location(location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view statistics for this location"
        )
    
    statistics = crud_application.get_application_statistics(
        db=db, location_id=location_id
    )
    
    return ApplicationStatistics(**statistics)


@router.delete("/expired-drafts")
def cleanup_expired_drafts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Delete expired draft applications (30+ days old)
    
    Requires: applications.delete permission
    """
    if not current_user.has_permission("applications.delete"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete applications"
        )
    
    deleted_count = crud_application.delete_expired_drafts(db=db)
    
    return {
        "message": f"Deleted {deleted_count} expired draft applications",
        "deleted_count": deleted_count
    }


@router.post("/{application_id}/documents")
async def upload_application_document(
    *,
    db: Session = Depends(get_db),
    application_id: uuid.UUID,
    file: UploadFile = File(...),
    document_type: str,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Upload document for application (medical certificate, parental consent, etc.)
    
    Requires: applications.update permission
    """
    if not current_user.has_permission("applications.update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to upload documents"
        )
    
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check location access
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to upload documents for this application"
        )
    
    # For now, return placeholder response - implement file upload logic later
    return {
        "status": "success",
        "message": "Document upload endpoint ready",
        "file_name": file.filename,
        "document_type": document_type,
        "notes": notes
    }


@router.post("/{application_id}/biometric-data")
async def upload_biometric_data(
    *,
    db: Session = Depends(get_db),
    application_id: uuid.UUID,
    file: UploadFile = File(...),
    data_type: str = Form(..., description="Type of biometric data: PHOTO, SIGNATURE, or FINGERPRINT"),
    capture_method: Optional[str] = Form(None, description="Capture method (WEBCAM, DIGITAL_PAD, etc.)"),
    current_user: User = Depends(get_current_user)
):
    """
    Upload biometric data for application (photo, signature, fingerprint)
    
    For PHOTO data_type: Automatically processes to ISO standards
    - Crops to 3:4 aspect ratio (35mm x 45mm equivalent)
    - Optimizes quality and file size
    - Standardizes format to JPEG
    
    Requires: applications.update permission
    """
    if not current_user.has_permission("applications.update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to upload biometric data"
        )
    
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check location access
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to upload biometric data for this application"
        )
    
    try:
        settings = get_settings()
        
        # Create date-based storage path for better organization and backup management
        now = datetime.now()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")
        
        storage_path = (
            settings.get_file_storage_path() / 
            "biometric" / 
            year / 
            month / 
            day / 
            str(application_id)
        )
        
        # Process based on data type
        if data_type.upper() == "PHOTO":
            # Process license photo with ISO standards
            result = ImageProcessingService.process_license_photo(
                image_file=file,
                storage_path=storage_path,
                filename_prefix=f"license_photo_{application_id}"
            )
            
            # Store biometric data record in database
            from app.schemas.application import ApplicationBiometricDataCreate
            biometric_data_create = ApplicationBiometricDataCreate(
                application_id=application_id,
                data_type="PHOTO",
                file_path=str(result["file_path"]),
                file_size=result["file_size"],
                file_format=result["format"],
                image_resolution=result["dimensions"],
                capture_method=capture_method or "WEBCAM",
                capture_metadata=result["processing_info"]
            )
            
            # Save to database
            biometric_record = crud_application_biometric_data.create_biometric_data(
                db=db,
                obj_in=biometric_data_create,
                created_by_user_id=current_user.id
            )
            
            # Update application photo status
            crud_application.update(
                db=db,
                db_obj=application,
                obj_in={"photo_captured": True}
            )
            
            return {
                "status": "success",
                "message": "Photo processed and saved successfully",
                "data_type": "PHOTO",
                "file_info": {
                    "filename": result["filename"],
                    "file_size": result["file_size"],
                    "dimensions": result["dimensions"],
                    "format": result["format"]
                },
                "processing_info": {
                    "iso_compliant": True,
                    "cropped_automatically": True,
                    "enhanced": True,
                    "compression_ratio": result["processing_info"]["compression_ratio"]
                },
                "original_filename": result["original_filename"]
            }
            
        elif data_type.upper() in ["SIGNATURE", "FINGERPRINT"]:
            # For signature and fingerprint, save as-is with basic validation
            if not file.content_type or not file.content_type.startswith('image/'):
                raise HTTPException(
                    status_code=400,
                    detail="File must be an image"
                )
            
            # Generate filename and save
            file_extension = "jpg" if data_type.upper() == "SIGNATURE" else "png"
            filename = f"{data_type.lower()}_{application_id}_{uuid.uuid4()}.{file_extension}"
            file_path = storage_path / filename
            
            # Ensure directory exists
            storage_path.mkdir(parents=True, exist_ok=True)
            
            # Save file
            file_content = await file.read()
            with open(file_path, "wb") as f:
                f.write(file_content)
            
            file_size = file_path.stat().st_size
            
            # Store biometric data record in database
            biometric_data_create = ApplicationBiometricDataCreate(
                application_id=application_id,
                data_type=data_type.upper(),
                file_path=str(file_path),
                file_size=file_size,
                file_format=file_extension.upper(),
                capture_method=capture_method or "DIGITAL_PAD"
            )
            
            # Save to database
            biometric_record = crud_application_biometric_data.create_biometric_data(
                db=db,
                obj_in=biometric_data_create,
                created_by_user_id=current_user.id
            )
            
            return {
                "status": "success",
                "message": f"{data_type.title()} saved successfully",
                "data_type": data_type.upper(),
                "file_info": {
                    "filename": filename,
                    "file_size": file_size,
                    "format": file_extension.upper()
                },
                "original_filename": file.filename
            }
        
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid data_type. Must be PHOTO, SIGNATURE, or FINGERPRINT"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Biometric data upload failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process biometric data"
        )


@router.get("/{application_id}/biometric-data")
async def get_biometric_data(
    *,
    db: Session = Depends(get_db),
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get all biometric data for an application
    Returns file paths and metadata for photo, signature, and fingerprint
    """
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check location access
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view biometric data for this application"
        )
    
    # Get biometric data
    biometric_data = crud_application_biometric_data.get_by_application(
        db=db, 
        application_id=application_id
    )
    
    # Organize by data type
    organized_data = {
        "photo": None,
        "signature": None,
        "fingerprint": None
    }
    
    for item in biometric_data:
        data_type = item.data_type.value.lower()
        if data_type in organized_data:
            organized_data[data_type] = {
                "id": str(item.id),
                "file_path": item.file_path,
                "file_size": item.file_size,
                "file_format": item.file_format,
                "capture_method": item.capture_method,
                "image_resolution": item.image_resolution,
                "quality_score": float(item.quality_score) if item.quality_score else None,
                "is_verified": item.is_verified,
                "capture_metadata": item.capture_metadata,
                "created_at": item.created_at.isoformat(),
                "notes": item.notes
            }
    
    return {
        "application_id": str(application_id),
        "biometric_data": organized_data,
        "summary": {
            "total_items": len(biometric_data),
            "photo_captured": organized_data["photo"] is not None,
            "signature_captured": organized_data["signature"] is not None,
            "fingerprint_captured": organized_data["fingerprint"] is not None
        }
    }


@router.get("/person/{person_id}/licenses")
def get_person_licenses(
    *,
    db: Session = Depends(get_db),
    person_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get all existing licenses for a person to support capture validation
    This returns actual license data from the licenses table
    """
    
    try:
        # Get all licenses for the person
        licenses = crud_license.get_by_person_id(db=db, person_id=person_id, skip=0, limit=1000, active_only=False)
        
        # Convert to system license format for frontend compatibility
        system_licenses = []
        for license in licenses:
            # Determine license type and expiry date
            is_learner_permit = license.category.value in ['1', '2', '3']
            license_type = "LEARNERS_PERMIT" if is_learner_permit else "DRIVERS_LICENSE"
            
            # Use actual expiry date for learner's permits, default for regular licenses
            if license.expiry_date:
                expiry_date = license.expiry_date.strftime("%Y-%m-%d")
            elif is_learner_permit:
                # Fallback: calculate 6-month expiry for learner's permits if not set in DB
                from datetime import timedelta
                calculated_expiry = license.issue_date + timedelta(days=180)
                expiry_date = calculated_expiry.strftime("%Y-%m-%d")
            else:
                expiry_date = "2099-12-31"  # Default for regular licenses
            
            system_license = {
                "id": str(license.id),
                "person_id": str(license.person_id),
                "license_number": f"L-{str(license.id)[:8]}",  # Use formatted ID as license number
                "license_type": license_type,
                "categories": [license.category.value],  # Single category per license
                "status": license.status.value,
                "issue_date": license.issue_date.strftime("%Y-%m-%d"),
                "expiry_date": expiry_date,
                "issuing_location": license.issuing_location.name if license.issuing_location else "Unknown",
                "restrictions": license.restrictions or [],
                "is_active": license.is_active
            }
            system_licenses.append(system_license)
        
        return {
            "person_id": str(person_id),
            "system_licenses": system_licenses,
            "total_count": len(system_licenses)
        }
        
    except Exception as e:
        # Log error but don't fail completely
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting person licenses: {e}")
        
        # Return empty data if there's an error
        return {
            "person_id": str(person_id),
            "system_licenses": [],
            "total_count": 0
        }


@router.post("/process-image")
async def process_biometric_image(
    *,
    file: UploadFile = File(...),
    data_type: str = Form(..., description="Type of biometric data: PHOTO, SIGNATURE, or FINGERPRINT"),
    current_user: User = Depends(get_current_user)
):
    """
    Process biometric image without requiring an existing application
    
    This endpoint allows processing of images (cropping, resizing, ISO compliance)
    before the application is submitted. The processed image is returned as base64
    data that can be stored in the frontend until final submission.
    """
    logger.info(f"Processing biometric image: {data_type} for user {current_user.id}")
    
    # Validate data type
    if data_type.upper() not in ["PHOTO", "SIGNATURE", "FINGERPRINT"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid data_type. Must be PHOTO, SIGNATURE, or FINGERPRINT"
        )
    
    # Validate file
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=400,
            detail="File must be an image"
        )
    
    try:
        if data_type.upper() == "PHOTO":
            # Process license photo with ISO standards
            import tempfile
            import base64
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Process the image
                result = ImageProcessingService.process_license_photo(
                    image_file=file,
                    storage_path=temp_path,
                    filename_prefix="temp_license_photo"
                )
                
                # Read the processed image and convert to base64
                processed_file_path = Path(result["file_path"])
                with open(processed_file_path, "rb") as f:
                    image_data = f.read()
                    image_base64 = base64.b64encode(image_data).decode('utf-8')
                
                return {
                    "status": "success",
                    "message": "Photo processed successfully",
                    "data_type": "PHOTO",
                    "processed_image": {
                        "data": image_base64,
                        "format": "JPEG",
                        "dimensions": result["dimensions"],
                        "file_size": result["file_size"]
                    },
                    "processing_info": {
                        "iso_compliant": True,
                        "cropped_automatically": True,
                        "enhanced": True,
                        "compression_ratio": result["processing_info"]["compression_ratio"]
                    },
                    "original_filename": result["original_filename"]
                }
        
        elif data_type.upper() in ["SIGNATURE", "FINGERPRINT"]:
            # For signature and fingerprint, return as-is with basic validation
            import base64
            
            # Read and encode the file
            file_content = await file.read()
            file_base64 = base64.b64encode(file_content).decode('utf-8')
            
            # Determine format from content type
            format_map = {
                'image/jpeg': 'JPEG',
                'image/jpg': 'JPEG',
                'image/png': 'PNG',
                'image/gif': 'GIF',
                'image/bmp': 'BMP'
            }
            file_format = format_map.get(file.content_type, 'JPEG')
            
            return {
                "status": "success",
                "message": f"{data_type.title()} processed successfully",
                "data_type": data_type.upper(),
                "processed_image": {
                    "data": file_base64,
                    "format": file_format,
                    "file_size": len(file_content)
                },
                "original_filename": file.filename
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image processing failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Image processing failed: {str(e)}"
        )


# Helper functions
def _validate_and_enhance_application(
    db: Session, 
    application_in: ApplicationCreate, 
    person: Any
) -> ApplicationCreate:
    """Validate application data and set required flags based on business rules"""
    
    # For capture applications, skip most validation and requirements
    if application_in.application_type in [ApplicationType.DRIVERS_LICENSE_CAPTURE, ApplicationType.LEARNERS_PERMIT_CAPTURE]:
        # Validate that license_capture data is provided
        if not application_in.license_capture:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="License capture data is required for capture applications"
            )
        
        # Validate that captured licenses exist
        if not application_in.license_capture.captured_licenses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one captured license is required for capture applications"
            )
        
        # Validate that captured license categories are valid enum values
        valid_categories = [category.value for category in LicenseCategory]
        
        for captured_license in application_in.license_capture.captured_licenses:
            if captured_license.license_category not in valid_categories:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid license category '{captured_license.license_category}'. Valid categories are: {', '.join(valid_categories)}"
                )
        
        # Skip all validation requirements for capture applications:
        # - No age requirements checking
        # - No medical certificate requirements
        # - No parental consent requirements  
        # - No existing license prerequisites
        # - No minimum age validation
        # The person can capture any valid license category regardless of their current status
        application_in.medical_certificate_required = False
        application_in.parental_consent_required = False
        application_in.requires_existing_license = False
        
        return application_in
    
    # Regular validation for non-capture applications
    # Calculate age
    from dateutil.relativedelta import relativedelta
    age = relativedelta(datetime.now().date(), person.birth_date).years
    
    # Check age requirements for selected category
    min_age = _get_minimum_age_for_category(application_in.license_category)
    
    if age < min_age:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Applicant is {age} years old, minimum age for category {application_in.license_category.value} is {min_age}"
        )
    
    # Set parental consent requirement for A1 category applicants aged 16-17 (motorcycles)
    if application_in.license_category == LicenseCategory.A1 and 16 <= age < 18:
        application_in.parental_consent_required = True
    
    # Set medical certificate requirement for heavy categories or age 60+
    heavy_categories = [
        LicenseCategory.C1, LicenseCategory.C, LicenseCategory.C1E, LicenseCategory.CE,
        LicenseCategory.D1, LicenseCategory.D, LicenseCategory.D2
    ]
    if application_in.license_category in heavy_categories or age >= 60:
        application_in.medical_certificate_required = True
    
    # Set existing license requirement for heavy categories  
    if application_in.license_category in heavy_categories:
        application_in.requires_existing_license = True
    
    # Professional permit validation
    if application_in.application_type == ApplicationType.PROFESSIONAL_LICENSE:
        # Validate professional permit categories
        if not application_in.professional_permit_categories:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Professional permit categories are required for professional license applications"
            )
        
        # Validate age requirements for professional permit categories
        for category in application_in.professional_permit_categories:
            category_min_age = _get_minimum_age_for_professional_permit_category(category)
            if age < category_min_age:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Applicant is {age} years old, minimum age for professional permit category {category.value} is {category_min_age}"
                )
        
        # Set medical certificate requirement for all professional permits
        application_in.medical_certificate_required = True
    
    return application_in


def _get_minimum_age_for_category(category: LicenseCategory) -> int:
    """Get minimum age requirement for a license category"""
    age_requirements = {
        # Motorcycles
        LicenseCategory.A1: 16,
        LicenseCategory.A2: 18,
        LicenseCategory.A: 18,
        
        # Light Vehicles
        LicenseCategory.B1: 16,
        LicenseCategory.B: 18,
        LicenseCategory.B2: 21,
        LicenseCategory.BE: 18,
        
        # Heavy Goods Vehicles
        LicenseCategory.C1: 18,
        LicenseCategory.C: 21,
        LicenseCategory.C1E: 18,
        LicenseCategory.CE: 21,
        
        # Passenger Transport
        LicenseCategory.D1: 21,
        LicenseCategory.D: 24,
        LicenseCategory.D2: 24,
        
        # Learner's permits
        LicenseCategory.LEARNERS_1: 16,
        LicenseCategory.LEARNERS_2: 16,
        LicenseCategory.LEARNERS_3: 16,
    }
    return age_requirements.get(category, 18)  # Default to 18 if not found


def _get_minimum_age_for_professional_permit_category(category) -> int:
    """Get minimum age requirement for professional permit category"""
    from app.models.enums import ProfessionalPermitCategory
    age_requirements = {
        ProfessionalPermitCategory.G: 18,  # Goods (18 years minimum)
        ProfessionalPermitCategory.P: 21,  # Passengers (21 years minimum)
        ProfessionalPermitCategory.D: 25,  # Dangerous goods (25 years minimum)
    }
    return age_requirements.get(category, 18)


def _is_valid_status_transition(current_status: ApplicationStatus, new_status: ApplicationStatus, application: Application) -> bool:
    """Validate if status transition is allowed"""
    
    # Define valid status transitions for simplified workflow
    valid_transitions = {
        ApplicationStatus.DRAFT: [
            ApplicationStatus.SUBMITTED, ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.SUBMITTED: [
            ApplicationStatus.PAID, ApplicationStatus.REJECTED, ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.PAID: [
            ApplicationStatus.PASSED, ApplicationStatus.FAILED, ApplicationStatus.ABSENT,
            ApplicationStatus.APPROVED, ApplicationStatus.ON_HOLD, ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.PASSED: [
            ApplicationStatus.APPROVED, ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.FAILED: [],  # Terminal - requires new application
        ApplicationStatus.ABSENT: [],  # Terminal - requires new application
        ApplicationStatus.ON_HOLD: [
            ApplicationStatus.PAID, ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.APPROVED: [
            ApplicationStatus.SENT_TO_PRINTER, ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.SENT_TO_PRINTER: [
            ApplicationStatus.CARD_PRODUCTION, ApplicationStatus.APPROVED
        ],
        ApplicationStatus.CARD_PRODUCTION: [
            ApplicationStatus.READY_FOR_COLLECTION, ApplicationStatus.SENT_TO_PRINTER
        ],
        ApplicationStatus.READY_FOR_COLLECTION: [
            ApplicationStatus.COMPLETED
        ],
        ApplicationStatus.COMPLETED: [],  # No transitions from completed
        ApplicationStatus.REJECTED: [],  # No transitions from rejected
        ApplicationStatus.CANCELLED: []  # No transitions from cancelled
    }
    
    # Special handling for license capture applications
    if application.application_type in [ApplicationType.DRIVERS_LICENSE_CAPTURE, ApplicationType.LEARNERS_PERMIT_CAPTURE]:
        # Authorization workflow for capture applications: DRAFT → SUBMITTED → APPROVED → COMPLETED
        if current_status == ApplicationStatus.DRAFT:
            return new_status in [ApplicationStatus.SUBMITTED, ApplicationStatus.CANCELLED]
        elif current_status == ApplicationStatus.SUBMITTED:
            return new_status in [ApplicationStatus.APPROVED, ApplicationStatus.CANCELLED]
        elif current_status == ApplicationStatus.APPROVED:
            return new_status in [ApplicationStatus.COMPLETED, ApplicationStatus.CANCELLED]
        elif current_status == ApplicationStatus.COMPLETED:
            return False  # No transitions from completed
        elif current_status == ApplicationStatus.CANCELLED:
            return False  # No transitions from cancelled
        else:
            # Allow any other transitions to follow normal rules (fallback)
            pass
    
    allowed_statuses = valid_transitions.get(current_status, [])
    return new_status in allowed_statuses 


# ====================
# AUTHORIZATION ENDPOINTS
# ====================


@router.get("/{application_id}/authorization")
def get_application_authorization(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get authorization details for an application
    
    Requires: applications.read permission
    """
    if not current_user.has_permission("applications.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to read authorization details"
        )
    
    # Get application
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check location access
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this application"
        )
    
    # Get authorization if it exists
    authorization = db.query(ApplicationAuthorization).filter(
        ApplicationAuthorization.application_id == application_id
    ).first()
    
    return {
        "application": application,
        "authorization": authorization,
        "can_authorize": (
            current_user.has_permission("applications.authorize") or
            current_user.role_hierarchy == RoleHierarchy.EXAMINER
        )
    }


@router.post("/{application_id}/authorization")
def create_application_authorization(
    *,
    db: Session = Depends(get_db),
    application_id: uuid.UUID,
    authorization_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Create or update authorization for an application
    
    Requires: applications.authorize permission or EXAMINER role
    """
    # Check if user has authorization permissions
    if not (current_user.has_permission("applications.authorize") or 
            current_user.role_hierarchy == RoleHierarchy.EXAMINER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to authorize applications"
        )
    
    # Get application
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check if application is in correct status
    if application.status != ApplicationStatus.PASSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Application status must be PASSED, current status: {application.status}"
        )
    
    # Check location access
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this application"
        )
    
    # Check if authorization already exists
    existing_authorization = db.query(ApplicationAuthorization).filter(
        ApplicationAuthorization.application_id == application_id
    ).first()
    
    if existing_authorization:
        # Update existing authorization
        for key, value in authorization_data.items():
            if hasattr(existing_authorization, key):
                setattr(existing_authorization, key, value)
        authorization = existing_authorization
    else:
        # Create new authorization
        authorization = ApplicationAuthorization(
            application_id=application_id,
            examiner_id=current_user.id,
            **authorization_data
        )
        db.add(authorization)
    
    # Determine if application should be authorized based on test results
    test_passed = (
        not authorization.is_absent and
        not authorization.is_failed and
        authorization.eye_test_result == "PASS" and
        authorization.driving_test_result == "PASS"
    )
    
    # Update authorization status
    authorization.is_authorized = test_passed
    authorization.authorization_date = datetime.utcnow()
    
    # Apply restrictions based on test results
    if test_passed:
        authorization.applied_restrictions = authorization.get_restriction_codes()
    
    db.commit()
    db.refresh(authorization)
    
    # Update application status based on authorization result
    if test_passed:
        # Move to APPROVED status and generate license
        application.status = ApplicationStatus.APPROVED
        
        # Generate license automatically
        license = _generate_license_from_authorization(db, application, authorization)
        
        # Update authorization with generated license
        authorization.license_generated = True
        authorization.license_id = license.id
        authorization.license_generated_at = datetime.utcnow()
        
        # Add status history
        from app.models.application import ApplicationStatusHistory
        status_history = ApplicationStatusHistory(
            application_id=application_id,
            from_status=ApplicationStatus.PASSED,
            to_status=ApplicationStatus.APPROVED,
            changed_by=current_user.id,
            reason="Application authorized by examiner",
            notes=f"Authorized by {current_user.username}"
        )
        db.add(status_history)
        
    else:
        # Move back to appropriate test status based on failure reason
        if authorization.is_absent:
            application.status = ApplicationStatus.ABSENT
        elif authorization.eye_test_result == "FAIL":
            application.status = ApplicationStatus.REJECTED
        elif authorization.driving_test_result == "FAIL":
            application.status = ApplicationStatus.FAILED
        else:
            application.status = ApplicationStatus.FAILED
    
    db.commit()
    db.refresh(application)
    
    return {
        "application": application,
        "authorization": authorization,
        "message": "Authorization processed successfully"
    }


@router.put("/{application_id}/authorization/{authorization_id}")
def update_application_authorization(
    *,
    db: Session = Depends(get_db),
    application_id: uuid.UUID,
    authorization_id: uuid.UUID,
    authorization_data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Update existing authorization
    
    Requires: applications.authorize permission or EXAMINER role
    """
    # Check if user has authorization permissions
    if not (current_user.has_permission("applications.authorize") or 
            current_user.role_hierarchy == RoleHierarchy.EXAMINER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update authorization"
        )
    
    # Get authorization
    authorization = db.query(ApplicationAuthorization).filter(
        ApplicationAuthorization.id == authorization_id,
        ApplicationAuthorization.application_id == application_id
    ).first()
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authorization not found"
        )
    
    # Check location access
    if not current_user.can_access_location(authorization.application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this authorization"
        )
    
    # Update authorization
    for key, value in authorization_data.items():
        if hasattr(authorization, key):
            setattr(authorization, key, value)
    
    db.commit()
    db.refresh(authorization)
    
    return {
        "authorization": authorization,
        "message": "Authorization updated successfully"
    }


def _generate_license_from_authorization(db: Session, application: Application, authorization: ApplicationAuthorization):
    """
    Generate a license from an authorized application
    """
    from app.models.license import License, LicenseStatus
    from app.models.user import Location
    
    # Get location for license number generation
    location = db.query(Location).filter(Location.id == application.location_id).first()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {application.location_id} not found"
        )
    
    # Create license
    license = License(
        person_id=application.person_id,
        created_from_application_id=application.id,
        category=application.license_category,
        status=LicenseStatus.ACTIVE,
        issue_date=datetime.utcnow(),
        issuing_location_id=application.location_id,
        issued_by_user_id=authorization.examiner_id,
        restrictions=authorization.applied_restrictions or []
    )
    
    db.add(license)
    db.commit()
    db.refresh(license)
    
    return license


def _generate_license_from_application_status(db: Session, application: Application, current_user: User):
    """
    Generate a license from an application status update (when moving to APPROVED)
    Used for status-based license generation without authorization data
    """
    from app.models.license import License, LicenseStatus
    from app.models.user import Location
    
    # Get location for license number generation
    location = db.query(Location).filter(Location.id == application.location_id).first()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location {application.location_id} not found"
        )
    
    # Create license with minimal restrictions (can be updated later)
    license = License(
        person_id=application.person_id,
        created_from_application_id=application.id,
        category=application.license_category,
        status=LicenseStatus.ACTIVE,
        issue_date=datetime.utcnow(),
        issuing_location_id=application.location_id,
        issued_by_user_id=current_user.id,
        restrictions=[]  # Empty restrictions - can be updated via authorization later
    )
    
    db.add(license)
    db.commit()
    db.refresh(license)
    
    return license


 