"""
License Management API Endpoints for Madagascar License System
Placeholder endpoints with mock data for testing application flow
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
import uuid
from datetime import datetime, timedelta

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/")
def get_licenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    status: Optional[str] = None,
    category: Optional[str] = None,
    location_id: Optional[str] = None
):
    """
    Get all issued licenses with filtering options
    PLACEHOLDER: Returns empty list for now
    """
    return {
        "licenses": [],
        "total": 0,
        "skip": skip,
        "limit": limit
    }


@router.get("/{license_id}")
def get_license(
    license_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get specific license by ID
    PLACEHOLDER: Returns mock data
    """
    # Mock license data
    return {
        "id": license_id,
        "license_number": f"MDG-{license_id[:6].upper()}",
        "person_id": f"person-{uuid.uuid4()}",
        "category": "B",
        "status": "ACTIVE",
        "issue_date": "2024-01-15",
        "expiry_date": "2029-01-15",
        "location_id": current_user.primary_location_id or "loc-001",
        "restrictions": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }


@router.get("/active")
def get_active_licenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    location_id: Optional[str] = None
):
    """
    Get all active licenses ready for printing/collection
    PLACEHOLDER: Returns empty list
    """
    return {
        "active_licenses": [],
        "total": 0,
        "location_id": location_id or current_user.primary_location_id
    }


@router.get("/pending-activation")
def get_pending_activation_licenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    location_id: Optional[str] = None
):
    """
    Get licenses pending activation from approved applications
    PLACEHOLDER: Returns empty list
    """
    return {
        "pending_licenses": [],
        "total": 0,
        "location_id": location_id or current_user.primary_location_id
    }


@router.get("/person/{person_id}/current")
def get_person_current_licenses(
    person_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current valid licenses for a person (for verification)
    PLACEHOLDER: Returns empty list
    """
    return {
        "person_id": person_id,
        "current_licenses": [],
        "has_active_licenses": False,
        "categories": []
    }


@router.get("/person/{person_id}")
def get_person_all_licenses(
    person_id: str,
    include_expired: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all licenses for a person (including expired if requested)
    PLACEHOLDER: Returns empty list
    """
    return {
        "person_id": person_id,
        "licenses": [],
        "include_expired": include_expired,
        "total": 0
    }


@router.post("/activate/{application_id}")
def activate_license_from_application(
    application_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Activate a license from an approved application
    PLACEHOLDER: Returns mock success
    """
    # Generate mock license number
    license_number = f"MDG-{application_id[:6].upper()}"
    license_id = str(uuid.uuid4())
    
    return {
        "success": True,
        "license_id": license_id,
        "license_number": license_number,
        "message": f"License {license_number} activated successfully",
        "activated_at": datetime.utcnow().isoformat()
    }


@router.post("/{license_id}/suspend")
def suspend_license(
    license_id: str,
    suspension_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Suspend a license
    PLACEHOLDER: Returns mock success
    """
    reason = suspension_data.get("reason", "Administrative action")
    notes = suspension_data.get("notes", "")
    
    return {
        "success": True,
        "message": f"License {license_id} suspended: {reason}",
        "suspended_at": datetime.utcnow().isoformat(),
        "reason": reason,
        "notes": notes
    }


@router.post("/{license_id}/reactivate")
def reactivate_license(
    license_id: str,
    reactivation_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reactivate a suspended license
    PLACEHOLDER: Returns mock success
    """
    notes = reactivation_data.get("notes", "")
    
    return {
        "success": True,
        "message": f"License {license_id} reactivated",
        "reactivated_at": datetime.utcnow().isoformat(),
        "notes": notes
    }


@router.post("/{license_id}/renew")
def renew_license(
    license_id: str,
    renewal_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Renew a license (creates new license record)
    PLACEHOLDER: Returns mock success
    """
    new_expiry_date = renewal_data.get("new_expiry_date")
    new_license_id = str(uuid.uuid4())
    
    return {
        "success": True,
        "new_license_id": new_license_id,
        "message": f"License renewed successfully. New expiry: {new_expiry_date}",
        "renewed_at": datetime.utcnow().isoformat(),
        "new_expiry_date": new_expiry_date
    }


@router.get("/statistics/summary")
def get_license_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    location_id: Optional[str] = None
):
    """
    Get license statistics for dashboard
    PLACEHOLDER: Returns mock statistics
    """
    return {
        "total_active": 0,
        "total_suspended": 0,
        "total_expired": 0,
        "pending_activation": 0,
        "by_category": {
            "A'": 0,
            "A": 0,
            "B": 0,
            "C": 0,
            "D": 0,
            "E": 0
        },
        "recent_activations": 0,
        "expiring_soon": 0,
        "location_id": location_id or current_user.primary_location_id,
        "generated_at": datetime.utcnow().isoformat()
    }


@router.get("/applications/{application_id}/preview")
def preview_license_from_application(
    application_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Preview what license will look like when activated from application
    PLACEHOLDER: Returns mock preview data
    """
    return {
        "application_id": application_id,
        "license_number": f"MDG-{application_id[:6].upper()}",
        "category": "B",
        "issue_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "expiry_date": (datetime.utcnow() + timedelta(days=1825)).strftime("%Y-%m-%d"),  # 5 years
        "restrictions": [],
        "photo_required": True,
        "signature_required": True,
        "fingerprint_required": True,
        "preview_generated_at": datetime.utcnow().isoformat()
    } 