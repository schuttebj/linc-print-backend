"""
Card File Management Service for Madagascar License System
Handles saving, serving, and cleanup of card files (PNG images and PDFs)
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import uuid
import base64
import shutil

from app.core.config import get_settings

logger = logging.getLogger(__name__)

class CardFileManager:
    """
    Manages card file storage and lifecycle
    
    File Structure:
    /var/madagascar-license-data/cards/
    ├── YYYY/MM/DD/print_job_id/
    │   ├── front.png
    │   ├── back.png
    │   ├── front.pdf
    │   ├── back.pdf
    │   └── combined.pdf
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.base_path = self.settings.get_file_storage_path()
        self.cards_path = self.base_path / "cards"
        
    def _get_print_job_directory(self, print_job_id: str, created_at: datetime = None) -> Path:
        """Get the directory path for a print job's files"""
        if created_at is None:
            created_at = datetime.utcnow()
            
        year = created_at.strftime("%Y")
        month = created_at.strftime("%m")
        day = created_at.strftime("%d")
        
        job_dir = self.cards_path / year / month / day / str(print_job_id)
        return job_dir
    
    def save_card_files(self, print_job_id: str, card_files_data: Dict[str, str], 
                       created_at: datetime = None) -> Dict[str, str]:
        """
        Save card files to disk and return file paths
        
        Args:
            print_job_id: Unique identifier for the print job
            card_files_data: Dictionary containing base64-encoded file data
            created_at: Creation timestamp (defaults to now)
            
        Returns:
            Dictionary mapping file types to their saved paths
        """
        if created_at is None:
            created_at = datetime.utcnow()
            
        # Create directory structure
        job_dir = self._get_print_job_directory(print_job_id, created_at)
        job_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Saving card files for print job {print_job_id} to {job_dir}")
        
        file_paths = {}
        
        # File mappings: internal name -> (filename, description)
        file_mappings = {
            "front_image": ("front.png", "Front card image"),
            "back_image": ("back.png", "Back card image"),
            "watermark_image": ("watermark.png", "Watermark template"),
            "front_pdf": ("front.pdf", "Front card PDF"),
            "back_pdf": ("back.pdf", "Back card PDF"),
            "combined_pdf": ("combined.pdf", "Combined card PDF")
        }
        
        # Save each file
        for internal_name, (filename, description) in file_mappings.items():
            if internal_name in card_files_data:
                file_path = job_dir / filename
                try:
                    # Decode base64 and save
                    file_data = base64.b64decode(card_files_data[internal_name])
                    with open(file_path, 'wb') as f:
                        f.write(file_data)
                    
                    # Store relative path from base storage directory
                    relative_path = file_path.relative_to(self.base_path)
                    file_paths[f"{internal_name}_path"] = str(relative_path)
                    
                    logger.info(f"Saved {description} to {relative_path} ({len(file_data):,} bytes)")
                    
                except Exception as e:
                    logger.error(f"Failed to save {description}: {e}")
                    # Continue with other files
                    
        logger.info(f"Saved {len(file_paths)} files for print job {print_job_id}")
        return file_paths
        
    def read_file_as_base64(self, file_path: str) -> Optional[str]:
        """
        Read a file and return it as base64 encoded string
        
        Args:
            file_path: Path to the file (can be absolute or relative to base_path)
            
        Returns:
            Base64 encoded string or None if file not found/error
        """
        try:
            # Handle both absolute and relative paths
            if os.path.isabs(file_path):
                full_path = Path(file_path)
            else:
                full_path = self.base_path / file_path
            
            if not full_path.exists():
                logger.warning(f"File not found: {full_path}")
                return None
                
            with open(full_path, 'rb') as f:
                file_data = f.read()
                
            base64_data = base64.b64encode(file_data).decode('utf-8')
            logger.info(f"Successfully read file as base64: {full_path} ({len(file_data):,} bytes)")
            return base64_data
            
        except Exception as e:
            logger.error(f"Failed to read file {file_path} as base64: {e}")
            return None
    
    def get_file_path(self, print_job_id: str, file_type: str, created_at: datetime = None) -> Optional[Path]:
        """
        Get the file path for a specific card file
        
        Args:
            print_job_id: Print job UUID
            file_type: Type of file (front_image, back_image, front_pdf, back_pdf, combined_pdf)
            created_at: Creation timestamp for directory lookup
            
        Returns:
            Path to the file or None if not found
        """
        job_dir = self._get_print_job_directory(print_job_id, created_at)
        
        file_mappings = {
            "front_image": "front.png",
            "back_image": "back.png",
            "front_pdf": "front.pdf", 
            "back_pdf": "back.pdf",
            "combined_pdf": "combined.pdf"
        }
        
        if file_type in file_mappings:
            file_path = job_dir / file_mappings[file_type]
            return file_path if file_path.exists() else None
        
        return None
    
    def file_exists(self, print_job_id: str, file_type: str, created_at: datetime = None) -> bool:
        """Check if a specific card file exists"""
        file_path = self.get_file_path(print_job_id, file_type, created_at)
        return file_path is not None and file_path.exists()
    
    def get_file_content(self, print_job_id: str, file_type: str, created_at: datetime = None) -> Optional[bytes]:
        """
        Get the content of a card file
        
        Returns:
            File content as bytes or None if file doesn't exist
        """
        file_path = self.get_file_path(print_job_id, file_type, created_at)
        
        if file_path and file_path.exists():
            try:
                with open(file_path, 'rb') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {e}")
                return None
        
        return None
    
    def delete_print_job_files(self, print_job_id: str, created_at: datetime = None) -> Dict[str, Any]:
        """
        Delete ALL files and the complete folder structure for a print job after QA completion
        
        This completely removes:
        - All card files (PNG images and PDFs)
        - The entire print job directory
        - Empty parent directories (day/month/year structure)
        
        Args:
            print_job_id: Print job UUID
            created_at: Creation timestamp for directory lookup
            
        Returns:
            Dictionary with cleanup results
        """
        try:
            job_dir = self._get_print_job_directory(print_job_id, created_at)
            
            if not job_dir.exists():
                logger.info(f"Print job directory {job_dir} does not exist - already cleaned up")
                return {
                    "status": "success",
                    "message": "Directory already cleaned up",
                    "files_deleted": 0,
                    "bytes_freed": 0,
                    "folder_removed": False
                }
            
            # Calculate total size and file count before deletion
            total_size = 0
            files_deleted = 0
            folders_to_cleanup = []
            
            # Recursively calculate all files in the job directory
            for file_path in job_dir.rglob('*'):
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    total_size += file_size
                    files_deleted += 1
                    logger.debug(f"Will delete file: {file_path} ({file_size} bytes)")
                elif file_path.is_dir():
                    folders_to_cleanup.append(str(file_path))
            
            # Store original path for logging
            original_job_dir = str(job_dir)
            
            # COMPLETE FOLDER REMOVAL - Remove entire print job directory tree
            logger.info(f"COMPLETE CLEANUP: Removing entire directory tree {job_dir} with {files_deleted} files")
            shutil.rmtree(job_dir)
            
            # Verify folder is completely gone
            if job_dir.exists():
                raise Exception(f"Failed to completely remove directory {job_dir}")
            
            logger.info(f"✅ FOLDER COMPLETELY REMOVED: {original_job_dir}")
            
            # Clean up empty parent directories to prevent bloat
            empty_dirs_cleaned = self._cleanup_empty_directories(job_dir.parent)
            
            logger.info(f"🧹 CLEANUP COMPLETE: Deleted {files_deleted} files ({total_size:,} bytes) + folder structure for print job {print_job_id}")
            
            return {
                "status": "success", 
                "message": f"Completely removed print job folder with {files_deleted} files",
                "files_deleted": files_deleted,
                "bytes_freed": total_size,
                "folder_removed": True,
                "folder_path": original_job_dir,
                "empty_dirs_cleaned": empty_dirs_cleaned,
                "total_cleanup_items": files_deleted + len(folders_to_cleanup)
            }
            
        except Exception as e:
            logger.error(f"❌ ERROR: Failed to delete folder for print job {print_job_id}: {e}")
            return {
                "status": "error",
                "message": f"Failed to delete print job folder: {str(e)}",
                "files_deleted": 0,
                "bytes_freed": 0,
                "folder_removed": False
            }
    
    def _cleanup_empty_directories(self, directory: Path, max_levels: int = 3) -> int:
        """
        Clean up empty parent directories (day/month/year structure) to prevent bloat
        
        This prevents empty directory accumulation by removing:
        - Empty day directories (DD)
        - Empty month directories (MM) 
        - Empty year directories (YYYY)
        
        Args:
            directory: Starting directory to check (day directory)
            max_levels: Maximum number of parent levels to check (3 = day/month/year)
            
        Returns:
            Number of empty directories removed
        """
        directories_cleaned = 0
        
        try:
            current_dir = directory
            levels_checked = 0
            
            logger.debug(f"🔍 Checking for empty directories starting from: {current_dir}")
            
            while (levels_checked < max_levels and 
                   current_dir != self.cards_path and 
                   current_dir.exists() and 
                   current_dir.is_dir()):
                
                # Check if directory is empty
                try:
                    dir_contents = list(current_dir.iterdir())
                    if len(dir_contents) == 0:
                        logger.info(f"🗑️  Removing empty directory: {current_dir}")
                        current_dir.rmdir()
                        directories_cleaned += 1
                        
                        # Move up to parent directory
                        current_dir = current_dir.parent
                        levels_checked += 1
                    else:
                        logger.debug(f"📁 Directory not empty (contains {len(dir_contents)} items): {current_dir}")
                        # Directory not empty, stop cleanup
                        break
                        
                except PermissionError as pe:
                    logger.warning(f"⚠️  Permission denied removing directory {current_dir}: {pe}")
                    break
                except OSError as ose:
                    logger.warning(f"⚠️  OS error removing directory {current_dir}: {ose}")
                    break
                    
            if directories_cleaned > 0:
                logger.info(f"✅ EMPTY DIR CLEANUP: Removed {directories_cleaned} empty directories")
            else:
                logger.debug(f"📁 No empty directories to clean up")
                
        except Exception as e:
            logger.warning(f"❌ Error during empty directory cleanup: {e}")
            
        return directories_cleaned
    
    def get_directory_size(self, print_job_id: str, created_at: datetime = None) -> int:
        """Get total size of all files for a print job"""
        job_dir = self._get_print_job_directory(print_job_id, created_at)
        
        if not job_dir.exists():
            return 0
            
        total_size = 0
        try:
            for file_path in job_dir.iterdir():
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            logger.error(f"Error calculating directory size for {job_dir}: {e}")
            
        return total_size
    
    def list_print_job_files(self, print_job_id: str, created_at: datetime = None) -> List[Dict[str, Any]]:
        """
        List all files for a print job with metadata
        
        Returns:
            List of file information dictionaries
        """
        job_dir = self._get_print_job_directory(print_job_id, created_at)
        
        if not job_dir.exists():
            return []
        
        files_info = []
        
        try:
            for file_path in job_dir.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    files_info.append({
                        "filename": file_path.name,
                        "file_path": str(file_path),
                        "size_bytes": stat.st_size,
                        "size_kb": stat.st_size / 1024,
                        "size_mb": stat.st_size / 1024 / 1024,
                        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                    
        except Exception as e:
            logger.error(f"Error listing files for print job {print_job_id}: {e}")
        
        return files_info
    
    def get_storage_statistics(self) -> Dict[str, Any]:
        """
        Get overall storage statistics for card files
        
        Returns:
            Dictionary with storage usage information
        """
        try:
            if not self.cards_path.exists():
                return {
                    "total_size_bytes": 0,
                    "total_files": 0,
                    "total_directories": 0,
                    "total_print_jobs": 0
                }
            
            total_size = 0
            total_files = 0
            total_directories = 0
            print_job_directories = set()
            
            # Walk through all files
            for root, dirs, files in os.walk(self.cards_path):
                total_directories += len(dirs)
                
                for file in files:
                    file_path = Path(root) / file
                    try:
                        total_size += file_path.stat().st_size
                        total_files += 1
                        
                        # Extract print job ID from path
                        path_parts = file_path.parts
                        if len(path_parts) >= 5:  # .../cards/YYYY/MM/DD/job_id/file
                            print_job_id = path_parts[-2]
                            print_job_directories.add(print_job_id)
                            
                    except Exception as e:
                        logger.warning(f"Error processing file {file_path}: {e}")
            
            return {
                "total_size_bytes": total_size,
                "total_size_mb": total_size / 1024 / 1024,
                "total_size_gb": total_size / 1024 / 1024 / 1024,
                "total_files": total_files,
                "total_directories": total_directories,
                "total_print_jobs": len(print_job_directories),
                "average_size_per_job_mb": (total_size / 1024 / 1024 / len(print_job_directories)) if print_job_directories else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting storage statistics: {e}")
            return {
                "error": str(e),
                "total_size_bytes": 0,
                "total_files": 0
            }

    def verify_complete_cleanup(self, print_job_id: str, created_at: datetime = None) -> Dict[str, Any]:
        """
        Verify that a print job's files and folders have been completely removed
        
        This ensures no bloat remains after cleanup operations.
        
        Args:
            print_job_id: Print job UUID to verify
            created_at: Creation timestamp for directory lookup
            
        Returns:
            Dictionary with verification results
        """
        try:
            job_dir = self._get_print_job_directory(print_job_id, created_at)
            
            verification_result = {
                "print_job_id": print_job_id,
                "expected_directory": str(job_dir),
                "completely_removed": not job_dir.exists(),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if job_dir.exists():
                # Directory still exists - check what's left
                remaining_files = []
                remaining_size = 0
                
                for item in job_dir.rglob('*'):
                    if item.is_file():
                        size = item.stat().st_size
                        remaining_files.append({
                            "file": str(item),
                            "size_bytes": size
                        })
                        remaining_size += size
                
                verification_result.update({
                    "status": "CLEANUP_INCOMPLETE",
                    "remaining_files": len(remaining_files),
                    "remaining_size_bytes": remaining_size,
                    "remaining_files_list": remaining_files,
                    "cleanup_needed": True
                })
                
                logger.warning(f"⚠️  CLEANUP INCOMPLETE: {len(remaining_files)} files still exist for print job {print_job_id}")
                
            else:
                verification_result.update({
                    "status": "CLEANUP_COMPLETE", 
                    "remaining_files": 0,
                    "remaining_size_bytes": 0,
                    "cleanup_needed": False
                })
                
                logger.debug(f"✅ CLEANUP VERIFIED: No traces remain for print job {print_job_id}")
            
            return verification_result
            
        except Exception as e:
            logger.error(f"❌ Error verifying cleanup for print job {print_job_id}: {e}")
            return {
                "print_job_id": print_job_id,
                "status": "VERIFICATION_ERROR",
                "error": str(e),
                "completely_removed": False,
                "cleanup_needed": True
            }
    
    def get_directory_bloat_report(self) -> Dict[str, Any]:
        """
        Generate a report on potential directory bloat and cleanup opportunities
        
        Identifies:
        - Empty directories that can be removed
        - Orphaned directories without database records
        - Large directories that may need attention
        
        Returns:
            Dictionary with bloat analysis
        """
        try:
            if not self.cards_path.exists():
                return {
                    "status": "no_storage",
                    "message": "No card storage directory found",
                    "bloat_detected": False
                }
            
            bloat_report = {
                "scan_timestamp": datetime.utcnow().isoformat(),
                "total_directories": 0,
                "empty_directories": [],
                "large_directories": [],
                "orphaned_directories": [],
                "bloat_detected": False,
                "cleanup_recommendations": []
            }
            
            # Scan all directories
            for root, dirs, files in os.walk(self.cards_path):
                root_path = Path(root)
                bloat_report["total_directories"] += len(dirs)
                
                # Check for empty directories
                if len(dirs) == 0 and len(files) == 0:
                    bloat_report["empty_directories"].append(str(root_path))
                    bloat_report["bloat_detected"] = True
                
                # Check for large directories (>50MB)
                if len(files) > 0:
                    dir_size = sum(Path(root, f).stat().st_size for f in files if Path(root, f).exists())
                    if dir_size > 50 * 1024 * 1024:  # 50MB threshold
                        bloat_report["large_directories"].append({
                            "directory": str(root_path),
                            "size_mb": dir_size / 1024 / 1024,
                            "file_count": len(files)
                        })
            
            # Generate cleanup recommendations
            if bloat_report["empty_directories"]:
                bloat_report["cleanup_recommendations"].append(
                    f"Remove {len(bloat_report['empty_directories'])} empty directories"
                )
            
            if bloat_report["large_directories"]:
                bloat_report["cleanup_recommendations"].append(
                    f"Investigate {len(bloat_report['large_directories'])} large directories"
                )
            
            if not bloat_report["cleanup_recommendations"]:
                bloat_report["cleanup_recommendations"].append("No cleanup needed - storage is optimized")
            
            return bloat_report
            
        except Exception as e:
            logger.error(f"❌ Error generating bloat report: {e}")
            return {
                "status": "error",
                "message": str(e),
                "bloat_detected": True,  # Assume bloat on error for safety
                "error": str(e)
            }


# Global instance
card_file_manager = CardFileManager() 