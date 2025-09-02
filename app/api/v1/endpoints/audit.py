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
from app.models.user import User, UserAuditLog, ApiRequestLog
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
    log_type: Optional[str] = Query(None, description="Filter by log type: 'transaction' for user actions, 'api' for request logs"),
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
    Supports log_type parameter to filter between transaction logs and API request logs
    Requires audit.read permission
    """
    # Validate log_type parameter
    if log_type and log_type not in ['transaction', 'api']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="log_type must be either 'transaction' or 'api'"
        )
    
    # Route to appropriate table and build query
    if log_type == 'api':
        # API Request Logs
        query = db.query(ApiRequestLog)
        
        # Apply API-specific filters
        if action_type:  # For API logs, this could be HTTP method
            query = query.filter_by(method=action_type.upper())
        
        if user_id:
            try:
                query = query.filter_by(user_id=uuid.UUID(user_id))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid user ID format"
                )
        
        if start_date:
            query = query.filter(ApiRequestLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(ApiRequestLog.created_at <= end_date)
        
        # Apply ordering and pagination
        query = query.order_by(ApiRequestLog.created_at.desc())
        total = query.count()
        offset = (page - 1) * per_page
        logs = query.offset(offset).limit(per_page).all()
        
        # Convert API logs to dict format
        log_data = []
        for log in logs:
            log_dict = {
                "id": str(log.id),
                "request_id": log.request_id,
                "method": log.method,
                "endpoint": log.endpoint,
                "query_params": log.query_params,
                "user_id": str(log.user_id) if log.user_id else None,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "status_code": log.status_code,
                "response_size_bytes": log.response_size_bytes,
                "duration_ms": log.duration_ms,
                "location_id": str(log.location_id) if log.location_id else None,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat() if log.created_at else None,
                "success": log.status_code < 400  # Derive success from status code
            }
            log_data.append(log_dict)
        
        resource_logged = "API_REQUEST_LOGS"
        
    else:
        # Transaction Audit Logs (default)
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
        
        # Convert audit logs to dict format
        audit_service = MadagascarAuditService(db)
        log_data = [audit_service._audit_log_to_dict(log) for log in logs]
        resource_logged = "AUDIT_LOGS"
    
    # Log the access
    audit_service = MadagascarAuditService(db)
    user_context = create_user_context(current_user, request)
    audit_service.log_view_access(
        resource_type=resource_logged,
        resource_id="all",
        user_context=user_context,
        screen_reference="AuditLogsPage",
        endpoint=str(request.url.path),
        method=request.method
    )
    
    return {
        "logs": log_data,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
        "filters_applied": {
            "log_type": log_type,
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


@router.get("/statistics/comprehensive", summary="Get Comprehensive System Statistics")
async def get_comprehensive_statistics(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="Days to analyze"),
    current_user: User = Depends(require_permission("audit.read")),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive system statistics for both transaction logs and API request logs
    Optimized database queries for dashboard and analytics use
    """
    from sqlalchemy import func, and_, desc, case
    
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    end_date = datetime.now(timezone.utc)
    
    # === TRANSACTION LOG STATISTICS ===
    
    # Basic transaction statistics
    transaction_query = db.query(UserAuditLog).filter(
        UserAuditLog.created_at >= start_date,
        UserAuditLog.created_at <= end_date
    )
    
    total_transactions = transaction_query.count()
    successful_transactions = transaction_query.filter(UserAuditLog.success == True).count()
    failed_transactions = total_transactions - successful_transactions
    
    # Unique users count
    unique_users = db.query(func.count(func.distinct(UserAuditLog.user_id))).filter(
        UserAuditLog.created_at >= start_date,
        UserAuditLog.created_at <= end_date,
        UserAuditLog.user_id.isnot(None)
    ).scalar() or 0
    
    # Security events count
    security_events = transaction_query.filter(
        UserAuditLog.action.like('%SECURITY%') | 
        UserAuditLog.action.like('%LOGIN_FAILED%') |
        (UserAuditLog.resource == 'SYSTEM_SECURITY') |
        (UserAuditLog.success == False)
    ).count()
    
    # Top actions
    top_actions = db.query(
        UserAuditLog.action,
        func.count(UserAuditLog.id).label('count')
    ).filter(
        UserAuditLog.created_at >= start_date,
        UserAuditLog.created_at <= end_date
    ).group_by(UserAuditLog.action).order_by(
        desc('count')
    ).limit(10).all()
    
    # Daily activity for last 7 days
    daily_activity = db.query(
        func.date(UserAuditLog.created_at).label('activity_date'),
        func.count(UserAuditLog.id).label('count')
    ).filter(
        UserAuditLog.created_at >= start_date,
        UserAuditLog.created_at <= end_date
    ).group_by(
        func.date(UserAuditLog.created_at)
    ).order_by('activity_date').all()
    
    # === API REQUEST LOG STATISTICS ===
    
    # Basic API statistics
    api_query = db.query(ApiRequestLog).filter(
        ApiRequestLog.created_at >= start_date,
        ApiRequestLog.created_at <= end_date
    )
    
    total_requests = api_query.count()
    successful_requests = api_query.filter(ApiRequestLog.status_code < 400).count()
    error_requests = total_requests - successful_requests
    
    # Response time statistics
    timing_stats = db.query(
        func.avg(ApiRequestLog.duration_ms).label('avg_duration'),
        func.min(ApiRequestLog.duration_ms).label('min_duration'),
        func.max(ApiRequestLog.duration_ms).label('max_duration'),
        func.percentile_cont(0.95).within_group(ApiRequestLog.duration_ms).label('p95_duration')
    ).filter(
        ApiRequestLog.created_at >= start_date,
        ApiRequestLog.created_at <= end_date
    ).first()
    
    # Top endpoints by request count
    top_endpoints = db.query(
        ApiRequestLog.endpoint,
        func.count(ApiRequestLog.id).label('request_count'),
        func.avg(ApiRequestLog.duration_ms).label('avg_duration')
    ).filter(
        ApiRequestLog.created_at >= start_date,
        ApiRequestLog.created_at <= end_date
    ).group_by(
        ApiRequestLog.endpoint
    ).order_by(
        desc('request_count')
    ).limit(10).all()
    
    # Status code distribution
    status_distribution = db.query(
        func.floor(ApiRequestLog.status_code / 100).label('status_category'),
        func.count(ApiRequestLog.id).label('count')
    ).filter(
        ApiRequestLog.created_at >= start_date,
        ApiRequestLog.created_at <= end_date
    ).group_by(
        func.floor(ApiRequestLog.status_code / 100)
    ).order_by('status_category').all()
    
    # Daily API requests
    daily_api_requests = db.query(
        func.date(ApiRequestLog.created_at).label('request_date'),
        func.count(ApiRequestLog.id).label('count')
    ).filter(
        ApiRequestLog.created_at >= start_date,
        ApiRequestLog.created_at <= end_date
    ).group_by(
        func.date(ApiRequestLog.created_at)
    ).order_by('request_date').all()
    
    # Log statistics access
    audit_service = MadagascarAuditService(db)
    user_context = create_user_context(current_user, request)
    audit_service.log_view_access(
        resource_type="COMPREHENSIVE_STATISTICS",
        resource_id="system",
        user_context=user_context,
        screen_reference="ComprehensiveStatisticsPage",
        endpoint=str(request.url.path),
        method=request.method
    )
    
    return {
        "time_period": {
            "days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat()
        },
        "transaction_logs": {
            "summary": {
                "total_actions": total_transactions,
                "successful_actions": successful_transactions,
                "failed_actions": failed_transactions,
                "success_rate": (successful_transactions / total_transactions * 100) if total_transactions > 0 else 0,
                "unique_users": unique_users,
                "security_events": security_events
            },
            "top_actions": [
                {"action": action, "count": count}
                for action, count in top_actions
            ],
            "daily_activity": [
                {"date": activity_date.isoformat(), "count": count}
                for activity_date, count in daily_activity
            ]
        },
        "api_requests": {
            "summary": {
                "total_requests": total_requests,
                "successful_requests": successful_requests,
                "error_requests": error_requests,
                "success_rate": (successful_requests / total_requests * 100) if total_requests > 0 else 0,
                "avg_response_time_ms": round(timing_stats.avg_duration or 0, 2),
                "min_response_time_ms": timing_stats.min_duration or 0,
                "max_response_time_ms": timing_stats.max_duration or 0,
                "p95_response_time_ms": round(timing_stats.p95_duration or 0, 2)
            },
            "top_endpoints": [
                {
                    "endpoint": endpoint,
                    "request_count": request_count,
                    "avg_duration_ms": round(avg_duration or 0, 2)
                }
                for endpoint, request_count, avg_duration in top_endpoints
            ],
            "status_distribution": [
                {
                    "status_category": f"{int(status_category)}xx",
                    "count": count
                }
                for status_category, count in status_distribution
            ],
            "daily_requests": [
                {"date": request_date.isoformat(), "count": count}
                for request_date, count in daily_api_requests
            ]
        },
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/statistics", summary="Get Audit Statistics (Legacy)")
async def get_audit_statistics(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="Days to analyze"),
    current_user: User = Depends(require_permission("audit.read")),
    db: Session = Depends(get_db)
):
    """
    Get audit log statistics and metrics (Legacy endpoint for backward compatibility)
    Consider using /statistics/comprehensive for more detailed analytics
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


# API Request Log Endpoints (Middleware Logs)

@router.get("/api-requests", summary="List API Request Logs")
async def list_api_request_logs(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=200, description="Items per page"),
    method: Optional[str] = Query(None, description="Filter by HTTP method"),
    endpoint: Optional[str] = Query(None, description="Filter by endpoint (contains)"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    status_code: Optional[int] = Query(None, description="Filter by status code"),
    min_duration: Optional[int] = Query(None, description="Minimum duration in ms"),
    max_duration: Optional[int] = Query(None, description="Maximum duration in ms"),
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    current_user: User = Depends(require_permission("audit.read")),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of API request logs from middleware
    Useful for system monitoring, performance analysis, and usage analytics
    """
    # Build query filters
    query = db.query(ApiRequestLog)
    
    if method:
        query = query.filter_by(method=method.upper())
    
    if endpoint:
        query = query.filter(ApiRequestLog.endpoint.contains(endpoint))
    
    if user_id:
        try:
            query = query.filter_by(user_id=uuid.UUID(user_id))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format"
            )
    
    if status_code:
        query = query.filter_by(status_code=status_code)
    
    if min_duration:
        query = query.filter(ApiRequestLog.duration_ms >= min_duration)
    
    if max_duration:
        query = query.filter(ApiRequestLog.duration_ms <= max_duration)
    
    if start_date:
        query = query.filter(ApiRequestLog.created_at >= start_date)
    
    if end_date:
        query = query.filter(ApiRequestLog.created_at <= end_date)
    
    # Apply ordering and pagination
    query = query.order_by(ApiRequestLog.created_at.desc())
    total = query.count()
    offset = (page - 1) * per_page
    logs = query.offset(offset).limit(per_page).all()
    
    # Convert logs to dict format
    log_data = []
    for log in logs:
        log_dict = {
            "id": str(log.id),
            "request_id": log.request_id,
            "method": log.method,
            "endpoint": log.endpoint,
            "query_params": log.query_params,
            "user_id": str(log.user_id) if log.user_id else None,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "status_code": log.status_code,
            "response_size_bytes": log.response_size_bytes,
            "duration_ms": log.duration_ms,
            "location_id": str(log.location_id) if log.location_id else None,
            "error_message": log.error_message,
            "created_at": log.created_at.isoformat() if log.created_at else None
        }
        log_data.append(log_dict)
    
    # Log this audit access
    audit_service = MadagascarAuditService(db)
    user_context = create_user_context(current_user, request)
    audit_service.log_view_access(
        resource_type="API_REQUEST_LOGS",
        resource_id="all",
        user_context=user_context,
        screen_reference="ApiRequestLogsPage",
        endpoint=str(request.url.path),
        method=request.method
    )
    
    return {
        "logs": log_data,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
        "filters_applied": {
            "method": method,
            "endpoint": endpoint,
            "user_id": user_id,
            "status_code": status_code,
            "min_duration": min_duration,
            "max_duration": max_duration,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None
        }
    }


@router.get("/api-requests/analytics", summary="API Request Analytics")
async def get_api_request_analytics(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Analysis period in hours"),
    current_user: User = Depends(require_permission("audit.read")),
    db: Session = Depends(get_db)
):
    """
    Get API request analytics and performance metrics
    Useful for system monitoring and capacity planning
    """
    from sqlalchemy import func, desc
    
    # Calculate time range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)
    
    # Base query for the time period
    base_query = db.query(ApiRequestLog).filter(
        ApiRequestLog.created_at >= start_time,
        ApiRequestLog.created_at <= end_time
    )
    
    # Total requests
    total_requests = base_query.count()
    
    # Success rate
    successful_requests = base_query.filter(
        ApiRequestLog.status_code < 400
    ).count()
    success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
    
    # Average response time
    avg_duration = db.query(func.avg(ApiRequestLog.duration_ms)).filter(
        ApiRequestLog.created_at >= start_time,
        ApiRequestLog.created_at <= end_time
    ).scalar() or 0
    
    # Top endpoints by request count
    top_endpoints = db.query(
        ApiRequestLog.endpoint,
        func.count(ApiRequestLog.id).label('request_count'),
        func.avg(ApiRequestLog.duration_ms).label('avg_duration')
    ).filter(
        ApiRequestLog.created_at >= start_time,
        ApiRequestLog.created_at <= end_time
    ).group_by(
        ApiRequestLog.endpoint
    ).order_by(
        desc('request_count')
    ).limit(10).all()
    
    # Status code distribution
    status_distribution = db.query(
        ApiRequestLog.status_code,
        func.count(ApiRequestLog.id).label('count')
    ).filter(
        ApiRequestLog.created_at >= start_time,
        ApiRequestLog.created_at <= end_time
    ).group_by(
        ApiRequestLog.status_code
    ).order_by(
        desc('count')
    ).all()
    
    # Slowest endpoints
    slowest_endpoints = db.query(
        ApiRequestLog.endpoint,
        func.avg(ApiRequestLog.duration_ms).label('avg_duration'),
        func.max(ApiRequestLog.duration_ms).label('max_duration'),
        func.count(ApiRequestLog.id).label('request_count')
    ).filter(
        ApiRequestLog.created_at >= start_time,
        ApiRequestLog.created_at <= end_time
    ).group_by(
        ApiRequestLog.endpoint
    ).order_by(
        desc('avg_duration')
    ).limit(10).all()
    
    # Most active users
    active_users = db.query(
        ApiRequestLog.user_id,
        func.count(ApiRequestLog.id).label('request_count')
    ).filter(
        ApiRequestLog.created_at >= start_time,
        ApiRequestLog.created_at <= end_time,
        ApiRequestLog.user_id.isnot(None)
    ).group_by(
        ApiRequestLog.user_id
    ).order_by(
        desc('request_count')
    ).limit(10).all()
    
    # Error rate by endpoint
    error_endpoints = db.query(
        ApiRequestLog.endpoint,
        func.count(ApiRequestLog.id).label('total_requests'),
        func.count(
            func.case([(ApiRequestLog.status_code >= 400, 1)])
        ).label('error_requests')
    ).filter(
        ApiRequestLog.created_at >= start_time,
        ApiRequestLog.created_at <= end_time
    ).group_by(
        ApiRequestLog.endpoint
    ).having(
        func.count(ApiRequestLog.id) > 5  # Only endpoints with significant traffic
    ).all()
    
    # Calculate error rates
    error_analysis = []
    for endpoint_data in error_endpoints:
        endpoint, total, errors = endpoint_data
        error_rate = (errors / total * 100) if total > 0 else 0
        if error_rate > 0:
            error_analysis.append({
                "endpoint": endpoint,
                "total_requests": total,
                "error_requests": errors,
                "error_rate_percent": round(error_rate, 2)
            })
    
    # Sort by error rate
    error_analysis.sort(key=lambda x: x["error_rate_percent"], reverse=True)
    
    # Log this analytics access
    audit_service = MadagascarAuditService(db)
    user_context = create_user_context(current_user, request)
    audit_service.log_view_access(
        resource_type="API_REQUEST_ANALYTICS",
        resource_id=f"last_{hours}_hours",
        user_context=user_context,
        screen_reference="ApiAnalyticsPage",
        endpoint=str(request.url.path),
        method=request.method
    )
    
    return {
        "period": {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "hours": hours
        },
        "overview": {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "success_rate_percent": round(success_rate, 2),
            "average_response_time_ms": round(avg_duration, 2)
        },
        "top_endpoints": [
            {
                "endpoint": ep.endpoint,
                "request_count": ep.request_count,
                "avg_duration_ms": round(ep.avg_duration, 2)
            }
            for ep in top_endpoints
        ],
        "status_code_distribution": [
            {
                "status_code": status.status_code,
                "count": status.count
            }
            for status in status_distribution
        ],
        "slowest_endpoints": [
            {
                "endpoint": ep.endpoint,
                "avg_duration_ms": round(ep.avg_duration, 2),
                "max_duration_ms": ep.max_duration,
                "request_count": ep.request_count
            }
            for ep in slowest_endpoints
        ],
        "most_active_users": [
            {
                "user_id": str(user.user_id),
                "request_count": user.request_count
            }
            for user in active_users
        ],
        "error_analysis": error_analysis[:10]  # Top 10 endpoints with highest error rates
    } 