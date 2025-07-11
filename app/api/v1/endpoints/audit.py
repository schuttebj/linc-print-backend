"""
Audit Log Endpoints for Madagascar License System
Provides access to comprehensive audit logs and security monitoring
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User, UserAuditLog
from app.services.audit_service import MadagascarAuditService, create_user_context

router = APIRouter()


def check_permission(user: User, permission: str) -> bool:
    """Check if user has specific permission"""
    if user.is_superuser:
        return True
    return user.has_permission(permission)


def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(current_user: User = Depends(get_current_user)):
        if not check_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}"
            )
        return current_user
    return decorator

@router.get("/", summary="List Audit Logs")
async def list_audit_logs(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    success_only: Optional[bool] = Query(None, description="Filter by success status"),
    current_user: User = Depends(require_permission("audit.read")),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of audit logs with filtering
    Requires audit.read permission
    """
    # Build query filters
    query = db.query(UserAuditLog)
    
    if action_type:
        query = query.filter_by(action=action_type)
    
    if resource_type:
        query = query.filter_by(resource=resource_type)
    
    if user_id:
        try:
            query = query.filter_by(user_id=uuid.UUID(user_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format"
            )
    
    if start_date:
        query = query.filter(UserAuditLog.created_at >= start_date)
    
    if end_date:
        query = query.filter(UserAuditLog.created_at <= end_date)
    
    if success_only is not None:
        query = query.filter_by(success=success_only)
    
    # Apply ordering and pagination
    query = query.order_by(UserAuditLog.created_at.desc())
    total = query.count()
    offset = (page - 1) * per_page
    logs = query.offset(offset).limit(per_page).all()
    
    # Log the audit access
    audit_service = MadagascarAuditService(db)
    user_context = create_user_context(current_user, request)
    audit_service.log_view_access(
        resource_type="AUDIT_LOGS",
        resource_id="all",
        user_context=user_context,
        screen_reference="AuditLogsPage",
        endpoint=str(request.url.path),
        method=request.method
    )
    
    return {
        "logs": [audit_service._audit_log_to_dict(log) for log in logs],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
        "filters_applied": {
            "action_type": action_type,
            "resource_type": resource_type,
            "user_id": user_id,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "success_only": success_only
        }
    }


@router.get("/user/{user_id}", summary="Get User Activity Logs")
async def get_user_activity(
    user_id: str,
    request: Request,
    start_date: Optional[datetime] = Query(None, description="Start date"),
    end_date: Optional[datetime] = Query(None, description="End date"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_permission("audit.read")),
    db: Session = Depends(get_db)
):
    """
    Get activity logs for a specific user
    """
    # Validate user ID format
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    # Check if target user exists
    target_user = db.query(User).filter(User.id == user_uuid).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Set default date range if not provided
    if not end_date:
        end_date = datetime.now(timezone.utc)
    if not start_date:
        start_date = end_date - timedelta(days=30)
    
    audit_service = MadagascarAuditService(db)
    result = audit_service.get_user_activity(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        page=page,
        per_page=per_page
    )
    
    # Log the access
    user_context = create_user_context(current_user, request)
    audit_service.log_view_access(
        resource_type="USER_AUDIT_LOGS",
        resource_id=user_id,
        user_context=user_context,
        screen_reference="UserAuditPage",
        endpoint=str(request.url.path),
        method=request.method
    )
    
    return result


@router.get("/resource/{resource_type}/{resource_id}", summary="Get Resource History")
async def get_resource_history(
    resource_type: str,
    resource_id: str,
    request: Request,
    current_user: User = Depends(require_permission("audit.read")),
    db: Session = Depends(get_db)
):
    """
    Get complete audit history for a specific resource
    """
    audit_service = MadagascarAuditService(db)
    history = audit_service.get_resource_history(
        resource_type=resource_type.upper(),
        resource_id=resource_id
    )
    
    # Log the access
    user_context = create_user_context(current_user, request)
    audit_service.log_view_access(
        resource_type="RESOURCE_AUDIT_HISTORY",
        resource_id=f"{resource_type}:{resource_id}",
        user_context=user_context,
        screen_reference="ResourceHistoryPage",
        endpoint=str(request.url.path),
        method=request.method
    )
    
    return {
        "resource_type": resource_type,
        "resource_id": resource_id,
        "history": history,
        "total_entries": len(history)
    }


@router.get("/security/suspicious-activity", summary="Get Suspicious Activity")
async def get_suspicious_activity(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    current_user: User = Depends(require_permission("audit.security")),
    db: Session = Depends(get_db)
):
    """
    Get detected suspicious activities
    Requires audit.security permission
    """
    audit_service = MadagascarAuditService(db)
    suspicious_events = audit_service.detect_suspicious_activity(hours=hours)
    
    # Log security monitoring access
    user_context = create_user_context(current_user, request)
    audit_service.log_security_event(
        event_type="SECURITY_MONITORING_ACCESS",
        description=f"User accessed suspicious activity report for last {hours} hours",
        user_context=user_context
    )
    
    return {
        "time_range_hours": hours,
        "suspicious_events": suspicious_events,
        "total_events": len(suspicious_events),
        "scan_timestamp": datetime.now(timezone.utc).isoformat()
    }


@router.get("/statistics", summary="Get Audit Statistics")
async def get_audit_statistics(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="Days to analyze"),
    current_user: User = Depends(require_permission("audit.read")),
    db: Session = Depends(get_db)
):
    """
    Get audit log statistics and metrics
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    from app.models.user import UserAuditLog
    from sqlalchemy import func, and_
    
    # Basic statistics
    total_logs = db.query(UserAuditLog).filter(
        UserAuditLog.created_at >= start_date
    ).count()
    
    successful_actions = db.query(UserAuditLog).filter(
        and_(
            UserAuditLog.created_at >= start_date,
            UserAuditLog.success == True
        )
    ).count()
    
    failed_actions = total_logs - successful_actions
    
    # Action type breakdown
    action_breakdown = db.query(
        UserAuditLog.action,
        func.count(UserAuditLog.id).label('count')
    ).filter(
        UserAuditLog.created_at >= start_date
    ).group_by(UserAuditLog.action).all()
    
    # Resource type breakdown
    resource_breakdown = db.query(
        UserAuditLog.resource,
        func.count(UserAuditLog.id).label('count')
    ).filter(
        UserAuditLog.created_at >= start_date
    ).group_by(UserAuditLog.resource).all()
    
    # Most active users
    user_activity = db.query(
        UserAuditLog.user_id,
        func.count(UserAuditLog.id).label('activity_count')
    ).filter(
        and_(
            UserAuditLog.created_at >= start_date,
            UserAuditLog.user_id.isnot(None)
        )
    ).group_by(UserAuditLog.user_id).order_by(
        func.count(UserAuditLog.id).desc()
    ).limit(10).all()
    
    # Log statistics access
    audit_service = MadagascarAuditService(db)
    user_context = create_user_context(current_user, request)
    audit_service.log_view_access(
        resource_type="AUDIT_STATISTICS",
        resource_id="system",
        user_context=user_context,
        screen_reference="AuditStatisticsPage",
        endpoint=str(request.url.path),
        method=request.method
    )
    
    return {
        "time_period_days": days,
        "summary": {
            "total_audit_logs": total_logs,
            "successful_actions": successful_actions,
            "failed_actions": failed_actions,
            "success_rate": (successful_actions / total_logs * 100) if total_logs > 0 else 0
        },
        "action_breakdown": [
            {"action": action, "count": count}
            for action, count in action_breakdown
        ],
        "resource_breakdown": [
            {"resource": resource or "UNKNOWN", "count": count}
            for resource, count in resource_breakdown
        ],
        "most_active_users": [
            {"user_id": str(user_id), "activity_count": count}
            for user_id, count in user_activity
        ],
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.post("/export", summary="Export Audit Logs")
async def export_audit_logs(
    request: Request,
    export_format: str = Query("csv", pattern="^(csv|json)$", description="Export format"),
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    current_user: User = Depends(require_permission("audit.export")),
    db: Session = Depends(get_db)
):
    """
    Export audit logs with filtering
    Requires audit.export permission
    """
    from app.models.user import UserAuditLog
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    # Build query with filters
    query = db.query(UserAuditLog)
    
    if action_type:
        query = query.filter_by(action=action_type)
    
    if resource_type:
        query = query.filter_by(resource=resource_type)
    
    if user_id:
        try:
            query = query.filter_by(user_id=uuid.UUID(user_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format"
            )
    
    if start_date:
        query = query.filter(UserAuditLog.created_at >= start_date)
    
    if end_date:
        query = query.filter(UserAuditLog.created_at <= end_date)
    
    # Get all matching logs
    logs = query.order_by(UserAuditLog.created_at.desc()).all()
    
    # Log the export action
    audit_service = MadagascarAuditService(db)
    user_context = create_user_context(current_user, request)
    audit_service.log_export_action(
        export_type="AUDIT_LOGS",
        filters={
            "action_type": action_type,
            "resource_type": resource_type,
            "user_id": user_id,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "format": export_format
        },
        record_count=len(logs),
        user_context=user_context,
        screen_reference="AuditExportPage"
    )
    
    if export_format == "csv":
        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            "Timestamp", "Action", "Resource", "Resource ID", "User ID",
            "IP Address", "Success", "Error Message", "Details"
        ])
        
        # Write data
        for log in logs:
            writer.writerow([
                log.created_at.isoformat(),
                log.action,
                log.resource,
                log.resource_id,
                str(log.user_id) if log.user_id else "",
                log.ip_address,
                log.success,
                log.error_message or "",
                log.details or ""
            ])
        
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
        )
    
    else:  # JSON format
        audit_service = MadagascarAuditService(db)
        json_data = {
            "export_metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "exported_by": current_user.username,
                "total_records": len(logs),
                "filters": {
                    "action_type": action_type,
                    "resource_type": resource_type,
                    "user_id": user_id,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                }
            },
            "audit_logs": [audit_service._audit_log_to_dict(log) for log in logs]
        }
        
        import json
        json_str = json.dumps(json_data, indent=2, default=str)
        
        return StreamingResponse(
            io.BytesIO(json_str.encode()),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"}
        ) 