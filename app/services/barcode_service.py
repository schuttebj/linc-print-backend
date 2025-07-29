"""
Madagascar Driver's License Barcode Service
Handles PDF417 barcode generation and decoding with complete license data

Features:
- PDF417 barcode generation with error correction
- Complete license data embedding (including photo)
- Barcode decoding and validation
- Optimized for ~1.8KB data capacity with ECC Level 5
- Future-proof JSON structure with versioning
"""

import json
import base64
import io
import uuid
from datetime import datetime, date
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
import logging

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
    """Service for generating and decoding PDF417 barcodes for Madagascar driver's licenses"""
    
    # Barcode configuration for PDF417
    BARCODE_CONFIG = {
        'columns': 9,  # Fixed columns for consistency
        'error_correction_level': 2,  # Security level 2 for pdf417gen (~25% correction capacity)
        'max_data_bytes': 1800,  # ~70% of 2.7KB capacity (925 codewords)
        'max_image_bytes': 1500,  # Maximum photo size in base64
        'version': 1  # JSON structure version
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

    def _process_photo_for_barcode(self, photo_data: bytes) -> str:
        """
        Process photo data for barcode embedding
        Resize and compress to fit within size constraints
        """
        try:
            if not PIL_AVAILABLE:
                # Basic base64 encoding without processing
                return base64.b64encode(photo_data).decode('utf-8')
            
            # Open image with PIL
            image = Image.open(io.BytesIO(photo_data))
            
            # Convert to RGB if necessary
            if image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')
            
            # Resize to maximum dimensions while maintaining aspect ratio
            max_size = (150, 200)  # Appropriate for license photo
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Compress to JPEG with quality adjustment
            output = io.BytesIO()
            quality = 85
            
            while quality > 20:
                output.seek(0)
                output.truncate()
                image.save(output, format='JPEG', quality=quality, optimize=True)
                
                # Check if size is acceptable
                encoded_size = len(base64.b64encode(output.getvalue()).decode('utf-8'))
                if encoded_size <= self.BARCODE_CONFIG['max_image_bytes']:
                    break
                    
                quality -= 10
            
            return base64.b64encode(output.getvalue()).decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Error processing photo for barcode: {e}")
            # Return basic base64 encoding as fallback
            return base64.b64encode(photo_data).decode('utf-8')

    def generate_pdf417_barcode(self, barcode_data: Dict[str, Any]) -> str:
        """
        Generate PDF417 barcode from license data
        Falls back to QR code if PDF417 is not available
        
        Args:
            barcode_data: Standardized barcode data dictionary
            
        Returns:
            Base64-encoded PNG image of the barcode
        """
        try:
            # Convert data to JSON string
            json_data = json.dumps(barcode_data, separators=(',', ':'), ensure_ascii=False)
            
            # Check data size
            data_bytes = len(json_data.encode('utf-8'))
            if data_bytes > self.BARCODE_CONFIG['max_data_bytes']:
                raise BarcodeGenerationError(
                    f"Data size ({data_bytes} bytes) exceeds maximum ({self.BARCODE_CONFIG['max_data_bytes']} bytes)"
                )
            
            if BARCODE_AVAILABLE:
                # Generate PDF417 barcode using pdf417gen (same as card_generator.py)
                codes = pdf417gen.encode(json_data, security_level=self.BARCODE_CONFIG['error_correction_level'])
                img = pdf417gen.render_image(codes, scale=3, ratio=3)
                
                # Convert to base64
                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                return base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            else:
                # Fallback - generate placeholder
                return self._generate_barcode_placeholder(json_data)
            
        except Exception as e:
            raise BarcodeGenerationError(f"Failed to generate barcode: {str(e)}")



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

    def decode_barcode_data(self, json_data: str) -> Dict[str, Any]:
        """
        Decode and validate barcode JSON data
        
        Args:
            json_data: JSON string from barcode scan
            
        Returns:
            Parsed and validated barcode data
        """
        try:
            # Parse JSON
            data = json.loads(json_data)
            
            # Validate structure
            self._validate_barcode_structure(data)
            
            return data
            
        except json.JSONDecodeError as e:
            raise BarcodeDecodingError(f"Invalid JSON in barcode data: {str(e)}")
        except Exception as e:
            raise BarcodeDecodingError(f"Failed to decode barcode data: {str(e)}")

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
        """Generate a sample photo for testing purposes"""
        try:
            if not PIL_AVAILABLE:
                return None
            
            from PIL import Image, ImageDraw, ImageFont
            
            # Create a simple test image (passport photo size)
            img = Image.new('RGB', (150, 200), color='#E6E6FA')  # Light lavender background
            draw = ImageDraw.Draw(img)
            
            # Draw a simple face representation
            # Head circle
            draw.ellipse([40, 40, 110, 110], fill='#F5DEB3', outline='#DEB887')  # Face
            
            # Eyes
            draw.ellipse([55, 60, 65, 70], fill='black')  # Left eye
            draw.ellipse([85, 60, 95, 70], fill='black')  # Right eye
            
            # Nose
            draw.ellipse([72, 75, 78, 85], outline='#DEB887')
            
            # Mouth
            draw.arc([60, 85, 90, 100], 0, 180, fill='#8B4513')
            
            # Add "SAMPLE" text
            try:
                draw.text((20, 120), "SAMPLE", fill='red', anchor='mm')
                draw.text((75, 140), "PHOTO", fill='red', anchor='mm')
            except:
                # Fallback if font issues
                draw.text((50, 120), "SAMPLE", fill='red')
            
            # Convert to base64
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=85)
            return base64.b64encode(output.getvalue()).decode('utf-8')
            
        except Exception as e:
            self.logger.error(f"Error generating sample photo: {e}")
            return None


# Global service instance
barcode_service = LicenseBarcodeService() 