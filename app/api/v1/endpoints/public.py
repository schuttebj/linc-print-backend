"""
Public endpoints for limited, non-sensitive data exposure

WARNING: These endpoints intentionally skip authentication for demo/showcase
purposes. Do not expose PII and keep responses minimal. Add auth/rate limiting
before production use.
"""

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.crud import person as crud_person, person_alias
from app.crud.crud_application import crud_application
from app.crud.crud_license import crud_license


router = APIRouter()


@router.get("/status/{id_number}", summary="Public status by ID number (applications and licenses)")
def public_status_by_id(
    id_number: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Return minimal status info for a person:
      - licenses: list of { category, status }
      - applications: list of { application_number, application_type, status, license_category }

    Authentication deliberately skipped for demo purposes. Response excludes PII.
    """
    if not id_number or not id_number.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="id_number is required")

    # Find person by ID number through their alias (document)
    found_alias = person_alias.get_by_document_number(
        db=db,
        document_number=id_number.strip(),
        document_type="MADAGASCAR_ID",
    )

    if not found_alias:
        # Fallback without document type filter
        found_alias = person_alias.get_by_document_number(db=db, document_number=id_number.strip())

    if not found_alias:
        # Return empty but valid payload rather than leaking existence checks
        return {
            "licenses": [],
            "applications": [],
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }

    person = crud_person.get(db=db, id=found_alias.person_id)
    if not person:
        return {
            "licenses": [],
            "applications": [],
            "last_updated": datetime.utcnow().isoformat() + "Z",
        }

    # Collect licenses (minimal fields only)
    licenses = crud_license.get_by_person_id(db=db, person_id=person.id, active_only=False, skip=0, limit=1000)
    licenses_payload: List[Dict[str, Any]] = [
        {
            "category": getattr(lic.category, "value", str(lic.category)),
            "status": getattr(lic.status, "value", str(lic.status)),
        }
        for lic in licenses
    ]

    # Collect applications (minimal fields only)
    apps = crud_application.get_by_person_id(db=db, person_id=person.id, status_filter=None, skip=0, limit=1000)
    applications_payload: List[Dict[str, Any]] = [
        {
            "application_number": app.application_number,
            "application_type": getattr(app.application_type, "value", str(app.application_type)),
            "status": getattr(app.status, "value", str(app.status)),
            "license_category": getattr(app.license_category, "value", str(app.license_category)) if app.license_category else None,
        }
        for app in apps
    ]

    return {
        "licenses": licenses_payload,
        "applications": applications_payload,
        "last_updated": datetime.utcnow().isoformat() + "Z",
    }


