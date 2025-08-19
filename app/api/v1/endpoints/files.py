"""
File Serving Endpoints for Madagascar License System

Serves stored files including fingerprint images, photos, and documents.
Provides secure access to persistent disk storage.
"""

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from pathlib import Path
import logging
import mimetypes

from app.core.config import get_settings
from app.services.fingerprint_image_service import fingerprint_image_service

logger = logging.getLogger(__name__)
router = APIRouter()

settings = get_settings()


@router.get("/fingerprints/{filename}")
async def serve_fingerprint_image(filename: str):
    """
    Serve fingerprint image files
    
    Args:
        filename: Image filename (should be {template_id}.png)
    """
    try:
        # Validate filename format
        if not filename.endswith('.png'):
            raise HTTPException(status_code=400, detail="Invalid file format")
        
        # Extract template ID from filename
        template_id_str = filename.replace('.png', '')
        
        # Get file path
        file_path = fingerprint_image_service.fingerprints_path / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Fingerprint image not found")
        
        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "image/png"
        
        return FileResponse(
            path=str(file_path),
            media_type=mime_type,
            filename=filename,
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                "Content-Disposition": f"inline; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving fingerprint image {filename}: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve fingerprint image")



@router.get("/photos/{filename}")
async def serve_photo(filename: str):
    """
    Serve photo files (for backward compatibility with existing photo system)
    
    Args:
        filename: Photo filename
    """
    try:
        # Get base storage path
        storage_path = settings.get_file_storage_path()
        photos_path = storage_path / "photos"
        
        file_path = photos_path / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Photo not found")
        
        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = "image/jpeg"
        
        return FileResponse(
            path=str(file_path),
            media_type=mime_type,
            filename=filename,
            headers={
                "Cache-Control": "public, max-age=3600",
                "Content-Disposition": f"inline; filename={filename}"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving photo {filename}: {e}")
        raise HTTPException(status_code=500, detail="Failed to serve photo")


@router.get("/health")
async def files_health_check():
    """Health check for file serving system"""
    try:
        # Check if storage directories are accessible
        storage_path = settings.get_file_storage_path()
        fingerprints_accessible = fingerprint_image_service.fingerprints_path.exists()
        
        return {
            "status": "healthy",
            "storage_path": str(storage_path),
            "fingerprints_accessible": fingerprints_accessible,
            "fingerprint_storage_path": str(fingerprint_image_service.fingerprints_path)
        }
        
    except Exception as e:
        logger.error(f"File serving health check failed: {e}")
        raise HTTPException(status_code=500, detail="File serving system unavailable")
