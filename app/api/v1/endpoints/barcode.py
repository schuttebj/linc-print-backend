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
    custom_photo_base64: Optional[str] = None  # Base64 encoded JPEG/PNG image (any format, will be processed)
    include_professional_permit: bool = False
    include_address_data: bool = True
    include_medical_data: bool = True
    include_license_history: bool = True
    test_scenario: str = "standard"  # standard, professional, restricted, international
    
    class Config:
        json_schema_extra = {
            "example": {
                "person_name": "RANDRIANARISOA Marie",
                "date_of_birth": "1990-01-01",
                "sex": "F",
                "license_codes": ["B", "EB"],
                "vehicle_restrictions": [],
                "driver_restrictions": ["glasses"],
                "include_sample_photo": True,
                "custom_photo_base64": "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCABgAEgBAREA/8QAHAAAAQQDAQAAAAAAAAAAAAAABwADBQYCBAgB/8QAPxAAAgEEAAQCBgMNCQAAAAAAAQIDAAQFEQYSITFBUQciImFxgRQVYggyQkRygpGTobGywdEjNFNUdIOSlKL/2gAIAQEAAD8AP9KlSpUqVYsuxWu8eqYGfxBHTJ2h/wB0VIKyugZSCrDYI8RXtMXV5b2UavcyrGrNygt4ny/ZTIy9gRsXUdL63sP81HXhzOPH4yvyU/0rE5qw8Jifgjf0py3vra9d1gdmZAC21I1v40M8rNiwIlxSTxFAwmEp2d9NddkefaidjTzY63J/w1/cK2qi83BHcJZRyqGQ3ScynsRo0+uHxyjQsoAPyBWQxdgO1nB/wFZfV9kPxSD9WK9FjZjtawfqxTkUUMXMsSRpruEAFAuOYsrMx2Tsn40a8SebF2x84k/hFbtaGU72X+qT+db9KlSrFUCu7b++IP7NVzxDc+wdeVHjBNzYSybzgT+EVI1HZdljS0diAq3KEk9gOvWtO54ssLUtzRXbqi8zMkPQDzOyDWFnxrgrycQC9SKUkAJKQuyfnqrBSpVy6kzop0fCujOGjzcO48+dvGf/AAtSxOhQ642z92c19UW0DMIljdQrAF5G5u/2VAB9+zQr4ss+KcxcMJ7+2BI0QilNa8OlVJuFM1br676xTnQbVQx/RRx9B3E1/msDkcbkeZpsZMiqznZCODpfkVbXuIHhRVpGuWlwHEoB3gsn/wBR/wCldHcMK8fDePSVGSRbeJXRhoqwRQQfeDUo6sxGn0PEa3uh/dhbLjrOZO6mU2QtYT7PtaIBVh8QU7e8UPs3xzg8rkhFa2kkT9g5Knn+QNVvIcSY+KUwASu/iF0APiTV19CkcUnGGYu/pPIz2MYS3J6upf2nI+yQBv7Zo51i50Kj1wWIIBXHWpB6g+rFb0FvDawiKCJIo17Kg0B8qcqh8Q21lYXmR9bGJorsCWWLoB16Eee99ST5jXahGuGw8WeS8lMNqpO0Mh0qgdBv9wFV64xllf5We45klAkJYqdg0zlctecO21te4XI3FjdCYxf2EnKSigMN67jZ7Hoa6t4fyoznDmMyoQJ9NtY7goPwSygkfLdb03RPnQ/9GeIzPD+Nkt7rLW1/imAa0RC5eI76jbAaXX4PXR7d6IKyBhWWxQF9IObXA+lm5jljKwZGwtwzaPtOpcD4jWxVXy901/bsIGjEJ9vm5Sxb3dOwqtRzNjl9Y8iiNj1UKQTVWy159NyEkuiAPZAPfpXS/oh9J2FzWMxnCpjltMlaWaQoJCClxyIASpHj0J5SO3idGipcnUQ+NCf0d8Vzsj47IQwRFQGV4nLdSTsHfy7US2uYooXmlkSOJFLO7sFVVHcknoB76oHEHps4Yw/NFYPJl7gfg2x5Yx8ZG7/mg1zrmOLMhn+Ko87k5/WTiZHPKNCMKRpVHgAPD+ZNT7qtxG95irz1MU5JKa2n6PA+6oRoZJbkPcT+uKdumgKjcokQjV9ASFtb8xTOFzN7w/mLbK46RY7u2bmjdkDgHRHYgjsTRn4Y+6FuJZ47Timyh9QxA+mWakFPeyEnmH5OvgalOFcQZrrQJBHtdPGql6X+P5r+7k4Yx1wRj7U8l0yH+8SjuD5qp6a8SCfAUJOdtg76+deE9Se1P217cWvMIpCFb75fA/Kn3yszRcgVVPmK0WdnO2Yk++vKVH3L8TNwhw/d31uR9LlX1Ft9l237X5oBPx1QEZ2diWJJPXZrGlSpUqVKv//Z",
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
    summary="Generate test barcode using CBOR+zlib encoding",
    description="Generate a PDF417 barcode with CBOR encoding and zlib compression for optimal size"
)
async def generate_test_barcode(
    request: TestBarcodeRequest,
    current_user: User = Depends(require_permission("licenses.read"))
):
    """Generate test barcode using new CBOR+zlib encoding system"""
    try:
        from datetime import datetime, timedelta
        import random
        import base64
        
        # Create mock Person object for testing
        class MockPerson:
            def __init__(self):
                self.surname = request.person_name.split()[0] if request.person_name else "DOE"
                self.first_name = " ".join(request.person_name.split()[1:]) if len(request.person_name.split()) > 1 else "JOHN"
                self.person_nature = "02" if request.sex == "F" else "01"
                self.birth_date = datetime.strptime(request.date_of_birth, "%Y-%m-%d").date()
        
        # Create mock License object for testing  
        class MockLicense:
            def __init__(self):
                self.issue_date = datetime.now() - timedelta(days=90)  # Current license issue
                self.first_issue_date = datetime.now() - timedelta(days=1825)  # First issued 5 years ago
                self.expiry_date = datetime.now() + timedelta(days=1825)  # Expires in 5 years
                self.category = type('MockCategory', (), {'value': request.license_codes[0] if request.license_codes else 'B'})()
        
        # Create mock Card object for testing
        class MockCard:
            def __init__(self):
        location_codes = ["T01", "F01", "M01", "A01", "D01", "N01"]
        location_code = random.choice(location_codes)
        sequence = random.randint(100000, 999999)
                self.card_number = f"MG{location_code}{sequence:06d}"
        
        person = MockPerson()
        license = MockLicense()
        card = MockCard()
        
        # Process custom photo if provided
        photo_bytes = None
        if request.custom_photo_base64:
            try:
                photo_bytes = base64.b64decode(request.custom_photo_base64)
                print(f"Custom photo decoded: {len(photo_bytes)} bytes")
            except Exception as e:
                print(f"Failed to decode custom photo: {e}")
        
        # Create compressed and encrypted CBOR payload using new system
        cbor_payload = barcode_service.create_cbor_payload_compressed_encrypted(
            license=license,
            person=person,
            card=card,
            photo_data=photo_bytes
        )
        
        # Generate PDF417 barcode using compressed/encrypted CBOR
        barcode_image = barcode_service.generate_pdf417_barcode_cbor(cbor_payload)
        
        # For the response, create a regular (unencrypted) payload to show what's inside
        # This is just for testing - in production you wouldn't expose the decrypted content
        display_payload = barcode_service.create_cbor_payload(
            license=license,
            person=person,
            card=card,
            photo_data=photo_bytes
        )
        decoded_payload = barcode_service.decode_cbor_payload(display_payload)
        
        # Convert to display format similar to old JSON structure
        display_data = decoded_payload.get("data", {})
        if "img" in decoded_payload:
            display_data["photo_included"] = True
            display_data["photo_size"] = len(decoded_payload["img"])
        
        return BarcodeGenerationResponse(
            success=True,
            barcode_image_base64=barcode_image,
            barcode_data=display_data,
            data_size_bytes=len(cbor_payload),
            message=f"CBOR License barcode: {card.card_number} ({len(cbor_payload)} bytes total, "
                   f"{'with photo' if photo_bytes else 'no photo'})"
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


class BarcodeDecodeRequest(BaseModel):
    """Request model for decoding barcode hex data"""
    hex_data: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "hex_data": "a16464617461ad637665720267636f756e747279624d47646e616d657452414e445249414e415249534f41204d617269656369646e6c37323836343938333434333663736578614663646f626a313939302d30312d30316266696a323032352d30352d30316276666a323032352d30352d30316276746a323033302d30372d32396563636f646573816142626472806276728068636172645f6e756d6b4d475430313530353136393"
            }
        }


@router.post(
    "/decode-hex",
    summary="Decode scanned barcode hex data",
    description="Decode CBOR-encoded barcode data and extract embedded image"
)
async def decode_barcode_data(
    request: BarcodeDecodeRequest,
    current_user: User = Depends(require_permission("licenses.read"))
):
    """Decode scanned barcode hex data and extract image"""
    try:
        import binascii
        
        # Try different decoding methods based on the input format
        binary_data = None
        decoding_method = "unknown"
        
        print(f"Input hex_data length: {len(request.hex_data)} characters")
        print(f"First 40 chars: {request.hex_data[:40]}")
        
        try:
            # Method 1: Try direct binary (if scanner returns raw bytes as hex)
            binary_data = binascii.unhexlify(request.hex_data)
            decoding_method = "hex"
            print(f"Hex decoding successful: {len(binary_data)} bytes")
        except Exception as hex_error:
            print(f"Hex decoding failed: {hex_error}")
            try:
                # Method 2: Try base64 decoding
                import base64
                binary_data = base64.b64decode(request.hex_data)
                decoding_method = "base64"
                print(f"Base64 decoding successful: {len(binary_data)} bytes")
            except Exception as b64_error:
                print(f"Base64 decoding failed: {b64_error}")
                try:
                    # Method 3: Try latin1 text decoding
                    binary_data = request.hex_data.encode('latin1')
                    decoding_method = "latin1"
                    print(f"Latin1 encoding successful: {len(binary_data)} bytes")
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Could not decode data as hex, base64, or latin1: {str(e)}"
                    )
        
        print(f"Decoded using method: {decoding_method}, data length: {len(binary_data)} bytes")
        
        # Try to decode as compressed/encrypted payload first, then fallback to regular
        try:
            print("Attempting compressed/encrypted decode...")
            decoded_data = barcode_service.decode_cbor_payload_compressed_encrypted(binary_data)
            decoding_format = "compressed+encrypted"
        except Exception as crypto_error:
            print(f"Compressed/encrypted decode failed: {crypto_error}")
            print("Falling back to regular CBOR decode...")
            try:
                decoded_data = barcode_service.decode_cbor_payload(binary_data)
                decoding_format = "regular"
            except Exception as regular_error:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to decode barcode data. Encrypted: {crypto_error}. Regular: {regular_error}"
                )
        
        # Check if image is present
        has_image = 'img' in decoded_data
        image_size = len(decoded_data['img']) if has_image else 0
        
        # Prepare response data
        license_data = decoded_data.get('data', {})
        
        response_data = {
            "success": True,
            "license_data": license_data,
            "has_image": has_image,
            "image_size_bytes": image_size,
            "total_payload_size": len(binary_data),
            "decoding_method": decoding_method,
            "decoding_format": decoding_format,
            "message": f"Barcode decoded successfully using {decoding_method} ({decoding_format}). {'Image found' if has_image else 'No image'} ({len(binary_data)} bytes total)"
        }
        
        # Add base64 encoded image if present
        if has_image:
            import base64
            
            try:
                # Image is already in JPEG/PNG format, just encode to base64
                image_bytes = decoded_data['img']
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                response_data["image_base64"] = image_base64
                response_data["image_format"] = "JPEG/PNG"
            except Exception as e:
                response_data["image_error"] = f"Failed to encode image: {str(e)}"
        
        return response_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to decode barcode: {str(e)}"
        ) 