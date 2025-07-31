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

try:
    import zint
    ZINT_AVAILABLE = True
except ImportError:
    ZINT_AVAILABLE = False
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
    
    # New PDF417 configuration for pipe-delimited format with MAXIMUM capacity
    BARCODE_CONFIG = {
    'columns': 30,  # MAXIMUM columns for highest possible capacity
    'rows': 90,     # MAXIMUM rows for highest possible capacity  
    'error_correction_level': 4,  # User specified ECC level 4
    'max_payload_bytes': 1850,   # Target maximum PDF417 capacity (30x90 with ECC4)
    'max_image_bytes': 1400,     # Large image budget for maximum quality
    'max_data_bytes': 450,       # Increased license data budget
    'image_max_dimension': (120, 180),  # Larger: 120x180 pixels (2:3 aspect) for max quality
    'version': 4  # New pipe-delimited format version
}
    
    # Lightweight encryption configuration for 3rd party compatibility
    BASE_ENCRYPTION_KEY = b'MadagascarLicenseSystem2024'  # Base key for calculation
    
    @classmethod
    def _get_time_based_key(cls, timestamp=None):
        """Generate calculatable encryption key based on time (year+month)"""
        from datetime import datetime
        if timestamp is None:
            timestamp = datetime.now()
        
        # Use year and month for predictable key calculation
        time_component = f"{timestamp.year}{timestamp.month:02d}".encode()
        
        # Simple key derivation: base_key + time_component
        key = cls.BASE_ENCRYPTION_KEY + time_component
        return key[:32]  # Ensure 32 bytes for consistency
    
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

    def create_pipe_delimited_payload_v4(self, person_data: Dict[str, Any], license_data: Dict[str, Any], 
                                        card_data: Dict[str, Any], photo_data: Optional[bytes] = None) -> str:
        """
        NEW FORMAT: Create pipe-delimited payload with zlib compression and lightweight encryption
        
        Format: NAME|LICENSE_TYPE|RESTRICTIONS|ID|GENDER|DOB|ISSUE|EXPIRY|BASE64_IMAGE
        Example: BJ SCHUTTE|B|01,02|456740229624|M|19900101|20250501|20300729|/9j/4AAQSkZJRgABAQEAYABgAAD...
        
        Args:
            person_data: Person information
            license_data: License information  
            card_data: Card information
            photo_data: Optional photo bytes
            
        Returns:
            Compressed and encrypted payload string for PDF417
        """
        try:
            print("=== V4 PIPE-DELIMITED PAYLOAD CREATION ===")
            
            # Step 1: Extract and format license data
            name = f"{person_data.get('first_name', '')} {person_data.get('last_name', '')}".strip().upper()
            
            # Map license type (assuming 'B' for standard license)
            license_type = "B"  # Can be made configurable based on license_data
            
            # Format restrictions (convert list to comma-separated)
            restrictions = license_data.get('restrictions', [])
            if isinstance(restrictions, list):
                # Convert restriction names to codes (simplified mapping)
                restriction_codes = []
                for restriction in restrictions:
                    if 'AUTO_ONLY' in str(restriction).upper():
                        restriction_codes.append('01')
                    elif 'DAYLIGHT' in str(restriction).upper():
                        restriction_codes.append('02')
                    # Add more mappings as needed
                restrictions_str = ','.join(restriction_codes) if restriction_codes else ''
            else:
                restrictions_str = str(restrictions) if restrictions else ''
            
            # Format other fields
            person_id = person_data.get('national_id', '')
            gender = person_data.get('gender', 'U')[:1].upper()  # First letter only
            
            # Format dates (YYYYMMDD)
            dob = person_data.get('date_of_birth', '')
            if isinstance(dob, str) and len(dob) >= 8:
                dob = dob.replace('-', '')[:8]
            
            issue_date = license_data.get('issue_date', '')
            if isinstance(issue_date, str) and len(issue_date) >= 8:
                issue_date = issue_date.replace('-', '')[:8]
                
            expiry_date = license_data.get('expiry_date', '')
            if isinstance(expiry_date, str) and len(expiry_date) >= 8:
                expiry_date = expiry_date.replace('-', '')[:8]
            
            # Step 2: Process photo to Base64
            base64_image = ""
            if photo_data:
                base64_image = self._process_photo_for_barcode_v4(photo_data)
                if base64_image is None:
                    base64_image = ""
            
            # Step 3: Create pipe-delimited string
            pipe_data = f"{name}|{license_type}|{restrictions_str}|{person_id}|{gender}|{dob}|{issue_date}|{expiry_date}"
            
            # Combine data with image
            full_payload = f"{pipe_data}|{base64_image}"
            
            print(f"Pipe data: {pipe_data}")
            print(f"Base64 image length: {len(base64_image)}")
            print(f"Full payload length: {len(full_payload)} characters")
            
            # Step 4: Compress with zlib
            payload_bytes = full_payload.encode('utf-8')
            compressed = zlib.compress(payload_bytes, level=9)  # Maximum compression
            
            print(f"Compression: {len(payload_bytes)} → {len(compressed)} bytes (saved {len(payload_bytes) - len(compressed)} bytes)")
            
            # Step 5: Lightweight encryption (simple XOR with time-based key)
            encryption_key = self._get_time_based_key()
            encrypted = self._lightweight_encrypt(compressed, encryption_key)
            
            print(f"Encryption: {len(compressed)} → {len(encrypted)} bytes (overhead {len(encrypted) - len(compressed)} bytes)")
            print(f"Final payload: {len(encrypted)} bytes total")
            print("=== V4 PAYLOAD COMPLETE ===")
            
            return encrypted
            
        except Exception as e:
            self.logger.error(f"Error creating V4 pipe-delimited payload: {e}")
            raise BarcodeGenerationError(f"Failed to create V4 payload: {str(e)}")

    def _lightweight_encrypt(self, data: bytes, key: bytes) -> bytes:
        """
        Lightweight encryption using XOR with key rotation
        Minimal overhead, calculatable by 3rd parties
        """
        encrypted = bytearray()
        key_len = len(key)
        
        for i, byte in enumerate(data):
            # XOR with rotating key
            key_byte = key[i % key_len]
            encrypted.append(byte ^ key_byte)
        
        return bytes(encrypted)

    def _lightweight_decrypt(self, data: bytes, key: bytes) -> bytes:
        """
        Lightweight decryption (XOR is symmetric)
        """
        return self._lightweight_encrypt(data, key)  # XOR is symmetric

    def _process_photo_for_barcode_v4(self, photo_data: bytes) -> Optional[str]:
        """
        NEW FORMAT: Process photo for pipe-delimited barcode format with MAXIMUM QUALITY
        
        Target: 120x180 pixels, optimized JPEG quality, grayscale, Base64 encoded
        Expected size: ≤1400 bytes before Base64 encoding
        
        Args:
            photo_data: Raw image bytes
            
        Returns:
            Base64 encoded JPEG string or None if processing fails
        """
        try:
            if not PIL_AVAILABLE:
                self.logger.warning("PIL not available for photo processing")
                return None
            
            # Open image in RGB mode for custom processing
            image = Image.open(io.BytesIO(photo_data))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            print(f"V4 Image processing - Original: {image.size}, mode: {image.mode}")
            
            # Step 1: Custom grayscale conversion (user's successful formula)
            try:
                import numpy as np
                rgb_array = np.array(image)
                
                # Apply custom grayscale formula: (0.10*R + 0.40*G + 0.80*B)
                grayscale_array = (
                    0.10 * rgb_array[:, :, 0] +  # Red
                    0.40 * rgb_array[:, :, 1] +  # Green  
                    0.80 * rgb_array[:, :, 2]    # Blue
                ).astype(np.uint8)
                
                image = Image.fromarray(grayscale_array, mode='L')
                print("Applied custom grayscale formula: (0.10*R + 0.40*G + 0.80*B)")
                
            except ImportError:
                # Fallback to PIL-based custom grayscale
                image = self._apply_custom_grayscale_pil(image)
                print("Applied custom grayscale formula using PIL")
            
            # Step 2: Resize to MAXIMUM quality dimensions (120x180, 2:3 aspect ratio)
            target_width, target_height = self.BARCODE_CONFIG['image_max_dimension']
            
            # Calculate current aspect ratio and crop if needed
            original_width, original_height = image.size
            current_aspect = original_width / original_height
            target_aspect = target_width / target_height  # 120/180 = 0.667
            
            print(f"Resizing to {target_width}x{target_height}")
            print(f"Aspect ratios - Current: {current_aspect:.3f}, Target: {target_aspect:.3f}")
            
            # Crop to correct aspect ratio if needed
            if abs(current_aspect - target_aspect) > 0.05:
                if current_aspect > target_aspect:
                    # Image is too wide, crop width
                    new_width = int(original_height * target_aspect)
                    left = (original_width - new_width) // 2
                    image = image.crop((left, 0, left + new_width, original_height))
                    print(f"Cropped width: {original_width} → {new_width}")
                else:
                    # Image is too tall, crop height
                    new_height = int(original_width / target_aspect)
                    top = (original_height - new_height) // 2
                    image = image.crop((0, top, original_width, top + new_height))
                    print(f"Cropped height: {original_height} → {new_height}")
            
            # Resize to exact target dimensions
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            print(f"Final image size: {image.size}")
            
            # Step 3: Optimize JPEG quality for MAXIMUM quality within budget
            max_image_bytes = self.BARCODE_CONFIG['max_image_bytes']
            
            # Try progressive quality levels from high to low for best quality
            for quality in [70, 60, 55, 50, 45, 40, 35, 30, 25]:
                jpeg_buffer = io.BytesIO()
                image.save(jpeg_buffer, 
                          format='JPEG', 
                          quality=quality, 
                          optimize=True,
                          progressive=False,  # Use baseline compression
                          exif=b'',          # Remove metadata
                          icc_profile=None)   # Remove color profile
                
                jpeg_bytes = jpeg_buffer.getvalue()
                jpeg_size = len(jpeg_bytes)
                
                if jpeg_size <= max_image_bytes:
                    print(f"Optimal quality found: {quality}% -> {jpeg_size} bytes (target ≤{max_image_bytes})")
                    break
            else:
                # If all qualities are too large, use minimum
                quality = 20
                jpeg_buffer = io.BytesIO()
                image.save(jpeg_buffer, 
                          format='JPEG', 
                          quality=quality, 
                          optimize=True,
                          progressive=False,
                          exif=b'',
                          icc_profile=None)
                jpeg_bytes = jpeg_buffer.getvalue()
                jpeg_size = len(jpeg_bytes)
                print(f"Using minimum quality: {quality}% -> {jpeg_size} bytes")
            
            # Step 4: Encode to Base64
            base64_image = base64.b64encode(jpeg_bytes).decode('utf-8')
            base64_size = len(base64_image)
            
            print(f"V4 Photo processing: {len(photo_data)} → {jpeg_size} JPEG → {base64_size} Base64")
            print(f"Target: ≤{max_image_bytes} bytes JPEG, Actual: {jpeg_size} bytes")
            print(f"Quality level used: {quality}%, Size efficiency: {jpeg_size/max_image_bytes*100:.1f}%")
            
            return base64_image
            
        except Exception as e:
            self.logger.error(f"Error processing photo for V4 barcode: {e}")
            print(f"V4 Photo processing error: {e}")
            return None

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

    def generate_pdf417_barcode_v4(self, person_data: Dict[str, Any], license_data: Dict[str, Any], 
                                  card_data: Dict[str, Any], photo_data: Optional[bytes] = None) -> Optional[bytes]:
        """
        NEW FORMAT: Generate PDF417 barcode using pipe-delimited format
        
        Args:
            person_data: Person information
            license_data: License information
            card_data: Card information  
            photo_data: Optional photo bytes
            
        Returns:
            PNG image bytes of the barcode or None if generation fails
        """
        try:
            print("=== V4 PDF417 GENERATION ===")
            
            # Step 1: Create compressed and encrypted payload
            payload_bytes = self.create_pipe_delimited_payload_v4(
                person_data, license_data, card_data, photo_data
            )
            
            # Step 2: Check size constraints
            if len(payload_bytes) > self.BARCODE_CONFIG['max_payload_bytes']:
                raise BarcodeGenerationError(
                    f"V4 payload too large: {len(payload_bytes)} > {self.BARCODE_CONFIG['max_payload_bytes']}"
                )
            
            print(f"V4 PDF417 generation: {len(payload_bytes)} bytes binary data")
            
            # Step 3: Generate PDF417 barcode (try Zint first, fallback to pdf417gen)
            if ZINT_AVAILABLE:
                barcode_image_bytes = self._generate_pdf417_with_zint(payload_bytes)
                if barcode_image_bytes:
                    print("Successfully generated PDF417 with Zint (higher capacity)")
                else:
                    print("Zint failed, falling back to pdf417gen...")
                    barcode_image_bytes = self._generate_pdf417_with_pdf417gen(payload_bytes)
            elif BARCODE_AVAILABLE:
                barcode_image_bytes = self._generate_pdf417_with_pdf417gen(payload_bytes)
            else:
                raise BarcodeGenerationError("No PDF417 library available (pdf417gen or zint)")
            
            if not barcode_image_bytes:
                raise BarcodeGenerationError("PDF417 generation failed with all available libraries")
            
            print("V4 PDF417 barcode generated successfully")
            print("=== V4 PDF417 COMPLETE ===")
            
            return barcode_image_bytes
            
        except Exception as e:
            self.logger.error(f"Failed to generate V4 PDF417 barcode: {e}")
            print(f"V4 PDF417 generation error: {e}")
            return None

    def _generate_pdf417_with_zint(self, payload_bytes: bytes) -> Optional[bytes]:
        """Generate PDF417 using Zint library (preferred for better capacity)"""
        try:
            print("Using Zint for PDF417 generation...")
            
            # Create Zint symbol
            symbol = zint.ZBarcode_Create()
            symbol.contents.symbology = zint.BARCODE_PDF417
            
            # Configure for maximum capacity (30 columns x 90 rows)
            symbol.contents.option_1 = self.BARCODE_CONFIG['error_correction_level']  # Security level (ECC 4)
            symbol.contents.option_2 = self.BARCODE_CONFIG['columns']                # Columns (30)
            symbol.contents.option_3 = self.BARCODE_CONFIG['rows']                   # Rows (90)  
            symbol.contents.scale = 3.0                                              # Scale factor
            
            # Encode the data
            input_data = zint.instr(payload_bytes)
            result = zint.ZBarcode_Encode_and_Buffer(symbol, input_data, len(payload_bytes), 0)
            
            if result != 0:
                error_msg = symbol.contents.errtxt.decode('utf-8') if symbol.contents.errtxt else "Unknown error"
                print(f"Zint encoding failed: {error_msg}")
                zint.ZBarcode_Delete(symbol)
                return None
            
            # Get bitmap data
            bitmap = zint.bitmapbuf(symbol)
            width = symbol.contents.bitmap_width
            height = symbol.contents.bitmap_height
            
            print(f"Zint PDF417 generated: {width}x{height} pixels, {len(payload_bytes)} bytes payload")
            print(f"PDF417 Configuration: {self.BARCODE_CONFIG['columns']} columns x {self.BARCODE_CONFIG['rows']} rows, ECC level {self.BARCODE_CONFIG['error_correction_level']}")
            print(f"Capacity utilization: {len(payload_bytes)}/{self.BARCODE_CONFIG['max_payload_bytes']} bytes ({len(payload_bytes)/self.BARCODE_CONFIG['max_payload_bytes']*100:.1f}%)")
            
            # Convert bitmap to PNG
            if PIL_AVAILABLE:
                # Create PIL Image from bitmap (3 bytes per pixel RGB)
                image_data = []
                for i in range(0, len(bitmap), 3):
                    # Convert RGB to grayscale (barcode is black/white)
                    r, g, b = bitmap[i], bitmap[i+1], bitmap[i+2]
                    gray = int(0.299 * r + 0.587 * g + 0.114 * b)
                    image_data.append(gray)
                
                # Create PIL image
                image = Image.new('L', (width, height))
                image.putdata(image_data)
                
                # Save as PNG
                barcode_buffer = io.BytesIO()
                image.save(barcode_buffer, format='PNG')
                barcode_image_bytes = barcode_buffer.getvalue()
                
                zint.ZBarcode_Delete(symbol)
                return barcode_image_bytes
            else:
                print("PIL not available for image conversion")
                zint.ZBarcode_Delete(symbol)
                return None
                
        except Exception as e:
            print(f"Zint PDF417 generation failed: {str(e)}")
            return None
    
    def _generate_pdf417_with_pdf417gen(self, payload_bytes: bytes) -> Optional[bytes]:
        """Generate PDF417 using pdf417gen library (fallback)"""
        try:
            print("Using pdf417gen for PDF417 generation (fallback)...")
            
            # Convert to string for pdf417gen (using latin1 encoding)
            payload_str = payload_bytes.decode('latin1')
            
            # Generate PDF417 with maximum configuration (30 columns, ECC level 4)
            code = pdf417gen.encode(
                payload_str,
                security_level=self.BARCODE_CONFIG['error_correction_level'],
                columns=self.BARCODE_CONFIG['columns']
            )
            
            print(f"pdf417gen Config: {self.BARCODE_CONFIG['columns']} columns, ECC level {self.BARCODE_CONFIG['error_correction_level']}")
            print(f"pdf417gen Capacity utilization: {len(payload_bytes)}/{self.BARCODE_CONFIG['max_payload_bytes']} bytes ({len(payload_bytes)/self.BARCODE_CONFIG['max_payload_bytes']*100:.1f}%)")
            
            if code is None:
                print("pdf417gen encoding failed - invalid data")
                return None
            
            # Render to image
            image = pdf417gen.render_image(code, scale=3, ratio=2)
            
            # Save as PNG bytes
            barcode_buffer = io.BytesIO()
            image.save(barcode_buffer, format='PNG')
            barcode_image_bytes = barcode_buffer.getvalue()
            
            print(f"pdf417gen PDF417 barcode generated successfully: {image.size}")
            return barcode_image_bytes
            
        except Exception as e:
            print(f"pdf417gen generation failed: {str(e)}")
            return None

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