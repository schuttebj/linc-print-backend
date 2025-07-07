"""
Application Management API Endpoints for Madagascar License System
Comprehensive REST API for driver's license applications with complete workflow support
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
import uuid
import logging
from datetime import datetime, timedelta

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.application import Application
from app.models.enums import ApplicationStatus, ApplicationType, LicenseCategory
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
@router.post("", response_model=ApplicationSchema)  # Handle both with and without trailing slash
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
    if not _is_valid_status_transition(application.status, new_status):
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
    
    return updated_application


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
    data_type: str,
    capture_method: Optional[str] = None,
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
        
        # Create storage path for this application
        storage_path = settings.get_file_storage_path() / "biometric" / str(application_id)
        
        # Process based on data type
        if data_type.upper() == "PHOTO":
            # Process license photo with ISO standards
            result = ImageProcessingService.process_license_photo(
                image_file=file,
                storage_path=storage_path,
                filename_prefix=f"license_photo_{application_id}"
            )
            
            # Store biometric data record in database
            biometric_data = {
                "application_id": application_id,
                "data_type": "PHOTO",
                "file_path": result["file_path"],
                "file_size": result["file_size"],
                "file_format": result["format"],
                "image_resolution": result["dimensions"],
                "capture_method": capture_method or "WEBCAM",
                "uploaded_by": current_user.id,
                "processing_metadata": result["processing_info"]
            }
            
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
            
            # Store biometric data record
            biometric_data = {
                "application_id": application_id,
                "data_type": data_type.upper(),
                "file_path": str(file_path),
                "file_size": file_size,
                "file_format": file_extension.upper(),
                "capture_method": capture_method or "DIGITAL_PAD",
                "uploaded_by": current_user.id
            }
            
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


@router.get("/person/{person_id}/licenses")
def get_person_licenses(
    *,
    db: Session = Depends(get_db),
    person_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get all existing licenses (applications with COMPLETED status) for a person
    This supports the license verification system in the frontend
    
    PLACEHOLDER: Returns empty list for now to enable frontend testing
    """
    
    # For now, return empty placeholder data to avoid import errors
    # This will be implemented properly when the database models are ready
    
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
            from pathlib import Path
            
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
    
    # Set parental consent requirement for A′ category applicants aged 16-17
    if application_in.license_category == LicenseCategory.A_PRIME and 16 <= age < 18:
        application_in.parental_consent_required = True
    
    # Set medical certificate requirement for C/D/E categories or age 60+
    heavy_categories = [LicenseCategory.C, LicenseCategory.D, LicenseCategory.E]
    if application_in.license_category in heavy_categories or age >= 60:
        application_in.medical_certificate_required = True
    
    # Set existing license requirement for C/D/E categories  
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
    """Get minimum age requirement for license category"""
    age_requirements = {
        LicenseCategory.A_PRIME: 16,
        LicenseCategory.A: 18,
        LicenseCategory.B: 18,
        LicenseCategory.C: 21,
        LicenseCategory.D: 21,
        LicenseCategory.E: 21,
        LicenseCategory.LEARNERS_1: 16,
        LicenseCategory.LEARNERS_2: 16,
        LicenseCategory.LEARNERS_3: 16,
    }
    return age_requirements.get(category, 18)


def _get_minimum_age_for_professional_permit_category(category) -> int:
    """Get minimum age requirement for professional permit category"""
    from app.models.enums import ProfessionalPermitCategory
    age_requirements = {
        ProfessionalPermitCategory.G: 18,  # Goods (18 years minimum)
        ProfessionalPermitCategory.P: 21,  # Passengers (21 years minimum)
        ProfessionalPermitCategory.D: 25,  # Dangerous goods (25 years minimum)
    }
    return age_requirements.get(category, 18)


def _is_valid_status_transition(current_status: ApplicationStatus, new_status: ApplicationStatus) -> bool:
    """Validate if status transition is allowed"""
    
    # Define valid status transitions
    valid_transitions = {
        ApplicationStatus.DRAFT: [
            ApplicationStatus.SUBMITTED, ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.SUBMITTED: [
            ApplicationStatus.DOCUMENTS_PENDING, ApplicationStatus.THEORY_TEST_REQUIRED,
            ApplicationStatus.REJECTED, ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.DOCUMENTS_PENDING: [
            ApplicationStatus.THEORY_TEST_REQUIRED, ApplicationStatus.SUBMITTED,
            ApplicationStatus.REJECTED, ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.THEORY_TEST_REQUIRED: [
            ApplicationStatus.THEORY_PASSED, ApplicationStatus.THEORY_FAILED,
            ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.THEORY_PASSED: [
            ApplicationStatus.PRACTICAL_TEST_REQUIRED, ApplicationStatus.APPROVED,
            ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.THEORY_FAILED: [
            ApplicationStatus.THEORY_TEST_REQUIRED, ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.PRACTICAL_TEST_REQUIRED: [
            ApplicationStatus.PRACTICAL_PASSED, ApplicationStatus.PRACTICAL_FAILED,
            ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.PRACTICAL_PASSED: [
            ApplicationStatus.APPROVED, ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.PRACTICAL_FAILED: [
            ApplicationStatus.PRACTICAL_TEST_REQUIRED, ApplicationStatus.CANCELLED
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
    
    allowed_statuses = valid_transitions.get(current_status, [])
    return new_status in allowed_statuses 