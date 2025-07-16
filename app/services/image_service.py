"""
Image Processing Service for Madagascar License System

Handles ISO-compliant photo processing for driver's license cards:
- Automatic cropping to 3:4 aspect ratio (35mm x 45mm equivalent)
- Face-centered positioning
- Quality optimization
- Format standardization
"""

import io
import uuid
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from PIL import Image, ImageEnhance, ImageFilter
from fastapi import HTTPException, UploadFile
import logging

logger = logging.getLogger(__name__)

class ImageProcessingService:
    """Service for processing driver's license photos to ISO standards"""
    
    # ISO standard dimensions for passport/license photos
    ISO_WIDTH = 300   # pixels (35mm equivalent)
    ISO_HEIGHT = 400  # pixels (45mm equivalent) 
    ISO_ASPECT_RATIO = 3 / 4  # width / height
    
    # License-ready dimensions (for card production)
    LICENSE_READY_MIN_HEIGHT = 64   # pixels
    LICENSE_READY_MAX_HEIGHT = 128  # pixels
    LICENSE_READY_TARGET_SIZE = 1500  # bytes (1.5KB max)
    
    # Quality settings
    JPEG_QUALITY = 90
    LICENSE_READY_QUALITY_START = 85  # Starting quality for license-ready
    MAX_FILE_SIZE_KB = 500  # Maximum output file size for standard
    
    # Supported formats
    SUPPORTED_FORMATS = {'JPEG', 'JPG', 'PNG', 'BMP', 'TIFF'}
    
    @classmethod
    def process_license_photo(
        cls, 
        image_file: UploadFile,
        storage_path: Path,
        filename_prefix: str = "license_photo"
    ) -> Dict[str, Any]:
        """
        Process uploaded image to ISO-compliant license photo
        
        Args:
            image_file: Uploaded image file
            storage_path: Directory to save processed image
            filename_prefix: Prefix for saved filename
            
        Returns:
            Dict with processing results and file info
        """
        try:
            # Validate file
            if not image_file.content_type or not image_file.content_type.startswith('image/'):
                raise HTTPException(
                    status_code=400,
                    detail="File must be an image"
                )
            
            # Read image data
            image_data = image_file.file.read()
            if len(image_data) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Empty image file"
                )
            
            # Open and validate image
            try:
                image = Image.open(io.BytesIO(image_data))
                image.verify()  # Verify it's a valid image
                
                # Reopen for processing (verify() closes the image)
                image = Image.open(io.BytesIO(image_data))
                
            except Exception as e:
                logger.error(f"Invalid image format: {e}")
                raise HTTPException(
                    status_code=400,
                    detail="Invalid image format or corrupted file"
                )
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Process image to ISO standards
            processed_image = cls._crop_to_iso_standards(image)
            
            # Enhance image quality
            processed_image = cls._enhance_image(processed_image)
            
            # Generate unique ID for this processing session
            file_id = str(uuid.uuid4())
            
            # Ensure directory exists
            storage_path.mkdir(parents=True, exist_ok=True)
            
            # Generate STANDARD version (for application review)
            standard_filename = f"{filename_prefix}_standard_{file_id}.jpg"
            standard_file_path = storage_path / standard_filename
            
            processed_image.save(
                standard_file_path,
                'JPEG',
                quality=cls.JPEG_QUALITY,
                optimize=True
            )
            
            # Generate LICENSE-READY version (for card production)
            license_ready_filename = f"{filename_prefix}_license_ready_{file_id}.jpg"
            license_ready_file_path = storage_path / license_ready_filename
            license_ready_image = cls._create_license_ready_image(processed_image)
            
            cls._save_license_ready_image(license_ready_image, license_ready_file_path)
            
            # Get file info for both versions
            standard_file_size = standard_file_path.stat().st_size
            license_ready_file_size = license_ready_file_path.stat().st_size
            
            # Log processing info
            original_size = len(image_data)
            standard_compression = (original_size - standard_file_size) / original_size * 100
            license_compression = (original_size - license_ready_file_size) / original_size * 100
            
            logger.info(
                f"Photo processed: {image_file.filename} -> Standard: {standard_filename} ({standard_file_size//1024}KB), "
                f"License-ready: {license_ready_filename} ({license_ready_file_size}B), "
                f"Original: {original_size//1024}KB"
            )
            
            return {
                "success": True,
                "standard_version": {
                    "file_path": str(standard_file_path),
                    "filename": standard_filename,
                    "file_size": standard_file_size,
                    "dimensions": f"{cls.ISO_WIDTH}x{cls.ISO_HEIGHT}",
                    "format": "JPEG"
                },
                "license_ready_version": {
                    "file_path": str(license_ready_file_path),
                    "filename": license_ready_filename,
                    "file_size": license_ready_file_size,
                    "dimensions": f"{license_ready_image.width}x{license_ready_image.height}",
                    "format": "JPEG"
                },
                # Legacy fields for backward compatibility (use standard version)
                "file_path": str(standard_file_path),
                "filename": standard_filename,
                "file_size": standard_file_size,
                "dimensions": f"{cls.ISO_WIDTH}x{cls.ISO_HEIGHT}",
                "format": "JPEG",
                "original_filename": image_file.filename,
                "processing_info": {
                    "cropped_to_iso": True,
                    "enhanced": True,
                    "compression_ratio": round(standard_compression, 1),
                    "license_ready_compression": round(license_compression, 1),
                    "license_ready_size": license_ready_file_size
                }
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            raise HTTPException(
                status_code=500,
                detail="Image processing failed"
            )
    
    @classmethod
    def _crop_to_iso_standards(cls, image: Image.Image) -> Image.Image:
        """
        Crop image to ISO license photo standards (3:4 aspect ratio)
        Centers the crop area to preserve face positioning
        """
        original_width, original_height = image.size
        original_aspect = original_width / original_height
        
        # Calculate crop dimensions
        if original_aspect > cls.ISO_ASPECT_RATIO:
            # Image is wider than target - crop from sides
            crop_height = original_height
            crop_width = int(original_height * cls.ISO_ASPECT_RATIO)
            crop_x = (original_width - crop_width) // 2
            crop_y = 0
        else:
            # Image is taller than target - crop from top/bottom
            crop_width = original_width
            crop_height = int(original_width / cls.ISO_ASPECT_RATIO)
            crop_x = 0
            # Position crop slightly higher to center face (rule of thirds)
            crop_y = max(0, int((original_height - crop_height) * 0.2))
        
        # Perform crop
        cropped = image.crop((
            crop_x,
            crop_y,
            crop_x + crop_width,
            crop_y + crop_height
        ))
        
        # Resize to exact ISO dimensions
        final_image = cropped.resize(
            (cls.ISO_WIDTH, cls.ISO_HEIGHT),
            Image.Resampling.LANCZOS
        )
        
        return final_image
    
    @classmethod
    def _enhance_image(cls, image: Image.Image) -> Image.Image:
        """
        Enhance image quality for license photo
        """
        # Slight sharpening for better clarity
        enhanced = image.filter(ImageFilter.UnsharpMask(
            radius=0.5,
            percent=120,
            threshold=3
        ))
        
        # Slight contrast enhancement
        enhancer = ImageEnhance.Contrast(enhanced)
        enhanced = enhancer.enhance(1.1)
        
        # Slight brightness adjustment
        enhancer = ImageEnhance.Brightness(enhanced)
        enhanced = enhancer.enhance(1.05)
        
        return enhanced
    
    @classmethod
    def validate_photo_quality(cls, image: Image.Image) -> Dict[str, Any]:
        """
        Validate photo meets quality standards
        """
        width, height = image.size
        
        # Check minimum resolution
        min_width, min_height = 200, 267  # Minimum for quality
        
        quality_checks = {
            "resolution_ok": width >= min_width and height >= min_height,
            "aspect_ratio_ok": abs((width/height) - cls.ISO_ASPECT_RATIO) < 0.1,
            "file_format_ok": image.format in cls.SUPPORTED_FORMATS,
            "color_mode_ok": image.mode in ['RGB', 'L']
        }
        
        return {
            "all_checks_passed": all(quality_checks.values()),
            "checks": quality_checks,
            "recommendations": cls._get_quality_recommendations(quality_checks)
        }
    
    @classmethod
    def _get_quality_recommendations(cls, checks: Dict[str, bool]) -> list:
        """Get recommendations for failed quality checks"""
        recommendations = []
        
        if not checks["resolution_ok"]:
            recommendations.append("Image resolution too low - use higher quality camera")
        if not checks["aspect_ratio_ok"]:
            recommendations.append("Adjust camera positioning - photo will be auto-cropped")
        if not checks["file_format_ok"]:
            recommendations.append("Use JPEG or PNG format")
        if not checks["color_mode_ok"]:
            recommendations.append("Use color photo")
            
        return recommendations
    
    @classmethod
    def _create_license_ready_image(cls, image: Image.Image) -> Image.Image:
        """
        Create license-ready image for card production
        - Convert to 8-bit grayscale
        - Resize to 64-128px height (maintaining aspect ratio)
        - Optimize for minimal file size while preserving quality
        """
        # Convert to grayscale (8-bit)
        grayscale_image = image.convert('L')
        
        # Calculate dimensions for license-ready version
        original_width, original_height = grayscale_image.size
        aspect_ratio = original_width / original_height
        
        # Use target height of 96px (middle of 64-128 range)
        target_height = 96
        target_width = int(target_height * aspect_ratio)
        
        # Ensure height is within range
        if target_height < cls.LICENSE_READY_MIN_HEIGHT:
            target_height = cls.LICENSE_READY_MIN_HEIGHT
            target_width = int(target_height * aspect_ratio)
        elif target_height > cls.LICENSE_READY_MAX_HEIGHT:
            target_height = cls.LICENSE_READY_MAX_HEIGHT
            target_width = int(target_height * aspect_ratio)
        
        # Resize with high-quality resampling
        license_ready = grayscale_image.resize(
            (target_width, target_height),
            Image.Resampling.LANCZOS
        )
        
        # Apply slight sharpening for small size clarity
        license_ready = license_ready.filter(ImageFilter.UnsharpMask(
            radius=0.3,
            percent=150,
            threshold=2
        ))
        
        return license_ready
    
    @classmethod
    def _save_license_ready_image(cls, image: Image.Image, file_path: Path) -> None:
        """
        Save license-ready image with optimal compression to meet size requirements
        Target: 1-1.5KB maximum file size
        """
        # Start with moderate quality and reduce until file size target is met
        quality = cls.LICENSE_READY_QUALITY_START
        min_quality = 30  # Don't go below this to maintain basic quality
        
        while quality >= min_quality:
            # Save to bytes buffer to check size
            buffer = io.BytesIO()
            image.save(
                buffer,
                'JPEG',
                quality=quality,
                optimize=True,
                progressive=False  # Disable progressive for smaller files
            )
            
            file_size = len(buffer.getvalue())
            
            # If file size is acceptable, save to actual file
            if file_size <= cls.LICENSE_READY_TARGET_SIZE:
                with open(file_path, 'wb') as f:
                    f.write(buffer.getvalue())
                logger.info(f"License-ready image saved: {file_path.name}, size: {file_size}B, quality: {quality}")
                return
            
            # Reduce quality and try again
            quality -= 5
        
        # If we can't meet the target size, save with minimum quality
        logger.warning(f"Could not achieve target size {cls.LICENSE_READY_TARGET_SIZE}B, saving with quality {min_quality}")
        image.save(
            file_path,
            'JPEG',
            quality=min_quality,
            optimize=True
        ) 