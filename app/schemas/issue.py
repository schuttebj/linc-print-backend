"""
Pydantic schemas for Issue Tracking System in Madagascar License System
Handles validation and serialization for issue reporting and management
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime
import uuid

from app.models.enums import (
    IssueStatus, IssueCategory, IssuePriority, IssueReportType
)


# Base schemas for issue management
class IssueBase(BaseModel):
    """Base schema for issue data"""
    title: str = Field(..., min_length=3, max_length=255, description="Issue title/summary")
    description: str = Field(..., min_length=5, description="Detailed issue description")
    category: IssueCategory = Field(..., description="Issue category")
    priority: IssuePriority = Field(default=IssuePriority.MEDIUM, description="Issue priority level")
    page_url: Optional[str] = Field(None, max_length=1000, description="URL where issue occurred")
    steps_to_reproduce: Optional[str] = Field(None, description="Steps to reproduce the issue")
    expected_behavior: Optional[str] = Field(None, description="What should have happened")
    actual_behavior: Optional[str] = Field(None, description="What actually happened")


class IssueCreate(IssueBase):
    """Schema for creating a new issue"""
    report_type: IssueReportType = Field(default=IssueReportType.USER_REPORTED, description="How the issue was reported")
    
    # Auto-captured data
    user_agent: Optional[str] = Field(None, max_length=1000, description="Browser/device information")
    error_message: Optional[str] = Field(None, description="Error message if available")
    stack_trace: Optional[str] = Field(None, description="Stack trace for errors")
    console_logs: Optional[List[str]] = Field(None, description="Console log entries")
    network_logs: Optional[List[Dict[str, Any]]] = Field(None, description="Failed API requests")
    
    # Environment data
    environment: Optional[str] = Field(None, max_length=50, description="Environment (prod/staging/dev)")
    browser_version: Optional[str] = Field(None, max_length=200, description="Browser version")
    operating_system: Optional[str] = Field(None, max_length=100, description="Operating system")
    
    @validator('console_logs')
    def validate_console_logs(cls, v):
        """Ensure console logs don't exceed reasonable limits"""
        if v and len(v) > 200:  # Configurable limit
            return v[-200:]  # Keep last 200 entries
        return v


class IssueUpdate(BaseModel):
    """Schema for updating an issue"""
    title: Optional[str] = Field(None, min_length=5, max_length=255)
    description: Optional[str] = Field(None, min_length=10)
    category: Optional[IssueCategory] = None
    priority: Optional[IssuePriority] = None
    status: Optional[IssueStatus] = None
    assigned_to: Optional[uuid.UUID] = None
    estimated_effort: Optional[str] = Field(None, max_length=50)
    resolution_notes: Optional[str] = None
    steps_to_reproduce: Optional[str] = None
    expected_behavior: Optional[str] = None
    actual_behavior: Optional[str] = None


class IssueResponse(IssueBase):
    """Schema for issue response data"""
    id: uuid.UUID
    status: IssueStatus
    report_type: IssueReportType
    
    # File paths
    screenshot_path: Optional[str] = None
    console_logs_path: Optional[str] = None
    additional_files_paths: Optional[List[str]] = None
    
    # Assignment and workflow
    assigned_to: Optional[uuid.UUID] = None
    estimated_effort: Optional[str] = None
    resolution_notes: Optional[str] = None
    
    # Timing
    reported_at: datetime
    assigned_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    
    # User tracking
    reported_by: Optional[uuid.UUID] = None
    resolved_by: Optional[uuid.UUID] = None
    
    # Environment data
    environment: Optional[str] = None
    browser_version: Optional[str] = None
    operating_system: Optional[str] = None
    
    # Additional metadata
    error_message: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserBasicInfo(BaseModel):
    """Basic user information for issue responses"""
    id: uuid.UUID
    username: str
    madagascar_id: Optional[str] = None
    full_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class IssueDetailResponse(IssueResponse):
    """Detailed schema for issue with relationships"""
    # User relationships (only include basic info for security)
    reported_by_user: Optional[UserBasicInfo] = None
    assigned_to_user: Optional[UserBasicInfo] = None
    resolved_by_user: Optional[UserBasicInfo] = None
    
    # Comments
    comments: List['IssueCommentResponse'] = []
    
    # File attachments
    attachments: List['IssueAttachmentResponse'] = []
    
    # Computed properties
    time_to_resolution: Optional[str] = None
    is_auto_reported: bool = False


# Comment schemas
class IssueCommentBase(BaseModel):
    """Base schema for issue comments"""
    content: str = Field(..., min_length=1, description="Comment content")
    comment_type: str = Field(default='comment', description="Type: comment, status_change, assignment")
    is_internal: bool = Field(default=False, description="Internal comment (not visible to reporter)")


class IssueCommentCreate(IssueCommentBase):
    """Schema for creating a comment"""
    issue_id: uuid.UUID
    
    # Change tracking (for status/assignment changes)
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    old_assignee: Optional[uuid.UUID] = None
    new_assignee: Optional[uuid.UUID] = None


class IssueCommentResponse(IssueCommentBase):
    """Schema for comment response data"""
    id: uuid.UUID
    issue_id: uuid.UUID
    created_by: uuid.UUID
    created_by_user: Optional[Dict[str, str]] = None  # Basic user info only
    created_at: datetime
    updated_at: datetime
    
    # Change tracking
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    old_assignee: Optional[uuid.UUID] = None
    new_assignee: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True


# Attachment schemas
class IssueAttachmentResponse(BaseModel):
    """Schema for issue attachment data"""
    id: uuid.UUID
    issue_id: uuid.UUID
    file_name: str
    file_path: str
    file_size: int
    file_type: str
    attachment_type: str
    uploaded_by: uuid.UUID
    uploaded_by_user: Optional[Dict[str, str]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Specialized schemas for different report types
class UserIssueCreate(IssueCreate):
    """Schema for user-reported issues"""
    report_type: IssueReportType = IssueReportType.USER_REPORTED
    
    # Screenshot data (base64 encoded)
    screenshot_data: Optional[str] = Field(None, description="Base64 encoded screenshot")


class AutoIssueCreate(IssueBase):
    """Schema for automatically reported issues"""
    report_type: IssueReportType
    error_message: str = Field(..., description="Error message")
    stack_trace: Optional[str] = None
    page_url: str = Field(..., description="URL where error occurred")
    user_agent: str = Field(..., description="Browser/device information")
    console_logs: Optional[List[str]] = None
    network_logs: Optional[List[Dict[str, Any]]] = None
    
    # Auto-detected priority based on error type
    @validator('priority', pre=True, always=True)
    def set_auto_priority(cls, v, values):
        """Auto-set priority based on error type"""
        if not v:
            error_message = values.get('error_message', '').lower()
            if any(keyword in error_message for keyword in ['uncaught', 'fatal', 'crash', 'network error']):
                return IssuePriority.HIGH
            elif any(keyword in error_message for keyword in ['warning', 'deprecated']):
                return IssuePriority.LOW
            else:
                return IssuePriority.MEDIUM
        return v


# List and filter schemas
class IssueFilter(BaseModel):
    """Schema for filtering issues"""
    status: Optional[List[IssueStatus]] = None
    category: Optional[List[IssueCategory]] = None
    priority: Optional[List[IssuePriority]] = None
    report_type: Optional[List[IssueReportType]] = None
    assigned_to: Optional[uuid.UUID] = None
    reported_by: Optional[uuid.UUID] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search: Optional[str] = Field(None, description="Search in title and description")


class IssueListResponse(BaseModel):
    """Schema for paginated issue list"""
    items: List[IssueResponse]
    total: int
    page: int
    size: int
    total_pages: int
    
    # Summary statistics
    status_counts: Dict[str, int] = {}
    priority_counts: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}


# Analytics and reporting schemas
class IssueStatsResponse(BaseModel):
    """Schema for issue statistics"""
    total_issues: int
    open_issues: int
    resolved_issues: int
    avg_resolution_time: Optional[str] = None
    
    # Breakdown by category
    by_status: Dict[str, int] = {}
    by_category: Dict[str, int] = {}
    by_priority: Dict[str, int] = {}
    by_report_type: Dict[str, int] = {}
    
    # Trend data (last 30 days)
    daily_reports: List[Dict[str, Any]] = []
    
    # Top reporters and assignees
    top_reporters: List[Dict[str, Any]] = []
    top_assignees: List[Dict[str, Any]] = []


# Console log capture schema
class ConsoleLogCapture(BaseModel):
    """Schema for console log capture configuration"""
    max_entries: int = Field(default=100, ge=10, le=500, description="Maximum console entries to capture")
    log_levels: List[str] = Field(default=['error', 'warn', 'info'], description="Log levels to capture")
    include_timestamps: bool = Field(default=True, description="Include timestamps in logs")


# Forward references for Pydantic
IssueDetailResponse.model_rebuild()
IssueCommentResponse.model_rebuild()
