"""
Madagascar License System - Comprehensive Audit Service
Tracks all user actions, data changes, and system events for compliance and security
Based on AMPRO audit patterns but adapted for Madagascar license requirements
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone, timedelta
import uuid
import json
from dataclasses import dataclass, asdict
from pathlib import Path
import structlog
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, JSON, Text, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from app.core.database import get_db
from app.models.user import User, UserAuditLog

logger = structlog.get_logger()

@dataclass
class UserContext:
    """User context for audit logging"""
    user_id: Optional[str] = None
    username: Optional[str] = None
    ip_address: str = "unknown"
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    location_id: Optional[str] = None
    
    def dict(self):
        return asdict(self)

@dataclass
class AuditLogData:
    """Data structure for comprehensive audit log entries"""
    action_type: str  # CREATE, READ, UPDATE, DELETE, LOGIN, LOGOUT, EXPORT, PRINT, etc.
    resource_type: str  # USER, PERSON, LOCATION, PERMISSION, etc.
    resource_id: Optional[str] = None
    screen_reference: Optional[str] = None  # Frontend component/page
    validation_codes: Optional[List[str]] = None
    business_rules_applied: Optional[List[str]] = None
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    changed_fields: Optional[List[str]] = None
    files_created: Optional[List[str]] = None
    files_modified: Optional[List[str]] = None
    files_deleted: Optional[List[str]] = None
    execution_time_ms: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    warning_messages: Optional[List[str]] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    ip_address: str = "unknown"
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    location_id: Optional[str] = None
    session_id: Optional[str] = None  # Added to fix TypeError
    
    def dict(self):
        return asdict(self)

class MadagascarAuditService:
    """
    Comprehensive audit service for Madagascar License System
    Provides complete transaction logging, fraud detection, and compliance reporting
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def log_action(self, action_data: AuditLogData, transaction_id: Optional[str] = None) -> str:
        """
        Log any system action with comprehensive tracking
        Returns: transaction_id for correlation
        """
        if transaction_id is None:
            transaction_id = str(uuid.uuid4())
        
        try:
            # Create enhanced audit log entry
            audit_log = UserAuditLog(
                user_id=uuid.UUID(action_data.user_id) if action_data.user_id else None,
                action=action_data.action_type,
                resource=action_data.resource_type,
                resource_id=action_data.resource_id,
                ip_address=action_data.ip_address,
                user_agent=action_data.user_agent,
                endpoint=action_data.endpoint,
                method=action_data.method,
                success=action_data.success,
                error_message=action_data.error_message,
                details=json.dumps({
                    "transaction_id": transaction_id,
                    "screen_reference": action_data.screen_reference,
                    "validation_codes": action_data.validation_codes,
                    "business_rules_applied": action_data.business_rules_applied,
                    "old_values": action_data.old_values,
                    "new_values": action_data.new_values,
                    "changed_fields": action_data.changed_fields,
                    "files_created": action_data.files_created,
                    "files_modified": action_data.files_modified,
                    "files_deleted": action_data.files_deleted,
                    "execution_time_ms": action_data.execution_time_ms,
                    "warning_messages": action_data.warning_messages,
                    "session_id": action_data.session_id
                }, default=str),
                location_id=uuid.UUID(action_data.location_id) if action_data.location_id else None
            )
            
            self.db.add(audit_log)
            self.db.commit()
            
            logger.info(
                "Audit log created",
                transaction_id=transaction_id,
                action=f"{action_data.action_type}:{action_data.resource_type}",
                user=action_data.username,
                success=action_data.success
            )
            
            return transaction_id
            
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            # In production, consider fallback to file logging
            return transaction_id
    
    def log_data_change(self, resource_type: str, resource_id: str, 
                       old_data: Dict[str, Any], new_data: Dict[str, Any], 
                       user_context: UserContext, screen_reference: Optional[str] = None,
                       validation_codes: Optional[List[str]] = None,
                       endpoint: Optional[str] = None, method: Optional[str] = None) -> str:
        """
        Log data changes with old/new value tracking
        Critical for compliance and fraud detection
        """
        changed_fields = self._identify_changed_fields(old_data, new_data)
        
        # Only store values for fields that actually changed
        filtered_old_values = {}
        filtered_new_values = {}
        
        for field in changed_fields:
            if not field.startswith("removed_"):
                if field in old_data:
                    filtered_old_values[field] = old_data[field]
                if field in new_data:
                    filtered_new_values[field] = new_data[field]
            else:
                # For removed fields, keep the old value
                original_field = field.replace("removed_", "")
                if original_field in old_data:
                    filtered_old_values[original_field] = old_data[original_field]
        
        audit_data = AuditLogData(
            action_type="UPDATE",
            resource_type=resource_type,
            resource_id=resource_id,
            screen_reference=screen_reference,
            validation_codes=validation_codes,
            old_values=filtered_old_values,
            new_values=filtered_new_values,
            changed_fields=changed_fields,
            endpoint=endpoint,
            method=method,
            **user_context.dict()
        )
        
        return self.log_action(audit_data)
    
    def log_creation(self, resource_type: str, resource_id: str, 
                    resource_data: Dict[str, Any], user_context: UserContext,
                    screen_reference: Optional[str] = None,
                    validation_codes: Optional[List[str]] = None,
                    endpoint: Optional[str] = None, method: Optional[str] = None) -> str:
        """Log resource creation"""
        audit_data = AuditLogData(
            action_type="CREATE",
            resource_type=resource_type,
            resource_id=resource_id,
            screen_reference=screen_reference,
            validation_codes=validation_codes,
            new_values=resource_data,
            endpoint=endpoint,
            method=method,
            **user_context.dict()
        )
        
        return self.log_action(audit_data)
    
    def log_deletion(self, resource_type: str, resource_id: str, 
                    resource_data: Dict[str, Any], user_context: UserContext,
                    screen_reference: Optional[str] = None,
                    endpoint: Optional[str] = None, method: Optional[str] = None) -> str:
        """Log resource deletion (soft delete)"""
        audit_data = AuditLogData(
            action_type="DELETE",
            resource_type=resource_type,
            resource_id=resource_id,
            screen_reference=screen_reference,
            old_values=resource_data,
            endpoint=endpoint,
            method=method,
            **user_context.dict()
        )
        
        return self.log_action(audit_data)
    
    def log_view_access(self, resource_type: str, resource_id: str, 
                       user_context: UserContext, screen_reference: Optional[str] = None,
                       endpoint: Optional[str] = None, method: Optional[str] = None) -> str:
        """Log when users view sensitive data"""
        audit_data = AuditLogData(
            action_type="READ",
            resource_type=resource_type,
            resource_id=resource_id,
            screen_reference=screen_reference,
            endpoint=endpoint,
            method=method,
            **user_context.dict()
        )
        
        return self.log_action(audit_data)
    
    def log_authentication(self, username: str, success: bool, ip_address: str,
                          user_agent: Optional[str] = None, error_message: Optional[str] = None,
                          location_id: Optional[str] = None) -> str:
        """Log authentication attempts"""
        audit_data = AuditLogData(
            action_type="LOGIN" if success else "LOGIN_FAILED",
            resource_type="AUTHENTICATION",
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message,
            location_id=location_id,
            endpoint="/api/v1/auth/login",
            method="POST"
        )
        
        return self.log_action(audit_data)
    
    def log_export_action(self, export_type: str, filters: Dict[str, Any],
                         record_count: int, user_context: UserContext,
                         screen_reference: Optional[str] = None) -> str:
        """Log data export actions for compliance"""
        audit_data = AuditLogData(
            action_type="EXPORT",
            resource_type=export_type.upper(),
            screen_reference=screen_reference,
            new_values={
                "export_type": export_type,
                "filters_applied": filters,
                "records_exported": record_count,
                "export_timestamp": datetime.now(timezone.utc).isoformat()
            },
            **user_context.dict()
        )
        
        return self.log_action(audit_data)
    
    def log_permission_change(self, target_user_id: str, permission_changes: Dict[str, Any],
                             user_context: UserContext, screen_reference: Optional[str] = None) -> str:
        """Log permission and role changes"""
        audit_data = AuditLogData(
            action_type="PERMISSION_CHANGE",
            resource_type="USER_PERMISSIONS",
            resource_id=target_user_id,
            screen_reference=screen_reference,
            new_values=permission_changes,
            **user_context.dict()
        )
        
        return self.log_action(audit_data)
    
    def log_security_event(self, event_type: str, description: str, 
                          user_context: UserContext, severity: str = "HIGH") -> str:
        """Log security-related events"""
        audit_data = AuditLogData(
            action_type="SECURITY_EVENT",
            resource_type="SYSTEM_SECURITY",
            new_values={
                "event_type": event_type,
                "description": description,
                "severity": severity,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            **user_context.dict()
        )
        
        return self.log_action(audit_data)
    
    def _identify_changed_fields(self, old_data: Dict[str, Any], 
                               new_data: Dict[str, Any]) -> List[str]:
        """Identify which fields changed between old and new data"""
        changed_fields = []
        
        # Check for modified fields
        for key, new_value in new_data.items():
            old_value = old_data.get(key)
            if old_value != new_value:
                changed_fields.append(key)
        
        # Check for removed fields
        for key in old_data.keys():
            if key not in new_data:
                changed_fields.append(f"removed_{key}")
        
        return changed_fields
    
    def get_user_activity(self, user_id: str, start_date: datetime, 
                         end_date: datetime, page: int = 1, per_page: int = 50) -> Dict[str, Any]:
        """Get user activity logs for audit review"""
        query = self.db.query(UserAuditLog).filter(
            UserAuditLog.user_id == uuid.UUID(user_id),
            UserAuditLog.created_at >= start_date,
            UserAuditLog.created_at <= end_date
        ).order_by(UserAuditLog.created_at.desc())
        
        total = query.count()
        offset = (page - 1) * per_page
        logs = query.offset(offset).limit(per_page).all()
        
        return {
            "logs": [self._audit_log_to_dict(log) for log in logs],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page
        }
    
    def get_resource_history(self, resource_type: str, resource_id: str) -> List[Dict[str, Any]]:
        """Get complete history for a specific resource"""
        logs = self.db.query(UserAuditLog).filter(
            UserAuditLog.resource == resource_type,
            UserAuditLog.resource_id == resource_id
        ).order_by(UserAuditLog.created_at.desc()).all()
        
        return [self._audit_log_to_dict(log) for log in logs]
    
    def detect_suspicious_activity(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Basic fraud detection - identify suspicious patterns"""
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        # Multiple failed login attempts
        failed_logins = self.db.query(UserAuditLog).filter(
            UserAuditLog.action == "LOGIN_FAILED",
            UserAuditLog.created_at >= start_time
        ).all()
        
        suspicious_events = []
        
        # Group by IP and user for analysis
        ip_failures = {}
        user_failures = {}
        
        for log in failed_logins:
            ip = log.ip_address or "unknown"
            if ip not in ip_failures:
                ip_failures[ip] = 0
            ip_failures[ip] += 1
            
            if log.user_id:
                user_id = str(log.user_id)
                if user_id not in user_failures:
                    user_failures[user_id] = 0
                user_failures[user_id] += 1
        
        # Flag IPs with many failures
        for ip, count in ip_failures.items():
            if count >= 5:
                suspicious_events.append({
                    "type": "multiple_failed_logins_ip",
                    "ip_address": ip,
                    "attempt_count": count,
                    "severity": "HIGH" if count >= 10 else "MEDIUM"
                })
        
        # Flag users with many failures
        for user_id, count in user_failures.items():
            if count >= 3:
                suspicious_events.append({
                    "type": "multiple_failed_logins_user",
                    "user_id": user_id,
                    "attempt_count": count,
                    "severity": "HIGH" if count >= 5 else "MEDIUM"
                })
        
        return suspicious_events
    
    def _audit_log_to_dict(self, audit_log: UserAuditLog) -> Dict[str, Any]:
        """Convert audit log model to dictionary"""
        details = {}
        if audit_log.details:
            try:
                details = json.loads(audit_log.details)
            except json.JSONDecodeError:
                details = {"raw_details": audit_log.details}
        
        return {
            "id": str(audit_log.id),
            "timestamp": audit_log.created_at.isoformat(),
            "action": audit_log.action,
            "resource": audit_log.resource,
            "resource_id": audit_log.resource_id,
            "user_id": str(audit_log.user_id) if audit_log.user_id else None,
            "ip_address": audit_log.ip_address,
            "user_agent": audit_log.user_agent,
            "endpoint": audit_log.endpoint,
            "method": audit_log.method,
            "success": audit_log.success,
            "error_message": audit_log.error_message,
            "location_id": str(audit_log.location_id) if audit_log.location_id else None,
            **details
        }

# Helper function to create user context from request
def create_user_context(user: User, request, session_id: Optional[str] = None) -> UserContext:
    """Create user context from current user and request"""
    return UserContext(
        user_id=str(user.id) if user else None,
        username=user.username if user else None,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent"),
        session_id=session_id,
        location_id=str(user.primary_location_id) if user and user.primary_location_id else None
    )

# Dependency to get audit service
def get_audit_service(db: Session = None) -> MadagascarAuditService:
    """Get audit service instance"""
    if db is None:
        db = next(get_db())
    return MadagascarAuditService(db) 