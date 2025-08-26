"""
Issue Tracking API Endpoints for Madagascar License System
Comprehensive REST API for issue reporting and management
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Request, Body, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from pathlib import Path
import uuid
import logging
from datetime import datetime
import base64
import io

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.issue import Issue, IssueComment, IssueAttachment
from app.models.enums import IssueStatus, IssueCategory, IssuePriority, IssueReportType
from app.schemas.issue import (
    IssueCreate, IssueUpdate, IssueResponse, IssueDetailResponse,
    IssueListResponse, IssueFilter, IssueStatsResponse,
    UserIssueCreate, AutoIssueCreate,
    IssueCommentCreate, IssueCommentResponse,
    ConsoleLogCapture, IssueStatusUpdate, IssueAssignment
)
from app.crud import issue as crud_issue, issue_comment as crud_issue_comment
from app.services.issue_file_manager import IssueFileManager
# Permission checking is done using current_user.has_permission()

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize file manager
file_manager = IssueFileManager()

@router.post("/", response_model=IssueDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_issue(
    *,
    db: Session = Depends(get_db),
    issue_in: UserIssueCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new issue report
    
    Supports:
    - User-reported issues with screenshots
    - Automatic file storage on persistent disk
    - Console log capture
    """
    try:
        # Extract file data before creating issue
        screenshot_data = getattr(issue_in, 'screenshot_data', None)
        console_logs = getattr(issue_in, 'console_logs', None)
        
        # Create issue data without file fields
        issue_dict = issue_in.dict(exclude={'screenshot_data', 'console_logs'})
        
        # Convert back to Pydantic model for proper validation
        from app.schemas.issue import IssueCreate
        issue_data = IssueCreate(**issue_dict)
        
        # Create the issue
        issue = crud_issue.create_with_reporter(
            db=db, 
            obj_in=issue_data, 
            reported_by=current_user.id
        )
        
        # Handle screenshot if provided
        if screenshot_data:
            try:
                # Decode base64 screenshot
                screenshot_bytes = base64.b64decode(screenshot_data.split(',')[-1])
                
                # Save screenshot to persistent disk
                screenshot_info = file_manager.save_screenshot(
                    issue_id=issue.id,
                    screenshot_data=screenshot_bytes,
                    created_at=issue.created_at
                )
                
                # Update issue with screenshot path
                issue.screenshot_path = screenshot_info["file_path"]
                db.commit()
                
            except Exception as e:
                logger.error(f"Failed to save screenshot for issue {issue.id}: {e}")
                # Continue without screenshot rather than failing the entire request
        
        # Handle console logs if provided
        if console_logs:
            try:
                console_logs_info = file_manager.save_console_logs(
                    issue_id=issue.id,
                    console_logs=console_logs,
                    created_at=issue.created_at
                )
                
                # Update issue with console logs path
                issue.console_logs_path = console_logs_info["file_path"]
                db.commit()
                
            except Exception as e:
                logger.error(f"Failed to save console logs for issue {issue.id}: {e}")
        
        # Get issue with full details
        issue_with_details = crud_issue.get_with_details(db, issue.id)
        
        logger.info(f"Issue created: {issue.id} by user {current_user.id}")
        
        return issue_with_details
        
    except Exception as e:
        logger.error(f"Failed to create issue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create issue"
        )


@router.post("/auto-report", response_model=IssueResponse, status_code=status.HTTP_201_CREATED)
async def auto_report_issue(
    *,
    db: Session = Depends(get_db),
    issue_in: AutoIssueCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Auto-report an issue (JavaScript errors, API failures, etc.)
    
    This endpoint is called automatically by the frontend when errors are detected.
    """
    try:
        # Create the auto-reported issue
        issue = crud_issue.create_with_reporter(
            db=db, 
            obj_in=issue_in, 
            reported_by=current_user.id
        )
        
        # Handle console logs if provided
        if issue_in.console_logs:
            try:
                console_logs_info = file_manager.save_console_logs(
                    issue_id=issue.id,
                    console_logs=issue_in.console_logs,
                    created_at=issue.created_at
                )
                
                # Update issue with console logs path
                issue.console_logs_path = console_logs_info["file_path"]
                db.commit()
                
            except Exception as e:
                logger.error(f"Failed to save console logs for auto-issue {issue.id}: {e}")
        
        logger.info(f"Auto-issue created: {issue.id} - {issue_in.error_message}")
        
        return issue
        
    except Exception as e:
        logger.error(f"Failed to auto-report issue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to auto-report issue"
        )


@router.get("/", response_model=IssueListResponse)
async def get_issues(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = Query(default=50, le=100),
    status: Optional[List[IssueStatus]] = Query(None),
    category: Optional[List[IssueCategory]] = Query(None),
    priority: Optional[List[IssuePriority]] = Query(None),
    report_type: Optional[List[IssueReportType]] = Query(None),
    assigned_to: Optional[uuid.UUID] = Query(None),
    reported_by: Optional[uuid.UUID] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user)
):
    """
    Get issues with filtering and pagination
    
    Access control:
    - Users can see issues they reported or are assigned to
    - Admins with 'admin.issues.read' permission can see all issues
    """
    # Check if user can view all issues
    user_can_view_all = current_user.has_permission("admin.issues.read")
    
    # Build filter parameters
    filter_params = IssueFilter(
        status=status,
        category=category,
        priority=priority,
        report_type=report_type,
        assigned_to=assigned_to,
        reported_by=reported_by,
        search=search
    )
    
    # Get filtered issues
    issues, total = crud_issue.get_filtered(
        db=db,
        filter_params=filter_params,
        skip=skip,
        limit=limit,
        current_user_id=current_user.id,
        user_can_view_all=user_can_view_all
    )
    
    # Calculate pagination
    total_pages = (total + limit - 1) // limit
    
    # Get summary statistics for current filter
    status_counts = {}
    priority_counts = {}
    category_counts = {}
    
    # These would ideally be computed in the CRUD layer for efficiency
    for issue in issues:
        status_counts[issue.status.value] = status_counts.get(issue.status.value, 0) + 1
        priority_counts[issue.priority.value] = priority_counts.get(issue.priority.value, 0) + 1
        category_counts[issue.category.value] = category_counts.get(issue.category.value, 0) + 1
    
    return IssueListResponse(
        items=issues,
        total=total,
        page=(skip // limit) + 1,
        size=limit,
        total_pages=total_pages,
        status_counts=status_counts,
        priority_counts=priority_counts,
        category_counts=category_counts
    )


@router.get("/{issue_id}", response_model=IssueDetailResponse)
async def get_issue(
    *,
    db: Session = Depends(get_db),
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """Get issue by ID with full details"""
    issue = crud_issue.get_with_details(db, issue_id)
    
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )
    
    # Check access permissions
    user_can_view_all = current_user.has_permission("admin.issues.read")
    
    if not user_can_view_all:
        # Users can only see issues they reported or are assigned to
        if issue.reported_by != current_user.id and issue.assigned_to != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view this issue"
            )
    
    return issue


@router.patch("/{issue_id}", response_model=IssueResponse)
async def update_issue(
    *,
    db: Session = Depends(get_db),
    issue_id: uuid.UUID,
    issue_in: IssueUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update issue (admin only or assigned user)"""
    issue = crud_issue.get(db, issue_id)
    
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )
    
    # Check permissions
    user_can_manage = current_user.has_permission("admin.issues.write")
    is_assigned = issue.assigned_to == current_user.id
    
    if not user_can_manage and not is_assigned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this issue"
        )
    
    # Update issue
    issue = crud_issue.update(db=db, db_obj=issue, obj_in=issue_in)
    
    logger.info(f"Issue updated: {issue_id} by user {current_user.id}")
    
    return issue


@router.patch("/{issue_id}/assign")
async def assign_issue(
    *,
    db: Session = Depends(get_db),
    issue_id: uuid.UUID,
    assignment: IssueAssignment,
    current_user: User = Depends(get_current_user)
):
    """Assign issue to a user (admin only)"""
    if not current_user.has_permission("admin.issues.write"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to assign issues"
        )
    
    issue = crud_issue.assign_issue(
        db=db,
        issue_id=issue_id,
        assigned_to=assignment.assigned_to,
        assigned_by=current_user.id
    )
    
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )
    
    logger.info(f"Issue assigned: {issue_id} to user {assignment.assigned_to} by {current_user.id}")
    
    return {"message": "Issue assigned successfully"}


@router.patch("/{issue_id}/status")
async def update_issue_status(
    *,
    db: Session = Depends(get_db),
    issue_id: uuid.UUID,
    status_update: IssueStatusUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update issue status"""
    issue = crud_issue.get(db, issue_id)
    
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )
    
    # Check permissions
    user_can_manage = current_user.has_permission("admin.issues.write")
    is_assigned = issue.assigned_to == current_user.id
    
    if not user_can_manage and not is_assigned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this issue status"
        )
    
    # Update status
    issue = crud_issue.update_status(
        db=db,
        issue_id=issue_id,
        new_status=status_update.new_status,
        updated_by=current_user.id,
        resolution_notes=status_update.resolution_notes
    )
    
    logger.info(f"Issue status updated: {issue_id} to {status_update.new_status.value} by {current_user.id}")
    
    return {"message": "Issue status updated successfully"}


@router.post("/{issue_id}/comments", response_model=IssueCommentResponse)
async def create_comment(
    *,
    db: Session = Depends(get_db),
    issue_id: uuid.UUID,
    comment_in: IssueCommentCreate,
    current_user: User = Depends(get_current_user)
):
    """Add comment to issue"""
    # Verify issue exists and user has access
    issue = crud_issue.get(db, issue_id)
    
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )
    
    # Check access
    user_can_view_all = current_user.has_permission("admin.issues.read")
    
    if not user_can_view_all:
        if issue.reported_by != current_user.id and issue.assigned_to != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to comment on this issue"
            )
    
    # Set issue_id in comment
    comment_in.issue_id = issue_id
    
    # Create comment
    comment = crud_issue_comment.create_with_user(
        db=db,
        obj_in=comment_in,
        created_by=current_user.id
    )
    
    logger.info(f"Comment added to issue {issue_id} by user {current_user.id}")
    
    return comment


@router.get("/{issue_id}/comments", response_model=List[IssueCommentResponse])
async def get_issue_comments(
    *,
    db: Session = Depends(get_db),
    issue_id: uuid.UUID,
    include_internal: bool = Query(False),
    current_user: User = Depends(get_current_user)
):
    """Get comments for an issue"""
    # Verify issue exists and user has access
    issue = crud_issue.get(db, issue_id)
    
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )
    
    # Check access
    user_can_view_all = current_user.has_permission("admin.issues.read")
    
    if not user_can_view_all:
        if issue.reported_by != current_user.id and issue.assigned_to != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view comments for this issue"
            )
        include_internal = False  # Regular users can't see internal comments
    
    # Get comments
    comments = crud_issue_comment.get_by_issue(
        db=db,
        issue_id=issue_id,
        include_internal=include_internal
    )
    
    return comments


@router.get("/{issue_id}/files/{file_type}")
async def get_issue_file(
    *,
    db: Session = Depends(get_db),
    issue_id: uuid.UUID,
    file_type: str,  # screenshot, console_logs, additional
    current_user: User = Depends(get_current_user)
):
    """Download issue attachment"""
    issue = crud_issue.get(db, issue_id)
    
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )
    
    # Check access
    user_can_view_all = current_user.has_permission("admin.issues.read")
    
    if not user_can_view_all:
        if issue.reported_by != current_user.id and issue.assigned_to != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access files for this issue"
            )
    
    # Get file path based on type
    file_path = None
    if file_type == "screenshot" and issue.screenshot_path:
        file_path = issue.screenshot_path
    elif file_type == "console_logs" and issue.console_logs_path:
        file_path = issue.console_logs_path
    
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File type '{file_type}' not found for this issue"
        )
    
    try:
        # Get file content
        content, mime_type = file_manager.get_file_content(file_path)
        
        # Return file
        return StreamingResponse(
            io.BytesIO(content),
            media_type=mime_type,
            headers={"Content-Disposition": f"inline; filename={Path(file_path).name}"}
        )
        
    except Exception as e:
        logger.error(f"Failed to serve file {file_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve file"
        )


@router.get("/stats/overview", response_model=IssueStatsResponse)
async def get_issue_statistics(
    *,
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user)
):
    """Get issue statistics (admin only)"""
    if not current_user.has_permission("admin.issues.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to view issue statistics"
        )
    
    stats = crud_issue.get_statistics(db, days=days)
    
    return IssueStatsResponse(**stats)


@router.get("/my-issues", response_model=IssueListResponse)
async def get_my_issues(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = Query(default=50, le=100),
    include_assigned: bool = Query(True),
    current_user: User = Depends(get_current_user)
):
    """Get issues for current user (reported or assigned)"""
    issues, total = crud_issue.get_user_issues(
        db=db,
        user_id=current_user.id,
        include_assigned=include_assigned,
        skip=skip,
        limit=limit
    )
    
    total_pages = (total + limit - 1) // limit
    
    return IssueListResponse(
        items=issues,
        total=total,
        page=(skip // limit) + 1,
        size=limit,
        total_pages=total_pages
    )


@router.delete("/{issue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_issue(
    *,
    db: Session = Depends(get_db),
    issue_id: uuid.UUID,
    current_user: User = Depends(get_current_user)
):
    """Delete issue (admin only)"""
    if not current_user.has_permission("admin.issues.delete"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete issues"
        )
    
    issue = crud_issue.get(db, issue_id)
    
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )
    
    # Delete associated files
    file_manager.delete_issue_files(issue.id, issue.created_at)
    
    # Delete issue from database
    crud_issue.remove(db=db, id=issue_id)
    
    logger.info(f"Issue deleted: {issue_id} by user {current_user.id}")
    
    return None
