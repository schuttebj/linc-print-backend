"""
Fingerprint Image Storage Service for Madagascar License System

Handles storage and retrieval of actual fingerprint images captured from BioMini scanner.
Stores images as PNG files on persistent disk using template ID for naming.
"""

import io
import uuid
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
from fastapi import UploadFile, HTTPException
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)

class FingerprintImageService:
    """Service for storing and managing fingerprint images on persistent disk"""
    
    def __init__(self):
        self.settings = get_settings()
        self.base_storage_path = self.settings.get_file_storage_path()
        self.fingerprints_path = self.base_storage_path / "fingerprints"
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure fingerprint storage directories exist"""
        try:
            self.fingerprints_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Fingerprint storage initialized at: {self.fingerprints_path}")
        except Exception as e:
            logger.error(f"Failed to create fingerprint directories: {e}")
            raise HTTPException(status_code=500, detail="Failed to initialize fingerprint storage")
    
    def save_fingerprint_image(
        self, 
        template_id: uuid.UUID, 
        image_data: bytes, 
        image_format: str = "BMP"
    ) -> str:
        """
        Save fingerprint image to persistent storage
        
        Args:
            template_id: UUID of the fingerprint template
            image_data: Raw image bytes from BioMini scanner
            image_format: Original format (usually BMP from BioMini)
            
        Returns:
            Path to saved image file
        """
        try:
            # Generate file path
            filename = f"{template_id}.png"
            file_path = self.fingerprints_path / filename
            
            # Process the image
            with Image.open(io.BytesIO(image_data)) as img:
                # Convert to RGBA to handle transparency
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # Process and resize image for license card use (250-300px on longest side)
                processed_img = self._process_fingerprint_image(img)
                
                # Save optimized image as PNG with transparency
                processed_img.save(
                    file_path,
                    'PNG',
                    optimize=True,
                    compress_level=6
                )
                
                # Log successful save
                file_size = file_path.stat().st_size
                
                logger.info(
                    f"Fingerprint image saved: {template_id} -> "
                    f"Size: {file_size//1024}KB, Dimensions: {processed_img.width}x{processed_img.height}px"
                )
                
                return str(file_path)
                
        except Exception as e:
            logger.error(f"Failed to save fingerprint image for template {template_id}: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to save fingerprint image: {str(e)}"
            )
    
    def _process_fingerprint_image(self, img: Image.Image) -> Image.Image:
        """
        Process fingerprint image to remove background, enhance quality, and resize for license card use
        
        Args:
            img: PIL Image of the fingerprint
            
        Returns:
            Processed PIL Image with transparent background, resized to 250-300px on longest side
        """
        # Convert to grayscale for processing
        gray = img.convert('L')
        
        # Create alpha channel based on intensity
        # Fingerprint ridges are typically darker, background is lighter
        alpha = gray.point(lambda x: 0 if x > 200 else 255)  # Remove light background
        
        # Apply some enhancement
        from PIL import ImageEnhance, ImageFilter
        
        # Slight contrast enhancement
        enhancer = ImageEnhance.Contrast(gray)
        enhanced = enhancer.enhance(1.2)
        
        # Slight sharpening
        sharpened = enhanced.filter(ImageFilter.UnsharpMask(radius=0.5, percent=120, threshold=3))
        
        # Combine processed image with alpha channel
        result = Image.new('RGBA', img.size, (255, 255, 255, 0))
        
        # Convert enhanced grayscale back to RGBA and apply alpha
        rgba_enhanced = sharpened.convert('RGBA')
        result.paste(rgba_enhanced, (0, 0), alpha)
        
        # Resize to optimal size for license card (250-300px on longest side)
        resized_img = self._resize_for_license_card(result)
        
        return resized_img
    
    def _resize_for_license_card(self, img: Image.Image) -> Image.Image:
        """
        Resize image to optimal size for license card use (250-300px on longest side)
        
        Args:
            img: Original PIL Image
            
        Returns:
            Resized PIL Image
        """
        # Target size: 280px on longest side (good balance for license cards)
        target_max_size = 280
        
        # Calculate new dimensions maintaining aspect ratio
        width, height = img.size
        if width >= height:
            # Width is the longest side
            new_width = target_max_size
            new_height = int((height * target_max_size) / width)
        else:
            # Height is the longest side
            new_height = target_max_size
            new_width = int((width * target_max_size) / height)
        
        # Resize with high-quality resampling
        resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        logger.debug(f"Resized fingerprint image from {width}x{height} to {new_width}x{new_height}")
        
        return resized
    
    def get_fingerprint_image_path(self, template_id: uuid.UUID) -> Optional[Path]:
        """
        Get path to stored fingerprint image
        
        Args:
            template_id: UUID of the fingerprint template
            
        Returns:
            Path to image file if it exists, None otherwise
        """
        filename = f"{template_id}.png"
        file_path = self.fingerprints_path / filename
        
        return file_path if file_path.exists() else None
    
    def get_fingerprint_image_url(self, template_id: uuid.UUID) -> Optional[str]:
        """
        Get public URL for stored fingerprint image
        
        Args:
            template_id: UUID of the fingerprint template
            
        Returns:
            Public URL to access the image
        """
        file_path = self.get_fingerprint_image_path(template_id)
        
        if not file_path:
            return None
        
        # Get the base URL from settings
        base_url = self.settings.get_backend_url()
        
        # Construct full public URL
        return f"{base_url}/api/v1/files/fingerprints/{template_id}.png"
    
    def delete_fingerprint_images(self, template_id: uuid.UUID) -> bool:
        """
        Delete fingerprint image for a template
        
        Args:
            template_id: UUID of the fingerprint template
            
        Returns:
            True if deletion was successful
        """
        try:
            # Delete image
            image_path = self.fingerprints_path / f"{template_id}.png"
            if image_path.exists():
                image_path.unlink()
                logger.info(f"Deleted fingerprint image for template {template_id}")
                return True
            else:
                logger.warning(f"No fingerprint image found for template {template_id}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to delete fingerprint image for template {template_id}: {e}")
            return False
    
    def cleanup_orphaned_images(self, valid_template_ids: list) -> int:
        """
        Clean up orphaned fingerprint images that don't have corresponding templates
        
        Args:
            valid_template_ids: List of valid template UUIDs
            
        Returns:
            Number of files cleaned up
        """
        try:
            valid_ids_str = [str(template_id) for template_id in valid_template_ids]
            cleaned_count = 0
            
            # Clean images
            for image_file in self.fingerprints_path.glob("*.png"):
                template_id = image_file.stem  # filename without extension
                if template_id not in valid_ids_str:
                    image_file.unlink()
                    cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} orphaned fingerprint images")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned fingerprint images: {e}")
            return 0
    
    def delete_all_images(self) -> int:
        """
        Delete all fingerprint images (for testing/reset purposes)
        
        Returns:
            Number of files deleted
        """
        try:
            deleted_count = 0
            
            # Delete all images
            for image_file in self.fingerprints_path.glob("*.png"):
                image_file.unlink()
                deleted_count += 1
            
            logger.info(f"Deleted all {deleted_count} fingerprint images")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete all fingerprint images: {e}")
            return 0


# Global service instance
fingerprint_image_service = FingerprintImageService()
