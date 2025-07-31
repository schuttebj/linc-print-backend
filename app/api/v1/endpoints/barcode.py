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
    """Request model for testing barcode with standardized Madagascar license format"""
    # Field 1: Initials and surname
    person_name: str = Field(default="BJ SCHUTTE", description="Full name (initials and surname)")
    
    # Field 2: ID Number
    id_number: str = Field(default="456740229624", description="National ID number (12 digits)")
    
    # Field 3: Date of Birth  
    date_of_birth: str = Field(default="19950127", description="Date of birth (YYYYMMDD format)")
    
    # Field 4: License Number
    license_number: str = Field(default="MGD0154747899", description="License number (13 digits)")
    
    # Field 5: Valid date range (From - To)
    valid_from: str = Field(default="20250501", description="Valid from date (YYYYMMDD format)")
    valid_to: str = Field(default="20300729", description="Valid to date (YYYYMMDD format)")
    
    # Field 6: License codes
    license_codes: List[str] = Field(default=["B", "C"], description="License category codes")
    
    # Field 7: Vehicle restrictions
    vehicle_restrictions: List[str] = Field(default=["AUTO_ONLY"], description="Vehicle restriction codes")
    
    # Field 8: Driver restrictions  
    driver_restrictions: List[str] = Field(default=["GLASSES"], description="Driver restriction codes")
    
    # Field 9: Sex
    sex: str = Field(default="M", description="Gender (M or F)")
    
    # Photo options
    include_sample_photo: bool = Field(default=True, description="Include a sample photo")
    custom_photo_base64: Optional[str] = Field(default=None, description="Custom photo as base64 string")
    
    class Config:
        json_schema_extra = {
            "example": {
                "person_name": "BJ SCHUTTE",
                "id_number": "456740229624", 
                "date_of_birth": "19950127",
                "license_number": "MGD0154747899",
                "valid_from": "20250501",
                "valid_to": "20300729",
                "license_codes": ["B", "C"],
                "vehicle_restrictions": ["AUTO_ONLY"],
                "driver_restrictions": ["GLASSES"],
                "sex": "M",
                "include_sample_photo": True,
                "custom_photo_base64": null
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
    summary="Generate test barcode using standardized Madagascar format",
    description="Generate a PDF417 barcode using PyZint with standardized pipe-delimited Madagascar license format"
)
async def generate_test_barcode(
    request: TestBarcodeRequest,
    current_user: User = Depends(require_permission("licenses.read"))
):
    """Generate test barcode using standardized Madagascar license format"""
    try:
        import base64
        import zlib
        import io
        from PIL import Image
        import pyzint
        
        # Step 1: Create standardized pipe-delimited license data
        # Format: Name|ID|DOB|LicenseNum|ValidFrom-ValidTo|Codes|VehicleRestr|DriverRestr|Sex
        
        # Format license codes as comma-separated
        license_codes_str = ','.join(request.license_codes) if request.license_codes else ""
        
        # Format vehicle restrictions as comma-separated
        vehicle_restrictions_str = ','.join(request.vehicle_restrictions) if request.vehicle_restrictions else ""
        
        # Format driver restrictions as comma-separated  
        driver_restrictions_str = ','.join(request.driver_restrictions) if request.driver_restrictions else ""
        
        # Format valid date range
        valid_date_range = f"{request.valid_from}-{request.valid_to}"
        
        # Create standardized pipe-delimited format
        license_data = f"{request.person_name}|{request.id_number}|{request.date_of_birth}|{request.license_number}|{valid_date_range}|{license_codes_str}|{vehicle_restrictions_str}|{driver_restrictions_str}|{request.sex}"
        license_data_bytes = license_data.encode("utf-8")
        
        print(f"Standardized license data: {license_data}")
        
        # Step 2: Process image if provided
        image_bytes = None
        if request.custom_photo_base64:
            try:
                # Decode custom photo
                photo_data = base64.b64decode(request.custom_photo_base64)
                image = Image.open(io.BytesIO(photo_data)).convert("L")
                image = image.resize((60, 90))
                
                # Try different quality levels starting from 50, stepping down by 5
                for quality in [50, 45, 40, 35, 30, 25, 20, 15, 10]:
                    img_buffer = io.BytesIO()
                    image.save(img_buffer, format="JPEG", quality=quality, optimize=True)
                    image_bytes = img_buffer.getvalue()
                    
                    # Check if combined data will fit (rough estimate)
                    test_combined = license_data_bytes + b"||IMG||" + image_bytes
                    test_compressed = zlib.compress(test_combined, level=9)
                    
                    if len(test_compressed) <= 1800:  # Conservative size limit
                        print(f"Image processed with quality {quality}: {len(image_bytes)} bytes")
                        break
                else:
                    print("Could not compress image to acceptable size")
                    image_bytes = None
                    
            except Exception as e:
                print(f"Failed to process custom photo: {e}")
                image_bytes = None
        elif request.include_sample_photo:
            # Generate a simple sample image (60x90 grayscale)
            image = Image.new('L', (60, 90), color=128)  # Gray background
            
            # Add simple pattern for testing
            for y in range(90):
                for x in range(60):
                    if (x + y) % 10 < 5:
                        image.putpixel((x, y), 180)
            
            # Compress with quality 50
            img_buffer = io.BytesIO()
            image.save(img_buffer, format="JPEG", quality=50, optimize=True)
            image_bytes = img_buffer.getvalue()
            print(f"Sample image generated: {len(image_bytes)} bytes")
        
        # Step 3: Combine and compress all data (exact format from working code)
        if image_bytes:
            combined_data = license_data_bytes + b"||IMG||" + image_bytes
        else:
            combined_data = license_data_bytes
            
        compressed = zlib.compress(combined_data, level=9)
        print(f"Compressed payload size: {len(compressed)} bytes")
        
        # Step 4: Create PDF417 barcode using PyZint (exact from working code)
        symbol = pyzint.Barcode.PDF417(compressed, option_1=5)
        
        # Step 5: Render as BMP and convert to PNG (exact from working code)
        bmp_data = symbol.render_bmp()
        bmp_stream = io.BytesIO(bmp_data)
        bmp_image = Image.open(bmp_stream)
        
        # Convert to PNG and base64 encode
        output_buffer = io.BytesIO()
        bmp_image.save(output_buffer, format="PNG")
        barcode_b64 = base64.b64encode(output_buffer.getvalue()).decode("utf-8")
        
        # Create response data
        display_data = {
            "version": 5,
            "format": "standardized_madagascar_license",
            "license_data": license_data,
            "fields": {
                "person_name": request.person_name,
                "id_number": request.id_number,
                "date_of_birth": request.date_of_birth,
                "license_number": request.license_number,
                "valid_from": request.valid_from,
                "valid_to": request.valid_to,
                "license_codes": request.license_codes,
                "vehicle_restrictions": request.vehicle_restrictions,
                "driver_restrictions": request.driver_restrictions,
                "sex": request.sex
            },
            "photo_included": image_bytes is not None,
            "photo_size": len(image_bytes) if image_bytes else 0,
            "compression": "zlib_level_9",
            "barcode_engine": "pyzint_pdf417"
        }
        
        return BarcodeGenerationResponse(
            success=True,
            barcode_image_base64=barcode_b64,
            barcode_data=display_data,
            data_size_bytes=len(compressed),
            message=f"Standardized Madagascar license barcode generated: {request.license_number} "
                   f"({len(compressed)} bytes compressed, {'with photo' if image_bytes else 'no photo'})"
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


class MadagascarBarcodeDecodeRequest(BaseModel):
    """Request model for decoding Madagascar standardized barcode"""
    hex_data: str = Field(..., description="Hex-encoded barcode data from scanner")
    
    class Config:
        json_schema_extra = {
            "example": {
                "hex_data": "789c4a722050534856553448494e5454c85648494e4956553449494dd52a3148515051b4aa4a4a5648c849494e4c5555b14e5451b130e4da4e4e4e5548514e4b55b130e4da4e5551b1343a4e4fd554"
            }
        }


class MadagascarBarcodeDecodeResponse(BaseModel):
    """Response model for decoded Madagascar barcode"""
    success: bool
    license_data: Dict[str, str]
    has_image: bool
    image_base64: Optional[str] = None
    image_size_bytes: int
    total_payload_size: int
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "license_data": {
                    "person_name": "BJ SCHUTTE",
                    "id_number": "456740229624",
                    "date_of_birth": "19950127", 
                    "license_number": "MGD0154747899",
                    "valid_from": "20250501",
                    "valid_to": "20300729",
                    "license_codes": ["B", "C"],
                    "vehicle_restrictions": ["AUTO_ONLY"],
                    "driver_restrictions": ["GLASSES"],
                    "sex": "M"
                },
                "has_image": True,
                "image_base64": "/9j/4AAQSkZJRgABA...",
                "image_size_bytes": 2048,
                "total_payload_size": 3584,
                "message": "Madagascar license barcode decoded successfully"
            }
        }


@router.post(
    "/decode-madagascar",
    response_model=MadagascarBarcodeDecodeResponse,
    summary="Decode Madagascar standardized license barcode",
    description="Decode standardized Madagascar license barcode with pipe-delimited format"
)
async def decode_madagascar_barcode(
    request: MadagascarBarcodeDecodeRequest,
    current_user: User = Depends(require_permission("licenses.read"))
):
    """Decode Madagascar standardized license barcode"""
    try:
        import binascii
        import base64
        import zlib
        
        print(f"Decoding Madagascar barcode: {len(request.hex_data)} hex characters")
        
        # Step 1: Decode hex to binary
        try:
            binary_data = binascii.unhexlify(request.hex_data)
            print(f"Hex decoded to {len(binary_data)} bytes")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid hex data: {str(e)}"
            )
        
        # Step 2: Decompress with zlib
        try:
            decompressed_data = zlib.decompress(binary_data)
            print(f"Decompressed to {len(decompressed_data)} bytes")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to decompress data: {str(e)}"
            )
        
        # Step 3: Check for image separator
        image_separator = b"||IMG||"
        has_image = image_separator in decompressed_data
        
        if has_image:
            # Split license data and image
            parts = decompressed_data.split(image_separator, 1)
            license_data_bytes = parts[0]
            image_bytes = parts[1] if len(parts) > 1 else b""
            print(f"Found image: {len(image_bytes)} bytes")
        else:
            license_data_bytes = decompressed_data
            image_bytes = b""
            print("No image found in barcode")
        
        # Step 4: Parse license data (pipe-delimited format)
        try:
            license_data_str = license_data_bytes.decode('utf-8')
            print(f"License data string: {license_data_str}")
            
            # Split by pipes: Name|ID|DOB|LicenseNum|ValidFrom-ValidTo|Codes|VehicleRestr|DriverRestr|Sex
            fields = license_data_str.split('|')
            
            if len(fields) != 9:
                raise ValueError(f"Expected 9 fields, got {len(fields)}")
            
            # Parse valid date range
            valid_dates = fields[4].split('-') if fields[4] else ['', '']
            valid_from = valid_dates[0] if len(valid_dates) > 0 else ''
            valid_to = valid_dates[1] if len(valid_dates) > 1 else ''
            
            # Parse license data
            parsed_data = {
                "person_name": fields[0],
                "id_number": fields[1],
                "date_of_birth": fields[2],
                "license_number": fields[3],
                "valid_from": valid_from,
                "valid_to": valid_to,
                "license_codes": fields[5].split(',') if fields[5] else [],
                "vehicle_restrictions": fields[6].split(',') if fields[6] else [],
                "driver_restrictions": fields[7].split(',') if fields[7] else [],
                "sex": fields[8]
            }
            
            print(f"Parsed license data: {parsed_data}")
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse license data: {str(e)}"
            )
        
        # Step 5: Encode image to base64 if present
        image_base64 = None
        if has_image and image_bytes:
            try:
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                print(f"Image encoded to base64: {len(image_base64)} characters")
            except Exception as e:
                print(f"Failed to encode image: {e}")
        
        return MadagascarBarcodeDecodeResponse(
            success=True,
            license_data=parsed_data,
            has_image=has_image,
            image_base64=image_base64,
            image_size_bytes=len(image_bytes),
            total_payload_size=len(binary_data),
            message=f"Madagascar license barcode decoded successfully. License: {parsed_data.get('license_number', 'Unknown')}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to decode Madagascar barcode: {str(e)}"
        ) 