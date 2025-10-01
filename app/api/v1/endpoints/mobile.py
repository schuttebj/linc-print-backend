"""
Mobile App API Endpoints for Madagascar Digital License
Provides secure access to license data for mobile applications
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import hashlib
import hmac
import json
from typing import Dict, Any, Optional
import os

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.person import Person
from app.models.license import License
from app.crud.crud_license import crud_license
from app.crud import person as crud_person

router = APIRouter()

# Secret key for QR signature (should be in environment variable in production)
QR_SECRET_KEY = os.getenv("QR_SECRET_KEY", "madagascar-license-qr-secret-2025")

@router.get("/license/{id_number}", summary="Get License by ID Number (Public Access)")
async def get_license_by_id(
    id_number: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get digital license by Madagascar ID number (no authentication required)
    
    This allows citizens to access their own license using just their ID number.
    Perfect for mobile app access where citizens don't have backend accounts.
    
    Flow:
    1. Citizen enters their Madagascar ID number
    2. Find person with that ID
    3. Get active licenses for that person
    4. Return latest license with all details
    """
    
    # Find person by their ID document number
    from app.crud import person_alias, person as crud_person
    
    # Try to find person by their ID document
    found_alias = person_alias.get_by_document_number(
        db=db,
        document_number=id_number.strip()
    )
    
    if not found_alias:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No person record found for ID {id_number}. Please verify your ID number."
        )
    
    person = crud_person.get(db=db, id=found_alias.person_id)
    
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person record not found"
        )
    
    # Get active licenses for this person
    licenses = crud_license.get_by_person_id(
        db=db, 
        person_id=person.id, 
        active_only=True,
        skip=0,
        limit=1000
    )
    
    if not licenses:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active licenses found for this person"
        )
    
    # Get the latest license
    latest_license = max(licenses, key=lambda l: l.issue_date)
    
    # Build photo URL
    photo_url = None
    if latest_license.photo_file_path:
        # Use the backend base URL
        photo_url = f"/api/v1/applications/files/{latest_license.photo_file_path}"
    
    # Generate a display number from license ID or use captured number
    license_display_number = (
        latest_license.captured_from_license_number or 
        latest_license.legacy_license_number or 
        f"DL-{str(latest_license.id)[:8].upper()}"  # Use first 8 chars of UUID if no number
    )
    
    # Prepare mobile-optimized response
    return {
        "license_id": str(latest_license.id),
        "license_number": license_display_number,
        "holder_name": f"{person.first_name} {person.surname}",
        "holder_photo_url": photo_url,
        "birth_date": person.birth_date.isoformat() if person.birth_date else None,
        "issue_date": latest_license.issue_date.isoformat() if latest_license.issue_date else None,
        "expiry_date": latest_license.expiry_date.isoformat() if latest_license.expiry_date else None,
        "categories": [latest_license.category.value] if latest_license.category else [],
        "restrictions": latest_license.restrictions or {},
        "status": latest_license.status.value if latest_license.status else "UNKNOWN",
        "is_valid": latest_license.status.value == "ACTIVE" if latest_license.status else False,
        "has_professional_permit": latest_license.has_professional_permit or False,
        "issuing_location": latest_license.issuing_location.name if latest_license.issuing_location else None,
        "last_synced": datetime.utcnow().isoformat() + "Z"
    }


@router.post("/generate-qr/{id_number}", summary="Generate Time-Limited Verification QR Code")
async def generate_verification_qr(
    id_number: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Generate a time-limited QR code for law enforcement verification
    QR expires after 30 seconds for security
    No authentication required - citizen just needs their ID number
    """
    
    # Find person by their ID document number
    from app.crud import person_alias, person as crud_person
    
    found_alias = person_alias.get_by_document_number(
        db=db,
        document_number=id_number.strip()
    )
    
    if not found_alias:
        raise HTTPException(status_code=404, detail="Person not found")
    
    person = crud_person.get(db=db, id=found_alias.person_id)
    
    # Get active licenses
    licenses = crud_license.get_by_person_id(
        db=db, 
        person_id=person.id, 
        active_only=True
    )
    
    if not licenses:
        raise HTTPException(status_code=404, detail="No active license")
    
    latest_license = max(licenses, key=lambda l: l.issue_date)
    
    # Generate a display number from license ID or use captured number
    license_display_number = (
        latest_license.captured_from_license_number or 
        latest_license.legacy_license_number or 
        f"DL-{str(latest_license.id)[:8].upper()}"
    )
    
    # Generate QR payload with timestamp
    timestamp = datetime.utcnow()
    expires_at = timestamp + timedelta(seconds=30)
    
    qr_payload = {
        "license_number": license_display_number,
        "timestamp": timestamp.isoformat() + "Z",
        "expires_at": expires_at.isoformat() + "Z",
        "status": latest_license.status.value if latest_license.status else "UNKNOWN",
        "holder_name": f"{person.first_name} {person.surname}",
        "categories": [latest_license.category.value] if latest_license.category else []
    }
    
    # Create HMAC signature
    payload_string = json.dumps(qr_payload, sort_keys=True)
    signature = hmac.new(
        QR_SECRET_KEY.encode(),
        payload_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    qr_payload["signature"] = signature
    
    return {
        "qr_data": qr_payload,
        "qr_json": json.dumps(qr_payload),
        "expires_in_seconds": 30,
        "generated_at": timestamp.isoformat() + "Z"
    }


@router.post("/verify-qr", summary="Verify QR Code from Mobile App")
async def verify_mobile_qr(
    qr_data: Dict[str, Any],
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Verify a scanned QR code from citizen's mobile app
    Used by law enforcement to validate digital licenses
    """
    
    # Verify signature
    signature = qr_data.pop("signature", None)
    if not signature:
        raise HTTPException(status_code=400, detail="Missing signature")
    
    payload_string = json.dumps(qr_data, sort_keys=True)
    expected_signature = hmac.new(
        QR_SECRET_KEY.encode(),
        payload_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if signature != expected_signature:
        raise HTTPException(status_code=401, detail="Invalid signature - QR code may be fake")
    
    # Check expiry
    try:
        expires_at = datetime.fromisoformat(qr_data["expires_at"].replace("Z", ""))
        if datetime.utcnow() > expires_at:
            raise HTTPException(status_code=401, detail="QR code expired - ask holder to regenerate")
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid QR data: {str(e)}")
    
    # Verify license in database (get current status)
    license_number = qr_data.get("license_number")
    if not license_number:
        raise HTTPException(status_code=400, detail="Invalid license number in QR")
    
    # Search for license by number (could be captured, legacy, or UUID format)
    license_obj = None
    
    # Try captured_from_license_number
    license_obj = db.query(License).filter(
        License.captured_from_license_number == license_number
    ).first()
    
    # Try legacy_license_number
    if not license_obj:
        license_obj = db.query(License).filter(
            License.legacy_license_number == license_number
        ).first()
    
    # Try extracting UUID from DL- format
    if not license_obj and license_number.startswith("DL-"):
        uuid_part = license_number[3:]  # Remove "DL-" prefix
        # Search for licenses where UUID starts with this
        from sqlalchemy import cast, String
        license_obj = db.query(License).filter(
            cast(License.id, String).ilike(f"{uuid_part}%")
        ).first()
    
    if not license_obj:
        raise HTTPException(status_code=404, detail="License not found in system")
    
    # Get person for photo
    person = db.query(Person).filter(Person.id == license_obj.person_id).first()
    
    # Build photo URL
    photo_url = None
    if license_obj.photo_file_path:
        photo_url = f"/api/v1/applications/files/{license_obj.photo_file_path}"
    
    # Check if status changed since QR was generated
    warning = None
    if license_obj.status.value != qr_data.get("status"):
        warning = f"STATUS CHANGED: Was {qr_data.get('status')}, now {license_obj.status.value}"
    
    # Return verification result
    return {
        "valid": True,
        "license_number": license_number,
        "holder_name": f"{person.first_name} {person.surname}" if person else qr_data.get("holder_name"),
        "current_status": license_obj.status.value,
        "categories": [license_obj.category.value] if license_obj.category else [],
        "restrictions": license_obj.restrictions or {},
        "photo_url": photo_url,
        "verified_at": datetime.utcnow().isoformat() + "Z",
        "warning": warning
    }


@router.get("/health", summary="Mobile API Health Check")
async def health_check():
    """Health check for mobile endpoints"""
    return {
        "status": "healthy",
        "service": "mobile_api",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
