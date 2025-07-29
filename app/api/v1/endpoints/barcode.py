"""
Barcode API endpoints for Madagascar License System
Handles PDF417 barcode generation, decoding, and testing
"""

import json
import uuid
import base64
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.license import License
from app.models.person import Person
from app.models.card import Card
from app.services.barcode_service import barcode_service, BarcodeGenerationError, BarcodeDecodingError
from app.crud.crud_license import crud_license
from app.crud.crud_card import crud_card

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


# Pydantic models for API
class BarcodeGenerationRequest(BaseModel):
    """Request model for generating barcode from license ID"""
    license_id: uuid.UUID
    card_id: Optional[uuid.UUID] = None
    include_photo: bool = True
    
    class Config:
        schema_extra = {
            "example": {
                "license_id": "123e4567-e89b-12d3-a456-426614174000",
                "card_id": "987fcdeb-51a2-43d1-9f12-123456789abc",
                "include_photo": True
            }
        }


class BarcodeGenerationResponse(BaseModel):
    """Response model for barcode generation"""
    success: bool
    barcode_image_base64: str
    barcode_data: Dict[str, Any]
    data_size_bytes: int
    message: str
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "barcode_image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
                "barcode_data": {
                    "ver": 1,
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "dob": "1990-05-12",
                    "sex": "M",
                    "codes": ["B"],
                    "country": "MG"
                },
                "data_size_bytes": 1250,
                "message": "Barcode generated successfully"
            }
        }


class BarcodeDecodingRequest(BaseModel):
    """Request model for decoding barcode data"""
    barcode_json: str = Field(..., description="JSON string extracted from barcode scan")
    
    class Config:
        schema_extra = {
            "example": {
                "barcode_json": '{"ver":1,"id":"123...","dob":"1990-05-12","sex":"M","codes":["B"],"country":"MG"}'
            }
        }


class BarcodeDecodingResponse(BaseModel):
    """Response model for barcode decoding"""
    success: bool
    decoded_data: Dict[str, Any]
    license_info: Dict[str, Any]
    message: str
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "decoded_data": {
                    "ver": 1,
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "SMITH John",
                    "dob": "1990-05-12",
                    "sex": "M",
                    "codes": ["B"],
                    "country": "MG"
                },
                "license_info": {
                    "full_name": "SMITH John",
                    "date_of_birth": "1990-05-12",
                    "sex": "Male",
                    "license_codes": ["B"],
                    "is_valid": True
                },
                "message": "Barcode decoded successfully"
            }
        }


class TestBarcodeRequest(BaseModel):
    """Request model for testing barcode with sample data"""
    person_name: str = "TEST USER"
    date_of_birth: str = "1990-01-01"
    sex: str = "M"  # M or F
    license_codes: List[str] = ["B"]
    vehicle_restrictions: List[str] = []
    driver_restrictions: List[str] = []
    include_sample_photo: bool = False
    
    class Config:
        schema_extra = {
            "example": {
                "person_name": "SMITH John",
                "date_of_birth": "1990-05-12",
                "sex": "M",
                "license_codes": ["B", "EB"],
                "vehicle_restrictions": ["auto"],
                "driver_restrictions": ["glasses"],
                "include_sample_photo": False
            }
        }


@router.post(
    "/generate",
    response_model=BarcodeGenerationResponse,
    summary="Generate PDF417 barcode for license",
    description="Generate a PDF417 barcode containing all license and card information"
)
async def generate_license_barcode(
    request: BarcodeGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("licenses.read"))
):
    """Generate PDF417 barcode for a specific license"""
    try:
        # Get license
        license = crud_license.get(db, id=request.license_id)
        if not license:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="License not found"
            )
        
        # Get person
        person = db.query(Person).filter(Person.id == license.person_id).first()
        if not person:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found"
            )
        
        # Get card if specified
        card = None
        if request.card_id:
            card = crud_card.get(db, id=request.card_id)
            if not card:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Card not found"
                )
        
        # Load photo data if requested
        photo_data = None
        if request.include_photo and license.photo_file_path:
            try:
                from pathlib import Path
                from app.core.config import settings
                photo_path = Path(settings.get_file_storage_path()) / license.photo_file_path
                if photo_path.exists():
                    with open(photo_path, 'rb') as f:
                        photo_data = f.read()
            except Exception as e:
                # Continue without photo if there's an error
                pass
        
        # Generate barcode data
        barcode_data = barcode_service.generate_license_barcode_data(
            license=license,
            person=person,
            card=card,
            photo_data=photo_data
        )
        
        # Generate PDF417 barcode image
        barcode_image = barcode_service.generate_pdf417_barcode(barcode_data)
        
        # Calculate data size
        data_size = len(json.dumps(barcode_data).encode('utf-8'))
        
        return BarcodeGenerationResponse(
            success=True,
            barcode_image_base64=barcode_image,
            barcode_data=barcode_data,
            data_size_bytes=data_size,
            message="Barcode generated successfully"
        )
        
    except BarcodeGenerationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Barcode generation failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/decode",
    response_model=BarcodeDecodingResponse,
    summary="Decode PDF417 barcode data",
    description="Decode and validate JSON data extracted from a scanned PDF417 barcode"
)
async def decode_license_barcode(
    request: BarcodeDecodingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("licenses.read"))
):
    """Decode and validate barcode JSON data"""
    try:
        # Decode barcode data
        decoded_data = barcode_service.decode_barcode_data(request.barcode_json)
        
        # Generate comprehensive license information
        license_info = barcode_service.generate_comprehensive_barcode_info(decoded_data)
        
        return BarcodeDecodingResponse(
            success=True,
            decoded_data=decoded_data,
            license_info=license_info,
            message="Barcode decoded successfully"
        )
        
    except BarcodeDecodingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Barcode decoding failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.post(
    "/test",
    response_model=BarcodeGenerationResponse,
    summary="Generate test barcode with sample data",
    description="Generate a test PDF417 barcode with sample data for testing scanner integration"
)
async def generate_test_barcode(
    request: TestBarcodeRequest,
    current_user: User = Depends(require_permission("licenses.read"))
):
    """Generate test barcode with sample data"""
    try:
        import uuid
        from datetime import datetime, timedelta
        
        # Create sample barcode data
        test_id = str(uuid.uuid4())
        issue_date = datetime.now()
        valid_until = issue_date + timedelta(days=1825)  # 5 years
        
        barcode_data = {
            "ver": 1,
            "id": test_id,
            "dob": request.date_of_birth,
            "sex": request.sex,
            "codes": request.license_codes,
            "valid_from": issue_date.strftime("%Y-%m-%d"),
            "valid_to": valid_until.strftime("%Y-%m-%d"),
            "first_issued": issue_date.strftime("%Y-%m-%d"),
            "country": "MG",
            "name": request.person_name.upper(),
            "vehicle_restrictions": request.vehicle_restrictions,
            "driver_restrictions": request.driver_restrictions,
            "card_num": f"TEST{test_id[:8].upper()}"
        }
        
        # Add sample photo if requested
        if request.include_sample_photo:
            # Create a simple test image
            sample_photo = barcode_service._generate_sample_photo()
            if sample_photo:
                barcode_data["photo"] = sample_photo
        
        # Generate PDF417 barcode image
        barcode_image = barcode_service.generate_pdf417_barcode(barcode_data)
        
        # Calculate data size
        data_size = len(json.dumps(barcode_data).encode('utf-8'))
        
        return BarcodeGenerationResponse(
            success=True,
            barcode_image_base64=barcode_image,
            barcode_data=barcode_data,
            data_size_bytes=data_size,
            message="Test barcode generated successfully"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate test barcode: {str(e)}"
        )


@router.post(
    "/decode/photo",
    summary="Extract photo from barcode data",
    description="Extract and return the embedded photo from decoded barcode data"
)
async def extract_barcode_photo(
    request: BarcodeDecodingRequest,
    current_user: User = Depends(require_permission("licenses.read"))
):
    """Extract photo from barcode data"""
    try:
        # Decode barcode data
        decoded_data = barcode_service.decode_barcode_data(request.barcode_json)
        
        # Extract photo
        photo_bytes = barcode_service.extract_photo_from_barcode(decoded_data)
        
        if not photo_bytes:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No photo found in barcode data"
            )
        
        # Return photo as base64
        photo_base64 = base64.b64encode(photo_bytes).decode('utf-8')
        
        return {
            "success": True,
            "photo_base64": photo_base64,
            "photo_size_bytes": len(photo_bytes),
            "message": "Photo extracted successfully"
        }
        
    except BarcodeDecodingError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Barcode decoding failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


@router.get(
    "/scan-test",
    summary="Test barcode scanning endpoint",
    description="Test endpoint for barcode scanner integration - returns sample barcode data"
)
async def test_barcode_scan():
    """Test endpoint for barcode scanner integration"""
    # Sample barcode JSON for testing
    sample_barcode_data = {
        "ver": 1,
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "dob": "1985-03-15",
        "sex": "F",
        "codes": ["B", "EB"],
        "valid_from": "2023-01-01",
        "valid_to": "2028-01-01",
        "first_issued": "2018-01-01",
        "country": "MG",
        "name": "RANDRIANARISOA Marie",
        "vehicle_restrictions": [],
        "driver_restrictions": ["glasses"],
        "card_num": "MG240001234"
    }
    
    return {
        "success": True,
        "sample_json": json.dumps(sample_barcode_data, separators=(',', ':')),
        "instructions": [
            "1. Use the 'sample_json' value to test barcode decoding",
            "2. POST to /api/v1/barcode/decode with this JSON",
            "3. For scanner integration, extract JSON from PDF417 barcode scan",
            "4. The JSON structure follows the Madagascar license standard"
        ],
        "barcode_format": "PDF417",
        "error_correction": "Level 5 (~25% correction)",
        "max_data_size": "1.8KB"
    }


@router.get(
    "/format",
    summary="Get barcode format specification",
    description="Returns the complete barcode data format specification"
)
async def get_barcode_format():
    """Get barcode format specification"""
    return {
        "version": barcode_service.BARCODE_CONFIG['version'],
        "format": "PDF417",
        "encoding": "UTF-8 JSON",
        "error_correction_level": barcode_service.BARCODE_CONFIG['error_correction_level'],
        "max_data_bytes": barcode_service.BARCODE_CONFIG['max_data_bytes'],
        "max_image_bytes": barcode_service.BARCODE_CONFIG['max_image_bytes'],
        "required_fields": [
            "ver",    # Version number
            "id",     # License UUID
            "country" # Country code (MG)
        ],
        "optional_fields": [
            "dob",                  # Date of birth (YYYY-MM-DD)
            "sex",                  # M or F
            "codes",                # License category codes
            "valid_from",           # Valid from date (YYYY-MM-DD)
            "valid_to",             # Valid until date (YYYY-MM-DD)
            "first_issued",         # First issue date (YYYY-MM-DD)
            "name",                 # Full name
            "vehicle_restrictions", # Vehicle restriction codes
            "driver_restrictions",  # Driver restriction codes
            "card_num",             # Physical card number
            "photo"                 # Base64 encoded photo
        ],
        "example": {
            "ver": 1,
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "dob": "1990-05-12",
            "sex": "M",
            "codes": ["B", "EB"],
            "valid_from": "2023-06-01",
            "valid_to": "2028-06-01",
            "first_issued": "2010-03-15",
            "country": "MG",
            "name": "SMITH John",
            "vehicle_restrictions": ["auto", "electric"],
            "driver_restrictions": ["glasses"],
            "card_num": "MG240001234",
            "photo": "<base64_image_data>"
        }
    } 