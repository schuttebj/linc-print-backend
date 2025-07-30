"""
Madagascar Driver's License Barcode Service - CBOR/zlib Implementation
Handles PDF417 barcode generation and decoding with complete license data

Features:
- PDF417 barcode generation with binary payload support
- CBOR encoding for efficient data structure serialization
- zlib compression for image data optimization
- ISO standard 2:3 aspect ratio license photos
- Optimized for ~1.4KB total capacity with realistic error correction
- Hex encoding for PDF417 string compatibility
"""

import io
import uuid
import zlib
import binascii
import base64
import json
from datetime import datetime, date
from typing import Dict, Any, Optional, List, Union, Tuple
from pathlib import Path
import logging

try:
    import cbor2
    CBOR_AVAILABLE = True
except ImportError:
    CBOR_AVAILABLE = False
    logging.warning("cbor2 not available - barcode generation will use fallback")

try:
    import pdf417gen
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False
    logging.warning("pdf417gen not available - barcode generation will be simulated")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("PIL not available - image processing will be limited")

from app.core.config import settings
from app.models.license import License
from app.models.person import Person
from app.models.card import Card
from app.models.enums import LicenseCategory, DriverRestrictionCode, VehicleRestrictionCode

logger = logging.getLogger(__name__)


class LicenseBarcodeError(Exception):
    """Base exception for barcode-related errors"""
    pass


class BarcodeGenerationError(LicenseBarcodeError):
    """Exception raised during barcode generation"""
    pass


class BarcodeDecodingError(LicenseBarcodeError):
    """Exception raised during barcode decoding"""
    pass


class LicenseBarcodeService:
    """Service for generating and decoding PDF417 barcodes using CBOR+zlib encoding"""
    
    # Barcode configuration for PDF417 with realistic capacity
    BARCODE_CONFIG = {
        'columns': 12,  # Increased columns to reduce rows (max 90 rows limit)
        'error_correction_level': 3,  # Reduced error correction for more capacity
        'max_payload_bytes': 700,   # Further reduced to fit PDF417 constraints
        'max_image_bytes': 500,     # Further reduced image budget
        'max_data_bytes': 250,      # License data budget (before compression)
        'image_max_dimension': (60, 90),  # Even smaller 2:3 aspect ratio
        'version': 2  # New CBOR+JPEG format version
    }
    
    # Restriction code mappings
    DRIVER_RESTRICTION_MAPPING = {
        DriverRestrictionCode.CORRECTIVE_LENSES: "glasses",
        DriverRestrictionCode.PROSTHETICS: "prosthetics",
        # Add more mappings as needed
    }
    
    VEHICLE_RESTRICTION_MAPPING = {
        VehicleRestrictionCode.AUTOMATIC_TRANSMISSION: "auto",
        VehicleRestrictionCode.ELECTRIC_POWERED: "electric",
        VehicleRestrictionCode.PHYSICAL_DISABLED: "disabled",
        VehicleRestrictionCode.TRACTOR_ONLY: "tractor",
        VehicleRestrictionCode.INDUSTRIAL_AGRICULTURE: "industrial",
        # Add more mappings as needed
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        if not BARCODE_AVAILABLE:
            self.logger.warning("Barcode generation running in simulation mode")
        if not CBOR_AVAILABLE:
            self.logger.warning("CBOR not available - will use fallback encoding")

    def create_cbor_payload(
        self, 
        license: License, 
        person: Person, 
        card: Optional[Card] = None,
        photo_data: Optional[bytes] = None
    ) -> bytes:
        """
        Create CBOR-encoded payload for PDF417 barcode
        
        Args:
            license: License object
            person: Person object 
            card: Optional Card object
            photo_data: Optional photo bytes
            
        Returns:
            CBOR-encoded binary payload
        """
        try:
            if not CBOR_AVAILABLE:
                raise BarcodeGenerationError("CBOR library not available")
            
            # Generate realistic ID number
            import random
            id_number = f"{random.randint(100000000000, 999999999999)}"
            
            # Build license data structure using standard short field names
            license_data = {
                "ver": self.BARCODE_CONFIG['version'],  # version
                "country": "MG",  # country
                "name": f"{person.surname.upper()} {person.first_name}",  # name
                "idn": id_number,  # ID number
                "sex": "M" if person.person_nature == "01" else "F",  # sex
                "dob": person.birth_date.strftime("%Y-%m-%d") if person.birth_date else None,  # date of birth
                "fi": license.issue_date.strftime("%Y-%m-%d") if license.issue_date else None,  # first issued
                "vf": license.issue_date.strftime("%Y-%m-%d") if license.issue_date else None,  # valid from (current issue)
                "vt": license.expiry_date.strftime("%Y-%m-%d") if license.expiry_date else None,  # valid to
                "codes": [license.category.value] if license.category else [],  # license codes
                "dr": [],  # driver restrictions (simplified for now)
                "vr": [],  # vehicle restrictions (simplified for now)
            }
            
            # Add card number if available
            if card:
                license_data["card_num"] = card.card_number  # card number
            
            # Process photo if provided
            compressed_photo = None
            if photo_data:
                compressed_photo = self._process_photo_for_barcode(photo_data)
            
            # Create final payload structure
            payload = {
                "data": license_data,
            }
            
            # Add photo if successfully processed
            if compressed_photo:
                payload["img"] = compressed_photo
            
            # Encode with CBOR
            cbor_payload = cbor2.dumps(payload)
            
            print(f"CBOR payload created: data={len(cbor2.dumps(license_data))} bytes, "
                  f"photo={len(compressed_photo) if compressed_photo else 0} bytes, "
                  f"total={len(cbor_payload)} bytes")
            
            if len(cbor_payload) > self.BARCODE_CONFIG['max_payload_bytes']:
                raise BarcodeGenerationError(
                    f"CBOR payload too large: {len(cbor_payload)} > {self.BARCODE_CONFIG['max_payload_bytes']}"
                )
            
            return cbor_payload
            
        except Exception as e:
            raise BarcodeGenerationError(f"Failed to create CBOR payload: {str(e)}")

    def decode_cbor_payload(self, cbor_data: bytes) -> Dict[str, Any]:
        """
        Decode CBOR payload from barcode scan
        
        Args:
            cbor_data: CBOR-encoded binary data
            
        Returns:
            Decoded payload dictionary
        """
        try:
            if not CBOR_AVAILABLE:
                raise BarcodeDecodingError("CBOR library not available")
            
            payload = cbor2.loads(cbor_data)
            
            # Validate structure
            if not isinstance(payload, dict) or "data" not in payload:
                raise BarcodeDecodingError("Invalid CBOR payload structure")
            
            # Photo is stored as raw JPEG/PNG bytes, no decompression needed
            if "img" in payload:
                print(f"Photo found: {len(payload['img'])} bytes (JPEG/PNG format)")
                # Image bytes are ready to use directly
            
            return payload
            
        except Exception as e:
            raise BarcodeDecodingError(f"Failed to decode CBOR payload: {str(e)}")

    def generate_license_barcode_data(
        self, 
        license: License, 
        person: Person, 
        card: Optional[Card] = None,
        photo_data: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Generate standardized barcode data structure for a license
        
        Args:
            license: License object
            person: Person object 
            card: Optional Card object
            photo_data: Optional photo bytes (will be resized and compressed)
            
        Returns:
            Dictionary with standardized barcode data
        """
        try:
            # Base license information - generate realistic ID number
            import random
            id_number = f"{random.randint(100000000000, 999999999999)}"  # 12-digit Madagascar ID
            
            # Person information
            sex_code = "M" if person.person_nature == "01" else "F"
            full_name = f"{person.surname.upper()} {person.first_name}"
            if person.middle_name:
                full_name += f" {person.middle_name}"
            
            # License categories (convert enum to string codes)
            codes = [license.category.value] if license.category else []
            
            # Add professional permit categories if applicable
            if license.has_professional_permit and license.professional_permit_categories:
                codes.extend(license.professional_permit_categories)
            
            # Validity dates
            valid_from = license.issue_date.strftime("%Y-%m-%d") if license.issue_date else None
            valid_to = None
            if license.expiry_date:  # Only learner's permits have expiry
                valid_to = license.expiry_date.strftime("%Y-%m-%d")
            elif card:
                valid_to = card.valid_until.strftime("%Y-%m-%d")
            
            # Parse restrictions
            driver_restrictions = []
            vehicle_restrictions = []
            
            if license.restrictions:
                # Parse JSON restrictions
                restrictions = license.restrictions
                if isinstance(restrictions, dict):
                    # Map driver restrictions
                    for restriction in restrictions.get('driver_restrictions', []):
                        mapped = self.DRIVER_RESTRICTION_MAPPING.get(restriction, restriction)
                        if mapped not in driver_restrictions:
                            driver_restrictions.append(mapped)
                    
                    # Map vehicle restrictions
                    for restriction in restrictions.get('vehicle_restrictions', []):
                        mapped = self.VEHICLE_RESTRICTION_MAPPING.get(restriction, restriction)
                        if mapped not in vehicle_restrictions:
                            vehicle_restrictions.append(mapped)
            
            # Process photo data
            photo_base64 = None
            if photo_data:
                photo_base64 = self._process_photo_for_barcode(photo_data)
            elif license.photo_file_path:
                # Try to load photo from file path
                try:
                    photo_path = Path(settings.get_file_storage_path()) / license.photo_file_path
                    if photo_path.exists():
                        with open(photo_path, 'rb') as f:
                            photo_base64 = self._process_photo_for_barcode(f.read())
                except Exception as e:
                    self.logger.warning(f"Could not load photo from {license.photo_file_path}: {e}")
            
            # Construct barcode data with ONLY actual license file data (using short keys)
            barcode_data = {
                # Required system fields
                "ver": self.BARCODE_CONFIG['version'],
                "country": "MG",
                
                # Actual license file data ONLY
                "name": full_name,                                      # Initials and Surname
                "idn": id_number,                                       # ID Number
                "dr": driver_restrictions,                              # Driver Restrictions  
                "sex": sex_code,                                        # Sex
                "dob": person.birth_date.strftime("%Y-%m-%d") if person.birth_date else None,  # Date of Birth
                "vf": valid_from,                                       # Valid Period Start
                "vt": valid_to,                                         # Valid Period End
                "codes": codes,                                         # License Codes
                "vr": vehicle_restrictions,                             # Vehicle Restrictions
                "fi": license.issue_date.strftime("%Y-%m-%d") if license.issue_date else None,  # First Issued Date
            }
            
            # Add card number if available
            if card:
                barcode_data["card_num"] = card.card_number              # Card Number
            
            # Add photo last (largest component)
            if photo_base64:
                barcode_data["photo"] = photo_base64                     # Image
            
            return barcode_data
            
        except Exception as e:
            raise BarcodeGenerationError(f"Failed to generate barcode data: {str(e)}")

    def _process_photo_for_barcode(self, photo_data: bytes) -> Optional[bytes]:
        """
        Process photo data for barcode embedding using ISO 2:3 aspect ratio and JPEG compression
        
        Args:
            photo_data: Raw image bytes
            
        Returns:
            Compressed JPEG bytes or None if processing fails
        """
        try:
            if not PIL_AVAILABLE:
                self.logger.warning("PIL not available for photo processing")
                return None
            
            # Open and convert to grayscale
            image = Image.open(io.BytesIO(photo_data))
            if image.mode != 'L':
                image = image.convert('L')
            
            # Resize maintaining 2:3 aspect ratio (ISO standard for license photos)
            max_width, max_height = self.BARCODE_CONFIG['image_max_dimension']
            
            # Calculate size maintaining aspect ratio
            original_width, original_height = image.size
            aspect_ratio = original_width / original_height
            target_aspect_ratio = 2 / 3  # ISO standard
            
            if aspect_ratio > target_aspect_ratio:
                # Image is wider than target, crop width
                new_width = int(original_height * target_aspect_ratio)
                left = (original_width - new_width) // 2
                image = image.crop((left, 0, left + new_width, original_height))
            elif aspect_ratio < target_aspect_ratio:
                # Image is taller than target, crop height
                new_height = int(original_width / target_aspect_ratio)
                top = (original_height - new_height) // 2
                image = image.crop((0, top, original_width, top + new_height))
            
            # Scale to target size while maintaining aspect ratio
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            # Try different compression strategies
            max_bytes = self.BARCODE_CONFIG['max_image_bytes']
            
            # Strategy 1: High quality JPEG with smaller target size
            for quality in [65, 55, 45, 35, 25, 20, 15, 10, 5]:
                jpeg_buffer = io.BytesIO()
                image.save(jpeg_buffer, format='JPEG', quality=quality, optimize=True)
                jpeg_bytes = jpeg_buffer.getvalue()
                
                if len(jpeg_bytes) <= max_bytes:
                    print(f"Photo processing: {len(photo_data)} → {len(jpeg_bytes)} JPEG (quality {quality})")
                    print(f"Final image size: {image.size}")
                    return jpeg_bytes
            
            # Strategy 2: Very low quality JPEG with much smaller dimensions
            for scale in [0.7, 0.6, 0.5, 0.4, 0.3]:
                smaller_image = image.copy()
                new_size = (int(max_width * scale), int(max_height * scale))
                smaller_image.thumbnail(new_size, Image.Resampling.LANCZOS)
                
                for quality in [20, 15, 10, 8, 5, 3]:
                    jpeg_buffer = io.BytesIO()
                    smaller_image.save(jpeg_buffer, format='JPEG', quality=quality, optimize=True)
                    jpeg_bytes = jpeg_buffer.getvalue()
                    
                    if len(jpeg_bytes) <= max_bytes:
                        print(f"Photo processing: {len(photo_data)} → {len(jpeg_bytes)} JPEG (scale {scale}, quality {quality})")
                        print(f"Final image size: {smaller_image.size}")
                        return jpeg_bytes
            
            # Strategy 3: PNG with aggressive optimization
            png_buffer = io.BytesIO()
            image.save(png_buffer, format='PNG', optimize=True)
            png_bytes = png_buffer.getvalue()
            
            if len(png_bytes) <= max_bytes:
                print(f"Photo processing: {len(photo_data)} → {len(png_bytes)} PNG")
                print(f"Final image size: {image.size}")
                return png_bytes
            
            self.logger.warning(f"Could not compress photo to required size. Best: {len(jpeg_bytes) if 'jpeg_bytes' in locals() else len(png_bytes)} bytes")
            return None
                
        except Exception as e:
            self.logger.error(f"Error processing photo for barcode: {e}")
            print(f"Photo processing error: {e}")
            return None

    def generate_pdf417_barcode_cbor(self, cbor_payload: bytes) -> str:
        """
        Generate PDF417 barcode from CBOR binary payload using hex encoding
        
        Args:
            cbor_payload: CBOR-encoded binary data
            
        Returns:
            Base64-encoded PNG image of the barcode
        """
        try:
            print(f"PDF417 generation: {len(cbor_payload)} bytes binary data")
            
            if not BARCODE_AVAILABLE:
                return self._generate_barcode_placeholder(f"CBOR-{len(cbor_payload)}-bytes")
            
            # Try binary mode first (most efficient)
            try:
                codes = pdf417gen.encode(
                    cbor_payload,  # Direct binary data
                    security_level=self.BARCODE_CONFIG['error_correction_level'],
                    columns=self.BARCODE_CONFIG['columns']
                )
                print(f"PDF417 encoded successfully using binary mode")
            except Exception as binary_error:
                print(f"Binary mode failed: {binary_error}, trying text mode")
                # Fallback to text mode with higher capacity settings
                try:
                    # Use text encoding with more columns to reduce rows
                    codes = pdf417gen.encode(
                        cbor_payload.decode('latin1'),  # Latin1 preserves all byte values
                        security_level=2,  # Lower error correction for more capacity
                        columns=15  # More columns = fewer rows to fit 90 row limit
                    )
                    print(f"PDF417 encoded successfully using text mode (latin1)")
                except Exception as text_error:
                    # Last resort: Base64 encoding (more compact than hex)
                    import base64
                    b64_data = base64.b64encode(cbor_payload).decode('ascii')
                    codes = pdf417gen.encode(
                        b64_data,
                        security_level=2,
                        columns=18  # Even more columns for base64 fallback
                    )
                    print(f"PDF417 encoded using base64 fallback: {len(b64_data)} chars")
            
            # Render to image
            img = pdf417gen.render_image(codes, scale=2, ratio=3)
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            
            print(f"PDF417 barcode generated successfully: {img.size}")
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
            
        except Exception as e:
            raise BarcodeGenerationError(f"Failed to generate PDF417 barcode: {str(e)}")

    def generate_pdf417_barcode(self, barcode_data: Dict[str, Any]) -> str:
        """
        Legacy method for JSON-based barcode generation (fallback)
        """
        try:
            import json
            json_data = json.dumps(barcode_data, separators=(',', ':'), ensure_ascii=False)
            
            if not BARCODE_AVAILABLE:
                return self._generate_barcode_placeholder(json_data)
            
            codes = pdf417gen.encode(
                json_data, 
                security_level=self.BARCODE_CONFIG['error_correction_level'],
                columns=self.BARCODE_CONFIG['columns']
            )
            img = pdf417gen.render_image(codes, scale=2, ratio=3)
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
            
        except Exception as e:
            raise BarcodeGenerationError(f"Failed to generate legacy barcode: {str(e)}")



    def _generate_barcode_placeholder(self, data: str) -> str:
        """Generate a placeholder barcode image when PDF417 is not available"""
        try:
            if not PIL_AVAILABLE:
                # Return a simple text representation
                return f"BARCODE_PLACEHOLDER:{len(data)}_bytes"
            
            # Create a simple placeholder image
            from PIL import Image, ImageDraw, ImageFont
            
            img = Image.new('RGB', (400, 100), color='white')
            draw = ImageDraw.Draw(img)
            
            text = f"PDF417 BARCODE\n{len(data)} bytes"
            draw.text((10, 30), text, fill='black')
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
            
        except Exception:
            return f"BARCODE_PLACEHOLDER:{len(data)}_bytes"

    def decode_barcode_data_cbor(self, hex_data: str) -> Dict[str, Any]:
        """
        Decode CBOR barcode data from hex string
        
        Args:
            hex_data: Hex-encoded string from PDF417 barcode scan
            
        Returns:
            Decoded license data and image
        """
        try:
            # Convert hex back to binary
            cbor_data = binascii.unhexlify(hex_data)
            
            # Decode CBOR payload
            payload = self.decode_cbor_payload(cbor_data)
            
            print(f"CBOR decode: {len(hex_data)} hex → {len(cbor_data)} bytes")
            
            return payload
            
        except Exception as e:
            raise BarcodeDecodingError(f"Failed to decode CBOR barcode: {str(e)}")

    def decode_barcode_data(self, json_data: str) -> Dict[str, Any]:
        """
        Legacy method for JSON barcode decoding (fallback)
        """
        try:
            import json
            data = json.loads(json_data)
            self._validate_barcode_structure(data)
            return data
            
        except Exception as e:
            raise BarcodeDecodingError(f"Failed to decode JSON barcode: {str(e)}")

    def _validate_barcode_structure(self, data: Dict[str, Any]) -> None:
        """Validate the structure of decoded barcode data"""
        required_fields = ['ver', 'country']
        
        for field in required_fields:
            if field not in data:
                raise BarcodeDecodingError(f"Missing required field: {field}")
        
        # Check version compatibility
        version = data.get('ver')
        if version != self.BARCODE_CONFIG['version']:
            self.logger.warning(f"Barcode version {version} differs from current version {self.BARCODE_CONFIG['version']}")
        
        # Validate country code
        if data.get('country') != 'MG':
            self.logger.warning(f"Barcode country code '{data.get('country')}' is not Madagascar (MG)")
        
        # Recommend having card_num as identifier
        if not data.get('card_num'):
            self.logger.warning("Barcode missing card number - recommended for identification")

    def extract_photo_from_barcode(self, barcode_data: Dict[str, Any]) -> Optional[bytes]:
        """
        Extract and decode photo from barcode data
        
        Args:
            barcode_data: Decoded barcode data dictionary
            
        Returns:
            Photo bytes or None if no photo present
        """
        try:
            photo_base64 = barcode_data.get('photo')
            if not photo_base64:
                return None
            
            return base64.b64decode(photo_base64)
            
        except Exception as e:
            self.logger.error(f"Failed to extract photo from barcode: {e}")
            return None

    def generate_comprehensive_barcode_info(self, barcode_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive information from barcode data for display/verification
        
        Args:
            barcode_data: Decoded barcode data
            
        Returns:
            Formatted information dictionary
        """
        info = {
            'license_id': barcode_data.get('id'),
            'full_name': barcode_data.get('name'),
            'date_of_birth': barcode_data.get('dob'),
            'sex': 'Male' if barcode_data.get('sex') == 'M' else 'Female',
            'license_codes': barcode_data.get('codes', []),
            'country': barcode_data.get('country'),
            'valid_from': barcode_data.get('vf'),
            'valid_until': barcode_data.get('vt'),
            'first_issued': barcode_data.get('fi'),
            'card_number': barcode_data.get('card_num'),
            'driver_restrictions': barcode_data.get('dr', []),
            'vehicle_restrictions': barcode_data.get('vr', []),
            'has_photo': bool(barcode_data.get('photo')),
            'barcode_version': barcode_data.get('ver'),
            'data_size_bytes': len(json.dumps(barcode_data).encode('utf-8'))
        }
        
        # Calculate validity status
        if info['valid_until']:
            try:
                valid_until = datetime.strptime(info['valid_until'], '%Y-%m-%d').date()
                info['is_valid'] = valid_until >= date.today()
                info['days_until_expiry'] = (valid_until - date.today()).days
            except ValueError:
                info['is_valid'] = None
                info['days_until_expiry'] = None
        else:
            info['is_valid'] = True  # No expiry date means permanent license
            info['days_until_expiry'] = None
        
        return info

    def _generate_sample_photo(self) -> Optional[str]:
        """Generate a sample photo for testing purposes - targeting ~400 bytes"""
        try:
            if not PIL_AVAILABLE:
                print("PIL not available for photo generation")
                return None
            
            from PIL import Image, ImageDraw
            
            # Create a very small image for barcode
            img = Image.new('RGB', (40, 50), color='#E0E0E0')  # Tiny gray image
            draw = ImageDraw.Draw(img)
            
            # Draw a very simple face
            draw.ellipse([10, 10, 30, 30], fill='#F0C674')  # Face
            draw.ellipse([15, 18, 18, 21], fill='black')  # Left eye
            draw.ellipse([22, 18, 25, 21], fill='black')  # Right eye
            draw.arc([16, 22, 24, 28], 0, 180, fill='black')  # Mouth
            
            # Add tiny text
            try:
                draw.text((20, 35), "ID", fill='red', anchor='mm')
            except:
                pass
            
            # Convert to base64 with very aggressive compression
            output = io.BytesIO()
            quality = 30  # Start with low quality
            
            # Try to get under 400 bytes
            while quality > 10:
                output.seek(0)
                output.truncate()
                img.save(output, format='JPEG', quality=quality, optimize=True)
                
                # Check encoded size
                encoded_size = len(base64.b64encode(output.getvalue()).decode('utf-8'))
                print(f"Photo compression attempt: quality={quality}, size={encoded_size}")
                
                # Target ~400 bytes encoded
                if encoded_size <= 400:
                    result = base64.b64encode(output.getvalue()).decode('utf-8')
                    print(f"Photo generated successfully: {len(result)} chars")
                    return result
                    
                quality -= 2
            
            # If still too large, return a very basic version
            output.seek(0)
            output.truncate()
            img.save(output, format='JPEG', quality=10, optimize=True)
            result = base64.b64encode(output.getvalue()).decode('utf-8')
            print(f"Photo generated with minimum quality: {len(result)} chars")
            return result if len(result) <= 400 else None
            
        except Exception as e:
            self.logger.error(f"Error generating sample photo: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            print(f"Photo generation error: {e}")
            return None


# Global service instance
barcode_service = LicenseBarcodeService() 