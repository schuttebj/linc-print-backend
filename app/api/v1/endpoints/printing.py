"""
Print Job Management API Endpoints
Handles card printing workflow, queue management, and production tracking
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
import base64
import logging
import os
import shutil
from pathlib import Path as FilePath

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.crud.crud_printing import crud_print_job, crud_print_queue
from app.crud.crud_application import crud_application
from app.crud.crud_license import crud_license
from app.crud.crud_person import person as crud_person
from app.crud.crud_card import crud_card
from app.models.user import User
from app.models.application import Application
from app.models.license import License
from app.models.card import CardNumberGenerator
from app.models.enums import ApplicationStatus, LicenseCategory
from app.models.printing import PrintJobStatus, PrintJobPriority, QualityCheckResult, PrintJobStatusHistory, PrintJob
from app.schemas.printing import (
    PrintJobCreateRequest, PrintJobResponse, PrintJobDetailResponse,
    PrintJobQueueMoveRequest, PrintJobAssignRequest, PrintJobStartRequest,
    PrintJobCompleteRequest, QualityCheckRequest, PrintJobSearchFilters,
    PrintQueueResponse, PrintJobStatistics, PrintJobSearchResponse
)
from app.services.card_file_manager import card_file_manager
from app.services.card_generator import madagascar_card_generator

logger = logging.getLogger(__name__)
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


@router.get("/card-ordering/search/{id_number}", summary="Search Person for Card Ordering")
async def search_person_for_card_ordering(
    id_number: str = Path(..., description="Person's ID number"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.create"))
):
    """
    Search for a person by ID number and return all data needed for card ordering:
    - Person details
    - All licenses (with eligibility status)
    - Applications ready for card ordering
    - Print eligibility status
    """
    try:
        # Search for person by ID number
        logger.info(f"Searching for person with ID number: {id_number}")
        person = crud_person.get_by_id_number(db, id_number=id_number)
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No person found with ID number: {id_number}"
            )
        
        logger.info(f"Found person: {person.first_name} {person.last_name} (ID: {person.id})")
        
        # Get all licenses for this person
        all_licenses = crud_license.get_by_person_id(db, person_id=person.id, active_only=True)
        logger.info(f"Found {len(all_licenses)} active licenses for person")
        
        # Filter licenses into card-eligible and non-eligible
        learners_categories = [LicenseCategory.LEARNERS_1, LicenseCategory.LEARNERS_2, LicenseCategory.LEARNERS_3]
        card_eligible_licenses = [
            license for license in all_licenses 
            if license.category not in learners_categories
        ]
        learners_permits = [
            license for license in all_licenses 
            if license.category in learners_categories
        ]
        
        logger.info(f"Card-eligible licenses: {len(card_eligible_licenses)}, Learners permits: {len(learners_permits)}")
        
        # Get applications that could be used for card ordering
        approved_applications = crud_application.get_by_person_id(
            db, 
            person_id=person.id,
            status_filter=[ApplicationStatus.APPROVED]
        )
        logger.info(f"Found {len(approved_applications)} approved applications")
        
        # Check print eligibility
        can_order_card = len(card_eligible_licenses) > 0
        eligibility_issues = []
        
        if len(card_eligible_licenses) == 0:
            eligibility_issues.append("No card-eligible licenses found")
        if len(approved_applications) == 0:
            eligibility_issues.append("No approved applications found")
        
        # Get accessible print locations for current user
        accessible_locations = []
        if current_user.is_superuser or current_user.user_type.value in ["SYSTEM_USER", "NATIONAL_ADMIN"]:
            from app.crud.crud_location import location as crud_location
            accessible_locations = crud_location.get_operational_locations(db)
        elif current_user.user_type.value == "PROVINCIAL_ADMIN":
            from app.crud.crud_location import location as crud_location
            accessible_locations = crud_location.get_by_province(db, province_code=current_user.scope_province)
        elif current_user.primary_location_id:
            from app.crud.crud_location import location as crud_location
            location = crud_location.get(db, id=current_user.primary_location_id)
            if location:
                accessible_locations = [location]
        
        return {
            "person": {
                "id": str(person.id),
                "first_name": person.first_name,
                "last_name": person.last_name,
                "id_number": person.id_number,
                "birth_date": person.birth_date.isoformat() if person.birth_date else None,
                "nationality": person.nationality,
                "photo_path": person.photo_path,
                "signature_path": person.signature_path
            },
            "card_eligible_licenses": [
                {
                    "id": str(license.id),
                    "category": license.category.value,
                    "status": license.status.value,
                    "issue_date": license.issue_date.isoformat(),
                    "expiry_date": license.expiry_date.isoformat() if license.expiry_date else None,
                    "restrictions": license.restrictions,
                    "medical_restrictions": license.medical_restrictions,
                    "issuing_location_id": str(license.issuing_location_id)
                }
                for license in card_eligible_licenses
            ],
            "learners_permits": [
                {
                    "id": str(license.id),
                    "category": license.category.value,
                    "status": license.status.value,
                    "issue_date": license.issue_date.isoformat(),
                    "expiry_date": license.expiry_date.isoformat() if license.expiry_date else None
                }
                for license in learners_permits
            ],
            "approved_applications": [
                {
                    "id": str(app.id),
                    "application_number": app.application_number,
                    "application_type": app.application_type.value,
                    "status": app.status.value,
                    "application_date": app.application_date.isoformat(),
                    "approval_date": app.approval_date.isoformat() if app.approval_date else None
                }
                for app in approved_applications
            ],
            "print_eligibility": {
                "can_order_card": can_order_card,
                "issues": eligibility_issues,
                "total_licenses": len(all_licenses),
                "card_eligible_count": len(card_eligible_licenses),
                "learners_permit_count": len(learners_permits)
            },
            "accessible_print_locations": [
                {
                    "id": str(location.id),
                    "name": location.name,
                    "code": location.code,
                    "province_code": location.province_code
                }
                for location in accessible_locations
            ]
        }
        
    except Exception as e:
        logger.error(f"Error searching person for card ordering: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search person for card ordering: {str(e)}"
        )


# Print Job Creation
@router.post("/jobs", response_model=PrintJobResponse, summary="Create Print Job")
async def create_print_job(
    request: PrintJobCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.create"))
):
    """
    Create a new print job from approved application(s)
    
    This endpoint:
    1. Validates application is ready for printing
    2. Validates user has access to print location
    3. Retrieves all person's licenses (excluding learners permits)
    4. Generates card number and PDF files
    5. Adds job to print queue
    """
    try:
        logger.info(f"=== Starting print job creation ===")
        logger.info(f"Request data: application_id={request.application_id}, location_id={request.location_id}, card_template={request.card_template}")
        logger.info(f"Current user: {current_user.id} ({current_user.username})")
        
        # Get primary application
        logger.info(f"Looking up application with ID: {request.application_id}")
        application = crud_application.get(db, id=request.application_id)
        if not application:
            logger.error(f"Application not found with ID: {request.application_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application not found with ID: {request.application_id}"
            )
        
        logger.info(f"Found application: {application.application_number} (status: {application.status})")
        
        # Determine print location (admin users can specify location, others use application location)
        if request.location_id:
            # Admin user specified a print location
            logger.info(f"Admin user specified print location: {request.location_id}")
            print_location_id = request.location_id
            
            # Validate user has access to the specified print location
            if not current_user.can_access_location(print_location_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to create print jobs for the specified location"
                )
            
            # Get the print location to validate it exists
            from app.crud.crud_location import location as crud_location
            print_location = crud_location.get(db, id=print_location_id)
            if not print_location:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Specified print location not found"
                )
                
        else:
            # Use application's location as print location
            print_location_id = application.location_id
            
            # Validate user has access to the application's location
            if not current_user.can_access_location(application.location_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to create print jobs for this location"
                )
        
        # Validate application is ready for printing
        if application.status not in [ApplicationStatus.APPROVED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Application status must be APPROVED, currently {application.status}"
            )
        
        # Get person details
        person = crud_person.get(db, id=application.person_id)
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found"
            )
        
        # Get all licenses for person (excluding learners permits)
        logger.info(f"Getting licenses for person {application.person_id}")
        person_licenses = crud_license.get_by_person_id(
            db, 
            person_id=application.person_id,
            active_only=True
        )
        logger.info(f"Found {len(person_licenses)} total licenses for person {application.person_id}")
        
        # Filter out learners permits (they don't go on cards)
        learners_categories = [LicenseCategory.LEARNERS_1, LicenseCategory.LEARNERS_2, LicenseCategory.LEARNERS_3]
        card_licenses = [
            license for license in person_licenses 
            if license.category not in learners_categories
        ]
        logger.info(f"Found {len(card_licenses)} card-eligible licenses (excluding learners permits: {[cat.value for cat in learners_categories]})")
        
        if not card_licenses:
            logger.error(f"No valid licenses found for card printing - person {application.person_id} has {len(person_licenses)} total licenses but none are card-eligible")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid licenses found for card printing"
            )
        
        # Generate card number
        # Use the print location (not application location) for card number generation
        logger.info(f"Looking up print location with ID: {print_location_id}")
        from app.crud.crud_location import location as crud_location
        print_location = crud_location.get(db, id=print_location_id)
        if not print_location:
            logger.error(f"Print location not found with ID: {print_location_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Print location not found with ID: {print_location_id}"
            )
        
        logger.info(f"Found print location: {print_location.name} (code: {print_location.code})")
        location_code = print_location.code
        logger.info(f"Generating card number with location code: {location_code}")
        sequence_number = CardNumberGenerator.get_next_sequence_number(db, location_code)
        card_number = CardNumberGenerator.generate_card_number(
            location_code, sequence_number, 
            card_type="STANDARD"
        )
        logger.info(f"Generated card number: {card_number}")
        
        # Prepare license data for card generation
        logger.info(f"Preparing license data for {len(card_licenses)} licenses")
        license_data = {
            "licenses": [
                {
                    "id": str(license.id),
                    "category": license.category.value,
                    "issue_date": license.issue_date.isoformat(),
                    "expiry_date": license.expiry_date.isoformat() if license.expiry_date else None,
                    "restrictions": license.restrictions,
                    "status": license.status.value
                }
                for license in card_licenses
            ],
            "total_licenses": len(card_licenses),
            "card_template": request.card_template
        }
        
        # Prepare person data for card generation
        logger.info(f"Preparing person data for person {person.id}")
        person_data = {
            "id": str(person.id),
            "first_name": person.first_name,
            "last_name": person.last_name,
            "date_of_birth": person.date_of_birth.isoformat(),
            "id_number": person.id_number,
            "nationality": person.nationality,
            "photo_path": person.photo_path,
            "signature_path": person.signature_path,
            "address": {
                "street": person.current_address.street if person.current_address else "",
                "city": person.current_address.city if person.current_address else "",
                "province": person.current_address.province if person.current_address else "",
                "postal_code": person.current_address.postal_code if person.current_address else ""
            }
        }
        
        # Create print job
        logger.info(f"Calling create_print_job with application_id={request.application_id}, print_location_id={print_location_id}")
        print_job = crud_print_job.create_print_job(
            db=db,
            application_id=request.application_id,
            person_id=application.person_id,
            print_location_id=print_location_id,
            card_number=card_number,
            license_data=license_data,
            person_data=person_data,
            current_user=current_user,
            additional_application_ids=request.additional_application_ids
        )
        logger.info(f"Print job created successfully with ID: {print_job.id}")
        
        # Update application status
        application.status = ApplicationStatus.SENT_TO_PRINTER
        application.print_job_id = print_job.id
        db.commit()
        
        return PrintJobResponse.from_orm(print_job)
        
    except Exception as e:
        logger.error(f"Print job creation failed: {str(e)}", exc_info=True)
        error_details = str(e) if str(e) else f"Unknown error: {type(e).__name__}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create print job: {error_details}"
        )


# Queue Management
@router.get("/queues", response_model=List[PrintQueueResponse], summary="Get Accessible Print Queues")
async def get_accessible_print_queues(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.read"))
):
    """
    Get all print queues accessible to the current user based on their role:
    - System/National Admins: All queues nationwide
    - Provincial Admins: All queues in their province
    - Location Users: Only their assigned location's queue
    """
    accessible_locations = []
    
    if current_user.is_superuser or current_user.user_type.value in ["SYSTEM_USER", "NATIONAL_ADMIN"]:
        # System and National admins can see all locations
        from app.crud.crud_location import location as crud_location
        accessible_locations = crud_location.get_operational_locations(db)
        
    elif current_user.user_type.value == "PROVINCIAL_ADMIN":
        # Provincial admin can see locations in their province
        from app.crud.crud_location import location as crud_location
        accessible_locations = crud_location.get_by_province(db, province_code=current_user.scope_province)
        
    elif current_user.primary_location_id:
        # Location user can only see their assigned location
        from app.crud.crud_location import location as crud_location
        location = crud_location.get(db, id=current_user.primary_location_id)
        if location:
            accessible_locations = [location]
    
    # Get print queues for accessible locations
    queues = []
    for location in accessible_locations:
        try:
            print_queue = crud_print_queue.get_or_create_queue(db, location_id=location.id)
            queue_response = PrintQueueResponse(
                location_id=location.id,
                location_name=location.name,
                current_queue_size=print_queue.current_queue_size,
                total_jobs_processed=print_queue.total_jobs_processed,
                average_processing_time_minutes=float(print_queue.average_processing_time_minutes) if print_queue.average_processing_time_minutes else None,
                last_updated=print_queue.last_updated,
                queued_jobs=[],  # Empty for summary view
                in_progress_jobs=[],  # Empty for summary view
                completed_jobs=[]  # Empty for summary view
            )
            queues.append(queue_response)
        except Exception as e:
            logger.warning(f"Failed to get queue for location {location.id}: {e}")
            continue
    
    return queues


@router.get("/queue/{location_id}", response_model=PrintQueueResponse, summary="Get Print Queue")
async def get_print_queue(
    location_id: UUID = Path(..., description="Location ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.read"))
):
    """
    Get print queue for a specific location
    
    Only users with access to the location can view its print queue.
    System/National admins can view any queue.
    Provincial admins can view queues in their province.
    Location users can only view their assigned location's queue.
    """
    # Validate user has access to this location
    if not current_user.can_access_location(location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view print queue for this location"
        )
    
    # Get print queue for location
    print_queue = crud_print_queue.get_or_create_queue(db, location_id=location_id)
    
    # Get queue jobs
    jobs = crud_print_job.get_print_queue(
        db=db,
        location_id=location_id,
        status=None, # No specific status filtering here, as the endpoint is for a single location
        limit=50 # Default limit for a single location
    )
    
    # Separate jobs by status
    queued_jobs = [job for job in jobs if job.status == PrintJobStatus.QUEUED]
    in_progress_jobs = [job for job in jobs if job.status in [
        PrintJobStatus.ASSIGNED, PrintJobStatus.PRINTING, PrintJobStatus.PRINTED, PrintJobStatus.QUALITY_CHECK
    ]]
    
    # Count completed today
    today = datetime.utcnow().date()
    completed_today = len([
        job for job in jobs 
        if job.status == PrintJobStatus.COMPLETED and 
        job.completed_at and job.completed_at.date() == today
    ])
    
    return PrintQueueResponse(
        location_id=location_id,
        location_name=print_queue.location.name if print_queue.location else None,
        current_queue_size=print_queue.current_queue_size,
        total_jobs_processed=print_queue.total_jobs_processed,
        average_processing_time_minutes=float(print_queue.average_processing_time_minutes) if print_queue.average_processing_time_minutes else None,
        last_updated=print_queue.last_updated,
        queued_jobs=[PrintJobResponse.from_orm(job) for job in queued_jobs],
        in_progress_jobs=[PrintJobResponse.from_orm(job) for job in in_progress_jobs],
        completed_today=completed_today
    )


@router.post("/jobs/{job_id}/move-to-top", response_model=PrintJobResponse, summary="Move Job to Top of Queue")
async def move_job_to_top(
    job_id: UUID = Path(..., description="Print Job ID"),
    request: PrintJobQueueMoveRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.queue_manage"))
):
    """
    Move a print job to the top of the queue
    
    This is used for urgent situations and requires a reason.
    Only jobs in QUEUED or ASSIGNED status can be moved.
    """
    print_job = crud_print_job.move_to_top_of_queue(
        db=db,
        job_id=job_id,
        reason=request.reason,
        current_user=current_user
    )
    
    return PrintJobResponse.from_orm(print_job)


# Job Processing Workflow
@router.post("/jobs/{job_id}/assign", response_model=PrintJobResponse, summary="Assign Job to Printer")
async def assign_job_to_printer(
    job_id: UUID = Path(..., description="Print Job ID"),
    request: PrintJobAssignRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.assign"))
):
    """
    Assign a print job to a printer operator
    
    Moves job from QUEUED to ASSIGNED status.
    """
    print_job = crud_print_job.assign_to_printer(
        db=db,
        job_id=job_id,
        printer_user_id=request.printer_user_id,
        current_user=current_user
    )
    
    return PrintJobResponse.from_orm(print_job)


@router.post("/jobs/{job_id}/start", response_model=PrintJobResponse, summary="Start Printing")
async def start_printing_job(
    job_id: UUID = Path(..., description="Print Job ID"),
    request: PrintJobStartRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.print"))
):
    """
    Start the printing process for a job
    
    Moves job from ASSIGNED to PRINTING status.
    Requires PDF files to be generated first.
    Only users with access to the print location can start jobs.
    """
    # Get print job first to validate location access
    print_job = crud_print_job.get(db, id=job_id)
    if not print_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Print job not found"
        )
    
    # Validate user has access to the print location
    if not current_user.can_access_location(print_job.print_location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to manage print jobs for this location"
        )
    
    print_job = crud_print_job.start_printing(
        db=db,
        job_id=job_id,
        current_user=current_user,
        printer_hardware_id=request.printer_hardware_id
    )
    
    return PrintJobResponse.from_orm(print_job)


@router.post("/jobs/{job_id}/complete", response_model=PrintJobResponse, summary="Complete Printing")
async def complete_printing_job(
    job_id: UUID = Path(..., description="Print Job ID"),
    request: PrintJobCompleteRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.print"))
):
    """
    Mark printing as completed
    
    Moves job from PRINTING to PRINTED status.
    Job then moves to quality check phase.
    """
    print_job = crud_print_job.complete_printing(
        db=db,
        job_id=job_id,
        current_user=current_user,
        production_notes=request.production_notes
    )
    
    return PrintJobResponse.from_orm(print_job)


# Quality Assurance
@router.post("/jobs/{job_id}/qa-start", response_model=PrintJobResponse, summary="Start Quality Check")
async def start_quality_check(
    job_id: UUID = Path(..., description="Print Job ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.qa"))
):
    """
    Start quality assurance review
    
    Moves job from PRINTED to QUALITY_CHECK status.
    """
    print_job = crud_print_job.start_quality_check(
        db=db,
        job_id=job_id,
        current_user=current_user
    )
    
    return PrintJobResponse.from_orm(print_job)


@router.post("/jobs/{job_id}/quality-check", response_model=PrintJobResponse, summary="Quality Check")
async def quality_check_job(
    job_id: UUID = Path(..., description="Print Job ID"),
    request: QualityCheckRequest = ...,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.quality_check"))
):
    """
    Perform quality assurance check on printed card
    
    Sets quality check result (PASS/FAIL/NEEDS_REPRINT).
    Only users with access to the print location can perform QA.
    """
    # Get print job first to validate location access
    print_job = crud_print_job.get(db, id=job_id)
    if not print_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Print job not found"
        )
    
    # Validate user has access to the print location
    if not current_user.can_access_location(print_job.print_location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to perform quality checks for this location"
        )
    
    print_job = crud_print_job.quality_check(
        db=db,
        job_id=job_id,
        quality_result=request.quality_result,
        quality_notes=request.quality_notes,
        current_user=current_user
    )
    
    return PrintJobResponse.from_orm(print_job)


# Job Information
@router.get("/jobs/{job_id}", response_model=PrintJobDetailResponse, summary="Get Print Job Details")
async def get_print_job(
    job_id: UUID = Path(..., description="Print Job ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.read"))
):
    """
    Get detailed information about a print job
    
    Includes full job history, status changes, and associated data.
    """
    print_job = crud_print_job.get(db, id=job_id)
    if not print_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Print job not found"
        )
    
    # Check user has access to this job's location
    if not current_user.can_access_location(print_job.print_location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this print job"
        )
    
    return PrintJobDetailResponse.from_orm(print_job)


@router.get("/jobs", response_model=PrintJobSearchResponse, summary="Search Print Jobs")
async def search_print_jobs(
    filters: PrintJobSearchFilters = Depends(),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.read"))
):
    """
    Search print jobs with filtering and pagination
    
    Supports filtering by location, status, person, application, and date ranges.
    Results are filtered based on user's location access permissions.
    """
    jobs = crud_print_job.get_jobs_by_location_and_user(
        db=db,
        user=current_user,
        status=filters.status,
        limit=page_size * 10  # Get more to allow for filtering
    )
    
    # Apply additional filters
    if filters.person_id:
        jobs = [job for job in jobs if job.person_id == filters.person_id]
    
    if filters.application_id:
        jobs = [
            job for job in jobs 
            if any(ja.application_id == filters.application_id for ja in job.job_applications)
        ]
    
    if filters.job_number:
        jobs = [job for job in jobs if filters.job_number.lower() in job.job_number.lower()]
    
    if filters.date_from:
        jobs = [job for job in jobs if job.submitted_at >= filters.date_from]
    
    if filters.date_to:
        jobs = [job for job in jobs if job.submitted_at <= filters.date_to]
    
    # Pagination
    total_count = len(jobs)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_jobs = jobs[start_idx:end_idx]
    
    return PrintJobSearchResponse(
        jobs=[PrintJobResponse.from_orm(job) for job in page_jobs],
        total_count=total_count,
        page=page,
        page_size=page_size,
        has_next_page=end_idx < total_count,
        has_previous_page=page > 1
    )


# Statistics and Reporting
@router.get("/statistics/{location_id}", response_model=PrintJobStatistics, summary="Get Print Job Statistics")
async def get_print_statistics(
    location_id: UUID = Path(..., description="Location ID"),
    days: int = Query(30, ge=1, le=365, description="Number of days for statistics"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.read"))
):
    """
    Get print job statistics for a location
    
    Provides counts, completion rates, and performance metrics.
    """
    # Check user has access to this location
    if not current_user.can_access_location(location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this location's statistics"
        )
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    # Get jobs in date range
    jobs = db.query(PrintJob).filter(
        and_(
            PrintJob.print_location_id == location_id,
            PrintJob.submitted_at >= start_date,
            PrintJob.submitted_at <= end_date
        )
    ).all()
    
    # Calculate statistics
    total_jobs = len(jobs)
    status_counts = {}
    for status in PrintJobStatus:
        status_counts[status.value] = len([job for job in jobs if job.status == status])
    
    # QA statistics
    qa_jobs = [job for job in jobs if job.quality_check_result]
    qa_pass_rate = 0.0
    if qa_jobs:
        passed_jobs = len([job for job in qa_jobs if job.quality_check_result == QualityCheckResult.PASSED])
        qa_pass_rate = (passed_jobs / len(qa_jobs)) * 100
    
    # Average completion time
    completed_jobs = [
        job for job in jobs 
        if job.status == PrintJobStatus.COMPLETED and job.completed_at and job.submitted_at
    ]
    avg_completion_time = None
    if completed_jobs:
        total_minutes = sum([
            (job.completed_at - job.submitted_at).total_seconds() / 60 
            for job in completed_jobs
        ])
        avg_completion_time = total_minutes / len(completed_jobs) / 60  # Convert to hours
    
    # Daily counts
    today = datetime.utcnow().date()
    jobs_completed_today = len([
        job for job in jobs 
        if job.status == PrintJobStatus.COMPLETED and 
        job.completed_at and job.completed_at.date() == today
    ])
    jobs_submitted_today = len([
        job for job in jobs 
        if job.submitted_at.date() == today
    ])
    
    return PrintJobStatistics(
        location_id=location_id,
        total_jobs=total_jobs,
        queued_jobs=status_counts.get("QUEUED", 0),
        in_progress_jobs=status_counts.get("ASSIGNED", 0) + status_counts.get("PRINTING", 0) + status_counts.get("PRINTED", 0) + status_counts.get("QUALITY_CHECK", 0),
        completed_jobs=status_counts.get("COMPLETED", 0),
        failed_jobs=status_counts.get("FAILED", 0),
        reprint_jobs=len([job for job in jobs if job.original_print_job_id]),
        qa_pass_rate=round(qa_pass_rate, 2),
        average_completion_time_hours=round(avg_completion_time, 2) if avg_completion_time else None,
        jobs_completed_today=jobs_completed_today,
        jobs_submitted_today=jobs_submitted_today,
        period_start=start_date,
        period_end=end_date
    ) 


@router.get("/jobs/{job_id}/files/front")
async def get_print_job_front_card(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Response:
    """Get front card image/PDF for print job"""
    
    # Check permissions
    if not current_user.has_permission("printing.read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get print job
    print_job = crud_print_job.get(db, id=job_id)
    if not print_job:
        raise HTTPException(status_code=404, detail="Print job not found")
    
    # Check if files were generated (may have been deleted after QA)
    if not print_job.generation_metadata or not print_job.generation_metadata.get("files_saved_to_disk"):
        raise HTTPException(status_code=404, detail="Card files were not generated")
    
    # Check if files still exist (deleted after QA completion)
    if print_job.generation_metadata.get("files_deleted_after_qa"):
        raise HTTPException(
            status_code=410, 
            detail="Card files have been deleted after QA completion"
        )
    
    try:
        # Get file content from disk
        file_content = card_file_manager.get_file_content(
            print_job_id=str(print_job.id),
            file_type="front_image",
            created_at=print_job.submitted_at
        )
        
        if not file_content:
            raise HTTPException(status_code=404, detail="Front card image not found on disk")
        
        return Response(
            content=file_content,
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename=card_front_{print_job.job_number}.png",
                "Content-Length": str(len(file_content))
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving front card for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving card file")


@router.get("/jobs/{job_id}/files/back")
async def get_print_job_back_card(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Response:
    """Get back card image/PDF for print job"""
    
    # Check permissions
    if not current_user.has_permission("printing.read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get print job
    print_job = crud_print_job.get(db, id=job_id)
    if not print_job:
        raise HTTPException(status_code=404, detail="Print job not found")
    
    # Check if files were generated and still exist
    if not print_job.generation_metadata or not print_job.generation_metadata.get("files_saved_to_disk"):
        raise HTTPException(status_code=404, detail="Card files were not generated")
    
    if print_job.generation_metadata.get("files_deleted_after_qa"):
        raise HTTPException(
            status_code=410, 
            detail="Card files have been deleted after QA completion"
        )
    
    try:
        # Get file content from disk
        file_content = card_file_manager.get_file_content(
            print_job_id=str(print_job.id),
            file_type="back_image", 
            created_at=print_job.submitted_at
        )
        
        if not file_content:
            raise HTTPException(status_code=404, detail="Back card image not found on disk")
        
        return Response(
            content=file_content,
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename=card_back_{print_job.job_number}.png",
                "Content-Length": str(len(file_content))
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving back card for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving card file")


@router.get("/jobs/{job_id}/files/combined-pdf")
async def get_print_job_combined_pdf(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Response:
    """Get combined PDF (front + back) for print job"""
    
    # Check permissions
    if not current_user.has_permission("printing.read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get print job
    print_job = crud_print_job.get(db, id=job_id)
    if not print_job:
        raise HTTPException(status_code=404, detail="Print job not found")
    
    # Check if files were generated and still exist
    if not print_job.generation_metadata or not print_job.generation_metadata.get("files_saved_to_disk"):
        raise HTTPException(status_code=404, detail="Card files were not generated")
    
    if print_job.generation_metadata.get("files_deleted_after_qa"):
        raise HTTPException(
            status_code=410, 
            detail="Card files have been deleted after QA completion"
        )
    
    try:
        # Get file content from disk
        file_content = card_file_manager.get_file_content(
            print_job_id=str(print_job.id),
            file_type="combined_pdf",
            created_at=print_job.submitted_at
        )
        
        if not file_content:
            raise HTTPException(status_code=404, detail="Combined PDF not found on disk")
        
        return Response(
            content=file_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=card_{print_job.job_number}.pdf",
                "Content-Length": str(len(file_content))
            }
        )
        
    except Exception as e:
        logger.error(f"Error retrieving combined PDF for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving PDF file")


@router.post("/jobs/{job_id}/regenerate-files")
async def regenerate_print_job_files(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> PrintJobResponse:
    """Regenerate card files for print job"""
    
    # Check permissions
    if not current_user.has_permission("printing.create"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get print job
    print_job = crud_print_job.get(db, id=job_id)
    if not print_job:
        raise HTTPException(status_code=404, detail="Print job not found")
    
    # Only allow regeneration for jobs that haven't started printing
    if print_job.status not in [PrintJobStatus.QUEUED, PrintJobStatus.ASSIGNED]:
        raise HTTPException(
            status_code=400, 
            detail="Cannot regenerate files for jobs that have started printing"
        )
    
    try:
        # Prepare data for card generation
        print_job_data = {
            "license_data": print_job.license_data,
            "person_data": print_job.person_data,
            "print_job_id": str(print_job.id),
            "job_number": print_job.job_number,
            "card_number": print_job.card_number
        }
        
        # Generate card files
        card_files = madagascar_card_generator.generate_card_files(print_job_data)
        
        # Update print job with new file data
        print_job.pdf_files_generated = True
        print_job.generation_metadata = {
            "generator_version": card_files.get("generator_version"),
            "generation_timestamp": card_files.get("generation_timestamp"),
            "regenerated_by": str(current_user.id),
            "regenerated_at": datetime.utcnow().isoformat(),
            "file_sizes": {
                "front_image": len(card_files.get("front_image", "")),
                "back_image": len(card_files.get("back_image", "")),
                "combined_pdf": len(card_files.get("combined_pdf", ""))
            }
        }
        
        # Store new card files
        print_job.card_files_data = card_files
        
        # Log regeneration in status history
        status_history = PrintJobStatusHistory(
            print_job_id=print_job.id,
            from_status=print_job.status,
            to_status=print_job.status,  # Keep same status
            changed_by_user_id=current_user.id,
            change_reason="Files regenerated",
            change_notes=f"Card files regenerated by {current_user.email}"
        )
        db.add(status_history)
        
        db.commit()
        db.refresh(print_job)
        
        # Convert to response format
        return PrintJobResponse.from_orm(print_job)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error regenerating files for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to regenerate files: {str(e)}") 


# Enhanced Storage Management
@router.get("/storage/bloat-report", summary="Get Storage Bloat Analysis")
async def get_storage_bloat_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.view_statistics"))
):
    """
    Analyze storage for potential bloat and cleanup opportunities
    
    Identifies:
    - Empty directories that should be removed
    - Orphaned files without database records
    - Large directories that may indicate cleanup failures
    - Overall storage health and optimization opportunities
    """
    try:
        # Get comprehensive bloat analysis
        bloat_report = card_file_manager.get_directory_bloat_report()
        
        # Get database records for cross-reference
        total_jobs = db.query(PrintJob).count()
        jobs_with_active_files = db.query(PrintJob).filter(
            PrintJob.pdf_files_generated == True,
            PrintJob.generation_metadata['files_deleted_after_qa'].astext != 'true'
        ).count()
        
        cleanup_failures = db.query(PrintJob).filter(
            PrintJob.generation_metadata['cleanup_failed'].astext == 'true'
        ).count()
        
        manual_cleanup_needed = db.query(PrintJob).filter(
            PrintJob.generation_metadata['manual_cleanup_needed'].astext == 'true'
        ).count()
        
        return {
            "bloat_analysis": bloat_report,
            "database_health": {
                "total_print_jobs": total_jobs,
                "jobs_with_active_files": jobs_with_active_files,
                "cleanup_failures": cleanup_failures,
                "manual_cleanup_needed": manual_cleanup_needed,
                "cleanup_success_rate": ((total_jobs - cleanup_failures) / total_jobs * 100) if total_jobs > 0 else 100
            },
            "health_indicators": {
                "storage_optimized": not bloat_report.get("bloat_detected", True),
                "cleanup_working": cleanup_failures < (total_jobs * 0.05),  # Less than 5% failures
                "no_manual_intervention_needed": manual_cleanup_needed == 0,
                "overall_health": "Excellent" if not bloat_report.get("bloat_detected") and cleanup_failures == 0 else "Good" if cleanup_failures < 10 else "Needs Attention"
            },
            "recommendations": bloat_report.get("cleanup_recommendations", [])
        }
        
    except Exception as e:
        logger.error(f"Error generating bloat report: {e}")
        raise HTTPException(status_code=500, detail="Error analyzing storage bloat")


@router.post("/storage/force-cleanup-empty-dirs", summary="Force Cleanup of Empty Directories")
async def force_cleanup_empty_directories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.delete"))
):
    """
    Force cleanup of all empty directories in the card storage structure
    
    This maintenance operation removes directory bloat by cleaning up:
    - Empty day directories (DD)
    - Empty month directories (MM)  
    - Empty year directories (YYYY)
    
    Use this to eliminate accumulated empty folder bloat.
    """
    try:
        # Collect all empty directories (bottom-up for safe removal)
        empty_dirs = []
        for root, dirs, files in os.walk(card_file_manager.cards_path, topdown=False):
            root_path = FilePath(root)
            
            # Skip the main cards directory
            if root_path == card_file_manager.cards_path:
                continue
                
            # Check if directory is empty
            try:
                if not any(root_path.iterdir()):
                    empty_dirs.append(root_path)
            except (PermissionError, OSError) as e:
                logger.warning(f"Cannot check directory {root_path}: {e}")
        
        # Remove empty directories
        for empty_dir in empty_dirs:
            try:
                empty_dir.rmdir()
                logger.info(f"🗑️  Removed empty directory: {empty_dir}")
            except (PermissionError, OSError) as e:
                logger.warning(f"⚠️  Could not remove directory {empty_dir}: {e}")
        
        return {
            "status": "success",
            "message": f"Removed {len(empty_dirs)} empty directories",
            "directories_removed": len(empty_dirs),
            "cleanup_paths": [str(d) for d in empty_dirs],
            "bloat_eliminated": True
        }
        
    except Exception as e:
        logger.error(f"Error during force empty directory cleanup: {e}")
        raise HTTPException(status_code=500, detail=f"Force cleanup failed: {str(e)}")


@router.get("/storage/verify-cleanup/{job_id}", summary="Verify Complete Cleanup for Print Job")
async def verify_print_job_cleanup(
    job_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.view_statistics"))
):
    """
    Verify that a specific print job's files and folders have been completely removed
    
    This endpoint helps ensure that QA completion properly cleaned up all files
    and prevents storage bloat from incomplete cleanup operations.
    """
    try:
        # Get print job from database
        print_job = crud_print_job.get(db, id=job_id)
        if not print_job:
            raise HTTPException(status_code=404, detail="Print job not found")
        
        # Verify cleanup status
        verification = card_file_manager.verify_complete_cleanup(
            print_job_id=str(print_job.id),
            created_at=print_job.submitted_at
        )
        
        # Get database cleanup metadata
        db_cleanup_status = print_job.generation_metadata or {}
        qa_completed = print_job.quality_check_result is not None
        should_be_cleaned = (qa_completed and 
                           print_job.quality_check_result == QualityCheckResult.PASSED)
        
        return {
            "print_job_id": str(job_id),
            "verification_result": verification,
            "database_status": {
                "qa_completed": qa_completed,
                "qa_result": print_job.quality_check_result,
                "should_be_cleaned": should_be_cleaned,
                "files_deleted_after_qa": db_cleanup_status.get("files_deleted_after_qa", False),
                "folder_completely_removed": db_cleanup_status.get("folder_completely_removed", False),
                "cleanup_failed": db_cleanup_status.get("cleanup_failed", False),
                "manual_cleanup_needed": db_cleanup_status.get("manual_cleanup_needed", False)
            },
            "consistency_check": {
                "cleanup_matches_expectation": (
                    verification.get("completely_removed", False) == should_be_cleaned
                ),
                "database_metadata_accurate": (
                    db_cleanup_status.get("folder_completely_removed", False) == 
                    verification.get("completely_removed", False)
                ),
                "no_bloat_detected": verification.get("status") == "CLEANUP_COMPLETE"
            }
        }
        
    except Exception as e:
        logger.error(f"Error verifying cleanup for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Error verifying cleanup status") 