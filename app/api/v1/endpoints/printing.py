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

from fastapi import APIRouter, Depends, HTTPException, status, Path, Query, Response, Body
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.core.audit_decorators import audit_create, audit_update, audit_delete
from app.crud.crud_printing import crud_print_job, crud_print_queue
from app.crud.crud_application import crud_application
from app.crud.crud_license import crud_license
from app.crud.crud_person import person as crud_person
from app.crud.crud_card import crud_card
from app.models.user import User
from app.models.application import Application
from app.models.license import License
from app.models.card import CardNumberGenerator, Card, CardType, CardStatus, CardLicense, ProductionStatus
from app.models.enums import ApplicationStatus, LicenseCategory, BiometricDataType
from app.models.printing import PrintJobStatus, PrintJobPriority, QualityCheckResult, PrintJobStatusHistory, PrintJob, PrintJobApplication
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


def get_person_primary_id_number(person) -> str:
    """
    Get the primary ID number from a person's aliases (identification documents)
    """
    if not person or not hasattr(person, 'aliases'):
        return None
    
    # Look for primary identification document
    for alias in person.aliases:
        if alias.is_primary and alias.is_current:
            return alias.document_number
    
    # If no primary found, get the first current document
    for alias in person.aliases:
        if alias.is_current:
            return alias.document_number
    
    return None


def serialize_print_job_response(print_job: PrintJob) -> PrintJobResponse:
    """
    Helper function to properly serialize PrintJob to PrintJobResponse
    Handles the applications field serialization manually to avoid Pydantic errors
    """
    # Prepare applications data manually
    applications_data = []
    if hasattr(print_job, 'job_applications') and print_job.job_applications:
        for job_app in print_job.job_applications:
            app_data = {
                "application_id": job_app.application_id,
                "application_number": job_app.application.application_number if job_app.application else "Unknown",
                "application_type": job_app.application.application_type.value if job_app.application else "Unknown",
                "is_primary": job_app.is_primary,
                "added_at": job_app.added_at
            }
            applications_data.append(app_data)
    
    # Create response data manually to avoid Pydantic serialization issues
    response_data = {
        "id": print_job.id,
        "job_number": print_job.job_number,
        "status": print_job.status,
        "priority": print_job.priority,
        "queue_position": print_job.queue_position,
        "person_id": print_job.person_id,
        "person_name": f"{print_job.person.first_name} {print_job.person.surname}" if print_job.person else None,
        "person_id_number": get_person_primary_id_number(print_job.person) if print_job.person else None,
        "print_location_id": print_job.print_location_id,
        "print_location_name": print_job.print_location.name if print_job.print_location else None,
        "assigned_to_user_id": print_job.assigned_to_user_id,
        "assigned_to_user_name": f"{print_job.assigned_to_user.first_name} {print_job.assigned_to_user.last_name}" if print_job.assigned_to_user else None,
        "card_number": print_job.card_number,
        "card_template": print_job.card_template,
        "submitted_at": print_job.submitted_at,
        "assigned_at": print_job.assigned_at,
        "printing_started_at": print_job.printing_started_at,
        "printing_completed_at": print_job.printing_completed_at,
        "completed_at": print_job.completed_at,
        "quality_check_result": print_job.quality_check_result,
        "quality_check_notes": print_job.quality_check_notes,
        "pdf_files_generated": print_job.pdf_files_generated,
        "original_print_job_id": print_job.original_print_job_id,
        "reprint_reason": print_job.reprint_reason,
        "reprint_count": print_job.reprint_count,
        "applications": applications_data
    }
    
    return PrintJobResponse(**response_data)


def serialize_print_job_detail_response(print_job: PrintJob) -> PrintJobDetailResponse:
    """
    Helper function to properly serialize PrintJob to PrintJobDetailResponse
    Extends the basic response with detailed fields and manual serialization
    """
    # Start with the basic serialization
    basic_data = serialize_print_job_response(print_job).__dict__
    
    # Add detailed fields manually
    detail_data = {
        **basic_data,
        
        # User information with proper name resolution
        "assigned_to_user_id": print_job.assigned_to_user_id,
        "assigned_to_user_name": print_job.assigned_to_user.full_name if print_job.assigned_to_user else None,
        "quality_check_by_user_id": print_job.quality_check_by_user_id,
        "quality_check_by_user_name": print_job.quality_check_by_user.full_name if print_job.quality_check_by_user else None,
        
        # Detailed timing
        "quality_check_started_at": print_job.quality_check_started_at,
        "quality_check_completed_at": print_job.quality_check_completed_at,
        "collection_ready_at": print_job.collection_ready_at,
        
        # Production details
        "production_batch_id": print_job.production_batch_id,
        "production_notes": print_job.production_notes,
        "printer_hardware_id": print_job.printer_hardware_id,
        
        # File paths
        "pdf_front_path": print_job.pdf_front_path,
        "pdf_back_path": print_job.pdf_back_path,
        "pdf_combined_path": print_job.pdf_combined_path,
        
        # Queue management (if available)
        "queue_changes": getattr(print_job, 'queue_changes', None),
        
        # Licenses (if available)
        "licenses": getattr(print_job, 'licenses', []),
    }
    
    # Manually prepare status history
    status_history_data = []
    if hasattr(print_job, 'status_history') and print_job.status_history:
        for history in print_job.status_history:
            history_data = {
                "id": history.id,
                "from_status": history.from_status,
                "to_status": history.to_status,
                "changed_at": history.changed_at,
                "changed_by_user_name": history.changed_by_user.full_name if history.changed_by_user else "System",
                "change_reason": history.change_reason,
                "change_notes": history.change_notes,
            }
            status_history_data.append(history_data)
    
    detail_data["status_history"] = status_history_data
    
    # Create response object manually
    return PrintJobDetailResponse(**detail_data)


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
        
        # Find person by ID number through their alias (document) - same pattern as approval/POS
        from app.crud import person_alias
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
                detail=f"No person found with ID number: {id_number}"
            )
        
        # Get the person from the alias
        person = crud_person.get(db=db, id=found_person_alias.person_id)
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person record not found"
            )
        
        logger.info(f"Found person: {person.first_name} {person.surname} (ID: {person.id})")
        
        # Get all licenses for this person
        all_licenses = crud_license.get_by_person_id(db, person_id=person.id, active_only=True)
        logger.info(f"Found {len(all_licenses)} active licenses for person")
        
        # Filter licenses into card-eligible and non-eligible
        learners_categories = [LicenseCategory.L1, LicenseCategory.L2, LicenseCategory.L3]
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
        
        # Check which approved applications are for card-eligible license categories
        learners_categories = [LicenseCategory.L1, LicenseCategory.L2, LicenseCategory.L3]
        card_eligible_applications = [
            app for app in approved_applications 
            if app.license_category and app.license_category not in learners_categories
        ]
        
        logger.info(f"Card-eligible applications: {len(card_eligible_applications)}")
        for app in card_eligible_applications:
            logger.info(f"  - Application {app.application_number}: Category {app.license_category.value if app.license_category else 'None'}")
        
        # Extract biometric data from applications for card printing
        biometric_data = {
            "photo_url": None,
            "photo_path": None,
            "signature_url": None,
            "signature_path": None,
            "fingerprint_url": None,
            "fingerprint_path": None
        }
        
        # Look through all approved applications for biometric data
        for app in approved_applications:
            if hasattr(app, 'biometric_data') and app.biometric_data:
                for bio_data in app.biometric_data:
                    if bio_data.data_type == BiometricDataType.PHOTO:
                        biometric_data["photo_url"] = None  # URL not available in ApplicationBiometricData model
                        biometric_data["photo_path"] = bio_data.file_path
                    elif bio_data.data_type == BiometricDataType.SIGNATURE:
                        biometric_data["signature_url"] = None  # URL not available in ApplicationBiometricData model
                        biometric_data["signature_path"] = bio_data.file_path
                    elif bio_data.data_type == BiometricDataType.FINGERPRINT:
                        biometric_data["fingerprint_url"] = None  # URL not available in ApplicationBiometricData model
                        biometric_data["fingerprint_path"] = bio_data.file_path
        
        # Check print eligibility - consider BOTH existing licenses AND approved applications
        can_order_card = len(card_eligible_licenses) > 0 or len(card_eligible_applications) > 0
        eligibility_issues = []
        
        if len(card_eligible_licenses) == 0 and len(card_eligible_applications) == 0:
            eligibility_issues.append("No card-eligible licenses or approved applications found")
        
        logger.info(f"Card ordering eligibility check:")
        logger.info(f"  - Existing card-eligible licenses: {len(card_eligible_licenses)}")
        logger.info(f"  - Approved card-eligible applications: {len(card_eligible_applications)}")
        logger.info(f"  - Can order card: {can_order_card}")
        logger.info(f"  - Issues: {eligibility_issues}")
        
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
                "last_name": person.surname,  # Use surname field from Person model
                "middle_name": person.middle_name,
                "id_number": found_person_alias.document_number,  # Use the actual ID number from alias
                "birth_date": person.birth_date.isoformat() if person.birth_date else None,
                "nationality_code": person.nationality_code,  # Use nationality_code field
                "person_nature": person.person_nature,  # Gender info
                "email_address": person.email_address,
                "cell_phone": person.cell_phone,
                "is_active": person.is_active
                # Note: photo_path and signature_path don't exist in Person model yet
                # TODO: Add biometric data fields when Persons module expands
            },
            "biometric_data": biometric_data,
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
                    "license_category": app.license_category.value if app.license_category else None,
                    "status": app.status.value,
                    "application_date": app.application_date.isoformat(),
                    "approval_date": app.approval_date.isoformat() if app.approval_date else None,
                    "photo_captured": app.photo_captured,
                    "signature_captured": app.signature_captured,
                    "fingerprint_captured": app.fingerprint_captured,
                    "is_card_eligible": app.license_category and app.license_category not in learners_categories
                }
                for app in approved_applications
            ],
            "print_eligibility": {
                "can_order_card": can_order_card,
                "issues": eligibility_issues,
                "total_licenses": len(all_licenses),
                "card_eligible_count": len(card_eligible_licenses),
                "learners_permit_count": len(learners_permits),
                "card_eligible_applications_count": len(card_eligible_applications),
                "eligible_sources": {
                    "existing_licenses": len(card_eligible_licenses) > 0,
                    "approved_applications": len(card_eligible_applications) > 0
                }
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
@audit_create(resource_type="PRINT_JOB", screen_reference="PrintJobCreation")
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
        
        # Get primary application with biometric data
        logger.info(f"Looking up application with ID: {request.application_id}")
        from sqlalchemy.orm import joinedload
        application = db.query(Application).options(
            joinedload(Application.biometric_data),
            joinedload(Application.person),
            joinedload(Application.location)
        ).filter(Application.id == request.application_id).first()
        
        if not application:
            logger.error(f"Application not found with ID: {request.application_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application not found with ID: {request.application_id}"
            )
        
        logger.info(f"Found application: {application.application_number} (status: {application.status})")
        
        # Debug: Check if biometric data was loaded
        logger.info(f"Application biometric_data loaded: {hasattr(application, 'biometric_data')}")
        if hasattr(application, 'biometric_data') and application.biometric_data:
            logger.info(f"Found {len(application.biometric_data)} biometric records in application")
            for i, bio_data in enumerate(application.biometric_data):
                logger.info(f"Biometric record {i}: type={bio_data.data_type}, file_path={bio_data.file_path}")
        else:
            logger.info("No biometric data found in loaded application")
        
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
        
        # Get person details with all related data (aliases and addresses)
        person = crud_person.get_with_details(db, id=application.person_id)
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found"
            )
        
        # Extract biometric data from the application for card printing
        biometric_data = {
            "photo_url": None,
            "photo_path": None,
            "signature_url": None,
            "signature_path": None,
            "fingerprint_url": None,
            "fingerprint_path": None
        }
        
        # Look through application biometric data
        logger.info(f"Checking application biometric data...")
        if hasattr(application, 'biometric_data') and application.biometric_data:
            logger.info(f"Found {len(application.biometric_data)} biometric data records")
            for i, bio_data in enumerate(application.biometric_data):
                logger.info(f"Biometric record {i}: type={bio_data.data_type}, file_path={bio_data.file_path}")
                logger.info(f"  bio_data.data_type type: {type(bio_data.data_type)}")
                logger.info(f"  BiometricDataType.PHOTO: {BiometricDataType.PHOTO}, type: {type(BiometricDataType.PHOTO)}")
                logger.info(f"  Comparison result: {bio_data.data_type == BiometricDataType.PHOTO}")
                
                if bio_data.data_type == BiometricDataType.PHOTO:
                    # Check if there's a license_ready version in metadata (optimized for card printing)
                    photo_path = bio_data.file_path
                    license_ready_photo_base64 = None
                    
                    logger.info(f"Photo metadata: {bio_data.metadata}")
                    if bio_data.metadata and isinstance(bio_data.metadata, dict):
                        logger.info(f"Photo metadata keys: {list(bio_data.metadata.keys())}")
                        license_ready = bio_data.metadata.get('license_ready_version', {})
                        logger.info(f"License ready info: {license_ready}")
                        if license_ready.get('file_path'):
                            photo_path = license_ready['file_path']
                            logger.info(f"Using license_ready photo: {photo_path}")
                            
                            # Also read license_ready photo as base64 for barcode generation
                            try:
                                from app.services.card_file_manager import card_file_manager
                                license_ready_photo_base64 = card_file_manager.read_file_as_base64(license_ready['file_path'])
                                logger.info(f"Read license_ready photo as base64: {len(license_ready_photo_base64)} chars")
                            except Exception as e:
                                logger.warning(f"Could not read license_ready photo as base64: {e}")
                        else:
                            logger.info("No license_ready file_path found in metadata")
                    else:
                        logger.info("No metadata found for photo biometric data")
                    
                    biometric_data["photo_url"] = None  # URL not available in ApplicationBiometricData model
                    biometric_data["photo_path"] = photo_path
                    biometric_data["license_ready_photo_base64"] = license_ready_photo_base64
                    logger.info(f"Set photo_path to: {photo_path}")
                    if license_ready_photo_base64:
                        logger.info(f"Set license_ready_photo_base64: {len(license_ready_photo_base64)} chars")
                    else:
                        logger.info("No license_ready_photo_base64 available")
                elif bio_data.data_type == BiometricDataType.SIGNATURE:
                    biometric_data["signature_url"] = None  # URL not available in ApplicationBiometricData model
                    biometric_data["signature_path"] = bio_data.file_path
                    logger.info(f"Set signature_path to: {bio_data.file_path}")
                elif bio_data.data_type == BiometricDataType.FINGERPRINT:
                    biometric_data["fingerprint_url"] = None  # URL not available in ApplicationBiometricData model
                    biometric_data["fingerprint_path"] = bio_data.file_path
                    logger.info(f"Set fingerprint_path to: {bio_data.file_path}")
                else:
                    logger.warning(f"Unknown biometric data type: {bio_data.data_type} (type: {type(bio_data.data_type)})")
        else:
            logger.info(f"No biometric data found for application. hasattr={hasattr(application, 'biometric_data')}, biometric_data={getattr(application, 'biometric_data', 'MISSING')}")
        
        # Debug: Log what biometric data was actually collected
        logger.info(f"Biometric data after processing:")
        for key, value in biometric_data.items():
            logger.info(f"  {key}: {value}")
        
        # Get all licenses for person (excluding learners permits)
        logger.info(f"Getting licenses for person {application.person_id}")
        person_licenses = crud_license.get_by_person_id(
            db, 
            person_id=application.person_id,
            active_only=True
        )
        logger.info(f"Found {len(person_licenses)} total licenses for person {application.person_id}")
        
        # Filter out learners permits (they don't go on cards)
        learners_categories = [LicenseCategory.L1, LicenseCategory.L2, LicenseCategory.L3]
        card_licenses = [
            license for license in person_licenses 
            if license.category not in learners_categories
        ]
        logger.info(f"Found {len(card_licenses)} card-eligible licenses (excluding learners permits: {[cat.value for cat in learners_categories]})")
        
        # Check if the approved application is for a card-eligible category
        application_is_card_eligible = (
            application.license_category and 
            application.license_category not in learners_categories
        )
        logger.info(f"Application {application.application_number} is card-eligible: {application_is_card_eligible} (category: {application.license_category.value if application.license_category else 'None'})")
        
        # Allow print job creation if there are existing card-eligible licenses OR the application is for a card-eligible category
        if not card_licenses and not application_is_card_eligible:
            logger.error(f"No valid licenses found for card printing - person {application.person_id} has {len(person_licenses)} total licenses but none are card-eligible, and application is not for a card-eligible category")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid licenses found for card printing - neither existing licenses nor the application qualify for card printing"
            )
        
        logger.info(f"Print job validation passed - existing card licenses: {len(card_licenses)}, application card-eligible: {application_is_card_eligible}")
        
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
        
        # Import CardType enum and use Card.generate_card_number (not CardNumberGenerator.generate_card_number)
        card_number = Card.generate_card_number(
            location_code, sequence_number, 
            card_type=CardType.STANDARD  # Use CardType enum, not string
        )
        logger.info(f"Generated card number: {card_number}")
        
        # Prepare license data for card generation
        logger.info(f"Preparing license data for {len(card_licenses)} existing licenses")
        
        # Start with existing card-eligible licenses
        licenses_for_card = [
            {
                "id": str(license.id),
                "category": license.category.value,
                "issue_date": license.issue_date.isoformat(),
                "expiry_date": license.expiry_date.isoformat() if license.expiry_date else None,
                "restrictions": license.restrictions,
                "status": license.status.value
            }
            for license in card_licenses
        ]
        
        # If no existing card-eligible licenses but application is for a card-eligible category,
        # add the application's license information (it will become a license when printed)
        if not card_licenses and application_is_card_eligible:
            logger.info(f"Adding application license data for category {application.license_category.value}")
            # Calculate issue and expiry dates for new license
            issue_date = datetime.now()
            expiry_date = issue_date + timedelta(days=365 * 10)  # 10 years validity
            
            licenses_for_card.append({
                "id": str(application.id),  # Use application ID as temporary license ID
                "category": application.license_category.value,
                "issue_date": issue_date.isoformat(),
                "expiry_date": expiry_date.isoformat(),
                "restrictions": "0",  # Default no restrictions
                "status": "ACTIVE"  # Will be active once issued
            })
        
        license_data = {
            "licenses": licenses_for_card,
            "total_licenses": len(licenses_for_card),
            "card_template": request.card_template,
            "card_number": card_number,  # Add the generated card number with location code + sequence + checksum
            "license_ready_photo_base64": biometric_data.get("license_ready_photo_base64")  # Add license_ready 8-bit photo for barcode
        }
        
        logger.info(f"Final license data contains {len(licenses_for_card)} licenses for card generation")
        
        # Prepare person data for card generation
        logger.info(f"Preparing person data for person {person.id}")
        
        # Get person ID number from their primary alias
        person_id_number = None
        if person.aliases:
            primary_alias = next((alias for alias in person.aliases if alias.is_primary), person.aliases[0] if person.aliases else None)
            if primary_alias:
                person_id_number = primary_alias.document_number
        
        # Get primary address if available
        primary_address = None
        if person.addresses:
            primary_address = next((addr for addr in person.addresses if addr.is_primary), person.addresses[0] if person.addresses else None)
        
        person_data = {
            "id": str(person.id),
            "first_name": person.first_name,
            "last_name": person.surname,  # Use surname field from Person model
            "middle_name": person.middle_name,
            "date_of_birth": person.birth_date.isoformat() if person.birth_date else None,
            "id_number": person_id_number,  # Use ID number from alias
            "nationality_code": person.nationality_code,  # Use nationality_code field
            "person_nature": person.person_nature,  # Gender info
            "email_address": person.email_address,
            "cell_phone": person.cell_phone,
            "is_active": person.is_active,
            # Address information
            "address": {
                "street_line1": primary_address.street_line1 if primary_address else "",
                "street_line2": primary_address.street_line2 if primary_address else "",
                "locality": primary_address.locality if primary_address else "",
                "town": primary_address.town if primary_address else "",
                "postal_code": primary_address.postal_code if primary_address else "",
                "province_code": primary_address.province_code if primary_address else ""
            },
            # Biometric data (from applications, not person directly)
            "biometric_data": {
                "photo_url": biometric_data.get("photo_url"),
                "photo_path": biometric_data.get("photo_path"),
                "signature_url": biometric_data.get("signature_url"),
                "signature_path": biometric_data.get("signature_path"),
                "fingerprint_url": biometric_data.get("fingerprint_url"),
                "fingerprint_path": biometric_data.get("fingerprint_path")
            }
        }
        
        # Debug: Log the final biometric data being passed to card generator
        logger.info(f"Final person_data biometric paths:")
        logger.info(f"  photo_path: {biometric_data.get('photo_path')}")
        logger.info(f"  signature_path: {biometric_data.get('signature_path')}")
        logger.info(f"  fingerprint_path: {biometric_data.get('fingerprint_path')}")
        
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
        
        # Create the actual Card entity that represents the physical card
        try:
            logger.info(f"Creating Card entity for print job {print_job.id}")
            
            # Calculate card validity period (5 years for standard cards)
            valid_from = datetime.utcnow()
            valid_until = valid_from + timedelta(days=365 * 5)  # 5 years
            
            # Create Card entity
            card = Card(
                card_number=card_number,
                person_id=application.person_id,
                card_type=CardType.STANDARD,
                status=CardStatus.PENDING_ORDER,  # Will change as print job progresses
                production_status=ProductionStatus.NOT_STARTED,
                valid_from=valid_from,
                valid_until=valid_until,
                created_from_application_id=request.application_id,
                production_location_id=print_location_id,
                collection_location_id=print_location_id,  # Same location for collection
                is_active=True,
                created_by=current_user.id,
                created_at=datetime.utcnow()
            )
            
            db.add(card)
            db.flush()  # Get card ID
            logger.info(f"Created Card entity with ID: {card.id}")
            
            # Create CardLicense associations for all card-eligible licenses
            for i, license in enumerate(card_licenses):
                card_license = CardLicense(
                    card_id=card.id,
                    license_id=license.id,
                    is_primary=(i == 0),  # First license is primary
                    added_by=current_user.id,
                    added_at=datetime.utcnow()
                )
                db.add(card_license)
                logger.info(f"Associated license {license.category.value} with card {card.id}")
            
            logger.info(f"Card entity created successfully with {len(card_licenses)} license associations")
            
        except Exception as card_error:
            logger.error(f"Failed to create Card entity: {card_error}", exc_info=True)
            # Don't fail the print job creation if card creation fails
            # The print job can still proceed without the card entity
        
        # Update application status
        application.status = ApplicationStatus.SENT_TO_PRINTER
        application.print_job_id = print_job.id
        db.commit()
        
        # Reload print job with all necessary relationships for response
        db.refresh(print_job)
        print_job_with_relations = db.query(PrintJob).options(
            selectinload(PrintJob.job_applications).selectinload(PrintJobApplication.application),
            selectinload(PrintJob.person),
            selectinload(PrintJob.print_location),
            selectinload(PrintJob.primary_application)
        ).filter(PrintJob.id == print_job.id).first()
        
        # Manually construct the response to match schema expectations
        applications_data = []
        for job_app in print_job_with_relations.job_applications:
            app_data = {
                "application_id": job_app.application_id,
                "application_number": job_app.application.application_number,
                "application_type": job_app.application.application_type.value,
                "is_primary": job_app.is_primary,
                "added_at": job_app.added_at
            }
            applications_data.append(app_data)
        
        # Create response data manually to avoid Pydantic serialization issues
        response_data = {
            "id": print_job_with_relations.id,
            "job_number": print_job_with_relations.job_number,
            "status": print_job_with_relations.status,
            "priority": print_job_with_relations.priority,
            "queue_position": print_job_with_relations.queue_position,
            "person_id": print_job_with_relations.person_id,
            "person_name": f"{print_job_with_relations.person.first_name} {print_job_with_relations.person.surname}" if print_job_with_relations.person else None,
            "print_location_id": print_job_with_relations.print_location_id,
            "print_location_name": print_job_with_relations.print_location.name if print_job_with_relations.print_location else None,
            "card_number": print_job_with_relations.card_number,
            "card_template": print_job_with_relations.card_template,
            "submitted_at": print_job_with_relations.submitted_at,
            "assigned_at": print_job_with_relations.assigned_at,
            "printing_started_at": print_job_with_relations.printing_started_at,
            "printing_completed_at": print_job_with_relations.printing_completed_at,
            "completed_at": print_job_with_relations.completed_at,
            "quality_check_result": print_job_with_relations.quality_check_result,
            "quality_check_notes": print_job_with_relations.quality_check_notes,
            "pdf_files_generated": print_job_with_relations.pdf_files_generated,
            "original_print_job_id": print_job_with_relations.original_print_job_id,
            "reprint_reason": print_job_with_relations.reprint_reason,
            "reprint_count": print_job_with_relations.reprint_count,
            "applications": applications_data
        }
        
        return PrintJobResponse(**response_data)
        
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
        queued_jobs=[serialize_print_job_response(job) for job in queued_jobs],
        in_progress_jobs=[serialize_print_job_response(job) for job in in_progress_jobs],
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
    
    return serialize_print_job_response(print_job)


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
    
    return serialize_print_job_response(print_job)


@router.post("/jobs/{job_id}/start", response_model=PrintJobResponse, summary="Start Printing")
@audit_update(
    resource_type="PRINT_JOB", 
    screen_reference="PrintingWorkflow",
    get_old_data=lambda db, job_id: db.query(crud_print_job.model).filter(crud_print_job.model.id == job_id).first()
)
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
    
    return serialize_print_job_response(print_job)


@router.post("/jobs/{job_id}/complete", response_model=PrintJobResponse, summary="Complete Printing")
@audit_update(
    resource_type="PRINT_JOB", 
    screen_reference="PrintingWorkflow",
    get_old_data=lambda db, job_id: db.query(crud_print_job.model).filter(crud_print_job.model.id == job_id).first()
)
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
    
    return serialize_print_job_response(print_job)


# Quality Assurance
@router.post("/jobs/{job_id}/qa-start", response_model=PrintJobResponse, summary="Start Quality Check")
async def start_quality_check(
    job_id: UUID = Path(..., description="Print Job ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.quality_check"))
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
    
    return serialize_print_job_response(print_job)


@router.post("/jobs/{job_id}/quality-check", response_model=PrintJobResponse, summary="Quality Check")
@audit_update(
    resource_type="PRINT_JOB", 
    screen_reference="QualityControl",
    get_old_data=lambda db, job_id: db.query(crud_print_job.model).filter(crud_print_job.model.id == job_id).first()
)
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
    
    return serialize_print_job_response(print_job)


@router.post("/jobs/{job_id}/qa-complete", summary="Complete QA Review")
@audit_update(
    resource_type="PRINT_JOB", 
    screen_reference="QualityAssurance",
    get_old_data=lambda db, job_id: db.query(crud_print_job.model).filter(crud_print_job.model.id == job_id).first()
)
async def complete_qa_review(
    job_id: UUID = Path(..., description="Print Job ID"),
    request: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.quality_check"))
):
    """
    Complete quality assurance review for a print job
    
    Accepts outcomes:
    - PASSED: Mark job as completed and application ready for collection
    - FAILED_PRINTING: Send back to print queue for reprinting
    - FAILED_DAMAGE: Mark as defective for handling
    
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
    
    # Validate job is in correct status
    if print_job.status != PrintJobStatus.PRINTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot perform QA on job with status {print_job.status}. Job must be PRINTED."
        )
    
    # Parse request data
    outcome = request.get('outcome')
    notes = request.get('notes', '')
    location_id = request.get('location_id')
    
    # Validate outcome
    if outcome not in ['PASSED', 'FAILED_PRINTING', 'FAILED_DAMAGE']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid outcome. Must be PASSED, FAILED_PRINTING, or FAILED_DAMAGE"
        )
    
    # Map frontend outcomes to backend enum values
    qa_result_mapping = {
        'PASSED': QualityCheckResult.PASSED,
        'FAILED_PRINTING': QualityCheckResult.FAILED_PRINTING,
        'FAILED_DAMAGE': QualityCheckResult.FAILED_DAMAGE
    }
    
    qa_result = qa_result_mapping[outcome]
    
    # Require notes for failures
    if qa_result != QualityCheckResult.PASSED and (not notes or len(notes.strip()) < 5):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Detailed notes are required when quality check fails"
        )
    
    # Complete quality check
    print_job = crud_print_job.complete_quality_check(
        db=db,
        print_job=print_job,
        qa_result=qa_result,
        qa_notes=notes,
        current_user=current_user
    )
    
    # Prepare response message
    if qa_result == QualityCheckResult.PASSED:
        message = f"Quality assurance passed. Job {print_job.job_number} completed and application ready for collection."
    elif qa_result == QualityCheckResult.FAILED_PRINTING:
        message = f"Quality assurance failed - printing issues. Job {print_job.job_number} sent back to print queue."
    else:
        message = f"Quality assurance failed - card defective. Job {print_job.job_number} marked for handling."
    
    response_data = serialize_print_job_response(print_job)
    
    # Return response with message in a dict format
    return {
        "job": response_data,
        "message": message
    }


# QA Search (must come before jobs/{job_id} to avoid route conflict)
@router.get("/jobs/qa-search", response_model=PrintJobSearchResponse, summary="Search Print Jobs for QA")
async def search_print_jobs_for_qa(
    search_term: Optional[str] = Query(None, description="Search by person ID number, card number, or job number"),
    status: str = Query("PRINTED", description="Job status to search for"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("printing.quality_check"))
):
    """
    Search print jobs ready for quality assurance
    
    Single search field that searches across person ID number, card number, and job number.
    Only returns jobs in PRINTED status that are ready for QA.
    Results are filtered based on user's location access permissions.
    """
    # Build search criteria
    search_filters = PrintJobSearchFilters(
        status=[PrintJobStatus.PRINTED] if status == "PRINTED" else [PrintJobStatus(status)]
    )
    
    # Use the search term for all possible fields
    extra_filters = {}
    if search_term:
        extra_filters['search_term'] = search_term.strip()
    
    # Search with location filtering
    result = crud_print_job.search_for_qa(
        db=db,
        filters=search_filters,
        extra_filters=extra_filters,
        page=page,
        page_size=page_size,
        current_user=current_user
    )
    
    return result


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
    # Load print job with all necessary relationships for detailed response
    print_job = db.query(PrintJob).options(
        selectinload(PrintJob.person),
        selectinload(PrintJob.primary_application),
        selectinload(PrintJob.print_location),
        selectinload(PrintJob.assigned_to_user),
        selectinload(PrintJob.quality_check_by_user),
        selectinload(PrintJob.status_history).selectinload(PrintJobStatusHistory.changed_by_user),
        selectinload(PrintJob.job_applications).selectinload(PrintJobApplication.application)
    ).filter(PrintJob.id == job_id).first()
    
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
    
    return serialize_print_job_detail_response(print_job)


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
        jobs=[serialize_print_job_response(job) for job in page_jobs],
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
        
        # Generate card files with database session for production barcode API
        card_files = madagascar_card_generator.generate_card_files(print_job_data, db_session=db)
        
        # Update print job with new file data
        print_job.pdf_files_generated = True
        print_job.generation_metadata = {
            "generator_version": card_files.get("generator_version"),
            "generation_timestamp": card_files.get("generation_timestamp"),
            "regenerated_by": str(current_user.id),
            "regenerated_at": datetime.utcnow().isoformat(),
            "files_saved_to_disk": card_files.get("files_saved_to_disk", True),
            "files_generated": card_files.get("files_generated", True),
            "file_sizes": card_files.get("file_sizes", {})
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
        return serialize_print_job_response(print_job)
        
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