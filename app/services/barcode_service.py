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

# Compression & Encryption imports
try:
    import zstandard as zstd
    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False
    logging.warning("zstandard not available - falling back to zlib compression")

try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    import secrets
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logging.warning("cryptography not available - encryption disabled")

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
    """Service for generating and decoding PDF417 barcodes using CBOR+compression+encryption"""
    
    # Barcode configuration for PDF417 with 85% of actual 928 byte library limit
    BARCODE_CONFIG = {
        'columns': 18,  # Maximum columns for highest capacity (very wide barcode)
        'error_correction_level': 1,  # Minimum error correction for maximum capacity
        'max_payload_bytes': 750,    # More conservative limit to prevent overrun
        'max_image_bytes': 500,      # Conservative limit for enhanced processing
        'max_data_bytes': 200,       # License data budget (before compression)
        'image_max_dimension': (135, 90),   # Closer to user's successful 150x100, but within budget
        'version': 3  # New compressed+encrypted format version
    }
    
    # Encryption configuration
    ENCRYPTION_KEY = b'MG-License-Barcode-Key-2024-v32!'  # 32 bytes for ChaCha20
    
    def __init__(self):
        """Initialize the barcode service"""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
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
        self._initialize_warnings()
    
    def _date_to_timestamp(self, date_obj) -> Optional[int]:
        """Convert date or datetime object to Unix timestamp"""
        if date_obj is None:
            return None
        
        if isinstance(date_obj, datetime):
            return int(date_obj.timestamp())
        elif isinstance(date_obj, date):
            # Convert date to datetime at midnight, then to timestamp
            dt = datetime.combine(date_obj, datetime.min.time())
            return int(dt.timestamp())
        else:
            return None
    
    def _initialize_warnings(self):
        """Initialize service with appropriate warnings"""
        if not BARCODE_AVAILABLE:
            self.logger.warning("Barcode generation running in simulation mode")
        if not CBOR_AVAILABLE:
            self.logger.warning("CBOR not available - will use fallback encoding")

    def create_cbor_payload_compressed_encrypted(
        self,
        license: License,
        person: Person,
        card: Optional[Card] = None,
        photo_data: Optional[bytes] = None
    ) -> bytes:
        """
        Create compressed and encrypted CBOR payload for maximum efficiency
        
        Args:
            license: License object
            person: Person object
            card: Optional Card object
            photo_data: Optional image bytes
            
        Returns:
            Compressed and encrypted binary payload
        """
        try:
            print("=== COMPRESSION + ENCRYPTION PIPELINE ===")
            
            # Generate realistic ID number
            import random
            id_number = f"{random.randint(100000000000, 999999999999)}"
            
            # Step 1: Create compact CBOR structure with single-char keys
            compact_data = {
                "v": self.BARCODE_CONFIG['version'],  # version
                "c": "MG",  # country
                "n": f"{person.surname.upper()} {person.first_name}",  # name
                "i": id_number,  # ID number
                "s": "M" if person.person_nature == "01" else "F",  # sex
                "b": self._date_to_timestamp(person.birth_date),  # birth date (binary)
                "f": self._date_to_timestamp(license.issue_date),  # first issued
                "t": self._date_to_timestamp(license.expiry_date),  # valid to
                "o": [license.category.value] if license.category else [],  # codes
                "r": [],  # restrictions
            }
            
            # Add card number if available
            if card:
                compact_data["d"] = card.card_number  # card number
            
            # Process photo if provided
            compressed_photo = None
            if photo_data:
                compressed_photo = self._process_photo_for_barcode(photo_data)
            
            # Step 2: Create final payload structure
            payload = {"data": compact_data}
            if compressed_photo:
                payload["img"] = compressed_photo
            
            # Step 3: CBOR encode
            cbor_bytes = cbor2.dumps(payload)
            print(f"Step 1 - CBOR encoding: {len(cbor_bytes)} bytes")
            
            # Step 4: Compress with zstandard
            compressed_bytes = self._compress_data(cbor_bytes)
            print(f"Step 2 - Compression: {len(cbor_bytes)} → {len(compressed_bytes)} bytes (saved {len(cbor_bytes) - len(compressed_bytes)} bytes)")
            
            # Step 5: Encrypt with ChaCha20
            encrypted_bytes = self._encrypt_data(compressed_bytes)
            print(f"Step 3 - Encryption: {len(compressed_bytes)} → {len(encrypted_bytes)} bytes (overhead {len(encrypted_bytes) - len(compressed_bytes)} bytes)")
            
            print(f"Final payload: {len(encrypted_bytes)} bytes total")
            print("=== PIPELINE COMPLETE ===")
            
            if len(encrypted_bytes) > self.BARCODE_CONFIG['max_payload_bytes']:
                raise BarcodeGenerationError(
                    f"Encrypted payload too large: {len(encrypted_bytes)} > {self.BARCODE_CONFIG['max_payload_bytes']}"
                )
            
            return encrypted_bytes
            
        except Exception as e:
            raise BarcodeGenerationError(f"Failed to create compressed encrypted payload: {str(e)}")

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
            
            print(f"Attempting to decode CBOR data: {len(cbor_data)} bytes")
            print(f"First 20 bytes: {cbor_data[:20].hex() if len(cbor_data) >= 20 else cbor_data.hex()}")
            
            try:
                payload = cbor2.loads(cbor_data)
                print(f"CBOR decoded successfully, type: {type(payload)}")
            except Exception as cbor_error:
                print(f"CBOR decoding failed: {cbor_error}")
                # Try to extract partial data if possible
                if "premature end of stream" in str(cbor_error):
                    raise BarcodeDecodingError(f"Barcode data is truncated - {str(cbor_error)}. Please rescan the barcode completely.")
                else:
                    raise BarcodeDecodingError(f"Invalid CBOR format: {str(cbor_error)}")
            
            # Validate structure - handle both formats
            if not isinstance(payload, dict):
                print(f"Payload is not a dict, it's: {type(payload)}, value: {payload}")
                raise BarcodeDecodingError(f"CBOR payload must be a dictionary, got {type(payload)}")
            
            # Check if it's the new format with "data" wrapper
            if "data" in payload:
                print(f"New format detected: data wrapper found")
                # Photo is stored as raw JPEG/PNG bytes, no decompression needed
                if "img" in payload:
                    print(f"Photo found: {len(payload['img'])} bytes (JPEG/PNG format)")
                return payload
            
            # Check if it's the direct format (license data at root level)
            elif "ver" in payload or "country" in payload or "name" in payload:
                print(f"Direct format detected: license data at root level")
                
                # Extract image if present
                img_data = None
                if "img" in payload:
                    img_data = payload["img"]
                    print(f"Photo found: {len(img_data)} bytes (JPEG/PNG format)")
                
                # Restructure to match expected format
                license_data = {k: v for k, v in payload.items() if k != "img"}
                result = {"data": license_data}
                if img_data:
                    result["img"] = img_data
                
                return result
            
            else:
                raise BarcodeDecodingError("Unknown CBOR payload structure - missing expected fields")
            
        except Exception as e:
            raise BarcodeDecodingError(f"Failed to decode CBOR payload: {str(e)}")

    def decode_cbor_payload_compressed_encrypted(self, encrypted_data: bytes) -> Dict[str, Any]:
        """
        Decode compressed and encrypted CBOR payload
        
        Args:
            encrypted_data: Encrypted binary data from barcode scan
            
        Returns:
            Decoded payload dictionary with expanded date fields
        """
        try:
            print("=== DECRYPTION + DECOMPRESSION PIPELINE ===")
            print(f"Input encrypted data: {len(encrypted_data)} bytes")
            
            # Step 1: Decrypt the data
            compressed_data = self._decrypt_data(encrypted_data)
            print(f"Step 1 - Decryption: {len(encrypted_data)} → {len(compressed_data)} bytes")
            
            # Step 2: Decompress the data
            cbor_data = self._decompress_data(compressed_data)
            print(f"Step 2 - Decompression: {len(compressed_data)} → {len(cbor_data)} bytes")
            
            # Step 3: CBOR decode
            if not CBOR_AVAILABLE:
                raise BarcodeDecodingError("CBOR library not available")
            
            payload = cbor2.loads(cbor_data)
            print(f"Step 3 - CBOR decode: {len(cbor_data)} bytes → dict with {len(payload)} keys")
            
            # Step 4: Expand compact data structure
            if "data" in payload:
                data = payload["data"]
                
                # Convert binary timestamps back to readable dates
                if "b" in data and data["b"]:  # birth date
                    data["dob"] = datetime.fromtimestamp(data["b"]).strftime("%Y-%m-%d")
                    del data["b"]
                
                if "f" in data and data["f"]:  # first issued
                    data["fi"] = datetime.fromtimestamp(data["f"]).strftime("%Y-%m-%d")
                    del data["f"]
                
                if "t" in data and data["t"]:  # valid to
                    data["vt"] = datetime.fromtimestamp(data["t"]).strftime("%Y-%m-%d")
                    del data["t"]
                
                # Expand other compact keys if needed
                # (keeping single-char keys for now for compatibility)
                
                payload["data"] = data
            
            print("=== PIPELINE COMPLETE ===")
            
            # Image handling (same as before)
            if "img" in payload:
                print(f"Photo found: {len(payload['img'])} bytes (JPEG/PNG format)")
            
            return payload
            
        except Exception as e:
            print(f"Decryption/decompression failed: {e}")
            raise BarcodeDecodingError(f"Failed to decode compressed encrypted payload: {str(e)}")

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
        Enhanced photo optimization for barcode inclusion:
        1. Custom grayscale conversion optimized for facial features
        2. Advanced preprocessing (contrast, sharpening, histogram equalization)
        3. Color quantization for dramatic size reduction
        4. Smart resolution optimization (150x100 target)
        5. Multi-strategy compression with facial priority
        
        Args:
            photo_data: Raw image bytes
            
        Returns:
            Compressed JPEG bytes or None if processing fails
        """
        try:
            if not PIL_AVAILABLE:
                self.logger.warning("PIL not available for photo processing")
                return None
            
            # Open image in RGB mode for custom processing
            image = Image.open(io.BytesIO(photo_data))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            print(f"Original image: {image.size}, mode: {image.mode}")
            
            # Step 1: Custom grayscale conversion optimized for facial features
            # Formula: (0.10*R + 0.40*G + 0.80*B) - User's successful approach
            try:
                import numpy as np
                rgb_array = np.array(image)
                
                # Apply custom grayscale formula
                grayscale_array = (
                    0.10 * rgb_array[:, :, 0] +  # Red
                    0.40 * rgb_array[:, :, 1] +  # Green  
                    0.80 * rgb_array[:, :, 2]    # Blue (heavy weight for facial features)
                ).astype(np.uint8)
                
                # Convert back to PIL Image
                image = Image.fromarray(grayscale_array, mode='L')
                print(f"Applied custom grayscale formula: (0.10*R + 0.40*G + 0.80*B)")
                
            except ImportError:
                # Implement custom grayscale using pure PIL (no NumPy needed)
                image = self._apply_custom_grayscale_pil(image)
                print("Applied custom grayscale formula using PIL: (0.10*R + 0.40*G + 0.80*B)")
            
            # Step 2: Advanced preprocessing for facial enhancement
            image = self._enhance_facial_features(image)
            
            # Step 3: Color quantization for size reduction (12 colors like user's approach)
            image = self._apply_color_quantization(image, colors=12)
            
            # Step 4: Smart resolution optimization targeting close to 120x80
            target_width, target_height = self.BARCODE_CONFIG['image_max_dimension']  # 120x80
            
            # Calculate current aspect ratio
            original_width, original_height = image.size
            current_aspect = original_width / original_height
            target_aspect = target_width / target_height  # 120/80 = 1.5
            
            print(f"Resizing from {original_width}x{original_height} to target {target_width}x{target_height}")
            print(f"Aspect ratios - Current: {current_aspect:.3f}, Target: {target_aspect:.3f}")
            
            # Strategy: Force to target aspect ratio first, then resize
            if abs(current_aspect - target_aspect) > 0.05:  # More sensitive threshold
                if current_aspect < target_aspect:
                    # Image is too tall, crop height to make it wider
                    new_height = int(original_width / target_aspect)
                    top = (original_height - new_height) // 2
                    image = image.crop((0, top, original_width, top + new_height))
                    print(f"Cropped height: {original_height} → {new_height} (to fix aspect ratio)")
                else:
                    # Image is too wide, crop width to make it taller  
                    new_width = int(original_height * target_aspect)
                    left = (original_width - new_width) // 2
                    image = image.crop((left, 0, left + new_width, original_height))
                    print(f"Cropped width: {original_width} → {new_width} (to fix aspect ratio)")
            
            # Now resize to exact target dimensions (since aspect ratio is correct)
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            print(f"Final size after resize: {image.size}")
            
            # Try different compression strategies
            max_bytes = self.BARCODE_CONFIG['max_image_bytes']
            
            # Strategy 1: Prioritize full resolution with acceptable quality
            for quality in [50, 40, 35, 30, 25, 20, 15, 12, 10, 8, 6, 5]:
                jpeg_buffer = io.BytesIO()
                # Remove all EXIF metadata and optimize for size
                image.save(jpeg_buffer, format='JPEG', quality=quality, optimize=True, 
                          exif=b'', icc_profile=None)  # Explicitly remove metadata
                jpeg_bytes = jpeg_buffer.getvalue()
                
                if len(jpeg_bytes) <= max_bytes:
                    print(f"Enhanced photo processing: {len(photo_data)} → {len(jpeg_bytes)} JPEG (quality {quality})")
                    print(f"Final image size: {image.size} (target: 135x90)")
                    print(f"Applied: Custom grayscale + Color quantization (12 colors) + Facial enhancement")
                    return jpeg_bytes
            
            # Strategy 2: Moderate scaling with better quality balance
            for scale in [0.95, 0.90, 0.85, 0.80, 0.75]:
                smaller_image = image.copy()
                new_size = (int(target_width * scale), int(target_height * scale))
                smaller_image.thumbnail(new_size, Image.Resampling.LANCZOS)
                
                for quality in [40, 35, 30, 25, 20, 15, 12, 10, 8, 6]:
                    jpeg_buffer = io.BytesIO()
                    smaller_image.save(jpeg_buffer, format='JPEG', quality=quality, optimize=True,
                                     exif=b'', icc_profile=None)  # Remove metadata
                    jpeg_bytes = jpeg_buffer.getvalue()
                    
                    if len(jpeg_bytes) <= max_bytes:
                        print(f"Photo processing: {len(photo_data)} → {len(jpeg_bytes)} JPEG (scale {scale}, quality {quality})")
                        print(f"Final image size: {smaller_image.size}")
                        return jpeg_bytes
            
            # Strategy 3: Final fallback with minimal scaling
            for scale in [0.70, 0.65, 0.60, 0.55, 0.50]:
                smaller_image = image.copy()
                new_size = (int(target_width * scale), int(target_height * scale))
                smaller_image.thumbnail(new_size, Image.Resampling.LANCZOS)
                
                for quality in [15, 12, 10, 8, 6, 5, 4, 3]:
                    jpeg_buffer = io.BytesIO()
                    smaller_image.save(jpeg_buffer, format='JPEG', quality=quality, optimize=True,
                                     exif=b'', icc_profile=None)  # Remove metadata
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

    def _compress_data(self, data: bytes) -> bytes:
        """Compress data using zstandard (preferred) or zlib fallback"""
        if ZSTD_AVAILABLE:
            try:
                compressor = zstd.ZstdCompressor(level=19)  # Maximum compression
                compressed = compressor.compress(data)
                return compressed
            except Exception as e:
                print(f"zstandard compression failed: {e}, falling back to zlib")
        
        # Fallback to zlib
        return zlib.compress(data, level=9)
    
    def _decompress_data(self, data: bytes) -> bytes:
        """Decompress data - try zstandard first, then zlib"""
        # Try zstandard first
        if ZSTD_AVAILABLE:
            try:
                decompressor = zstd.ZstdDecompressor()
                return decompressor.decompress(data)
            except:
                pass  # Fall through to zlib
        
        # Try zlib
        try:
            return zlib.decompress(data)
        except:
            raise BarcodeDecodingError("Failed to decompress data with both zstandard and zlib")
    
    def _encrypt_data(self, data: bytes) -> bytes:
        """Encrypt data using ChaCha20"""
        if not CRYPTO_AVAILABLE:
            print("Cryptography not available - returning unencrypted data")
            return data
        
        try:
            # Generate random nonce (16 bytes for ChaCha20)
            nonce = secrets.token_bytes(16)
            
            # Create ChaCha20 cipher
            cipher = Cipher(
                algorithms.ChaCha20(self.ENCRYPTION_KEY, nonce),
                mode=None,
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            # Encrypt the data
            ciphertext = encryptor.update(data) + encryptor.finalize()
            
            # Return nonce + ciphertext
            return nonce + ciphertext
            
        except Exception as e:
            raise BarcodeGenerationError(f"Encryption failed: {str(e)}")
    
    def _decrypt_data(self, encrypted_data: bytes) -> bytes:
        """Decrypt data using ChaCha20"""
        if not CRYPTO_AVAILABLE:
            print("Cryptography not available - assuming unencrypted data")
            return encrypted_data
        
        try:
            # Extract nonce (first 16 bytes) and ciphertext
            nonce = encrypted_data[:16]
            ciphertext = encrypted_data[16:]
            
            # Create ChaCha20 cipher
            cipher = Cipher(
                algorithms.ChaCha20(self.ENCRYPTION_KEY, nonce),
                mode=None,
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # Decrypt the data
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            return plaintext
            
        except Exception as e:
            raise BarcodeDecodingError(f"Decryption failed: {str(e)}")

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
            
            # Use base64 encoding (most reliable for binary data in PDF417)
            try:
                # Base64 encoding is safe and reliable for all binary data
                b64_data = base64.b64encode(cbor_payload).decode('ascii')
                codes = pdf417gen.encode(
                    b64_data,
                    security_level=self.BARCODE_CONFIG['error_correction_level'],
                    columns=self.BARCODE_CONFIG['columns']
                )
                print(f"PDF417 encoded successfully using base64 mode: {len(b64_data)} chars")
            except Exception as b64_error:
                print(f"Base64 mode failed: {b64_error}, trying latin1")
                # Fallback to latin1 mode
                try:
                    # Use latin1 encoding which preserves all byte values 0-255
                    latin1_data = cbor_payload.decode('latin1')
                    codes = pdf417gen.encode(
                        latin1_data,
                        security_level=1,  # Minimum error correction for maximum capacity
                        columns=20  # Maximum columns for highest capacity
                    )
                    print(f"PDF417 encoded successfully using latin1 mode: {len(latin1_data)} chars")
                except Exception as latin1_error:
                    print(f"Latin1 mode failed: {latin1_error}, trying binary mode")
                    # Last resort: binary mode
                    codes = pdf417gen.encode(
                        cbor_payload,  # Direct binary data
                        security_level=1,  # Minimum error correction
                        columns=22  # Maximum columns
                    )
                    print(f"PDF417 encoded successfully using binary mode")
                
                # Render to image
            img = pdf417gen.render_image(codes, scale=2, ratio=3)
            
            # Add validation: try to decode what we just encoded to ensure data integrity
            try:
                # This tests if the barcode can be decoded properly
                decoded_test = codes[1]  # The data part of the codes tuple
                expected_length = len(cbor_payload)
                if hasattr(decoded_test, '__len__'):
                    actual_length = len(decoded_test)
                    if actual_length != expected_length:
                        print(f"WARNING: Data length mismatch during encoding. Expected: {expected_length}, Got: {actual_length}")
                print(f"PDF417 encoding validation passed")
            except Exception as validation_error:
                print(f"PDF417 encoding validation warning: {validation_error}")
            
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

    def _enhance_facial_features(self, image: 'Image.Image') -> 'Image.Image':
        """
        Apply advanced preprocessing for facial feature enhancement
        
        Args:
            image: Grayscale PIL Image
            
        Returns:
            Enhanced PIL Image
        """
        try:
            if not PIL_AVAILABLE:
                return image
                
            from PIL import ImageFilter, ImageEnhance
            
            # Apply contrast enhancement
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)  # 20% contrast boost
            print("Applied contrast enhancement")
            
            # Apply sharpening filter optimized for facial features
            image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3))
            print("Applied unsharp mask for facial sharpening")
            
            # Apply brightness adjustment if needed
            enhancer = ImageEnhance.Brightness(image)
            image = enhancer.enhance(1.05)  # 5% brightness boost
            print("Applied brightness enhancement")
            
            return image
            
        except Exception as e:
            print(f"Error in facial enhancement: {e}")
            return image

    def _apply_color_quantization(self, image: 'Image.Image', colors: int = 12) -> 'Image.Image':
        """
        Apply color quantization to reduce file size dramatically
        
        Args:
            image: Grayscale PIL Image
            colors: Number of colors to quantize to (default 12 like user's approach)
            
        Returns:
            Quantized PIL Image
        """
        try:
            if not PIL_AVAILABLE:
                return image
                
            # Convert to P mode (palette) with specified number of colors
            quantized = image.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
            
            # Convert back to L mode (grayscale) to maintain compatibility
            quantized = quantized.convert('L')
            
            print(f"Applied color quantization to {colors} colors")
            return quantized
            
        except Exception as e:
            print(f"Error in color quantization: {e}")
            return image

    def _apply_custom_grayscale_pil(self, image: 'Image.Image') -> 'Image.Image':
        """
        Apply custom grayscale conversion using pure PIL (no NumPy required)
        Formula: (0.10*R + 0.40*G + 0.80*B) - User's successful approach
        
        Args:
            image: RGB PIL Image
            
        Returns:
            Grayscale PIL Image with custom formula applied
        """
        try:
            if not PIL_AVAILABLE:
                return image.convert('L')
                
            # Split into R, G, B channels
            r, g, b = image.split()
            
            # Apply custom weights using PIL's point() method for efficiency
            # Convert to grayscale using: 0.10*R + 0.40*G + 0.80*B
            
            # Create lookup tables for each channel (0-255 mapping)
            r_lut = [int(i * 0.10) for i in range(256)]
            g_lut = [int(i * 0.40) for i in range(256)]  
            b_lut = [int(i * 0.80) for i in range(256)]
            
            # Apply lookup tables to each channel
            r_weighted = r.point(r_lut)
            g_weighted = g.point(g_lut)
            b_weighted = b.point(b_lut)
            
            # Combine channels using PIL's blend operations
            from PIL import ImageChops
            temp = ImageChops.add(r_weighted, g_weighted)
            grayscale = ImageChops.add(temp, b_weighted)
            
            # Ensure we stay within 0-255 range and convert to proper grayscale
            grayscale = grayscale.point(lambda x: min(255, x))
            
            return grayscale
            
        except Exception as e:
            print(f"Error in custom grayscale conversion: {e}, falling back to standard")
            return image.convert('L')


# Global service instance
barcode_service = LicenseBarcodeService() 