"""
Issue File Storage Service for Madagascar License System

Handles storage and retrieval of issue-related files following the persistent disk pattern:
- Screenshots of reported issues
- Console log files  
- Additional attachments

Storage Structure:
/var/madagascar-license-data/issues/
└── YYYY/MM/DD/
    └── {issue_id}/
        ├── screenshot.png
        ├── console_logs.txt
        └── additional_{filename}

This follows the same date-based organization as biometric files for backup management.
"""

import io
import json
import uuid
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime
from PIL import Image
from fastapi import UploadFile, HTTPException
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)

class IssueFileManager:
    """Service for storing and managing issue-related files on persistent disk"""
    
    def __init__(self):
        self.settings = get_settings()
        self.base_storage_path = self.settings.get_file_storage_path()
        self.issues_path = self.base_storage_path / "issues"
        
        # Ensure directories exist
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure issue storage directories exist"""
        try:
            self.issues_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Issue storage initialized at: {self.issues_path}")
        except Exception as e:
            logger.error(f"Failed to create issue directories: {e}")
            raise HTTPException(status_code=500, detail="Failed to initialize issue storage")
    
    def _get_issue_storage_path(self, issue_id: uuid.UUID, created_at: Optional[datetime] = None) -> Path:
        """
        Get storage path for a specific issue using date-based organization
        
        Args:
            issue_id: Issue UUID
            created_at: Issue creation date (defaults to now)
            
        Returns:
            Path to issue storage directory
        """
        if created_at is None:
            created_at = datetime.now()
            
        year = created_at.strftime("%Y")
        month = created_at.strftime("%m")
        day = created_at.strftime("%d")
        
        storage_path = self.issues_path / year / month / day / str(issue_id)
        storage_path.mkdir(parents=True, exist_ok=True)
        
        return storage_path
    
    def save_screenshot(
        self, 
        issue_id: uuid.UUID, 
        screenshot_data: bytes,
        created_at: Optional[datetime] = None
    ) -> Dict[str, str]:
        """
        Save screenshot for an issue
        
        Args:
            issue_id: Issue UUID
            screenshot_data: Screenshot image data
            created_at: Issue creation date
            
        Returns:
            Dictionary with file info (path, filename, size)
        """
        try:
            storage_path = self._get_issue_storage_path(issue_id, created_at)
            filename = "screenshot.png"
            file_path = storage_path / filename
            
            # Validate and process image
            try:
                image = Image.open(io.BytesIO(screenshot_data))
                
                # Convert to PNG if necessary and optimize
                if image.format != 'PNG':
                    # Convert to RGB if necessary (removes alpha channel issues)
                    if image.mode == 'RGBA':
                        background = Image.new('RGB', image.size, (255, 255, 255))
                        background.paste(image, mask=image.split()[-1])
                        image = background
                    
                # Save optimized screenshot
                with open(file_path, 'wb') as f:
                    image.save(f, 'PNG', optimize=True)
                    
            except Exception as e:
                logger.warning(f"Failed to process image, saving raw data: {e}")
                # Save raw data if image processing fails
                with open(file_path, 'wb') as f:
                    f.write(screenshot_data)
            
            file_size = file_path.stat().st_size
            
            logger.info(f"Screenshot saved: {file_path} ({file_size} bytes)")
            
            return {
                "file_path": str(file_path),
                "filename": filename,
                "file_size": file_size,
                "storage_path": str(storage_path)
            }
            
        except Exception as e:
            logger.error(f"Failed to save screenshot for issue {issue_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save screenshot: {str(e)}")
    
    def save_console_logs(
        self, 
        issue_id: uuid.UUID, 
        console_logs: List[str],
        created_at: Optional[datetime] = None
    ) -> Dict[str, str]:
        """
        Save console logs for an issue
        
        Args:
            issue_id: Issue UUID
            console_logs: List of console log entries
            created_at: Issue creation date
            
        Returns:
            Dictionary with file info (path, filename, size)
        """
        try:
            storage_path = self._get_issue_storage_path(issue_id, created_at)
            filename = "console_logs.txt"
            file_path = storage_path / filename
            
            # Format console logs with timestamps
            timestamp = datetime.now().isoformat()
            log_content = f"Console Logs captured at {timestamp}\n"
            log_content += "=" * 50 + "\n\n"
            
            for i, log_entry in enumerate(console_logs, 1):
                log_content += f"[{i:03d}] {log_entry}\n"
            
            # Save console logs
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(log_content)
            
            file_size = file_path.stat().st_size
            
            logger.info(f"Console logs saved: {file_path} ({file_size} bytes)")
            
            return {
                "file_path": str(file_path),
                "filename": filename,
                "file_size": file_size,
                "storage_path": str(storage_path)
            }
            
        except Exception as e:
            logger.error(f"Failed to save console logs for issue {issue_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save console logs: {str(e)}")
    
    def save_additional_file(
        self, 
        issue_id: uuid.UUID, 
        file: UploadFile,
        created_at: Optional[datetime] = None
    ) -> Dict[str, str]:
        """
        Save additional attachment for an issue
        
        Args:
            issue_id: Issue UUID
            file: Uploaded file
            created_at: Issue creation date
            
        Returns:
            Dictionary with file info (path, filename, size, mime_type)
        """
        try:
            storage_path = self._get_issue_storage_path(issue_id, created_at)
            
            # Generate safe filename
            original_filename = file.filename or "attachment"
            file_extension = Path(original_filename).suffix
            safe_filename = f"additional_{uuid.uuid4().hex[:8]}{file_extension}"
            file_path = storage_path / safe_filename
            
            # Save file
            file_content = file.file.read()
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            file_size = file_path.stat().st_size
            
            logger.info(f"Additional file saved: {file_path} ({file_size} bytes)")
            
            return {
                "file_path": str(file_path),
                "filename": safe_filename,
                "original_filename": original_filename,
                "file_size": file_size,
                "mime_type": file.content_type,
                "storage_path": str(storage_path)
            }
            
        except Exception as e:
            logger.error(f"Failed to save additional file for issue {issue_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    def get_file_content(self, file_path: str) -> Tuple[bytes, str]:
        """
        Retrieve file content for serving
        
        Args:
            file_path: Path to the file
            
        Returns:
            Tuple of (file_content, mime_type)
        """
        try:
            path = Path(file_path)
            
            if not path.exists():
                raise HTTPException(status_code=404, detail="File not found")
            
            with open(path, 'rb') as f:
                content = f.read()
            
            # Determine MIME type based on extension
            extension = path.suffix.lower()
            mime_type_map = {
                '.png': 'image/png',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.gif': 'image/gif',
                '.txt': 'text/plain',
                '.json': 'application/json',
                '.pdf': 'application/pdf'
            }
            
            mime_type = mime_type_map.get(extension, 'application/octet-stream')
            
            return content, mime_type
            
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="File not found")
        except Exception as e:
            logger.error(f"Failed to retrieve file {file_path}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve file")
    
    def delete_issue_files(self, issue_id: uuid.UUID, created_at: Optional[datetime] = None) -> bool:
        """
        Delete all files for an issue
        
        Args:
            issue_id: Issue UUID
            created_at: Issue creation date
            
        Returns:
            True if successful
        """
        try:
            storage_path = self._get_issue_storage_path(issue_id, created_at)
            
            if storage_path.exists():
                # Remove all files in the issue directory
                for file_path in storage_path.iterdir():
                    if file_path.is_file():
                        file_path.unlink()
                        logger.info(f"Deleted file: {file_path}")
                
                # Remove the issue directory if empty
                try:
                    storage_path.rmdir()
                    logger.info(f"Deleted issue directory: {storage_path}")
                except OSError:
                    # Directory not empty, that's okay
                    pass
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete files for issue {issue_id}: {e}")
            return False
    
    def get_storage_stats(self) -> Dict[str, int]:
        """
        Get storage statistics for issue files
        
        Returns:
            Dictionary with storage statistics
        """
        try:
            total_files = 0
            total_size = 0
            
            if self.issues_path.exists():
                for file_path in self.issues_path.rglob("*"):
                    if file_path.is_file():
                        total_files += 1
                        total_size += file_path.stat().st_size
            
            return {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "storage_path": str(self.issues_path)
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {
                "total_files": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "storage_path": str(self.issues_path),
                "error": str(e)
            }
