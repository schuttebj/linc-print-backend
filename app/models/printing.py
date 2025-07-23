"""
Printing Module for Madagascar License System
Handles card printing workflow, queue management, and production tracking
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Numeric, JSON, Enum as SQLEnum, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Session
from sqlalchemy.sql import func
import uuid
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum

from app.models.base import BaseModel


class PrintJobStatus(str, Enum):
    """Print job status enumeration with clear workflow progression"""
    QUEUED = "QUEUED"                           # Added to print queue (FIFO order)
    ASSIGNED = "ASSIGNED"                       # Assigned to printer operator
    PRINTING = "PRINTING"                       # Currently being printed
    PRINTED = "PRINTED"                         # Physical card printed successfully
    QUALITY_CHECK = "QUALITY_CHECK"             # Quality assurance review
    COMPLETED = "COMPLETED"                     # QA passed, ready for collection
    REPRINT_REQUIRED = "REPRINT_REQUIRED"       # QA failed, needs reprint
    CANCELLED = "CANCELLED"                     # Job cancelled
    FAILED = "FAILED"                           # Printing failed (technical error)


class PrintJobPriority(str, Enum):
    """Print job priority levels"""
    NORMAL = "NORMAL"                           # Regular processing order
    HIGH = "HIGH"                               # Moved to top of queue
    URGENT = "URGENT"                           # Emergency processing
    REPRINT = "REPRINT"                         # Reprint jobs (automatically high priority)


class QualityCheckResult(str, Enum):
    """Quality check results"""
    PENDING = "PENDING"                         # Not yet checked
    PASSED = "PASSED"                           # Quality check passed
    FAILED_PRINTING = "FAILED_PRINTING"        # Print quality issues
    FAILED_DATA = "FAILED_DATA"                 # Data accuracy issues
    FAILED_DAMAGE = "FAILED_DAMAGE"             # Physical damage during production


class PrintJob(BaseModel):
    """
    Print Job entity for managing card printing workflow
    
    Each print job represents a single card to be printed with all associated licenses.
    Multiple applications can be linked to one print job when person has pending applications.
    """
    __tablename__ = "print_jobs"

    # Job identification
    job_number = Column(String(20), nullable=False, unique=True, index=True, comment="Unique print job number")
    
    # Queue management
    status = Column(SQLEnum(PrintJobStatus), nullable=False, default=PrintJobStatus.QUEUED, comment="Current job status")
    priority = Column(SQLEnum(PrintJobPriority), nullable=False, default=PrintJobPriority.NORMAL, comment="Job priority level")
    queue_position = Column(Integer, nullable=True, comment="Position in print queue (1 = next to print)")
    submitted_at = Column(DateTime, nullable=False, default=func.now(), comment="When job was submitted to queue")
    
    # Person and location
    person_id = Column(UUID(as_uuid=True), ForeignKey('persons.id'), nullable=False, index=True, comment="Person for whom card is printed")
    print_location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=False, index=True, comment="Location where card will be printed")
    
    # Associated applications (multiple applications can share one print job)
    primary_application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, comment="Primary application triggering print job")
    
    # Card specifications
    card_number = Column(String(20), nullable=False, unique=True, comment="Generated card number")
    card_template = Column(String(50), nullable=False, default="MADAGASCAR_STANDARD", comment="Card design template")
    
    # License data (JSON containing all licenses to print on card)
    license_data = Column(JSON, nullable=False, comment="All license information for card generation")
    person_data = Column(JSON, nullable=False, comment="Person information for card generation")
    
    # Printing workflow tracking
    assigned_to_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="Printer operator assigned to job")
    assigned_at = Column(DateTime, nullable=True, comment="When job was assigned to operator")
    printing_started_at = Column(DateTime, nullable=True, comment="When printing actually started")
    printing_completed_at = Column(DateTime, nullable=True, comment="When printing was completed")
    
    # Quality assurance
    quality_check_started_at = Column(DateTime, nullable=True, comment="When QA review started")
    quality_check_completed_at = Column(DateTime, nullable=True, comment="When QA review completed")
    quality_check_result = Column(SQLEnum(QualityCheckResult), nullable=True, comment="QA result")
    quality_check_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who performed QA")
    quality_check_notes = Column(Text, nullable=True, comment="QA review notes")
    
    # Reprint handling
    original_print_job_id = Column(UUID(as_uuid=True), ForeignKey('print_jobs.id'), nullable=True, comment="Original job if this is a reprint")
    reprint_reason = Column(Text, nullable=True, comment="Reason for reprint")
    reprint_count = Column(Integer, nullable=False, default=0, comment="Number of times this job has been reprinted")
    
    # Queue management history
    queue_changes = Column(JSON, nullable=True, comment="History of queue position changes")
    
    # File generation
    pdf_files_generated = Column(Boolean, nullable=False, default=False, comment="PDF files generated successfully")
    pdf_front_path = Column(String(500), nullable=True, comment="Path to front PDF file")
    pdf_back_path = Column(String(500), nullable=True, comment="Path to back PDF file")
    pdf_combined_path = Column(String(500), nullable=True, comment="Path to combined PDF file")
    
    # Production metadata
    production_batch_id = Column(String(50), nullable=True, comment="Production batch identifier")
    production_notes = Column(Text, nullable=True, comment="Production process notes")
    printer_hardware_id = Column(String(100), nullable=True, comment="Physical printer used")
    
    # Completion tracking
    completed_at = Column(DateTime, nullable=True, comment="When job was fully completed")
    collection_ready_at = Column(DateTime, nullable=True, comment="When card became ready for collection")
    
    # Relationships
    person = relationship("Person")
    print_location = relationship("Location", foreign_keys=[print_location_id])
    primary_application = relationship("Application", foreign_keys=[primary_application_id])
    assigned_to_user = relationship("User", foreign_keys=[assigned_to_user_id])
    quality_check_by_user = relationship("User", foreign_keys=[quality_check_by_user_id])
    original_print_job = relationship("PrintJob", remote_side="PrintJob.id", foreign_keys=[original_print_job_id])
    
    # Associated applications (many-to-many through association table)
    job_applications = relationship("PrintJobApplication", back_populates="print_job", cascade="all, delete-orphan")
    
    # Status history tracking
    status_history = relationship("PrintJobStatusHistory", back_populates="print_job", cascade="all, delete-orphan")
    
    # Database constraints and indexes
    __table_args__ = (
        # Index for queue management queries
        Index('idx_print_queue_location_status', 'print_location_id', 'status', 'queue_position'),
        Index('idx_print_queue_priority_submitted', 'priority', 'submitted_at'),
        Index('idx_print_job_person_status', 'person_id', 'status'),
        # Index for reprint tracking
        Index('idx_print_job_original', 'original_print_job_id'),
    )

    def __repr__(self):
        return f"<PrintJob(number='{self.job_number}', status='{self.status}', person_id={self.person_id})>"

    @property
    def applications(self):
        """Get all applications associated with this print job"""
        return [ja.application for ja in self.job_applications]

    def add_queue_change_record(self, action: str, reason: str, user_id: uuid.UUID, old_position: int = None, new_position: int = None):
        """Add queue change to history"""
        if not self.queue_changes:
            self.queue_changes = []
        
        change_record = {
            "action": action,
            "reason": reason,
            "user_id": str(user_id),
            "timestamp": datetime.utcnow().isoformat(),
            "old_position": old_position,
            "new_position": new_position
        }
        
        self.queue_changes.append(change_record)

    def can_move_to_top(self) -> bool:
        """Check if job can be moved to top of queue"""
        return self.status in [PrintJobStatus.QUEUED, PrintJobStatus.ASSIGNED]

    def can_start_printing(self) -> bool:
        """Check if job is ready to start printing"""
        return self.status in [PrintJobStatus.QUEUED, PrintJobStatus.ASSIGNED] and self.pdf_files_generated


class PrintJobApplication(BaseModel):
    """
    Association table linking print jobs to multiple applications
    
    Handles cases where person has multiple pending applications that should
    be processed together on one card.
    """
    __tablename__ = "print_job_applications"

    print_job_id = Column(UUID(as_uuid=True), ForeignKey('print_jobs.id'), nullable=False, primary_key=True)
    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=False, primary_key=True)
    is_primary = Column(Boolean, nullable=False, default=False, comment="Is this the primary application for the print job")
    added_at = Column(DateTime, nullable=False, default=func.now(), comment="When application was added to print job")
    added_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who added application to job")
    
    # Relationships
    print_job = relationship("PrintJob", back_populates="job_applications")
    application = relationship("Application")
    added_by_user = relationship("User")
    
    def __repr__(self):
        return f"<PrintJobApplication(job_id={self.print_job_id}, app_id={self.application_id}, primary={self.is_primary})>"


class PrintJobStatusHistory(BaseModel):
    """Track status changes for print jobs"""
    __tablename__ = "print_job_status_history"

    print_job_id = Column(UUID(as_uuid=True), ForeignKey('print_jobs.id'), nullable=False, index=True)
    from_status = Column(SQLEnum(PrintJobStatus), nullable=True, comment="Previous status")
    to_status = Column(SQLEnum(PrintJobStatus), nullable=False, comment="New status")
    changed_at = Column(DateTime, nullable=False, default=func.now(), comment="When status changed")
    changed_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who changed status")
    change_reason = Column(Text, nullable=True, comment="Reason for status change")
    change_notes = Column(Text, nullable=True, comment="Additional notes")
    
    # Relationships
    print_job = relationship("PrintJob", back_populates="status_history")
    changed_by_user = relationship("User")
    
    def __repr__(self):
        return f"<PrintJobStatusHistory(job_id={self.print_job_id}, from='{self.from_status}', to='{self.to_status}')>"


class PrintQueue(BaseModel):
    """
    Print queue management per location
    
    Manages FIFO ordering and queue positions for each print location
    """
    __tablename__ = "print_queues"

    location_id = Column(UUID(as_uuid=True), ForeignKey('locations.id'), nullable=False, primary_key=True)
    current_queue_size = Column(Integer, nullable=False, default=0, comment="Current number of jobs in queue")
    next_queue_position = Column(Integer, nullable=False, default=1, comment="Next available queue position")
    last_updated = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="Last queue update")
    updated_by_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who last updated queue")
    
    # Statistics
    total_jobs_processed = Column(Integer, nullable=False, default=0, comment="Total jobs processed by this location")
    average_processing_time_minutes = Column(Numeric(10, 2), nullable=True, comment="Average time to complete job")
    
    # Relationships
    location = relationship("Location")
    updated_by_user = relationship("User")
    
    def __repr__(self):
        return f"<PrintQueue(location_id={self.location_id}, size={self.current_queue_size})>"

    def get_next_position(self) -> int:
        """Get next available queue position"""
        next_pos = self.next_queue_position
        self.next_queue_position += 1
        return next_pos

    def recalculate_queue_positions(self, db_session: Session):
        """Recalculate queue positions after changes"""
        from app.models.printing import PrintJob
        
        # Get all queued jobs for this location ordered by priority and submission time
        queued_jobs = db_session.query(PrintJob).filter(
            PrintJob.print_location_id == self.location_id,
            PrintJob.status.in_([PrintJobStatus.QUEUED, PrintJobStatus.ASSIGNED])
        ).order_by(
            PrintJob.priority.desc(),  # High priority first
            PrintJob.submitted_at.asc()  # Then FIFO
        ).all()
        
        # Reassign positions
        for i, job in enumerate(queued_jobs, 1):
            job.queue_position = i
        
        self.current_queue_size = len(queued_jobs)
        self.next_queue_position = len(queued_jobs) + 1
        
        db_session.commit() 