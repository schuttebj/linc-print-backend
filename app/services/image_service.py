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
    
    # Quality settings
    JPEG_QUALITY = 90
    MAX_FILE_SIZE_KB = 500  # Maximum output file size
    
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
            
            # Generate filename and save
            file_id = str(uuid.uuid4())
            filename = f"{filename_prefix}_{file_id}.jpg"
            file_path = storage_path / filename
            
            # Ensure directory exists
            storage_path.mkdir(parents=True, exist_ok=True)
            
            # Save with optimization
            processed_image.save(
                file_path,
                'JPEG',
                quality=cls.JPEG_QUALITY,
                optimize=True
            )
            
            # Get file info
            file_size = file_path.stat().st_size
            
            # Log processing info
            original_size = len(image_data)
            compression_ratio = (original_size - file_size) / original_size * 100
            
            logger.info(
                f"Photo processed: {image_file.filename} -> {filename}, "
                f"Original: {original_size//1024}KB, Final: {file_size//1024}KB, "
                f"Compression: {compression_ratio:.1f}%"
            )
            
            return {
                "success": True,
                "file_path": str(file_path),
                "filename": filename,
                "file_size": file_size,
                "dimensions": f"{cls.ISO_WIDTH}x{cls.ISO_HEIGHT}",
                "format": "JPEG",
                "original_filename": image_file.filename,
                "processing_info": {
                    "cropped_to_iso": True,
                    "enhanced": True,
                    "compression_ratio": round(compression_ratio, 1)
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