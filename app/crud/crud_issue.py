"""
CRUD operations for Issue Tracking System in Madagascar License System
Provides comprehensive database operations for issue management
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func, extract
from datetime import datetime, timedelta
import uuid

from app.crud.base import CRUDBase
from app.models.issue import Issue, IssueComment, IssueAttachment
from app.models.user import User
from app.schemas.issue import (
    IssueCreate, IssueUpdate, IssueFilter,
    IssueCommentCreate, IssueCommentResponse
)
from app.models.enums import IssueStatus, IssueReportType, IssuePriority


class CRUDIssue(CRUDBase[Issue, IssueCreate, IssueUpdate]):
    """CRUD operations for issues"""
    
    def create_with_reporter(
        self, 
        db: Session, 
        *, 
        obj_in: IssueCreate, 
        reported_by: Optional[uuid.UUID] = None
    ) -> Issue:
        """Create issue with reporter information"""
        obj_data = obj_in.model_dump()
        
        # Set reporter if provided
        if reported_by:
            obj_data["reported_by"] = reported_by
        
        # Set timestamps
        obj_data["reported_at"] = datetime.now()
        
        db_obj = Issue(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_with_details(self, db: Session, id: uuid.UUID) -> Optional[Issue]:
        """Get issue with all related data loaded"""
        return db.query(Issue).options(
            joinedload(Issue.reported_by_user),
            joinedload(Issue.assigned_to_user),
            joinedload(Issue.resolved_by_user),
            joinedload(Issue.comments).joinedload(IssueComment.created_by_user)
        ).filter(Issue.id == id).first()
    
    def get_filtered(
        self, 
        db: Session, 
        *, 
        filter_params: IssueFilter,
        skip: int = 0, 
        limit: int = 100,
        current_user_id: Optional[uuid.UUID] = None,
        user_can_view_all: bool = False
    ) -> Tuple[List[Issue], int]:
        """Get filtered issues with pagination"""
        query = db.query(Issue)
        
        # Apply user-based filtering if not admin
        if not user_can_view_all and current_user_id:
            # Users can see issues they reported or are assigned to
            query = query.filter(
                or_(
                    Issue.reported_by == current_user_id,
                    Issue.assigned_to == current_user_id
                )
            )
        
        # Apply filters
        if filter_params.status:
            query = query.filter(Issue.status.in_(filter_params.status))
        
        if filter_params.category:
            query = query.filter(Issue.category.in_(filter_params.category))
        
        if filter_params.priority:
            query = query.filter(Issue.priority.in_(filter_params.priority))
        
        if filter_params.report_type:
            query = query.filter(Issue.report_type.in_(filter_params.report_type))
        
        if filter_params.assigned_to:
            query = query.filter(Issue.assigned_to == filter_params.assigned_to)
        
        if filter_params.reported_by:
            query = query.filter(Issue.reported_by == filter_params.reported_by)
        
        if filter_params.date_from:
            query = query.filter(Issue.reported_at >= filter_params.date_from)
        
        if filter_params.date_to:
            query = query.filter(Issue.reported_at <= filter_params.date_to)
        
        if filter_params.search:
            search_term = f"%{filter_params.search}%"
            query = query.filter(
                or_(
                    Issue.title.ilike(search_term),
                    Issue.description.ilike(search_term),
                    Issue.error_message.ilike(search_term)
                )
            )
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        issues = query.order_by(desc(Issue.created_at)).offset(skip).limit(limit).all()
        
        return issues, total
    
    def assign_issue(
        self, 
        db: Session, 
        *, 
        issue_id: uuid.UUID, 
        assigned_to: uuid.UUID,
        assigned_by: uuid.UUID
    ) -> Optional[Issue]:
        """Assign issue to a user"""
        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        if not issue:
            return None
        
        old_assignee = issue.assigned_to
        issue.assigned_to = assigned_to
        issue.assigned_at = datetime.now()
        
        # Update status if it's new
        if issue.status == IssueStatus.NEW:
            issue.status = IssueStatus.IN_PROGRESS
            issue.started_at = datetime.now()
        
        db.commit()
        db.refresh(issue)
        
        # Create comment for assignment change
        self._create_assignment_comment(
            db, issue_id, old_assignee, assigned_to, assigned_by
        )
        
        return issue
    
    def update_status(
        self, 
        db: Session, 
        *, 
        issue_id: uuid.UUID, 
        new_status: IssueStatus,
        updated_by: uuid.UUID,
        resolution_notes: Optional[str] = None
    ) -> Optional[Issue]:
        """Update issue status with automatic timestamp management"""
        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        if not issue:
            return None
        
        old_status = issue.status
        issue.status = new_status
        
        # Set appropriate timestamps
        now = datetime.now()
        if new_status == IssueStatus.IN_PROGRESS and not issue.started_at:
            issue.started_at = now
        elif new_status == IssueStatus.RESOLVED:
            issue.resolved_at = now
            issue.resolved_by = updated_by
            if resolution_notes:
                issue.resolution_notes = resolution_notes
        elif new_status == IssueStatus.CLOSED:
            if not issue.resolved_at:
                issue.resolved_at = now
                issue.resolved_by = updated_by
            issue.closed_at = now
        
        db.commit()
        db.refresh(issue)
        
        # Create comment for status change
        self._create_status_comment(
            db, issue_id, old_status, new_status, updated_by, resolution_notes
        )
        
        return issue
    
    def get_user_issues(
        self, 
        db: Session, 
        user_id: uuid.UUID, 
        include_assigned: bool = True,
        skip: int = 0, 
        limit: int = 100
    ) -> Tuple[List[Issue], int]:
        """Get issues for a specific user (reported or assigned)"""
        query = db.query(Issue)
        
        if include_assigned:
            query = query.filter(
                or_(
                    Issue.reported_by == user_id,
                    Issue.assigned_to == user_id
                )
            )
        else:
            query = query.filter(Issue.reported_by == user_id)
        
        total = query.count()
        issues = query.order_by(desc(Issue.created_at)).offset(skip).limit(limit).all()
        
        return issues, total
    
    def get_auto_reported_issues(
        self, 
        db: Session, 
        *, 
        days: int = 7,
        skip: int = 0, 
        limit: int = 100
    ) -> Tuple[List[Issue], int]:
        """Get automatically reported issues from the last N days"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        query = db.query(Issue).filter(
            and_(
                Issue.report_type.in_([
                    IssueReportType.AUTO_REPORTED_JS_ERROR,
                    IssueReportType.AUTO_REPORTED_API_ERROR
                ]),
                Issue.reported_at >= cutoff_date
            )
        )
        
        total = query.count()
        issues = query.order_by(desc(Issue.created_at)).offset(skip).limit(limit).all()
        
        return issues, total
    
    def get_statistics(self, db: Session, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive issue statistics"""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Basic counts
        total_issues = db.query(Issue).count()
        open_issues = db.query(Issue).filter(
            Issue.status.in_([IssueStatus.NEW, IssueStatus.IN_PROGRESS, IssueStatus.TESTING])
        ).count()
        resolved_issues = db.query(Issue).filter(
            Issue.status.in_([IssueStatus.RESOLVED, IssueStatus.CLOSED])
        ).count()
        
        # Status breakdown
        status_counts = {}
        for status in IssueStatus:
            count = db.query(Issue).filter(Issue.status == status).count()
            status_counts[status.value] = count
        
        # Category breakdown
        category_counts = {}
        category_query = db.query(
            Issue.category, func.count(Issue.id)
        ).group_by(Issue.category).all()
        for category, count in category_query:
            category_counts[category.value] = count
        
        # Priority breakdown
        priority_counts = {}
        priority_query = db.query(
            Issue.priority, func.count(Issue.id)
        ).group_by(Issue.priority).all()
        for priority, count in priority_query:
            priority_counts[priority.value] = count
        
        # Report type breakdown
        report_type_counts = {}
        report_type_query = db.query(
            Issue.report_type, func.count(Issue.id)
        ).group_by(Issue.report_type).all()
        for report_type, count in report_type_query:
            report_type_counts[report_type.value] = count
        
        # Daily reports (last 30 days)
        daily_query = db.query(
            func.date(Issue.reported_at),
            func.count(Issue.id)
        ).filter(
            Issue.reported_at >= cutoff_date
        ).group_by(
            func.date(Issue.reported_at)
        ).all()
        
        daily_reports = [
            {"date": str(date), "count": count}
            for date, count in daily_query
        ]
        
        # Average resolution time
        resolved_issues_with_time = db.query(Issue).filter(
            and_(
                Issue.resolved_at.isnot(None),
                Issue.reported_at.isnot(None)
            )
        ).all()
        
        avg_resolution_time = None
        if resolved_issues_with_time:
            total_seconds = sum([
                (issue.resolved_at - issue.reported_at).total_seconds()
                for issue in resolved_issues_with_time
            ])
            avg_seconds = total_seconds / len(resolved_issues_with_time)
            avg_hours = avg_seconds / 3600
            avg_resolution_time = f"{avg_hours:.1f} hours"
        
        return {
            "total_issues": total_issues,
            "open_issues": open_issues,
            "resolved_issues": resolved_issues,
            "avg_resolution_time": avg_resolution_time,
            "by_status": status_counts,
            "by_category": category_counts,
            "by_priority": priority_counts,
            "by_report_type": report_type_counts,
            "daily_reports": daily_reports
        }
    
    def _create_status_comment(
        self, 
        db: Session, 
        issue_id: uuid.UUID,
        old_status: IssueStatus, 
        new_status: IssueStatus,
        updated_by: uuid.UUID,
        resolution_notes: Optional[str] = None
    ):
        """Create a comment for status changes"""
        content = f"Status changed from {old_status.value} to {new_status.value}"
        if resolution_notes:
            content += f"\n\nResolution notes: {resolution_notes}"
        
        comment = IssueComment(
            issue_id=issue_id,
            content=content,
            comment_type="status_change",
            old_status=old_status.value,
            new_status=new_status.value,
            created_by=updated_by,
            is_internal=False
        )
        db.add(comment)
        db.commit()
    
    def _create_assignment_comment(
        self, 
        db: Session, 
        issue_id: uuid.UUID,
        old_assignee: Optional[uuid.UUID], 
        new_assignee: uuid.UUID,
        assigned_by: uuid.UUID
    ):
        """Create a comment for assignment changes"""
        if old_assignee:
            content = f"Issue reassigned to new user"
        else:
            content = f"Issue assigned to user"
        
        comment = IssueComment(
            issue_id=issue_id,
            content=content,
            comment_type="assignment",
            old_assignee=old_assignee,
            new_assignee=new_assignee,
            created_by=assigned_by,
            is_internal=False
        )
        db.add(comment)
        db.commit()


class CRUDIssueComment(CRUDBase[IssueComment, IssueCommentCreate, None]):
    """CRUD operations for issue comments"""
    
    def create_with_user(
        self, 
        db: Session, 
        *, 
        obj_in: IssueCommentCreate, 
        created_by: uuid.UUID
    ) -> IssueComment:
        """Create comment with user information"""
        obj_data = obj_in.model_dump()
        obj_data["created_by"] = created_by
        
        db_obj = IssueComment(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_by_issue(
        self, 
        db: Session, 
        issue_id: uuid.UUID,
        include_internal: bool = False
    ) -> List[IssueComment]:
        """Get comments for an issue"""
        query = db.query(IssueComment).filter(IssueComment.issue_id == issue_id)
        
        if not include_internal:
            query = query.filter(IssueComment.is_internal == False)
        
        return query.order_by(IssueComment.created_at).all()


class CRUDIssueAttachment(CRUDBase[IssueAttachment, None, None]):
    """CRUD operations for issue attachments"""
    
    def create_attachment(
        self, 
        db: Session, 
        *,
        issue_id: uuid.UUID,
        file_name: str,
        file_path: str,
        file_size: int,
        file_type: str,
        attachment_type: str,
        uploaded_by: uuid.UUID
    ) -> IssueAttachment:
        """Create issue attachment"""
        db_obj = IssueAttachment(
            issue_id=issue_id,
            file_name=file_name,
            file_path=file_path,
            file_size=file_size,
            file_type=file_type,
            attachment_type=attachment_type,
            uploaded_by=uploaded_by
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get_by_issue(self, db: Session, issue_id: uuid.UUID) -> List[IssueAttachment]:
        """Get attachments for an issue"""
        return db.query(IssueAttachment).filter(
            IssueAttachment.issue_id == issue_id
        ).order_by(IssueAttachment.created_at).all()


# Create CRUD instances
issue = CRUDIssue(Issue)
issue_comment = CRUDIssueComment(IssueComment)
issue_attachment = CRUDIssueAttachment(IssueAttachment)
