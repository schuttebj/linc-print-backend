"""
Issue Tracking System Models for Madagascar License System

Provides comprehensive issue tracking and bug reporting capabilities with:
- User-reported issues (manual submissions)
- Auto-reported issues (JavaScript errors, API failures)
- File attachments (screenshots, console logs)
- Priority and category management
- Assignment and status tracking
- Persistent disk storage following biometric pattern
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Numeric, JSON, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from typing import Optional

from app.models.base import BaseModel
from app.models.enums import (
    IssueStatus, IssueCategory, IssuePriority, IssueReportType
)


class Issue(BaseModel):
    """
    Core issue tracking model
    Supports both user-reported and automatically captured issues
    """
    __tablename__ = "issues"

    # Basic issue information
    title = Column(String(255), nullable=False, comment="Issue title/summary")
    description = Column(Text, nullable=False, comment="Detailed issue description")
    
    # Classification
    category = Column(SQLEnum(IssueCategory, native_enum=False), nullable=False, comment="Issue category")
    priority = Column(SQLEnum(IssuePriority, native_enum=False), nullable=False, default=IssuePriority.MEDIUM, comment="Issue priority level")
    status = Column(SQLEnum(IssueStatus, native_enum=False), nullable=False, default=IssueStatus.NEW, comment="Current issue status")
    report_type = Column(SQLEnum(IssueReportType, native_enum=False), nullable=False, comment="How the issue was reported")
    
    # Context information
    page_url = Column(String(1000), nullable=True, comment="URL where issue occurred")
    user_agent = Column(String(500), nullable=True, comment="Browser/device information")
    steps_to_reproduce = Column(Text, nullable=True, comment="Steps to reproduce the issue")
    expected_behavior = Column(Text, nullable=True, comment="What should have happened")
    actual_behavior = Column(Text, nullable=True, comment="What actually happened")
    
    # File attachments (stored on persistent disk)
    screenshot_path = Column(String(500), nullable=True, comment="Path to screenshot file")
    console_logs_path = Column(String(500), nullable=True, comment="Path to console logs file")
    additional_files_paths = Column(JSON, nullable=True, comment="Paths to additional attached files")
    
    # Technical details
    error_message = Column(Text, nullable=True, comment="Error message if available")
    stack_trace = Column(Text, nullable=True, comment="Stack trace for errors")
    console_logs = Column(JSON, nullable=True, comment="Console log entries")
    network_logs = Column(JSON, nullable=True, comment="Failed API requests")
    
    # Assignment and workflow
    assigned_to = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="Assigned developer/admin")
    estimated_effort = Column(String(50), nullable=True, comment="Estimated effort (e.g., '2 hours', '1 day')")
    resolution_notes = Column(Text, nullable=True, comment="Notes about how issue was resolved")
    
    # Timing and tracking
    reported_at = Column(DateTime, nullable=False, default=func.now(), comment="When issue was reported")
    assigned_at = Column(DateTime, nullable=True, comment="When issue was assigned")
    started_at = Column(DateTime, nullable=True, comment="When work started")
    resolved_at = Column(DateTime, nullable=True, comment="When issue was resolved")
    closed_at = Column(DateTime, nullable=True, comment="When issue was closed")
    
    # User tracking
    reported_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who reported the issue")
    resolved_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who resolved the issue")
    
    # Metadata
    environment = Column(String(50), nullable=True, comment="Environment where issue occurred (prod/staging/dev)")
    browser_version = Column(String(100), nullable=True, comment="Browser version information")
    operating_system = Column(String(100), nullable=True, comment="Operating system information")
    
    # Relationships
    reported_by_user = relationship("User", foreign_keys=[reported_by], back_populates="reported_issues")
    assigned_to_user = relationship("User", foreign_keys=[assigned_to], back_populates="assigned_issues")
    resolved_by_user = relationship("User", foreign_keys=[resolved_by], back_populates="resolved_issues")
    comments = relationship("IssueComment", back_populates="issue", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Issue(id={self.id}, title='{self.title[:50]}...', status={self.status.value}, priority={self.priority.value})>"
    
    @property
    def is_auto_reported(self) -> bool:
        """Check if this issue was automatically reported"""
        return self.report_type in [IssueReportType.AUTO_REPORTED_JS_ERROR, IssueReportType.AUTO_REPORTED_API_ERROR]
    
    @property
    def time_to_resolution(self) -> Optional[str]:
        """Calculate time from reporting to resolution"""
        if not self.resolved_at or not self.reported_at:
            return None
        
        delta = self.resolved_at - self.reported_at
        days = delta.days
        hours = delta.seconds // 3600
        
        if days > 0:
            return f"{days} days, {hours} hours"
        else:
            return f"{hours} hours"


class IssueComment(BaseModel):
    """
    Comments/updates on issues for tracking progress and communication
    """
    __tablename__ = "issue_comments"
    
    issue_id = Column(UUID(as_uuid=True), ForeignKey('issues.id'), nullable=False, comment="Issue this comment belongs to")
    content = Column(Text, nullable=False, comment="Comment content")
    comment_type = Column(String(50), nullable=False, default='comment', comment="Type: comment, status_change, assignment")
    
    # Change tracking
    old_status = Column(String(50), nullable=True, comment="Previous status if this is a status change")
    new_status = Column(String(50), nullable=True, comment="New status if this is a status change")
    old_assignee = Column(UUID(as_uuid=True), nullable=True, comment="Previous assignee if this is an assignment change")
    new_assignee = Column(UUID(as_uuid=True), nullable=True, comment="New assignee if this is an assignment change")
    
    # Metadata
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who created the comment")
    is_internal = Column(Boolean, nullable=False, default=False, comment="Internal comment (not visible to issue reporter)")
    
    # Relationships
    issue = relationship("Issue", back_populates="comments")
    created_by_user = relationship("User", foreign_keys=[created_by])
    
    def __repr__(self):
        return f"<IssueComment(id={self.id}, issue_id={self.issue_id}, type={self.comment_type})>"


class IssueAttachment(BaseModel):
    """
    File attachments for issues
    Following the persistent disk storage pattern used for biometrics
    """
    __tablename__ = "issue_attachments"
    
    issue_id = Column(UUID(as_uuid=True), ForeignKey('issues.id'), nullable=False, comment="Issue this attachment belongs to")
    file_name = Column(String(255), nullable=False, comment="Original filename")
    file_path = Column(String(500), nullable=False, comment="Path to file on persistent disk")
    file_size = Column(Integer, nullable=False, comment="File size in bytes")
    file_type = Column(String(100), nullable=False, comment="MIME type")
    attachment_type = Column(String(50), nullable=False, comment="Type: screenshot, console_logs, additional")
    
    # Metadata
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False, comment="User who uploaded the file")
    
    # Relationships
    issue = relationship("Issue")
    uploaded_by_user = relationship("User")
    
    def __repr__(self):
        return f"<IssueAttachment(id={self.id}, filename='{self.file_name}', type={self.attachment_type})>"
