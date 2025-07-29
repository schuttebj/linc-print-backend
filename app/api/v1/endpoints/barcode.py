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
        json_schema_extra = {
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
        json_schema_extra = {
            "example": {
                "success": True,
                "barcode_image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
                "barcode_data": {
                    "ver": 1,
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
        json_schema_extra = {
            "example": {
                "barcode_json": '{"ver":1,"dob":"1990-05-12","sex":"M","codes":["B"],"country":"MG"}'
            }
        }


class BarcodeDecodingResponse(BaseModel):
    """Response model for barcode decoding"""
    success: bool
    decoded_data: Dict[str, Any]
    license_info: Dict[str, Any]
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "decoded_data": {
                    "ver": 1,
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
    """Request model for testing barcode with comprehensive sample data"""
    person_name: str = "RANDRIANARISOA Marie"
    date_of_birth: str = "1990-01-01"
    sex: str = "F"  # M or F
    license_codes: List[str] = ["B", "EB"]
    vehicle_restrictions: List[str] = []
    driver_restrictions: List[str] = []
    include_sample_photo: bool = True
    include_professional_permit: bool = False
    include_address_data: bool = True
    include_medical_data: bool = True
    include_license_history: bool = True
    test_scenario: str = "standard"  # standard, professional, restricted, international
    
    class Config:
        json_schema_extra = {
            "example": {
                "person_name": "RANDRIANARISOA Marie",
                "date_of_birth": "1990-05-12",
                "sex": "F",
                "license_codes": ["B", "EB"],
                "vehicle_restrictions": ["auto"],
                "driver_restrictions": ["glasses"],
                "include_sample_photo": True,
                "include_professional_permit": False,
                "include_address_data": True,
                "include_medical_data": True,
                "include_license_history": True,
                "test_scenario": "standard"
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
    summary="Generate test barcode with license data only",
    description="Generate a PDF417 barcode with only the actual Madagascar license file data"
)
async def generate_test_barcode(
    request: TestBarcodeRequest,
    current_user: User = Depends(require_permission("licenses.read"))
):
    """Generate test barcode with only actual license file data"""
    try:
        import uuid
        from datetime import datetime, timedelta
        import random
        
        # Generate realistic dates
        first_issue_date = datetime.now() - timedelta(days=1825)  # 5 years ago
        current_issue_date = datetime.now() - timedelta(days=90)  # 3 months ago  
        expiry_date = current_issue_date + timedelta(days=1825)   # 5 years from current issue
        
        # Generate realistic card number (Madagascar format)
        location_codes = ["T01", "F01", "M01", "A01", "D01", "N01"]
        location_code = random.choice(location_codes)
        sequence = random.randint(100000, 999999)
        card_number = f"MG{location_code}{sequence:06d}"
        
        # Generate realistic ID number (Madagascar national ID format)
        id_number = f"{random.randint(100000000000, 999999999999)}"  # 12-digit ID
        
        # Create barcode with ONLY the actual license file data (using short keys)
        barcode_data = {
            # Required system fields
            "ver": 1,
            "country": "MG",
            
            # Actual license file data ONLY
            "name": request.person_name.upper(),                    # Initials and Surname
            "idn": id_number,                                       # ID Number  
            "card_num": card_number,                               # Card Number
            "dr": request.driver_restrictions,                     # Driver Restrictions
            "sex": request.sex,                                    # Sex
            "dob": request.date_of_birth,                          # Date of Birth
            "vf": current_issue_date.strftime("%Y-%m-%d"),         # Valid Period Start
            "vt": expiry_date.strftime("%Y-%m-%d"),                # Valid Period End
            "codes": request.license_codes,                        # License Codes
            "vr": request.vehicle_restrictions,                    # Vehicle Restrictions
            "fi": first_issue_date.strftime("%Y-%m-%d"),           # First Issued Date
        }
        
        # Add image only if requested and space allows
        if request.include_sample_photo:
            # Check space before adding photo
            json_size = len(json.dumps(barcode_data, separators=(',', ':')).encode('utf-8'))
            max_photo_size = 1700 - json_size  # Leave buffer
            
            if max_photo_size > 500:
                try:
                    sample_photo = barcode_service._generate_sample_photo()
                    if sample_photo and len(sample_photo) <= max_photo_size:
                        barcode_data["photo"] = sample_photo
                except:
                    pass  # Skip photo if generation fails
        
        # Generate PDF417 barcode image
        barcode_image = barcode_service.generate_pdf417_barcode(barcode_data)
        
        # Calculate final data size
        data_size = len(json.dumps(barcode_data, separators=(',', ':')).encode('utf-8'))
        
        return BarcodeGenerationResponse(
            success=True,
            barcode_image_base64=barcode_image,
            barcode_data=barcode_data,
            data_size_bytes=data_size,
            message=f"License barcode: {card_number} (ID: {id_number}, {data_size} bytes)"
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
        "required_fields": ["ver", "country"],
        "required_field_descriptions": {
            "ver": "Format version number",
            "country": "ISO country code (MG for Madagascar)"
        },
        "recommended_fields": ["card_num"],
        "recommended_field_descriptions": {
            "card_num": "Physical card number (primary identifier for verification)"
        },
        "optional_fields": [
            "dob", "sex", "codes", "valid_from", "valid_to", 
            "first_issued", "name", "vehicle_restrictions", 
            "driver_restrictions", "photo"
        ],
        "optional_field_descriptions": {
            "dob": "Date of birth (YYYY-MM-DD)",
            "sex": "Gender (M or F)",
            "codes": "License category codes array",
            "valid_from": "Valid from date (YYYY-MM-DD)",
            "valid_to": "Valid until date (YYYY-MM-DD)",
            "first_issued": "First issue date (YYYY-MM-DD)",
            "name": "Full name (uppercase)",
            "vehicle_restrictions": "Vehicle restriction codes array",
            "driver_restrictions": "Driver restriction codes array",
            "card_num": "Physical card number",
            "photo": "Base64 encoded JPEG photo"
        },
        "license_categories": {
            "A": "Motorcycle",
            "B": "Light vehicle (cars)",
            "C": "Heavy vehicle (trucks)", 
            "D": "Bus/taxi",
            "EB": "Light trailer",
            "EC": "Heavy trailer"
        },
        "restriction_codes": {
            "driver_restrictions": {
                "glasses": "Must wear corrective lenses",
                "prosthetics": "Uses artificial limb/prosthetics"
            },
            "vehicle_restrictions": {
                "auto": "Automatic transmission only",
                "electric": "Electric powered vehicles only",
                "disabled": "Vehicles adapted for disabilities",
                "tractor": "Tractor vehicles only",
                "industrial": "Industrial/agriculture vehicles only"
            }
        },
        "example": {
            "ver": 1,
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