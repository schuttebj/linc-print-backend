"""
Application Management API Endpoints for Madagascar License System
Comprehensive REST API for driver's license applications with complete workflow support
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, and_, or_, func
from pathlib import Path
import uuid
import logging
from datetime import datetime, timedelta
from decimal import Decimal
import tempfile
import os
import io
from PIL import Image

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.application import Application, ApplicationAuthorization, ApplicationBiometricData
from app.models.enums import ApplicationStatus, ApplicationType, LicenseCategory, RoleHierarchy, TestResult
from app.schemas.application import (
    Application as ApplicationSchema,
    ApplicationCreate,
    ApplicationUpdate, 
    ApplicationSearch,
    ApplicationWithDetails,


    ApplicationStatistics,
    ApplicationBiometricDataCreate
)
from app.crud.crud_application import (
    crud_application,
    crud_application_biometric_data,
    crud_application_test_attempt,
    crud_application_document
)
from app.crud.crud_license import crud_license
from app.services.image_service import ImageProcessingService
from app.core.config import get_settings
from app.core.audit_decorators import audit_create, audit_update, audit_delete, get_application_by_id

logger = logging.getLogger(__name__)
router = APIRouter()


def get_current_user_for_files(request: Request, db: Session = Depends(get_db)) -> User:
    """
    Manual authentication for file serving that handles both Authorization headers and cookies.
    Browsers don't send Authorization headers with <img> tags, so we need to check cookies too.
    """
    from app.core.security import verify_token
    from app.crud.crud_user import user as crud_user
    
    logger.info(f"=== FILE AUTH DEBUG ===")
    logger.info(f"Request URL: {request.url}")
    logger.info(f"Request headers: {dict(request.headers)}")
    logger.info(f"Request cookies: {dict(request.cookies)}")
    
    # Try Authorization header first (for API calls)
    authorization = request.headers.get("authorization")
    logger.info(f"Authorization header: {authorization}")
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]  # Remove "Bearer " prefix
        try:
            payload = verify_token(token)
            user_id = payload.get("sub")  # JWT standard uses "sub" for subject (user ID)
            logger.info(f"Extracted user_id from header: {user_id}")
            if user_id:
                user = crud_user.get(db=db, id=uuid.UUID(user_id))
                if user:
                    logger.info(f"✅ Authenticated user {user.username} via Authorization header")
                    return user
        except Exception as e:
            logger.info(f"❌ Authorization header authentication failed: {e}")
    
    # Try refresh_token cookie (which browsers send automatically)
    refresh_token = request.cookies.get("refresh_token")
    logger.info(f"refresh_token cookie: {refresh_token}")
    if refresh_token:
        try:
            payload = verify_token(refresh_token)
            logger.info(f"Token payload: {payload}")
            user_id = payload.get("sub")  # JWT standard uses "sub" for subject (user ID)
            logger.info(f"Extracted user_id: {user_id}")
            if user_id:
                user = crud_user.get(db=db, id=uuid.UUID(user_id))
                if user:
                    logger.info(f"✅ Authenticated user {user.username} via refresh_token cookie")
                    return user
        except Exception as e:
            logger.info(f"❌ Cookie authentication failed: {e}")
    
    # No valid authentication found
    logger.warning(f"❌ File request failed authentication - no valid token found")
    logger.warning(f"Available cookies: {list(request.cookies.keys())}")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required for file access"
    )


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
@audit_create(resource_type="APPLICATION", screen_reference="ApplicationForm")
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
            from app.crud.crud_location import location as crud_location
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


@router.get("/pending-approval", response_model=List[ApplicationSchema])
def get_applications_pending_approval(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    location_id: Optional[uuid.UUID] = None
) -> List[ApplicationSchema]:
    """
    Get NEW_LICENSE and LEARNERS_PERMIT applications in PAID status that need approval
    
    Requires: applications.authorize permission or EXAMINER role
    """
    # Check if user has authorization permissions
    if not (current_user.has_permission("applications.authorize") or 
            current_user.role_hierarchy == RoleHierarchy.EXAMINER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view applications pending approval"
        )
    
    # Apply location filtering for location users
    if current_user.user_type.value == "LOCATION_USER":
        location_id = current_user.primary_location_id
    
    # Get applications that need approval (NEW_LICENSE and LEARNERS_PERMIT in PAID status)
    query = db.query(Application).filter(
        Application.status == ApplicationStatus.PAID,
        Application.application_type.in_([ApplicationType.NEW_LICENSE, ApplicationType.LEARNERS_PERMIT]),
        Application.approval_outcome.is_(None)  # Not yet approved/failed/absent
    )
    
    # Apply location filtering if specified
    if location_id:
        query = query.filter(Application.location_id == location_id)
    
    # Apply pagination
    applications = query.offset(skip).limit(limit).all()
    
    return [ApplicationSchema.from_orm(app) for app in applications]


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
    
    # Build detailed response with related data - use json serialization to avoid SQLAlchemy objects
    try:
        application_dict = ApplicationSchema.from_orm(application).dict()
    except Exception as e:
        logger.warning(f"Failed to serialize application with from_orm: {e}")
        # Fallback to manual serialization
        application_dict = {
            "id": str(application.id),
            "application_number": application.application_number,
            "application_type": application.application_type.value,
            "status": application.status.value,
            "person_id": str(application.person_id) if application.person_id else None,
            "location_id": str(application.location_id) if application.location_id else None,
            "created_at": application.created_at.isoformat() if application.created_at else None,
            "updated_at": application.updated_at.isoformat() if application.updated_at else None,
            # Add other required fields as needed
        }
    
    # Add related data - convert model instances to dictionaries for proper serialization
    biometric_data = crud_application_biometric_data.get_by_application(
        db=db, application_id=application_id
    )
    
    def safe_serialize_metadata(metadata):
        """Safely serialize metadata, filtering out SQLAlchemy objects"""
        if metadata is None:
            return None
            
        # Handle SQLAlchemy MetaData objects specifically - this is the main issue
        if str(type(metadata)) == "<class 'sqlalchemy.sql.schema.MetaData'>":
            logger.warning(f"Found SQLAlchemy MetaData object instead of JSON data - database issue!")
            return None
            
        if isinstance(metadata, dict):
            return metadata  # Return dict as-is if it's already a proper dict
                
        logger.warning(f"Unexpected metadata type {type(metadata)}: {metadata}")
        return str(metadata)
    
    # Serialize biometric data with file URLs and organized structure
    biometric_data_list = []
    organized_biometric_data = {}
    
    for bd in biometric_data:
        # Generate file URL for serving
        file_url = f"/api/v1/applications/files/{bd.file_path.replace('/var/madagascar-license-data/', '')}" if bd.file_path else None
        
        biometric_item = {
            "id": str(bd.id),
            "application_id": str(bd.application_id),
            "data_type": bd.data_type.value,
            "file_path": bd.file_path,
            "file_url": file_url,
            "metadata": safe_serialize_metadata(bd.capture_metadata),  # FIX: Use capture_metadata field
            "created_at": bd.created_at.isoformat() if bd.created_at else None,
            "updated_at": bd.updated_at.isoformat() if bd.updated_at else None
        }
        
        biometric_data_list.append(biometric_item)
        
        # Organize by type for frontend convenience
        data_type_lower = bd.data_type.value.lower()
        if data_type_lower not in organized_biometric_data:
            organized_biometric_data[data_type_lower] = biometric_item
        else:
            # Handle multiple records of same type (keep most recent)
            if bd.created_at and organized_biometric_data[data_type_lower].get("created_at"):
                if bd.created_at.isoformat() > organized_biometric_data[data_type_lower]["created_at"]:
                    organized_biometric_data[data_type_lower] = biometric_item
    
    application_dict["biometric_data"] = biometric_data_list
    application_dict["organized_biometric_data"] = organized_biometric_data
    
    # Fees are now handled by the transactions module
    application_dict["fees"] = []
    
    test_attempts = crud_application_test_attempt.get_by_application(
        db=db, application_id=application_id
    )
    application_dict["test_attempts"] = [
        {
            "id": str(ta.id),
            "application_id": str(ta.application_id),
            "test_type": ta.test_type.value,
            "test_result": ta.test_result.value if ta.test_result else None,
            "score": ta.score,
            "test_date": ta.test_date.isoformat() if ta.test_date else None,
            "notes": ta.notes,
            "created_at": ta.created_at.isoformat() if ta.created_at else None,
            "updated_at": ta.updated_at.isoformat() if ta.updated_at else None
        }
        for ta in test_attempts
    ] if test_attempts else []
    
    documents = crud_application_document.get_by_application(
        db=db, application_id=application_id
    )
    application_dict["documents"] = [
        {
            "id": str(doc.id),
            "application_id": str(doc.application_id),
            "document_type": doc.document_type,
            "file_path": doc.file_path,
            "original_filename": doc.original_filename,
            "file_size": doc.file_size,
            "metadata": safe_serialize_metadata(doc.metadata),
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None
        }
        for doc in documents
    ] if documents else []
    
    child_applications = crud_application.get_associated_applications(
        db=db, parent_application_id=application_id
    )
    application_dict["child_applications"] = [
        {
            "id": str(ca.id),
            "application_number": ca.application_number,
            "application_type": ca.application_type.value,
            "status": ca.status.value,
            "created_at": ca.created_at.isoformat() if ca.created_at else None
        }
        for ca in child_applications
    ] if child_applications else []
    
    try:
        return ApplicationWithDetails(**application_dict)
    except Exception as e:
        logger.error(f"Failed to create ApplicationWithDetails: {e}")
        logger.error(f"Application dict keys: {list(application_dict.keys())}")
        # For debugging, log problematic fields
        for key, value in application_dict.items():
            try:
                # Try to serialize each field individually
                import json
                json.dumps(value, default=str)
            except Exception as field_error:
                logger.error(f"Field '{key}' serialization error: {field_error}, value type: {type(value)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to serialize application details: {str(e)}"
        )


@router.put("/{application_id}", response_model=ApplicationSchema)
@audit_update(
    resource_type="APPLICATION", 
    screen_reference="ApplicationForm",
    get_old_data=get_application_by_id
)
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
@audit_update(
    resource_type="APPLICATION", 
    screen_reference="ApplicationStatusForm",
    get_old_data=get_application_by_id
)
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
    if application.status not in [ApplicationStatus.SUBMITTED, ApplicationStatus.PASSED, ApplicationStatus.CARD_PAYMENT_PENDING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Application cannot be approved from status {application.status}"
        )
    
    # Handle different approval scenarios based on application type and current status
    if application.application_type == ApplicationType.NEW_LICENSE:
        if application.status == ApplicationStatus.SUBMITTED:
            # First approval: Mark as passed, require card payment, and CREATE LICENSE
            application.test_result = TestResult.PASSED
            application.status = ApplicationStatus.CARD_PAYMENT_PENDING
            
            updated_application = crud_application.update_status(
                db=db,
                application_id=application_id,
                new_status=ApplicationStatus.CARD_PAYMENT_PENDING,
                changed_by=current_user.id,
                reason=reason or "Test passed, awaiting card payment",
                notes=notes
            )
            
            # CREATE LICENSE AT APPROVAL TIME
            license = _generate_license_from_application(db, updated_application, {})
            
            return {
                "application": updated_application,
                "license": license,
                "message": "Test passed! License created. Card payment (38,000 MGA) required for card ordering",
                "next_step": "card_payment_required",
                "card_payment_amount": "38,000 MGA"
            }
            
        elif application.status == ApplicationStatus.CARD_PAYMENT_PENDING:
            # Second approval: Just update status (license already exists)
            if not application.card_payment_completed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Card payment must be completed before final approval"
                )
            
            # Update to APPROVED status
            updated_application = crud_application.update_status(
                db=db,
                application_id=application_id,
                new_status=ApplicationStatus.APPROVED,
                changed_by=current_user.id,
                reason=reason or "Application approved after card payment",
                notes=notes
            )
            
            # License already exists from first approval - just find it
            from app.models.license import License
            license = db.query(License).filter(License.created_from_application_id == application_id).first()
            
            return {
                "application": updated_application,
                "license": license,
                "message": "Application approved successfully - license already exists"
            }
    else:
        # Other application types: Single-step approval to APPROVED with license generation
        updated_application = crud_application.update_status(
            db=db,
            application_id=application_id,
            new_status=ApplicationStatus.APPROVED,
            changed_by=current_user.id,
            reason=reason or "Application approved by examiner",
            notes=notes
        )
        
        # Generate license immediately for non-NEW_LICENSE applications
        license = None
        try:
            license = _generate_license_from_application(db, updated_application, {})
            logger.info(f"Generated license {license.id} for application {application_id}")
        except Exception as e:
            logger.error(f"Failed to generate license for application {application_id}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Application approved but license generation failed"
            )
        
        return {
            "application": updated_application,
            "license": license,
            "message": "Application approved successfully and license generated"
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
    document_type: str = Form(...),
    document_name: Optional[str] = Form(None),
    document_number: Optional[str] = Form(None),
    issue_date: Optional[str] = Form(None),
    expiry_date: Optional[str] = Form(None),
    issuing_authority: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """
    Upload document for application (medical certificate, police clearance, parental consent, etc.)
    
    Requires: applications.update permission
    """
    import os
    import mimetypes
    from pathlib import Path
    from app.core.config import get_settings
    from app.crud.crud_application import crud_application_document
    from app.schemas.application import ApplicationDocumentCreate
    
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
    
    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )
    
    # Check file size (10MB limit)
    file_content = await file.read()
    file_size = len(file_content)
    max_size = 10 * 1024 * 1024  # 10MB
    
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {max_size / 1024 / 1024}MB"
        )
    
    # Validate file type (images and PDFs only)
    allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    file_extension = Path(file.filename).suffix.lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Get MIME type
    mime_type, _ = mimetypes.guess_type(file.filename)
    if not mime_type:
        # Fallback MIME types
        mime_type_map = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.bmp': 'image/bmp',
            '.tiff': 'image/tiff'
        }
        mime_type = mime_type_map.get(file_extension, 'application/octet-stream')
    
    try:
        # Get storage settings
        settings = get_settings()
        storage_base_path = settings.get_file_storage_path()
        
        # Create application documents directory: {storage_base}/applications/{application_id}/documents/
        app_documents_dir = storage_base_path / "applications" / str(application_id) / "documents"
        app_documents_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename to prevent conflicts
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{document_type}_{timestamp}_{uuid.uuid4().hex[:8]}{file_extension}"
        file_path = app_documents_dir / safe_filename
        
        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Parse dates if provided
        parsed_issue_date = None
        parsed_expiry_date = None
        
        if issue_date:
            try:
                parsed_issue_date = datetime.strptime(issue_date, "%Y-%m-%d")
            except ValueError:
                pass  # Invalid date format, ignore
                
        if expiry_date:
            try:
                parsed_expiry_date = datetime.strptime(expiry_date, "%Y-%m-%d")
            except ValueError:
                pass  # Invalid date format, ignore
        
        # Create database record
        document_create = ApplicationDocumentCreate(
            application_id=application_id,
            document_type=document_type,
            document_name=document_name or file.filename,
            file_path=str(file_path),
            original_filename=file.filename,
            file_size=file_size,
            file_format=file_extension[1:],  # Remove the dot
            mime_type=mime_type,
            document_number=document_number,
            issue_date=parsed_issue_date,
            expiry_date=parsed_expiry_date,
            issuing_authority=issuing_authority,
            uploaded_by=current_user.id
        )
        
        # Save to database using CRUD
        document_record = crud_application_document.create(db=db, obj_in=document_create)
        
        return {
            "status": "success",
            "message": "Document uploaded successfully",
            "document_id": str(document_record.id),
            "file_name": file.filename,
            "file_size": file_size,
            "document_type": document_type,
            "file_path": str(file_path),
            "uploaded_at": document_record.created_at.isoformat()
        }
        
    except Exception as e:
        # Clean up file if database save failed
        if 'file_path' in locals() and file_path.exists():
            try:
                file_path.unlink()
            except:
                pass
        
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )


@router.get("/{application_id}/documents")
def get_application_documents(
    *,
    db: Session = Depends(get_db),
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Get all documents for an application
    
    Requires: applications.read permission
    """
    if not current_user.has_permission("applications.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view application documents"
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
            detail="Not authorized to view documents for this application"
        )
    
    # Get documents using CRUD
    documents = crud_application_document.get_by_application(db=db, application_id=application_id)
    
    return {
        "application_id": str(application_id),
        "documents": [
            {
                "id": str(doc.id),
                "document_type": doc.document_type,
                "document_name": doc.document_name,
                "original_filename": doc.original_filename,
                "file_size": doc.file_size,
                "file_format": doc.file_format,
                "mime_type": doc.mime_type,
                "document_number": doc.document_number,
                "issue_date": doc.issue_date.isoformat() if doc.issue_date else None,
                "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
                "issuing_authority": doc.issuing_authority,
                "is_verified": doc.is_verified,
                "verification_status": doc.verification_status,
                "uploaded_at": doc.uploaded_at.isoformat(),
                "uploaded_by": str(doc.uploaded_by)
            }
            for doc in documents
        ]
    }


@router.get("/{application_id}/documents/{document_id}/download")
def download_application_document(
    *,
    db: Session = Depends(get_db),
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """
    Download an application document
    
    Requires: applications.read permission
    """
    if not current_user.has_permission("applications.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to download application documents"
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
            detail="Not authorized to download documents for this application"
        )
    
    # Get the specific document
    document = crud_application_document.get(db=db, id=document_id)
    if not document or document.application_id != application_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    # Check if file exists on disk
    file_path = Path(document.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found on disk"
        )
    
    # Return file response
    return FileResponse(
        path=str(file_path),
        filename=document.original_filename,
        media_type=document.mime_type
    )


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
            
            # Store biometric data record in database with both file versions
            # Use explicit JSON serialization to avoid SQLAlchemy MetaData conflicts
            import json
            
            metadata_dict = {
                "processing_info": result["processing_info"],
                "standard_version": {
                    "file_path": str(result["standard_version"]["file_path"]),
                    "filename": result["standard_version"]["filename"],
                    "file_size": result["standard_version"]["file_size"],
                    "dimensions": result["standard_version"]["dimensions"]
                },
                "license_ready_version": {
                    "file_path": str(result["license_ready_version"]["file_path"]),
                    "filename": result["license_ready_version"]["filename"],
                    "file_size": result["license_ready_version"]["file_size"],
                    "dimensions": result["license_ready_version"]["dimensions"]
                }
            }
            
            # Ensure it's properly serializable as JSON
            try:
                metadata_json_str = json.dumps(metadata_dict)
                metadata_clean = json.loads(metadata_json_str)
                logger.info(f"=== BIOMETRIC METADATA DEBUG ===")
                logger.info(f"JSON serialization SUCCESS")
                logger.info(f"Original metadata dict type: {type(metadata_dict)}")
                logger.info(f"JSON-serialized metadata type: {type(metadata_clean)}")
                logger.info(f"Metadata keys: {list(metadata_clean.keys())}")
            except Exception as json_error:
                logger.error(f"JSON serialization FAILED: {json_error}")
                logger.error(f"Original metadata dict: {metadata_dict}")
                # Fallback to None if JSON serialization fails
                metadata_clean = None
            
            logger.info(f"About to create ApplicationBiometricDataCreate with metadata type: {type(metadata_clean)}")
            logger.info(f"Metadata value being passed: {metadata_clean}")
            
            biometric_data_create = ApplicationBiometricDataCreate(
                application_id=application_id,
                data_type="PHOTO",
                file_path=str(result["standard_version"]["file_path"]),  # Primary path for standard version
                file_name=result["standard_version"]["filename"],
                file_size=result["standard_version"]["file_size"],
                file_format=result["standard_version"]["format"],
                capture_device=capture_method or "WEBCAM",
                capture_software="ImageService",
                capture_metadata=metadata_clean,  # Use the JSON-cleaned version
                captured_by=current_user.id,
                is_processed=True
            )
            
            create_dict = biometric_data_create.dict()
            logger.info(f"ApplicationBiometricDataCreate.dict() result:")
            logger.info(f"  - capture_metadata type: {type(create_dict.get('capture_metadata'))}")
            logger.info(f"  - capture_metadata value: {create_dict.get('capture_metadata')}")
            
            # Save to database
            biometric_record = crud_application_biometric_data.create_biometric_data(
                db=db,
                obj_in=biometric_data_create,
                created_by_user_id=current_user.id
            )
            
            # Debug what was actually saved
            logger.info(f"=== POST-SAVE DEBUG ===")
            logger.info(f"Saved biometric record ID: {biometric_record.id}")
            logger.info(f"Saved metadata type: {type(biometric_record.capture_metadata)}")
            logger.info(f"Saved metadata value: {biometric_record.capture_metadata}")
            logger.info(f"Saved metadata repr: {repr(biometric_record.capture_metadata)}")
            
            # Test immediate retrieval
            fresh_record = crud_application_biometric_data.get(db=db, id=biometric_record.id)
            if fresh_record:
                logger.info(f"Fresh retrieval metadata type: {type(fresh_record.capture_metadata)}")
                logger.info(f"Fresh retrieval metadata value: {fresh_record.capture_metadata}")
                logger.info(f"Fresh retrieval metadata repr: {repr(fresh_record.capture_metadata)}")
            
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
                file_name=filename,
                file_size=file_size,
                file_format=file_extension.upper(),
                capture_device=capture_method or "DIGITAL_PAD",
                capture_software="FileUpload",
                captured_by=current_user.id,
                is_processed=True
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
    Returns complete biometric information including:
    - File paths and metadata for photo, signature, and fingerprint
    - Direct file URLs for frontend consumption
    - License-ready version info for photos (8-bit, compressed for card production)
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
            # Base biometric data
            biometric_item = {
                "id": str(item.id),
                "file_path": item.file_path,
                "file_name": item.file_name,
                "file_size": item.file_size,
                "file_format": item.file_format,
                "capture_device": item.capture_device,
                "capture_software": item.capture_software,
                "quality_score": float(item.quality_score) if item.quality_score else None,
                "quality_metrics": item.quality_metrics,
                "is_processed": item.is_processed,
                "is_verified": item.is_verified,
                "capture_metadata": item.capture_metadata,
                "processing_notes": item.processing_notes,
                "created_at": item.created_at.isoformat(),
                "captured_by": str(item.captured_by) if item.captured_by else None,
                "verified_by": str(item.verified_by) if item.verified_by else None,
                "verified_at": item.verified_at.isoformat() if item.verified_at else None
            }
            
            # Add file URLs for frontend consumption
            if item.file_path:
                # Extract relative path for API file serving
                file_path_str = str(item.file_path)
                if '/biometric/' in file_path_str:
                    relative_path = file_path_str[file_path_str.index('biometric/'):]
                    biometric_item["file_url"] = f"/api/v1/applications/files/{relative_path}"
                else:
                    biometric_item["file_url"] = f"/api/v1/applications/files/{item.file_path}"
            
            # For photos, add license-ready version info and URL
            if data_type == "photo" and item.capture_metadata:
                metadata = item.capture_metadata
                license_ready_info = metadata.get("license_ready_version")
                
                if license_ready_info:
                    biometric_item["license_ready"] = {
                        "file_path": license_ready_info.get("file_path"),
                        "filename": license_ready_info.get("filename"),
                        "file_size": license_ready_info.get("file_size"),
                        "dimensions": license_ready_info.get("dimensions"),
                        "file_url": f"/api/v1/applications/{application_id}/biometric-data/PHOTO/license-ready"
                    }
                else:
                    biometric_item["license_ready"] = None
            
            organized_data[data_type] = biometric_item
    
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
            ApplicationStatus.CARD_PAYMENT_PENDING, ApplicationStatus.APPROVED, ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.FAILED: [],  # Terminal - requires new application
        ApplicationStatus.ABSENT: [],  # Terminal - requires new application
        ApplicationStatus.ON_HOLD: [
            ApplicationStatus.PAID, ApplicationStatus.CANCELLED
        ],
        ApplicationStatus.CARD_PAYMENT_PENDING: [
            ApplicationStatus.APPROVED, ApplicationStatus.CANCELLED
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
        # Set test result first
        application.test_result = TestResult.PASSED
        
        # Follow staged payment workflow for NEW_LICENSE applications
        if application.application_type == ApplicationType.NEW_LICENSE:
            # NEW_LICENSE: Move to CARD_PAYMENT_PENDING to require card payment
            application.status = ApplicationStatus.CARD_PAYMENT_PENDING
            
            # CREATE LICENSE AT APPROVAL TIME (not payment time)
            license = _generate_license_from_application(db, application, final_restrictions)
            
            db.commit()
            
            return {
                "success": True,
                "message": "Test passed! License created. Card payment (38,000 MGA) required for card ordering",
                "application_status": application.status.value,
                "test_result": application.test_result.value,
                "license_id": str(license.id),
                "next_step": "card_payment_required",
                "card_payment_amount": "38,000 MGA",
                "applied_restrictions": final_restrictions
            }
        else:
            # Other application types: Go directly to APPROVED and generate license
            application.status = ApplicationStatus.APPROVED
            
            # Auto-generate license
            license = _generate_license_from_application(db, application, final_restrictions)
            
            # Update authorization with generated license
            authorization.license_generated = True
            authorization.license_id = license.id
            authorization.license_generated_at = datetime.utcnow()
            
            # Add status history
            from app.models.application import ApplicationStatusHistory
            status_history = ApplicationStatusHistory(
                application_id=application_id,
                previous_status=ApplicationStatus.PAID,
                new_status=ApplicationStatus.APPROVED,
                changed_by=current_user.id,
                change_reason="Application authorized by examiner",
                change_notes=f"Authorized by {current_user.username}"
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
    
    # Create license
    license = License(
        person_id=application.person_id,
        created_from_application_id=application.id,
        category=application.license_category,
        status=LicenseStatus.ACTIVE,
        issue_date=application.approval_date,
        issuing_location_id=application.approved_at_location_id,
        issued_by_user_id=application.approved_by_user_id,
        restrictions=authorization.applied_restrictions or [],
        medical_restrictions=[],  # Can be populated from medical_information if needed
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


@router.get("/files/{file_path:path}")
def serve_biometric_file(
    file_path: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Serve biometric files (photos, signatures, fingerprints)
    
    Requires: applications.read permission
    """
    from fastapi.responses import FileResponse
    from fastapi import HTTPException
    import os
    from app.core.config import get_settings
    
    # Use manual authentication that handles both Authorization headers and cookies
    current_user = get_current_user_for_files(request, db)
    
    logger.info(f"=== FILE SERVING DEBUG ===")
    logger.info(f"File request: {file_path} by user: {current_user.username}")
    logger.info(f"User type: {current_user.user_type}")
    logger.info(f"Has applications.read: {current_user.has_permission('applications.read')}")
    
    if not current_user.has_permission("applications.read"):
        logger.error(f"User {current_user.username} lacks applications.read permission")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access files"
        )
    
    settings = get_settings()
    
    # Get the base storage path
    if hasattr(settings, 'FILE_STORAGE_PATH'):
        base_path = Path(settings.FILE_STORAGE_PATH)
    else:
        base_path = Path(settings.FILE_STORAGE_BASE_PATH)
    
    # Handle both absolute and relative file paths
    file_path_obj = Path(file_path)
    if file_path_obj.is_absolute():
        # If file_path is already absolute, use it directly
        full_file_path = file_path_obj
    else:
        # If relative, append to base path
        full_file_path = base_path / file_path
    
    logger.info(f"Path resolution: {file_path} -> {full_file_path}")
    logger.info(f"Base path: {base_path}")
    
    # Security check - ensure file is within the storage directory
    try:
        full_file_path = full_file_path.resolve()
        base_path = base_path.resolve()
        logger.info(f"Resolved paths - File: {full_file_path}, Base: {base_path}")
        logger.info(f"Path security check: {str(full_file_path).startswith(str(base_path))}")
        
        if not str(full_file_path).startswith(str(base_path)):
            logger.error(f"SECURITY VIOLATION: File path {full_file_path} not within base {base_path}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Invalid file path"
            )
    except Exception as path_error:
        logger.error(f"Path resolution error: {path_error}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Invalid file path"
        )
    
    # File existence already checked above
    
    # Location-based access control for biometric files
    path_parts = Path(file_path).parts
    if len(path_parts) >= 5 and path_parts[0] == 'biometric':
        try:
            # Extract application ID from path for security check
            potential_app_id = path_parts[4]
            application_id = uuid.UUID(potential_app_id)
            logger.info(f"Serving biometric file for application: {application_id}")
            
            # Verify user can access this application's location
            application = crud_application.get(db=db, id=application_id)
            if not application:
                logger.error(f"Application {application_id} not found for file access")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Application not found"
                )
            
            if not current_user.can_access_location(application.location_id):
                logger.error(f"User {current_user.username} cannot access location {application.location_id} for application {application_id}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to access files for this application"
                )
            
            logger.info(f"Location access verified for user {current_user.username} on application {application_id}")
            
        except ValueError as e:
            logger.error(f"Invalid application ID in file path: {file_path}, error: {e}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid file path"
            )
        except IndexError as e:
            logger.error(f"Invalid file path format: {file_path}, error: {e}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid file path format"
            )
    
    logger.info(f"Serving file: {full_file_path} (exists: {full_file_path.exists()})")
    
    # Determine content type
    content_type = "application/octet-stream"
    if file_path.lower().endswith(('.jpg', '.jpeg')):
        content_type = "image/jpeg"
    elif file_path.lower().endswith('.png'):
        content_type = "image/png"
    elif file_path.lower().endswith('.pdf'):
        content_type = "application/pdf"
    
    return FileResponse(
        path=full_file_path,
        media_type=content_type,
        filename=full_file_path.name
    )


@router.post("/cleanup-biometric-metadata", summary="[TEMPORARY] Clean up corrupted biometric metadata")
def cleanup_biometric_metadata(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    TEMPORARY EMERGENCY CLEANUP: Fix corrupted SQLAlchemy MetaData objects in biometric records
    
    ⚠️ ONE-TIME USE ONLY ⚠️
    This endpoint fixes a specific bug where SQLAlchemy MetaData objects were stored 
    instead of JSON metadata. Run once, then remove this endpoint.
    
    Future uploads will store proper JSON metadata automatically.
    """
    if not current_user.has_permission("applications.update"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to clean up metadata"
        )
    
    # Get all biometric data records with corrupted metadata
    biometric_records = db.query(ApplicationBiometricData).all()
    
    cleaned_count = 0
    for record in biometric_records:
        # Check if metadata is corrupted (SQLAlchemy MetaData object)
        if str(type(record.capture_metadata)) == "<class 'sqlalchemy.sql.schema.MetaData'>":
            logger.info(f"Cleaning corrupted metadata for biometric record {record.id}")
            
            # Set metadata to None for now - new uploads will have proper metadata
            record.capture_metadata = None
            cleaned_count += 1
    
    db.commit()
    
    logger.info(f"Cleaned up {cleaned_count} corrupted biometric metadata records")
    
    return {
        "message": f"Successfully cleaned up {cleaned_count} corrupted biometric metadata records",
        "cleaned_count": cleaned_count
    }


@router.get("/test-file-auth", summary="[TEST] Test file authentication")
def test_file_authentication(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Test endpoint to verify file authentication works with both Authorization headers and cookies
    """
    try:
        current_user = get_current_user_for_files(request, db)
        return {
            "status": "success",
            "message": "Authentication successful",
            "user": {
                "username": current_user.username,
                "email": current_user.email,
                "has_applications_read": current_user.has_permission("applications.read")
            },
            "auth_method": "header" if request.headers.get("authorization") else "cookie"
        }
    except HTTPException as e:
        return {
            "status": "failed",
            "message": str(e.detail),
            "error_code": e.status_code
        }


@router.get("/{application_id}/biometric-data/{data_type}/license-ready")
def get_license_ready_biometric(
    application_id: uuid.UUID,
    data_type: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get license-ready version of biometric data for card production
    
    Returns the optimized, small-size version suitable for license cards
    Specifically for PHOTO data type (8-bit, 64-128px height, ~1.5KB)
    
    Requires: applications.read permission
    """
    from fastapi.responses import FileResponse
    
    # Use manual authentication that handles both Authorization headers and cookies
    current_user = get_current_user_for_files(request, db)
    
    logger.info(f"=== LICENSE-READY FILE DEBUG ===")
    logger.info(f"Request for {data_type} license-ready file for application {application_id} by user: {current_user.username}")
    
    if not current_user.has_permission("applications.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access biometric data"
        )
    
    # Validate data type
    if data_type.upper() not in ["PHOTO", "SIGNATURE", "FINGERPRINT"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid data_type. Must be PHOTO, SIGNATURE, or FINGERPRINT"
        )
    
    # Get application and check permissions
    application = crud_application.get(db=db, id=application_id)
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    if not current_user.can_access_location(application.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this application's biometric data"
        )
    
    # Get biometric data record
    biometric_data = crud_application_biometric_data.get_by_application_and_type(
        db=db, application_id=application_id, data_type=data_type.upper()
    )
    
    if not biometric_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {data_type.lower()} data found for this application"
        )
    
    # Get license-ready file path from metadata
    metadata = biometric_data.capture_metadata or {}
    logger.info(f"Biometric metadata type: {type(metadata)}")
    logger.info(f"Biometric metadata: {metadata}")
    
    license_ready_info = metadata.get("license_ready_version")
    logger.info(f"License ready info: {license_ready_info}")
    
    if not license_ready_info or not license_ready_info.get("file_path"):
        logger.error(f"No license-ready version found in metadata for {data_type.lower()}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No license-ready version available for {data_type.lower()}"
        )
    
    license_ready_path = Path(license_ready_info["file_path"])
    logger.info(f"License ready file path: {license_ready_path}")
    
    # Check if file exists
    logger.info(f"File exists: {license_ready_path.exists()}")
    logger.info(f"Is file: {license_ready_path.is_file()}")
    
    if not license_ready_path.exists() or not license_ready_path.is_file():
        logger.error(f"License-ready file not found at: {license_ready_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="License-ready file not found on disk"
        )
    
    # Determine content type
    content_type = "application/octet-stream"
    if license_ready_path.suffix.lower() in ['.jpg', '.jpeg']:
        content_type = "image/jpeg"
    elif license_ready_path.suffix.lower() == '.png':
        content_type = "image/png"
    
    return FileResponse(
        path=license_ready_path,
        media_type=content_type,
        filename=f"license_ready_{data_type.lower()}_{application_id}.jpg"
    )


@router.get("/search-for-approval/{id_number}")
def search_person_for_approval(
    id_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Search for a person by ID number and return their applications pending approval
    Only returns NEW_LICENSE and LEARNERS_PERMIT applications in PAID status
    """
    # Check permissions
    if not (current_user.has_permission("applications.authorize") or 
            current_user.role_hierarchy == RoleHierarchy.EXAMINER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to search for applications"
        )
    
    # Find person by ID number through their alias (document)
    # First try to find the alias by document number
    from app.crud import person as crud_person, person_alias
    found_person_alias = person_alias.get_by_document_number(
        db=db, 
        document_number=id_number.strip(),
        document_type="MADAGASCAR_ID"  # National ID document type
    )
    
    # If not found as MADAGASCAR_ID, try without document type filter
    if not found_person_alias:
        found_person_alias = person_alias.get_by_document_number(
            db=db, 
            document_number=id_number.strip()
        )
    
    if not found_person_alias:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found with this ID number"
        )
    
    # Get the person from the alias
    person = crud_person.get(db=db, id=found_person_alias.person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person record not found"
        )

    # Get applications pending approval for this person
    applications = db.query(Application).filter(
        Application.person_id == person.id,
        Application.status == ApplicationStatus.PAID,
        Application.application_type.in_([ApplicationType.NEW_LICENSE, ApplicationType.LEARNERS_PERMIT]),
        Application.approval_outcome.is_(None)
    ).all()
    
    # Get available restrictions based on application types
    from app.models.enums import DriverRestrictionCode, VehicleRestrictionCode, DRIVER_RESTRICTION_MAPPING, VEHICLE_RESTRICTION_MAPPING
    
    restrictions_info = {}
    for app in applications:
        app_type = app.application_type
        
        # Get medical information to check for vision test results
        medical_info = app.medical_information or {}
        vision_test = medical_info.get('vision_test', {})
        
        # Check if corrective lenses are required from vision test
        corrective_lenses_required = vision_test.get('corrective_lenses_required', False)
        vision_meets_standards = vision_test.get('vision_meets_standards', True)
        
        # Pre-selected restrictions based on medical information
        pre_selected_driver_restrictions = []
        if corrective_lenses_required or not vision_meets_standards:
            pre_selected_driver_restrictions.append(DriverRestrictionCode.CORRECTIVE_LENSES.value)
        
        if app_type == ApplicationType.NEW_LICENSE:
            # All restrictions available for NEW_LICENSE
            driver_restrictions = [
                {
                    "code": DriverRestrictionCode.CORRECTIVE_LENSES.value,
                    "description": DRIVER_RESTRICTION_MAPPING[DriverRestrictionCode.CORRECTIVE_LENSES]["description"],
                    "pre_selected": DriverRestrictionCode.CORRECTIVE_LENSES.value in pre_selected_driver_restrictions,
                    "locked": DriverRestrictionCode.CORRECTIVE_LENSES.value in pre_selected_driver_restrictions
                },
                {
                    "code": DriverRestrictionCode.PROSTHETICS.value,
                    "description": DRIVER_RESTRICTION_MAPPING[DriverRestrictionCode.PROSTHETICS]["description"],
                    "pre_selected": False,
                    "locked": False
                }
            ]
            
            vehicle_restrictions = [
                {
                    "code": VehicleRestrictionCode.AUTOMATIC_TRANSMISSION.value,
                    "description": VEHICLE_RESTRICTION_MAPPING[VehicleRestrictionCode.AUTOMATIC_TRANSMISSION]["description"]
                },
                {
                    "code": VehicleRestrictionCode.ELECTRIC_POWERED.value,
                    "description": VEHICLE_RESTRICTION_MAPPING[VehicleRestrictionCode.ELECTRIC_POWERED]["description"]
                },
                {
                    "code": VehicleRestrictionCode.PHYSICAL_DISABLED.value,
                    "description": VEHICLE_RESTRICTION_MAPPING[VehicleRestrictionCode.PHYSICAL_DISABLED]["description"]
                },
                {
                    "code": VehicleRestrictionCode.TRACTOR_ONLY.value,
                    "description": VEHICLE_RESTRICTION_MAPPING[VehicleRestrictionCode.TRACTOR_ONLY]["description"]
                },
                {
                    "code": VehicleRestrictionCode.INDUSTRIAL_AGRICULTURE.value,
                    "description": VEHICLE_RESTRICTION_MAPPING[VehicleRestrictionCode.INDUSTRIAL_AGRICULTURE]["description"]
                }
            ]
            
        elif app_type == ApplicationType.LEARNERS_PERMIT:
            # Limited restrictions for LEARNERS_PERMIT
            driver_restrictions = [
                {
                    "code": DriverRestrictionCode.CORRECTIVE_LENSES.value,
                    "description": DRIVER_RESTRICTION_MAPPING[DriverRestrictionCode.CORRECTIVE_LENSES]["description"],
                    "pre_selected": DriverRestrictionCode.CORRECTIVE_LENSES.value in pre_selected_driver_restrictions,
                    "locked": DriverRestrictionCode.CORRECTIVE_LENSES.value in pre_selected_driver_restrictions
                },
                {
                    "code": DriverRestrictionCode.PROSTHETICS.value,
                    "description": DRIVER_RESTRICTION_MAPPING[DriverRestrictionCode.PROSTHETICS]["description"],
                    "pre_selected": False,
                    "locked": False
                }
            ]
            
            vehicle_restrictions = [
                {
                    "code": VehicleRestrictionCode.PHYSICAL_DISABLED.value,
                    "description": VEHICLE_RESTRICTION_MAPPING[VehicleRestrictionCode.PHYSICAL_DISABLED]["description"]
                }
            ]
        
        restrictions_info[str(app.id)] = {
            "driver_restrictions": driver_restrictions,
            "vehicle_restrictions": vehicle_restrictions,
            "pre_selected_driver_restrictions": pre_selected_driver_restrictions
        }
    
    return {
        "person": {
            "id": str(person.id),
            "name": f"{person.first_name} {person.surname}",
            "id_number": found_person_alias.document_number
        },
        "applications": [
            {
                "id": str(app.id),
                "application_number": app.application_number,
                "application_type": app.application_type.value,
                "license_category": app.license_category.value,
                "status": app.status.value,
                "medical_information": app.medical_information
            } for app in applications
        ],
        "restrictions_info": restrictions_info
    }


@router.post("/process-approval/{application_id}")
def process_application_approval(
    application_id: uuid.UUID,
    approval_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Process approval outcome for an application (PASS, FAIL, or ABSENT)
    For PASS: captures restrictions and auto-generates license
    For FAIL/ABSENT: marks application as terminal status
    """
    # Check permissions
    if not (current_user.has_permission("applications.authorize") or 
            current_user.role_hierarchy == RoleHierarchy.EXAMINER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to process approvals"
        )
    
    # Get application
    application = db.query(Application).filter(Application.id == application_id).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Validate application is eligible for approval
    if application.status != ApplicationStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application must be in PAID status for approval"
        )
    
    if application.application_type not in [ApplicationType.NEW_LICENSE, ApplicationType.LEARNERS_PERMIT]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only NEW_LICENSE and LEARNERS_PERMIT applications can be approved"
        )
    
    if application.approval_outcome is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application has already been processed"
        )
    
    # Validate required fields
    outcome = approval_data.get("outcome")
    if outcome not in ["PASSED", "FAILED", "ABSENT"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Outcome must be PASSED, FAILED, or ABSENT"
        )
    
    location_id = approval_data.get("location_id")
    if not location_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Location ID is required"
        )
    
    # Update application with approval data
    application.approval_outcome = TestResult(outcome)
    application.approved_by_user_id = current_user.id
    application.approved_at_location_id = uuid.UUID(location_id)
    application.approval_date = datetime.utcnow()
    
    # Handle outcome-specific processing
    if outcome == "PASSED":
        # Get the restrictions data from the request
        restrictions_data = approval_data.get("restrictions", {})
        
        # Auto-add vision-based restrictions if needed
        medical_info = application.medical_information or {}
        vision_test = medical_info.get('vision_test', {})
        
        # Ensure corrective lenses restriction is added if required by vision test
        corrective_lenses_required = vision_test.get('corrective_lenses_required', False)
        vision_meets_standards = vision_test.get('vision_meets_standards', True)
        
        driver_restrictions = restrictions_data.get("driver_restrictions", [])
        vehicle_restrictions = restrictions_data.get("vehicle_restrictions", [])
        
        # Auto-add corrective lenses restriction if vision test requires it
        if (corrective_lenses_required or not vision_meets_standards):
            from app.models.enums import DriverRestrictionCode
            if DriverRestrictionCode.CORRECTIVE_LENSES.value not in driver_restrictions:
                driver_restrictions.append(DriverRestrictionCode.CORRECTIVE_LENSES.value)
        
        # Structure the final restrictions data
        final_restrictions = {
            "driver_restrictions": driver_restrictions,
            "vehicle_restrictions": vehicle_restrictions
        }
        
        # Validate restrictions for application type
        if not _validate_restrictions_for_application_type(application.application_type.value, final_restrictions):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid restrictions for {application.application_type.value} application type"
            )
        
        application.identified_restrictions = final_restrictions
        
        # Set test result first
        application.test_result = TestResult.PASSED
        
        # Follow staged payment workflow for NEW_LICENSE applications
        if application.application_type == ApplicationType.NEW_LICENSE:
            # NEW_LICENSE: Move to CARD_PAYMENT_PENDING to require card payment
            application.status = ApplicationStatus.CARD_PAYMENT_PENDING
            
            # CREATE LICENSE AT APPROVAL TIME (not payment time)
            license = _generate_license_from_application(db, application, final_restrictions)
            
            db.commit()
            
            return {
                "success": True,
                "message": "Test passed! License created. Card payment (38,000 MGA) required for card ordering",
                "application_status": application.status.value,
                "test_result": application.test_result.value,
                "license_id": str(license.id),
                "next_step": "card_payment_required",
                "card_payment_amount": "38,000 MGA",
                "applied_restrictions": final_restrictions
            }
        else:
            # Other application types: Go directly to APPROVED and generate license
            application.status = ApplicationStatus.APPROVED
            
            # Auto-generate license
            license = _generate_license_from_application(db, application, final_restrictions)
            
            db.commit()
            
            return {
                "success": True,
                "message": "Application approved successfully and license generated",
                "application_status": application.status.value,
                "test_result": application.test_result.value,
                "license_id": str(license.id),
                "applied_restrictions": final_restrictions
            }
        
    else:  # FAILED or ABSENT
        # Update status to terminal
        if outcome == "FAILED":
            application.status = ApplicationStatus.FAILED
        else:  # ABSENT
            application.status = ApplicationStatus.ABSENT
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Application marked as {outcome}",
            "application_status": application.status.value
        }


def _generate_license_from_application(db: Session, application: Application, restrictions_data: dict = None) -> "License":
    """
    Generate a license from an approved application
    restrictions_data format: {"driver_restrictions": ["01"], "vehicle_restrictions": ["01", "03"]}
    """
    from app.models.license import License, LicenseStatus
    
    # Convert restrictions to license format (structured JSON)
    license_restrictions = restrictions_data or {"driver_restrictions": [], "vehicle_restrictions": []}
    
    # Create license
    license = License(
        person_id=application.person_id,
        created_from_application_id=application.id,
        category=application.license_category,
        status=LicenseStatus.ACTIVE,
        issue_date=application.approval_date,
        issuing_location_id=application.approved_at_location_id,
        issued_by_user_id=application.approved_by_user_id,
        restrictions=license_restrictions,
        medical_restrictions=[],  # Can be populated from medical_information if needed
    )
    
    # Set expiry date for learner's permits (6 months)
    if application.application_type == ApplicationType.LEARNERS_PERMIT:
        from datetime import timedelta
        license.expiry_date = application.approval_date + timedelta(days=180)
    
    db.add(license)
    db.flush()  # Get the license ID
    
    return license


def _validate_restrictions_for_application_type(application_type: str, restrictions_data: dict) -> bool:
    """
    Validate that the selected restrictions are allowed for the application type
    Expected format: {"driver_restrictions": ["01"], "vehicle_restrictions": ["01", "03"]}
    """
    from app.models.enums import ApplicationType, DriverRestrictionCode, VehicleRestrictionCode
    
    driver_restrictions = restrictions_data.get("driver_restrictions", [])
    vehicle_restrictions = restrictions_data.get("vehicle_restrictions", [])
    
    # Define allowed restrictions for each application type
    if application_type == ApplicationType.NEW_LICENSE.value:
        # All restrictions allowed for NEW_LICENSE
        allowed_driver_restrictions = [code.value for code in DriverRestrictionCode]
        allowed_vehicle_restrictions = [code.value for code in VehicleRestrictionCode]
        
    elif application_type == ApplicationType.LEARNERS_PERMIT.value:
        # Limited restrictions for LEARNERS_PERMIT
        allowed_driver_restrictions = [
            DriverRestrictionCode.NONE.value,
            DriverRestrictionCode.CORRECTIVE_LENSES.value,
            DriverRestrictionCode.PROSTHETICS.value
        ]
        allowed_vehicle_restrictions = [
            VehicleRestrictionCode.NONE.value,
            VehicleRestrictionCode.PHYSICAL_DISABLED.value  # Only disabled adaptation for learners
        ]
    else:
        # No restrictions allowed for other application types
        allowed_driver_restrictions = []
        allowed_vehicle_restrictions = []
    
    # Check if all selected restrictions are allowed
    for restriction in driver_restrictions:
        if restriction not in allowed_driver_restrictions:
            return False
    
    for restriction in vehicle_restrictions:
        if restriction not in allowed_vehicle_restrictions:
            return False
    
    return True


@router.post("/{application_id}/mark-card-payment-pending", response_model=ApplicationSchema)
def mark_application_card_payment_pending(
    *,
    db: Session = Depends(get_db),
    application_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
) -> ApplicationSchema:
    """
    Mark NEW_LICENSE application as requiring card payment after passing test
    
    Requires: applications.authorize permission or EXAMINER role
    """
    if not (current_user.has_permission("applications.authorize") or 
            current_user.role_hierarchy == RoleHierarchy.EXAMINER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update application status"
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
    
    # Validate this is a NEW_LICENSE application that has passed
    if application.application_type != ApplicationType.NEW_LICENSE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only NEW_LICENSE applications can be marked as card payment pending"
        )
    
    if application.status != ApplicationStatus.PASSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Application must be in PASSED status, currently {application.status}"
        )
    
    if application.test_result != TestResult.PASSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application must have passed the test before requiring card payment"
        )
    
    # Update status to card payment pending
    updated_application = crud_application.update_status(
        db=db,
        application_id=application_id,
        new_status=ApplicationStatus.CARD_PAYMENT_PENDING,
        changed_by=current_user.id,
        reason="Test passed, awaiting card payment",
        notes="Automatically marked as card payment pending after test approval"
    )
    
    return ApplicationSchema.from_orm(updated_application)


@router.post("/fix-new-license-workflow/{application_id}")
def fix_new_license_workflow(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fix NEW_LICENSE applications that bypassed the staged payment workflow
    
    This endpoint fixes applications that went directly to APPROVED without
    going through PASSED -> CARD_PAYMENT_PENDING workflow.
    
    Requires: applications.change_status permission
    """
    if not current_user.has_permission("applications.change_status"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to fix application workflow"
        )
    
    application = db.query(Application).filter(Application.id == application_id).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Only fix NEW_LICENSE applications
    if application.application_type != ApplicationType.NEW_LICENSE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint only fixes NEW_LICENSE applications"
        )
    
    # Only fix applications that are in APPROVED status but shouldn't be
    if application.status != ApplicationStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Application is in {application.status} status, expected APPROVED"
        )
    
    # Check if this application bypassed the staged payment workflow
    if application.test_result is None or not application.card_payment_completed:
        # This application needs to be fixed
        
        # Set test result to PASSED (since it was approved)
        application.test_result = TestResult.PASSED
        
        # Check if card payment was completed
        if not application.card_payment_completed:
            # Move back to CARD_PAYMENT_PENDING to require card payment
            application.status = ApplicationStatus.CARD_PAYMENT_PENDING
            
            db.commit()
            
            return {
                "success": True,
                "message": "Application fixed: moved to CARD_PAYMENT_PENDING status",
                "application_status": application.status.value,
                "test_result": application.test_result.value,
                "next_step": "card_payment_required",
                "card_payment_amount": "38,000 MGA"
            }
        else:
            # Card payment was completed, application can stay APPROVED
            db.commit()
            
            return {
                "success": True,
                "message": "Application workflow corrected: test_result set to PASSED",
                "application_status": application.status.value,
                "test_result": application.test_result.value,
                "next_step": "ready_for_card_ordering"
            }
    else:
        # Application is already in correct state
        return {
            "success": True,
            "message": "Application workflow is already correct",
            "application_status": application.status.value,
            "test_result": application.test_result.value,
            "next_step": "ready_for_card_ordering"
        }

 