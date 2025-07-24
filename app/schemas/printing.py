"""
Printing Management Schemas for Madagascar License System
Pydantic models for print job workflow and queue management
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from uuid import UUID

from app.models.printing import PrintJobStatus, PrintJobPriority, QualityCheckResult


# Base schemas
class PrintJobBase(BaseModel):
    """Base schema for print job"""
    person_id: UUID = Field(..., description="Person for whom card is printed")
    print_location_id: UUID = Field(..., description="Location where card will be printed")
    primary_application_id: UUID = Field(..., description="Primary application triggering print job")
    card_number: str = Field(..., description="Generated card number")
    card_template: str = Field("MADAGASCAR_STANDARD", description="Card design template")
    production_notes: Optional[str] = Field(None, description="Production process notes")


# Request schemas
class PrintJobCreateRequest(BaseModel):
    """Schema for creating a new print job"""
    application_id: UUID = Field(..., description="Primary application ID")
    additional_application_ids: Optional[List[UUID]] = Field(None, description="Additional applications to include")
    card_template: str = Field("MADAGASCAR_STANDARD", description="Card design template")
    production_notes: Optional[str] = Field(None, description="Initial production notes")
    location_id: Optional[UUID] = Field(None, description="Location to handle the print job (for admin users)")

    @validator('additional_application_ids')
    def validate_additional_apps(cls, v):
        """Ensure additional applications list is not empty if provided"""
        if v is not None and len(v) == 0:
            return None
        return v


class PrintJobQueueMoveRequest(BaseModel):
    """Schema for moving job to top of queue"""
    reason: str = Field(..., min_length=5, max_length=500, description="Reason for moving job to top")


class PrintJobAssignRequest(BaseModel):
    """Schema for assigning job to printer"""
    printer_user_id: UUID = Field(..., description="User ID of printer operator")


class PrintJobStartRequest(BaseModel):
    """Schema for starting print job"""
    printer_hardware_id: Optional[str] = Field(None, description="Physical printer identifier")


class PrintJobCompleteRequest(BaseModel):
    """Schema for completing print job"""
    production_notes: Optional[str] = Field(None, description="Production completion notes")


class QualityCheckRequest(BaseModel):
    """Schema for quality check completion"""
    qa_result: QualityCheckResult = Field(..., description="Quality check result")
    qa_notes: Optional[str] = Field(None, description="Quality assurance notes")

    @validator('qa_notes')
    def validate_qa_notes_for_failure(cls, v, values):
        """Require notes when QA fails"""
        if 'qa_result' in values and values['qa_result'] != QualityCheckResult.PASSED:
            if not v or len(v.strip()) < 10:
                raise ValueError("Detailed notes are required when quality check fails")
        return v


class PrintJobSearchFilters(BaseModel):
    """Schema for print job search filters"""
    location_id: Optional[UUID] = Field(None, description="Filter by print location")
    status: Optional[List[PrintJobStatus]] = Field(None, description="Filter by job status")
    person_id: Optional[UUID] = Field(None, description="Filter by person")
    application_id: Optional[UUID] = Field(None, description="Filter by application")
    job_number: Optional[str] = Field(None, description="Search by job number")
    date_from: Optional[datetime] = Field(None, description="Jobs submitted after this date")
    date_to: Optional[datetime] = Field(None, description="Jobs submitted before this date")
    priority: Optional[PrintJobPriority] = Field(None, description="Filter by priority")
    assigned_to: Optional[UUID] = Field(None, description="Filter by assigned user")


# Response schemas
class PrintJobApplicationResponse(BaseModel):
    """Schema for application associated with print job"""
    application_id: UUID
    application_number: str
    application_type: str
    is_primary: bool
    added_at: datetime
    
    class Config:
        from_attributes = True


class PersonLicenseInfo(BaseModel):
    """Schema for license information on card"""
    license_id: UUID
    category: str
    issue_date: datetime
    expiry_date: Optional[datetime]
    status: str
    restrictions: Dict[str, List[str]]
    
    class Config:
        from_attributes = True


class PrintJobStatusHistoryResponse(BaseModel):
    """Schema for print job status history"""
    id: UUID
    from_status: Optional[PrintJobStatus]
    to_status: PrintJobStatus
    changed_at: datetime
    changed_by_user_name: Optional[str]
    change_reason: Optional[str]
    change_notes: Optional[str]
    
    class Config:
        from_attributes = True


class PrintJobResponse(BaseModel):
    """Basic print job response schema"""
    id: UUID
    job_number: str
    status: PrintJobStatus
    priority: PrintJobPriority
    queue_position: Optional[int]
    
    # Person and location
    person_id: UUID
    person_name: Optional[str] = Field(None, description="Person's full name")
    print_location_id: UUID
    print_location_name: Optional[str] = Field(None, description="Print location name")
    
    # Card details
    card_number: str
    card_template: str
    
    # Timing
    submitted_at: datetime
    assigned_at: Optional[datetime]
    printing_started_at: Optional[datetime]
    printing_completed_at: Optional[datetime]
    completed_at: Optional[datetime]
    
    # Quality check
    quality_check_result: Optional[QualityCheckResult]
    quality_check_notes: Optional[str]
    
    # Files
    pdf_files_generated: bool
    
    # Reprint info
    original_print_job_id: Optional[UUID]
    reprint_reason: Optional[str]
    reprint_count: int
    
    # Associated applications
    applications: List[PrintJobApplicationResponse] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


class PrintJobDetailResponse(PrintJobResponse):
    """Detailed print job response with full information"""
    # License data
    licenses: List[PersonLicenseInfo] = Field(default_factory=list, description="Licenses to print on card")
    
    # User information
    assigned_to_user_id: Optional[UUID]
    assigned_to_user_name: Optional[str]
    quality_check_by_user_id: Optional[UUID]
    quality_check_by_user_name: Optional[str]
    
    # Detailed timing
    quality_check_started_at: Optional[datetime]
    quality_check_completed_at: Optional[datetime]
    collection_ready_at: Optional[datetime]
    
    # Production details
    production_batch_id: Optional[str]
    production_notes: Optional[str]
    printer_hardware_id: Optional[str]
    
    # Queue management
    queue_changes: Optional[List[Dict[str, Any]]] = Field(None, description="History of queue changes")
    
    # File paths
    pdf_front_path: Optional[str]
    pdf_back_path: Optional[str]
    pdf_combined_path: Optional[str]
    
    # Status history
    status_history: List[PrintJobStatusHistoryResponse] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


class PrintQueueResponse(BaseModel):
    """Schema for print queue status"""
    location_id: UUID
    location_name: Optional[str]
    current_queue_size: int
    total_jobs_processed: int
    average_processing_time_minutes: Optional[float]
    last_updated: datetime
    
    # Current queue
    queued_jobs: List[PrintJobResponse] = Field(default_factory=list)
    in_progress_jobs: List[PrintJobResponse] = Field(default_factory=list)
    completed_today: int = 0
    
    class Config:
        from_attributes = True


class PrintJobStatistics(BaseModel):
    """Schema for print job statistics"""
    location_id: Optional[UUID] = None
    location_name: Optional[str] = None
    
    # Counts by status
    total_jobs: int = 0
    queued_jobs: int = 0
    in_progress_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    reprint_jobs: int = 0
    
    # Quality metrics
    qa_pass_rate: float = 0.0
    average_completion_time_hours: Optional[float] = None
    
    # Daily statistics
    jobs_completed_today: int = 0
    jobs_submitted_today: int = 0
    
    # Time period
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


class BulkPrintJobAction(BaseModel):
    """Schema for bulk operations on print jobs"""
    job_ids: List[UUID] = Field(..., min_items=1, description="Print job IDs")
    action: str = Field(..., description="Action to perform")
    reason: Optional[str] = Field(None, description="Reason for bulk action")
    
    @validator('action')
    def validate_action(cls, v):
        """Validate bulk action type"""
        allowed_actions = ["cancel", "reassign", "move_to_top"]
        if v not in allowed_actions:
            raise ValueError(f"Action must be one of: {allowed_actions}")
        return v


# Search and pagination
class PrintJobSearchResponse(BaseModel):
    """Schema for paginated print job search results"""
    jobs: List[PrintJobResponse]
    total_count: int
    page: int
    page_size: int
    has_next_page: bool
    has_previous_page: bool 