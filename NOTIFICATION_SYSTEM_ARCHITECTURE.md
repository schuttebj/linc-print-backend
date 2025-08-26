# Notification System Architecture - Issue Tracking

## Overview

This document outlines the architecture for implementing a comprehensive notification system for the issue tracking module in the Madagascar License System. The system is designed to be modular, scalable, and easily integrated with the existing infrastructure.

## Current State

The issue tracking system is fully functional with:
- ✅ Issue reporting (manual and automatic)
- ✅ File storage (screenshots, console logs)
- ✅ Kanban dashboard for management
- ✅ Permission-based access control
- ✅ Complete API endpoints

## Notification System Components

### 1. Database Models

#### NotificationTemplate
```sql
CREATE TABLE notification_templates (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(150) NOT NULL,
    description TEXT,
    template_type VARCHAR(50) NOT NULL, -- EMAIL, SMS, IN_APP, WEBHOOK
    subject_template TEXT,
    body_template TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### NotificationPreference
```sql
CREATE TABLE notification_preferences (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    notification_type VARCHAR(50) NOT NULL, -- ISSUE_ASSIGNED, ISSUE_RESOLVED, etc.
    delivery_method VARCHAR(20) NOT NULL, -- EMAIL, SMS, IN_APP
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, notification_type, delivery_method)
);
```

#### NotificationQueue
```sql
CREATE TABLE notification_queue (
    id UUID PRIMARY KEY,
    recipient_id UUID REFERENCES users(id),
    template_name VARCHAR(100) NOT NULL,
    delivery_method VARCHAR(20) NOT NULL,
    subject VARCHAR(255),
    content TEXT NOT NULL,
    context_data JSON,
    status VARCHAR(20) DEFAULT 'PENDING', -- PENDING, SENT, FAILED, CANCELLED
    scheduled_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### NotificationLog
```sql
CREATE TABLE notification_logs (
    id UUID PRIMARY KEY,
    queue_id UUID REFERENCES notification_queue(id),
    user_id UUID REFERENCES users(id),
    notification_type VARCHAR(50) NOT NULL,
    delivery_method VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    sent_at TIMESTAMP,
    error_details TEXT,
    context JSON,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 2. Notification Types for Issues

#### Issue-Related Notifications
- `ISSUE_CREATED` - New issue reported
- `ISSUE_ASSIGNED` - Issue assigned to user
- `ISSUE_STATUS_CHANGED` - Issue status updated
- `ISSUE_RESOLVED` - Issue marked as resolved
- `ISSUE_COMMENT_ADDED` - New comment on issue
- `HIGH_PRIORITY_ISSUE` - Critical/High priority issue reported
- `AUTO_ISSUE_DETECTED` - Automatic error detection
- `ISSUE_OVERDUE` - Issue taking too long to resolve

#### System-Related Notifications
- `DAILY_ISSUE_SUMMARY` - Daily summary for admins
- `WEEKLY_ISSUE_REPORT` - Weekly analytics report
- `SYSTEM_ERROR_SPIKE` - Unusual increase in auto-reported errors

### 3. Backend Services

#### NotificationService (`app/services/notification_service.py`)
```python
class NotificationService:
    def __init__(self):
        self.email_provider = EmailProvider()
        self.sms_provider = SMSProvider()  # Optional
        self.webhook_provider = WebhookProvider()  # Optional
    
    async def send_issue_notification(
        self,
        notification_type: str,
        issue: Issue,
        recipients: List[UUID],
        context: Dict = None
    ) -> bool:
        """Send notification about an issue event"""
        
    async def queue_notification(
        self,
        template_name: str,
        recipient_id: UUID,
        context: Dict,
        delivery_method: str = "EMAIL",
        scheduled_at: datetime = None
    ) -> NotificationQueue:
        """Queue a notification for delivery"""
    
    async def process_notification_queue(self):
        """Process pending notifications in queue"""
        
    def get_user_preferences(self, user_id: UUID) -> List[NotificationPreference]:
        """Get notification preferences for user"""
```

#### EmailProvider (`app/services/providers/email_provider.py`)
```python
class EmailProvider:
    def __init__(self):
        # Configure SMTP or email service (SendGrid, AWS SES, etc.)
        self.smtp_config = get_settings().EMAIL_CONFIG
    
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        template_data: Dict = None
    ) -> bool:
        """Send email notification"""
```

#### NotificationTemplateEngine (`app/services/template_engine.py`)
```python
class NotificationTemplateEngine:
    def render_template(
        self,
        template: NotificationTemplate,
        context: Dict
    ) -> Tuple[str, str]:  # (subject, body)
        """Render notification template with context data"""
```

### 4. API Endpoints

#### Notification Management (`app/api/v1/endpoints/notifications.py`)
```python
# User notification preferences
@router.get("/preferences", response_model=List[NotificationPreferenceResponse])
async def get_notification_preferences(current_user: User = Depends(get_current_user))

@router.put("/preferences", response_model=NotificationPreferenceResponse)
async def update_notification_preferences(...)

# Admin notification management
@router.get("/templates", response_model=List[NotificationTemplateResponse])
async def get_notification_templates(...)  # Admin only

@router.post("/templates", response_model=NotificationTemplateResponse)
async def create_notification_template(...)  # Admin only

@router.get("/queue", response_model=List[NotificationQueueResponse])
async def get_notification_queue(...)  # Admin only

@router.post("/send-test", response_model=Dict)
async def send_test_notification(...)  # Admin only
```

### 5. Frontend Components

#### NotificationSettings Component
```typescript
interface NotificationSettingsProps {
  userId: string;
}

const NotificationSettings: React.FC<NotificationSettingsProps> = ({ userId }) => {
  // Allow users to configure their notification preferences
  // Toggle email/SMS notifications for different issue events
  // Set quiet hours, frequency limits, etc.
};
```

#### InAppNotifications Component
```typescript
interface InAppNotificationsProps {
  // Bell icon with notification count
  // Dropdown with recent notifications
  // Mark as read functionality
}

const InAppNotifications: React.FC<InAppNotificationsProps> = () => {
  // Real-time notifications using WebSocket or SSE
  // Notification history
  // Action buttons (view issue, mark as read)
};
```

### 6. Integration Points

#### Issue Event Triggers
```python
# In issue CRUD operations, trigger notifications:

# Issue created
await notification_service.send_issue_notification(
    "ISSUE_CREATED",
    issue,
    recipients=[admin_user_ids],
    context={"reporter": user.username, "category": issue.category}
)

# Issue assigned
await notification_service.send_issue_notification(
    "ISSUE_ASSIGNED",
    issue,
    recipients=[issue.assigned_to],
    context={"assigned_by": current_user.username}
)

# High priority issue
if issue.priority in ["CRITICAL", "HIGH"]:
    await notification_service.send_issue_notification(
        "HIGH_PRIORITY_ISSUE",
        issue,
        recipients=await get_admin_users()
    )
```

#### Auto-Error Detection
```python
# In auto error reporter, send immediate notifications for critical errors
if error_priority == "CRITICAL":
    await notification_service.send_issue_notification(
        "AUTO_ISSUE_DETECTED",
        issue,
        recipients=await get_on_call_admins(),
        context={"error_type": "CRITICAL_JS_ERROR"}
    )
```

### 7. Configuration

#### Environment Variables
```env
# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=notifications@madagascar-license.gov.mg
SMTP_PASSWORD=...
EMAIL_FROM=noreply@madagascar-license.gov.mg

# Notification Settings
NOTIFICATION_QUEUE_ENABLED=true
NOTIFICATION_RETRY_ATTEMPTS=3
NOTIFICATION_BATCH_SIZE=50
```

#### Default Templates
```json
{
  "ISSUE_ASSIGNED": {
    "subject": "Issue Assigned: {issue.title}",
    "body": "Hello {user.name},\n\nYou have been assigned issue #{issue.id}: {issue.title}\n\nPriority: {issue.priority}\nReported by: {issue.reporter}\n\nView issue: {app_url}/admin/issues/{issue.id}"
  },
  "ISSUE_RESOLVED": {
    "subject": "Issue Resolved: {issue.title}",
    "body": "Issue #{issue.id} has been resolved.\n\nResolution notes: {issue.resolution_notes}\n\nResolved by: {resolved_by}"
  }
}
```

### 8. Implementation Phases

#### Phase 1: Core Infrastructure
1. Create database models and migrations
2. Implement basic NotificationService
3. Create email provider with SMTP
4. Add basic notification templates

#### Phase 2: Issue Integration
1. Add notification triggers to issue operations
2. Implement user notification preferences
3. Create admin notification management interface
4. Add notification queue processing

#### Phase 3: Advanced Features
1. In-app notifications with real-time updates
2. SMS notifications (optional)
3. Webhook notifications for external systems
4. Advanced template engine with conditional logic

#### Phase 4: Analytics & Optimization
1. Notification delivery analytics
2. User engagement tracking
3. Performance optimization
4. A/B testing for notification content

### 9. Background Task Processing

#### Celery Integration (Recommended)
```python
# app/tasks/notification_tasks.py
from celery import Celery

@celery.task
def process_notification_queue():
    """Background task to process queued notifications"""
    notification_service = NotificationService()
    await notification_service.process_notification_queue()

@celery.task
def send_daily_issue_summary():
    """Send daily summary to admins"""
    # Generate summary of new/resolved issues
    # Send to admin users with appropriate preferences
```

#### Scheduled Tasks
```python
# Schedule periodic tasks
CELERYBEAT_SCHEDULE = {
    'process-notifications': {
        'task': 'app.tasks.notification_tasks.process_notification_queue',
        'schedule': 30.0,  # Every 30 seconds
    },
    'daily-issue-summary': {
        'task': 'app.tasks.notification_tasks.send_daily_issue_summary',
        'schedule': crontab(hour=8, minute=0),  # 8 AM daily
    },
}
```

### 10. Security Considerations

#### Data Protection
- Encrypt sensitive notification content
- Implement rate limiting to prevent spam
- Validate all template inputs to prevent injection
- Log all notification activities for audit

#### Privacy Controls
- Allow users to opt-out of non-critical notifications
- Respect user privacy preferences
- Implement unsubscribe mechanisms
- Comply with data protection regulations

### 11. Testing Strategy

#### Unit Tests
- NotificationService functionality
- Template rendering
- Email provider reliability
- Queue processing logic

#### Integration Tests
- End-to-end notification flow
- Issue event triggers
- Email delivery confirmation
- User preference handling

#### Load Testing
- Queue processing under high volume
- Email delivery performance
- Database performance with large notification history

## Benefits

1. **Immediate Awareness**: Admins get notified of critical issues instantly
2. **Improved Response Times**: Assigned users know immediately when they have new issues
3. **Better Collaboration**: Comments and status changes keep everyone informed
4. **Proactive Monitoring**: Auto-detected errors are escalated appropriately
5. **User Engagement**: Users get feedback when their reported issues are resolved
6. **Audit Trail**: Complete notification history for compliance

## Future Enhancements

1. **Mobile Push Notifications**: For mobile app users
2. **Slack/Teams Integration**: Send notifications to team channels
3. **AI-Powered Routing**: Smart assignment based on expertise and availability
4. **Escalation Rules**: Automatic escalation if issues aren't addressed in time
5. **Custom Workflows**: User-defined notification workflows for different scenarios

This architecture provides a solid foundation for implementing notifications while maintaining the flexibility to enhance and expand the system as requirements evolve.
