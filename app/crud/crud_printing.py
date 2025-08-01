"""
CRUD operations for Print Job Management System
Handles print queue, job processing, and workflow management
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from sqlalchemy.orm import Session, selectinload
from sqlalchemy import func, desc, asc, and_, or_

from app.crud.base import CRUDBase
from app.models.printing import (
    PrintJob, PrintJobApplication, PrintJobStatusHistory, PrintQueue,
    PrintJobStatus, PrintJobPriority, QualityCheckResult
)
from app.models.license import License
from app.models.application import Application
from app.models.user import User, Location
from app.models.enums import UserType

# Initialize logger for this module
logger = logging.getLogger(__name__)


class CRUDPrintJob(CRUDBase[PrintJob, dict, dict]):
    """CRUD operations for Print Job management"""

    def generate_job_number(self, db: Session, location_id: UUID) -> str:
        """Generate unique print job number: PJ{YYYYMMDD}{LocationCode}{Sequence}"""
        
        # Get location code
        location = db.query(Location).filter(Location.id == location_id).first()
        if not location:
            raise ValueError("Location not found")
        
        location_code = location.code
        today = datetime.utcnow().strftime("%Y%m%d")
        
        # Get next sequence for today and location
        prefix = f"PJ{today}{location_code}"
        last_job = db.query(PrintJob).filter(
            PrintJob.job_number.like(f"{prefix}%")
        ).order_by(desc(PrintJob.job_number)).first()
        
        if last_job:
            last_seq = int(last_job.job_number[-3:])
            new_seq = last_seq + 1
        else:
            new_seq = 1
        
        return f"{prefix}{new_seq:03d}"

    def create_print_job(
        self,
        db: Session,
        *,
        application_id: UUID,
        person_id: UUID,
        print_location_id: UUID,
        card_number: str,
        license_data: Dict[str, Any],
        person_data: Dict[str, Any],
        current_user: User,
        additional_application_ids: Optional[List[UUID]] = None
    ) -> PrintJob:
        """
        Create a new print job for card production
        
        Args:
            application_id: Primary application triggering the print job
            person_id: Person for whom card is being printed
            print_location_id: Location where card will be printed
            card_number: Generated card number
            license_data: All license information for card
            person_data: Person information for card
            current_user: User creating the job
            additional_application_ids: Other applications to include in same print job
        """
        try:
            # Generate job number
            logger.info(f"Starting print job creation for application {application_id}")
            job_number = self.generate_job_number(db, print_location_id)
            logger.info(f"Generated job number: {job_number}")
            
            # Get queue position
            logger.info(f"Getting queue position for location {print_location_id}")
            queue_position = crud_print_queue.get_next_queue_position(db, print_location_id)
            logger.info(f"Queue position: {queue_position}")
            
            # Create print job
            logger.info(f"Creating print job database record")
            print_job = PrintJob(
                job_number=job_number,
                status=PrintJobStatus.QUEUED,
                priority=PrintJobPriority.NORMAL,
                queue_position=queue_position,
                person_id=person_id,
                print_location_id=print_location_id,
                primary_application_id=application_id,
                card_number=card_number,
                license_data=license_data,
                person_data=person_data,
                created_by=current_user.id,
                created_at=datetime.utcnow()
            )
            
            db.add(print_job)
            db.flush()  # Get print job ID
            logger.info(f"Created print job with ID: {print_job.id}")
            
            # Create application associations
            logger.info(f"Creating application associations")
            application_ids = [application_id]
            if additional_application_ids:
                application_ids.extend(additional_application_ids)
            
            for app_id in application_ids:
                job_app = PrintJobApplication(
                    print_job_id=print_job.id,
                    application_id=app_id,
                    is_primary=(app_id == application_id),
                    added_by_user_id=current_user.id
                )
                db.add(job_app)
            
            # Create initial status history
            logger.info(f"Creating status history")
            status_history = PrintJobStatusHistory(
                print_job_id=print_job.id,
                from_status=None,
                to_status=PrintJobStatus.QUEUED,
                changed_by_user_id=current_user.id,
                change_reason="Print job created",
                change_notes=f"Created from application {application_id}"
            )
            db.add(status_history)
            
            # Update queue size
            logger.info(f"Updating queue size")
            crud_print_queue.increment_queue_size(db, print_location_id)
            
            # Generate card files immediately after job creation
            try:
                logger.info(f"Starting card generation for print job {print_job.id}")
                from app.services.card_generator import madagascar_card_generator
                
                # Prepare data for card generation
                print_job_data = {
                    "license_data": license_data,
                    "person_data": person_data,
                    "print_job_id": str(print_job.id),
                    "job_number": job_number,
                    "card_number": card_number
                }
                
                logger.info(f"Calling card generator for print job {print_job.id}")
                # Generate card files and save to disk with database session for production barcode API
                generation_result = madagascar_card_generator.generate_card_files(print_job_data, db_session=db)
                
                logger.info(f"Card generation completed for print job {print_job.id}")
                # Update print job with file paths and metadata (no base64 data stored)
                print_job.pdf_files_generated = generation_result.get("files_generated", False)
                print_job.pdf_front_path = generation_result.get("file_paths", {}).get("front_image_path")
                print_job.pdf_back_path = generation_result.get("file_paths", {}).get("back_image_path")
                print_job.pdf_combined_path = generation_result.get("file_paths", {}).get("combined_pdf_path")
                
                # Store generation metadata (file sizes, timestamps, etc.)
                print_job.generation_metadata = {
                    "generator_version": generation_result.get("generator_version"),
                    "generation_timestamp": generation_result.get("generation_timestamp"),
                    "file_sizes": generation_result.get("file_sizes", {}),
                    "files_saved_to_disk": True,
                    "total_size_mb": generation_result.get("file_sizes", {}).get("total_bytes", 0) / 1024 / 1024
                }
                
                # Remove card_files_data field - files are now on disk
                print_job.card_files_data = None
                
                logger.info(f"Generated and saved card files for print job {print_job.id} - Total size: {generation_result.get('file_sizes', {}).get('total_bytes', 0):,} bytes")
                
            except Exception as card_error:
                # Log card generation error but don't fail the print job creation
                logger.error(f"Card generation failed for print job {print_job.id}: {card_error}")
                
                # Mark as failed generation but keep job in queue for manual retry
                print_job.pdf_files_generated = False
                print_job.generation_metadata = {
                    "error": str(card_error),
                    "error_timestamp": datetime.utcnow().isoformat(),
                    "files_saved_to_disk": False
                }
            
            db.commit()
            db.refresh(print_job)
            
            return print_job
            
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create print job: {str(e)}", exc_info=True)
            raise Exception(f"Failed to create print job: {str(e) if str(e) else repr(e)}")

    def get_print_queue(
        self,
        db: Session,
        *,
        location_id: UUID,
        status: Optional[List[PrintJobStatus]] = None,
        limit: int = 100
    ) -> List[PrintJob]:
        """Get print queue for a location ordered by priority and FIFO"""
        query = db.query(PrintJob).options(
            selectinload(PrintJob.person),
            selectinload(PrintJob.primary_application),
            selectinload(PrintJob.job_applications).selectinload(PrintJobApplication.application)
        ).filter(
            PrintJob.print_location_id == location_id
        )
        
        if status:
            query = query.filter(PrintJob.status.in_(status))
        else:
            # Default to active queue statuses
            query = query.filter(PrintJob.status.in_([
                PrintJobStatus.QUEUED,
                PrintJobStatus.ASSIGNED,
                PrintJobStatus.PRINTING,
                PrintJobStatus.PRINTED,
                PrintJobStatus.QUALITY_CHECK
            ]))
        
        # Order by priority (HIGH first), then by queue position (FIFO)
        return query.order_by(
            PrintJob.priority.desc(),
            PrintJob.queue_position.asc()
        ).limit(limit).all()

    def move_to_top_of_queue(
        self,
        db: Session,
        *,
        job_id: UUID,
        reason: str,
        current_user: User
    ) -> PrintJob:
        """Move a print job to the top of the queue"""
        print_job = self.get(db, id=job_id)
        if not print_job:
            raise ValueError("Print job not found")
        
        if not print_job.can_move_to_top():
            raise ValueError(f"Cannot move job in status {print_job.status} to top of queue")
        
        old_position = print_job.queue_position
        
        # Get all jobs in same location with better positions
        jobs_to_move_down = db.query(PrintJob).filter(
            PrintJob.print_location_id == print_job.print_location_id,
            PrintJob.status.in_([PrintJobStatus.QUEUED, PrintJobStatus.ASSIGNED]),
            PrintJob.queue_position < print_job.queue_position,
            PrintJob.id != print_job.id
        ).all()
        
        # Move other jobs down by 1
        for job in jobs_to_move_down:
            job.queue_position += 1
        
        # Move this job to position 1
        print_job.queue_position = 1
        print_job.priority = PrintJobPriority.HIGH
        
        # Record queue change
        print_job.add_queue_change_record(
            action="MOVE_TO_TOP",
            reason=reason,
            user_id=current_user.id,
            old_position=old_position,
            new_position=1
        )
        
        # Create status history
        status_history = PrintJobStatusHistory(
            print_job_id=print_job.id,
            from_status=print_job.status,
            to_status=print_job.status,  # Status doesn't change
            changed_by_user_id=current_user.id,
            change_reason=f"Moved to top of queue: {reason}",
            change_notes=f"Priority changed from position {old_position} to 1"
        )
        db.add(status_history)
        
        db.commit()
        db.refresh(print_job)
        
        return print_job

    def assign_to_printer(
        self,
        db: Session,
        *,
        job_id: UUID,
        printer_user_id: UUID,
        current_user: User
    ) -> PrintJob:
        """Assign print job to a printer operator"""
        print_job = self.get(db, id=job_id)
        if not print_job:
            raise ValueError("Print job not found")
        
        if print_job.status != PrintJobStatus.QUEUED:
            raise ValueError(f"Cannot assign job in status {print_job.status}")
        
        # Update job
        print_job.status = PrintJobStatus.ASSIGNED
        print_job.assigned_to_user_id = printer_user_id
        print_job.assigned_at = datetime.utcnow()
        
        # Create status history
        status_history = PrintJobStatusHistory(
            print_job_id=print_job.id,
            from_status=PrintJobStatus.QUEUED,
            to_status=PrintJobStatus.ASSIGNED,
            changed_by_user_id=current_user.id,
            change_reason="Assigned to printer operator",
            change_notes=f"Assigned to user {printer_user_id}"
        )
        db.add(status_history)
        
        db.commit()
        db.refresh(print_job)
        
        return print_job

    def start_printing(
        self,
        db: Session,
        *,
        job_id: UUID,
        current_user: User,
        printer_hardware_id: Optional[str] = None
    ) -> PrintJob:
        """Start the printing process for a job"""
        print_job = self.get(db, id=job_id)
        if not print_job:
            raise ValueError("Print job not found")
        
        if not print_job.can_start_printing():
            raise ValueError(f"Cannot start printing job in status {print_job.status}")
        
        if not print_job.pdf_files_generated:
            raise ValueError("PDF files must be generated before printing can start")
        
        # Update job
        print_job.status = PrintJobStatus.PRINTING
        print_job.printing_started_at = datetime.utcnow()
        if printer_hardware_id:
            print_job.printer_hardware_id = printer_hardware_id
        
        # Create status history
        status_history = PrintJobStatusHistory(
            print_job_id=print_job.id,
            from_status=PrintJobStatus.ASSIGNED,
            to_status=PrintJobStatus.PRINTING,
            changed_by_user_id=current_user.id,
            change_reason="Printing started",
            change_notes=f"Printer: {printer_hardware_id}" if printer_hardware_id else "Printing started"
        )
        db.add(status_history)
        
        db.commit()
        db.refresh(print_job)
        
        return print_job

    def complete_printing(
        self,
        db: Session,
        *,
        job_id: UUID,
        current_user: User,
        production_notes: Optional[str] = None
    ) -> PrintJob:
        """Mark printing as completed and move to quality check"""
        print_job = self.get(db, id=job_id)
        if not print_job:
            raise ValueError("Print job not found")
        
        if print_job.status != PrintJobStatus.PRINTING:
            raise ValueError(f"Cannot complete printing for job in status {print_job.status}")
        
        # Update job
        print_job.status = PrintJobStatus.PRINTED
        print_job.printing_completed_at = datetime.utcnow()
        if production_notes:
            print_job.production_notes = production_notes
        
        # Create status history
        status_history = PrintJobStatusHistory(
            print_job_id=print_job.id,
            from_status=PrintJobStatus.PRINTING,
            to_status=PrintJobStatus.PRINTED,
            changed_by_user_id=current_user.id,
            change_reason="Printing completed",
            change_notes=production_notes or "Physical card printed successfully"
        )
        db.add(status_history)
        
        db.commit()
        db.refresh(print_job)
        
        return print_job

    def start_quality_check(
        self,
        db: Session,
        *,
        job_id: UUID,
        current_user: User
    ) -> PrintJob:
        """Start quality assurance review"""
        print_job = self.get(db, id=job_id)
        if not print_job:
            raise ValueError("Print job not found")
        
        if print_job.status != PrintJobStatus.PRINTED:
            raise ValueError(f"Cannot start QA for job in status {print_job.status}")
        
        # Update job
        print_job.status = PrintJobStatus.QUALITY_CHECK
        print_job.quality_check_started_at = datetime.utcnow()
        print_job.quality_check_by_user_id = current_user.id
        print_job.quality_check_result = QualityCheckResult.PENDING
        
        # Create status history
        status_history = PrintJobStatusHistory(
            print_job_id=print_job.id,
            from_status=PrintJobStatus.PRINTED,
            to_status=PrintJobStatus.QUALITY_CHECK,
            changed_by_user_id=current_user.id,
            change_reason="Quality assurance started",
            change_notes="Card quality review in progress"
        )
        db.add(status_history)
        
        db.commit()
        db.refresh(print_job)
        
        return print_job

    def complete_quality_check(
        self,
        db: Session,
        *,
        print_job: PrintJob,
        qa_result: QualityCheckResult,
        qa_notes: str,
        current_user: User
    ) -> PrintJob:
        """
        Complete quality assurance check for a print job
        
        When QA passes (PASSED result), files are deleted from disk to save storage.
        When QA fails, files are kept for reprint processing.
        """
        try:
            # Update QA fields
            print_job.quality_check_result = qa_result
            print_job.quality_check_notes = qa_notes
            print_job.quality_check_by_user_id = current_user.id
            print_job.quality_check_completed_at = datetime.utcnow()
            
            # Update status based on QA result
            if qa_result == QualityCheckResult.PASSED:
                print_job.status = PrintJobStatus.COMPLETED
                print_job.completed_at = datetime.utcnow()
                
                # Clean up files after successful QA - they're no longer needed
                try:
                    from app.services.card_file_manager import card_file_manager
                    
                    # COMPLETE FOLDER REMOVAL after QA passes
                    cleanup_result = card_file_manager.delete_print_job_files(
                        print_job_id=str(print_job.id),
                        created_at=print_job.submitted_at
                    )
                    
                    if cleanup_result["status"] == "success":
                        # Verify complete cleanup to ensure no bloat remains
                        verification = card_file_manager.verify_complete_cleanup(
                            print_job_id=str(print_job.id),
                            created_at=print_job.submitted_at
                        )
                        
                        # Update metadata to reflect complete folder cleanup
                        if print_job.generation_metadata:
                            print_job.generation_metadata.update({
                                "files_deleted_at": datetime.utcnow().isoformat(),
                                "files_deleted_after_qa": True,
                                "folder_completely_removed": cleanup_result.get("folder_removed", False),
                                "cleanup_result": {
                                    "files_deleted": cleanup_result["files_deleted"],
                                    "bytes_freed": cleanup_result["bytes_freed"],
                                    "folder_path": cleanup_result.get("folder_path"),
                                    "empty_dirs_cleaned": cleanup_result.get("empty_dirs_cleaned", 0),
                                    "total_cleanup_items": cleanup_result.get("total_cleanup_items", 0)
                                },
                                "cleanup_verification": {
                                    "completely_removed": verification.get("completely_removed", False),
                                    "verification_timestamp": verification.get("timestamp"),
                                    "no_bloat_remaining": verification.get("status") == "CLEANUP_COMPLETE"
                                }
                            })
                        
                        # Clear ALL file paths since entire folder is deleted
                        print_job.pdf_front_path = None
                        print_job.pdf_back_path = None
                        print_job.pdf_combined_path = None
                        print_job.pdf_files_generated = False  # Files no longer available
                        
                        logger.info(f"✅ QA PASSED - COMPLETE CLEANUP: Deleted {cleanup_result['files_deleted']} files + folder structure ({cleanup_result['bytes_freed']:,} bytes freed) for print job {print_job.id}")
                        
                        if not verification.get("completely_removed", False):
                            logger.warning(f"⚠️  QA CLEANUP WARNING: Verification shows incomplete cleanup for print job {print_job.id}")
                        
                    else:
                        logger.error(f"❌ QA PASSED but complete folder cleanup FAILED for print job {print_job.id}: {cleanup_result.get('message')}")
                        # Still mark as completed but note the cleanup failure
                        if print_job.generation_metadata:
                            print_job.generation_metadata.update({
                                "cleanup_failed": True,
                                "cleanup_error": cleanup_result.get("message"),
                                "manual_cleanup_needed": True
                            })
                        
                except Exception as cleanup_error:
                    logger.error(f"❌ CRITICAL: Error during complete folder cleanup after QA for print job {print_job.id}: {cleanup_error}")
                    # Don't fail the QA completion but flag for manual attention
                    if print_job.generation_metadata:
                        print_job.generation_metadata.update({
                            "cleanup_failed": True,
                            "cleanup_error": str(cleanup_error),
                            "manual_cleanup_needed": True,
                            "cleanup_failure_timestamp": datetime.utcnow().isoformat()
                        })
            
            else:
                # QA failed - determine appropriate reprint status
                if qa_result == QualityCheckResult.FAILED_PRINTING:
                    print_job.status = PrintJobStatus.REPRINT_REQUIRED
                    print_job.priority = PrintJobPriority.HIGH
                elif qa_result == QualityCheckResult.FAILED_DATA:
                    print_job.status = PrintJobStatus.REPRINT_REQUIRED
                    print_job.priority = PrintJobPriority.URGENT
                elif qa_result == QualityCheckResult.FAILED_DAMAGE:
                    print_job.status = PrintJobStatus.REPRINT_REQUIRED
                    print_job.priority = PrintJobPriority.URGENT
                else:
                    print_job.status = PrintJobStatus.REPRINT_REQUIRED
                    print_job.priority = PrintJobPriority.HIGH
                
                # Keep files for reprint - they'll be cleaned up when reprint QA passes
                logger.info(f"QA FAILED ({qa_result}): Keeping files for reprint - print job {print_job.id}")
            
            # Create status history entry
            status_history = PrintJobStatusHistory(
                print_job_id=print_job.id,
                from_status=PrintJobStatus.QUALITY_CHECK,
                to_status=print_job.status,
                changed_by_user_id=current_user.id,
                change_reason=f"Quality check completed: {qa_result}",
                change_notes=qa_notes[:500] if qa_notes else None  # Limit notes length
            )
            db.add(status_history)
            
            db.commit()
            db.refresh(print_job)
            
            return print_job
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error completing quality check for print job {print_job.id}: {e}")
            raise Exception(f"Failed to complete quality check: {str(e)}")

    def create_reprint_job(
        self,
        db: Session,
        *,
        original_job_id: UUID,
        reprint_reason: str,
        current_user: User
    ) -> PrintJob:
        """Create a reprint job that goes to top of queue"""
        original_job = self.get(db, id=original_job_id)
        if not original_job:
            raise ValueError("Original print job not found")
        
        # Generate new job number
        job_number = self.generate_job_number(db, original_job.print_location_id)
        
        # Create reprint job (goes to top of queue)
        reprint_job = PrintJob(
            job_number=job_number,
            status=PrintJobStatus.QUEUED,
            priority=PrintJobPriority.REPRINT,  # High priority
            queue_position=1,  # Top of queue
            person_id=original_job.person_id,
            print_location_id=original_job.print_location_id,
            primary_application_id=original_job.primary_application_id,
            card_number=original_job.card_number,
            license_data=original_job.license_data,
            person_data=original_job.person_data,
            card_template=original_job.card_template,
            original_print_job_id=original_job_id,
            reprint_reason=reprint_reason,
            reprint_count=original_job.reprint_count + 1,
            created_by=current_user.id,
            created_at=datetime.utcnow()
        )
        
        db.add(reprint_job)
        db.flush()
        
        # Move all other jobs down by 1 position
        jobs_to_move = db.query(PrintJob).filter(
            PrintJob.print_location_id == original_job.print_location_id,
            PrintJob.status.in_([PrintJobStatus.QUEUED, PrintJobStatus.ASSIGNED]),
            PrintJob.id != reprint_job.id
        ).all()
        
        for job in jobs_to_move:
            job.queue_position += 1
        
        # Copy application associations from original job
        for original_job_app in original_job.job_applications:
            reprint_job_app = PrintJobApplication(
                print_job_id=reprint_job.id,
                application_id=original_job_app.application_id,
                is_primary=original_job_app.is_primary,
                added_by_user_id=current_user.id
            )
            db.add(reprint_job_app)
        
        # Record queue change
        reprint_job.add_queue_change_record(
            action="REPRINT_CREATED",
            reason=reprint_reason,
            user_id=current_user.id,
            old_position=None,
            new_position=1
        )
        
        # Create status history
        status_history = PrintJobStatusHistory(
            print_job_id=reprint_job.id,
            from_status=None,
            to_status=PrintJobStatus.QUEUED,
            changed_by_user_id=current_user.id,
            change_reason=f"Reprint job created",
            change_notes=f"Reprint of job {original_job.job_number}: {reprint_reason}"
        )
        db.add(status_history)
        
        db.commit()
        db.refresh(reprint_job)
        
        return reprint_job

    def get_jobs_by_location_and_user(
        self,
        db: Session,
        *,
        user: User,
        status: Optional[List[PrintJobStatus]] = None,
        limit: int = 100
    ) -> List[PrintJob]:
        """Get print jobs based on user permissions"""
        query = db.query(PrintJob).options(
            selectinload(PrintJob.person),
            selectinload(PrintJob.primary_application),
            selectinload(PrintJob.print_location)
        )
        
        # Apply location-based filtering based on user type
        if user.user_type == UserType.LOCATION_USER:
            # Location users can only see jobs for their location
            if user.primary_location_id:
                query = query.filter(PrintJob.print_location_id == user.primary_location_id)
        elif user.user_type == UserType.PROVINCIAL_ADMIN:
            # Provincial admins can see jobs for any location in their province
            if user.scope_province:
                from app.models.user import Location
                province_locations = db.query(Location.id).filter(
                    Location.province_code == user.scope_province
                ).subquery()
                query = query.filter(PrintJob.print_location_id.in_(province_locations))
        # National and system admins can see all jobs (no filter)
        
        if status:
            query = query.filter(PrintJob.status.in_(status))
        
        return query.order_by(desc(PrintJob.submitted_at)).limit(limit).all()


class CRUDPrintQueue(CRUDBase[PrintQueue, dict, dict]):
    """CRUD operations for Print Queue management"""

    def get_or_create_queue(self, db: Session, location_id: UUID) -> PrintQueue:
        """Get or create print queue for location"""
        queue = db.query(PrintQueue).filter(PrintQueue.location_id == location_id).first()
        if not queue:
            queue = PrintQueue(
                location_id=location_id,
                current_queue_size=0,
                next_queue_position=1
            )
            db.add(queue)
            db.commit()
            db.refresh(queue)
        return queue

    def get_next_queue_position(self, db: Session, location_id: UUID) -> int:
        """Get next available queue position for location"""
        queue = self.get_or_create_queue(db, location_id)
        next_position = queue.get_next_position()
        db.commit()
        return next_position

    def increment_queue_size(self, db: Session, location_id: UUID):
        """Increment queue size after adding job"""
        queue = self.get_or_create_queue(db, location_id)
        queue.current_queue_size += 1
        db.commit()

    def recalculate_queue(self, db: Session, location_id: UUID):
        """Recalculate entire queue for location"""
        queue = self.get_or_create_queue(db, location_id)
        queue.recalculate_queue_positions(db)


# Create CRUD instances
crud_print_job = CRUDPrintJob(PrintJob)
crud_print_queue = CRUDPrintQueue(PrintQueue) 