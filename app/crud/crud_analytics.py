"""
CRUD operations for Analytics in Madagascar License System
Handles all analytics data aggregation and calculation operations
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func, cast, String, extract, text
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from app.models.application import Application
from app.models.license import License  
from app.models.printing import PrintJob
from app.models.transaction import Transaction
from app.models.user import User
from app.models.enums import (
    ApplicationStatus, ApplicationType, LicenseCategory, 
    PrintJobStatus, TransactionStatus, TransactionType
)
from app.schemas.analytics import (
    AnalyticsFilters, ApplicationKPI, LicenseKPI, PrintingKPI, FinancialKPI,
    ApplicationTrendDataPoint, LicenseTrendDataPoint, PrintingTrendDataPoint,
    FinancialTrendDataPoint, ApplicationTypeDistribution, LicenseCategoryDistribution,
    ProcessingPipelineData, PaymentMethodDistribution,
    APIPerformance, DatabaseHealth, StorageHealth, ServiceHealth,
    ActivityItem, ErrorSummary, TopError, LocationPerformance
)

logger = logging.getLogger(__name__)


class CRUDAnalytics:
    """Analytics CRUD operations"""
    
    def _get_date_range_filter(self, filters: AnalyticsFilters) -> Tuple[datetime, datetime]:
        """Calculate start and end dates based on filters"""
        if filters.start_date and filters.end_date:
            return filters.start_date, filters.end_date
        
        now = datetime.utcnow()
        
        if filters.date_range == "7days":
            start_date = now - timedelta(days=7)
        elif filters.date_range == "90days":
            start_date = now - timedelta(days=90)
        elif filters.date_range == "6months":
            start_date = now - timedelta(days=180)
        elif filters.date_range == "1year":
            start_date = now - timedelta(days=365)
        else:  # default "30days"
            start_date = now - timedelta(days=30)
        
        return start_date, now
    
    def _calculate_trend(self, current: int, previous: int) -> Tuple[float, str]:
        """Calculate percentage change and trend direction"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0, "up" if current > 0 else "flat"
        
        change_percent = ((current - previous) / previous) * 100
        
        if change_percent > 5:
            trend = "up"
        elif change_percent < -5:
            trend = "down"
        else:
            trend = "flat"
        
        return round(change_percent, 1), trend

    def get_application_kpi(self, db: Session, filters: AnalyticsFilters) -> ApplicationKPI:
        """Get application KPI metrics"""
        start_date, end_date = self._get_date_range_filter(filters)
        
        # Base query with location filter
        base_query = db.query(Application)
        if filters.location_id:
            base_query = base_query.filter(Application.location_id == filters.location_id)
        
        # Current period metrics
        current_query = base_query.filter(
            Application.created_at >= start_date,
            Application.created_at <= end_date
        )
        
        total = current_query.count()
        pending = current_query.filter(Application.status == ApplicationStatus.PENDING_REVIEW).count()
        approved = current_query.filter(Application.status == ApplicationStatus.COMPLETED).count()
        rejected = current_query.filter(Application.status == ApplicationStatus.REJECTED).count()
        
        # Previous period for comparison
        period_length = end_date - start_date
        prev_start = start_date - period_length
        prev_end = start_date
        
        prev_total = base_query.filter(
            Application.created_at >= prev_start,
            Application.created_at < prev_end
        ).count()
        
        change_percent, trend = self._calculate_trend(total, prev_total)
        
        return ApplicationKPI(
            total=total,
            pending=pending,
            approved=approved,
            rejected=rejected,
            change_percent=change_percent,
            trend=trend
        )
    
    def get_license_kpi(self, db: Session, filters: AnalyticsFilters) -> LicenseKPI:
        """Get license KPI metrics"""
        start_date, end_date = self._get_date_range_filter(filters)
        
        # Base query with location filter
        base_query = db.query(License)
        if filters.location_id:
            base_query = base_query.filter(License.issued_location_id == filters.location_id)
        
        # Current metrics
        total = base_query.count()
        active = base_query.filter(License.expiry_date > datetime.utcnow()).count()
        
        # Expiring in next 30 days
        thirty_days_from_now = datetime.utcnow() + timedelta(days=30)
        expiring = base_query.filter(
            License.expiry_date > datetime.utcnow(),
            License.expiry_date <= thirty_days_from_now
        ).count()
        
        expired = base_query.filter(License.expiry_date <= datetime.utcnow()).count()
        
        # Current period new licenses
        current_new = base_query.filter(
            License.issued_date >= start_date,
            License.issued_date <= end_date
        ).count()
        
        # Previous period for comparison
        period_length = end_date - start_date
        prev_start = start_date - period_length
        prev_end = start_date
        
        prev_new = base_query.filter(
            License.issued_date >= prev_start,
            License.issued_date < prev_end
        ).count()
        
        change_percent, trend = self._calculate_trend(current_new, prev_new)
        
        return LicenseKPI(
            total=total,
            active=active,
            expiring=expiring,
            expired=expired,
            change_percent=change_percent,
            trend=trend
        )
    
    def get_printing_kpi(self, db: Session, filters: AnalyticsFilters) -> PrintingKPI:
        """Get printing job KPI metrics"""
        start_date, end_date = self._get_date_range_filter(filters)
        
        # Base query with location filter
        base_query = db.query(PrintJob)
        if filters.location_id:
            base_query = base_query.filter(PrintJob.location_id == filters.location_id)
        
        # Current period metrics
        current_query = base_query.filter(
            PrintJob.created_at >= start_date,
            PrintJob.created_at <= end_date
        )
        
        total_jobs = current_query.count()
        completed = current_query.filter(PrintJob.status == PrintJobStatus.COMPLETED).count()
        pending = current_query.filter(PrintJob.status == PrintJobStatus.PENDING).count()
        failed = current_query.filter(PrintJob.status == PrintJobStatus.FAILED).count()
        
        # Previous period for comparison
        period_length = end_date - start_date
        prev_start = start_date - period_length
        prev_end = start_date
        
        prev_total = base_query.filter(
            PrintJob.created_at >= prev_start,
            PrintJob.created_at < prev_end
        ).count()
        
        change_percent, trend = self._calculate_trend(total_jobs, prev_total)
        
        return PrintingKPI(
            total_jobs=total_jobs,
            completed=completed,
            pending=pending,
            failed=failed,
            change_percent=change_percent,
            trend=trend
        )
    
    def get_financial_kpi(self, db: Session, filters: AnalyticsFilters) -> FinancialKPI:
        """Get financial KPI metrics"""
        start_date, end_date = self._get_date_range_filter(filters)
        
        # Base query for successful transactions with location filter
        base_query = db.query(Transaction).filter(
            Transaction.status == TransactionStatus.COMPLETED
        )
        if filters.location_id:
            base_query = base_query.filter(Transaction.location_id == filters.location_id)
        
        # Current period metrics
        current_query = base_query.filter(
            Transaction.created_at >= start_date,
            Transaction.created_at <= end_date
        )
        
        # Calculate revenue by transaction type
        total_revenue = current_query.with_entities(
            func.sum(Transaction.amount)
        ).scalar() or Decimal('0')
        
        application_fees = current_query.filter(
            Transaction.transaction_type == TransactionType.APPLICATION_FEE
        ).with_entities(func.sum(Transaction.amount)).scalar() or Decimal('0')
        
        license_fees = current_query.filter(
            Transaction.transaction_type == TransactionType.LICENSE_FEE
        ).with_entities(func.sum(Transaction.amount)).scalar() or Decimal('0')
        
        card_fees = current_query.filter(
            Transaction.transaction_type == TransactionType.CARD_FEE
        ).with_entities(func.sum(Transaction.amount)).scalar() or Decimal('0')
        
        other_fees = total_revenue - application_fees - license_fees - card_fees
        
        # Previous period for comparison
        period_length = end_date - start_date
        prev_start = start_date - period_length
        prev_end = start_date
        
        prev_revenue = base_query.filter(
            Transaction.created_at >= prev_start,
            Transaction.created_at < prev_end
        ).with_entities(func.sum(Transaction.amount)).scalar() or Decimal('0')
        
        change_percent, trend = self._calculate_trend(
            float(total_revenue), float(prev_revenue)
        )
        
        return FinancialKPI(
            total_revenue=total_revenue,
            application_fees=application_fees,
            license_fees=license_fees,
            card_fees=card_fees,
            other_fees=other_fees,
            change_percent=change_percent,
            trend=trend,
            currency="MGA"
        )
    
    def get_application_trends(self, db: Session, filters: AnalyticsFilters) -> List[ApplicationTrendDataPoint]:
        """Get application trends over time"""
        start_date, end_date = self._get_date_range_filter(filters)
        
        # Base query with location filter
        base_query = db.query(Application)
        if filters.location_id:
            base_query = base_query.filter(Application.location_id == filters.location_id)
        
        # Group by date and status
        results = base_query.filter(
            Application.created_at >= start_date,
            Application.created_at <= end_date
        ).with_entities(
            func.date(Application.created_at).label('date'),
            Application.status,
            func.count(Application.id).label('count')
        ).group_by(
            func.date(Application.created_at),
            Application.status
        ).all()
        
        # Process results into daily data points
        daily_data = {}
        current = start_date.date()
        end = end_date.date()
        
        # Initialize all dates with zero values
        while current <= end:
            daily_data[current] = {
                'new_applications': 0,
                'completed': 0,
                'pending': 0,
                'rejected': 0
            }
            current += timedelta(days=1)
        
        # Fill in actual data
        for result in results:
            date = result.date
            status = result.status
            count = result.count
            
            if date in daily_data:
                if status == ApplicationStatus.COMPLETED:
                    daily_data[date]['completed'] = count
                elif status == ApplicationStatus.PENDING_REVIEW:
                    daily_data[date]['pending'] = count
                elif status == ApplicationStatus.REJECTED:
                    daily_data[date]['rejected'] = count
                
                # All applications are "new" when created
                daily_data[date]['new_applications'] += count
        
        # Convert to list of data points
        return [
            ApplicationTrendDataPoint(
                date=date.isoformat(),
                new_applications=data['new_applications'],
                completed=data['completed'],
                pending=data['pending'],
                rejected=data['rejected']
            )
            for date, data in sorted(daily_data.items())
        ]
    
    def get_application_type_distribution(self, db: Session, filters: AnalyticsFilters) -> List[ApplicationTypeDistribution]:
        """Get application type distribution"""
        start_date, end_date = self._get_date_range_filter(filters)
        
        # Base query with filters
        base_query = db.query(Application).filter(
            Application.created_at >= start_date,
            Application.created_at <= end_date
        )
        if filters.location_id:
            base_query = base_query.filter(Application.location_id == filters.location_id)
        
        # Get distribution by type
        results = base_query.with_entities(
            Application.application_type,
            func.count(Application.id).label('count')
        ).group_by(Application.application_type).all()
        
        total = sum(result.count for result in results)
        
        # Map application types to human-readable labels
        type_labels = {
            ApplicationType.LEARNERS_PERMIT_CAPTURE: "Learner's Permit",
            ApplicationType.DRIVERS_LICENSE_CAPTURE: "Driving License",
            ApplicationType.PROFESSIONAL_PERMIT_CAPTURE: "Professional Permit",
            ApplicationType.LICENSE_RENEWAL: "License Renewal",
            ApplicationType.DUPLICATE_LICENSE: "Duplicate License"
        }
        
        return [
            ApplicationTypeDistribution(
                type=result.application_type.value,
                label=type_labels.get(result.application_type, str(result.application_type)),
                count=result.count,
                percentage=round((result.count / total * 100), 1) if total > 0 else 0
            )
            for result in results
        ]
    
    def get_processing_pipeline_data(self, db: Session, filters: AnalyticsFilters) -> List[ProcessingPipelineData]:
        """Get processing pipeline funnel data"""
        start_date, end_date = self._get_date_range_filter(filters)
        
        # Base query with filters
        base_query = db.query(Application).filter(
            Application.created_at >= start_date,
            Application.created_at <= end_date
        )
        if filters.location_id:
            base_query = base_query.filter(Application.location_id == filters.location_id)
        
        total_submitted = base_query.count()
        
        # Define pipeline stages
        stages = [
            ("Submitted", total_submitted),
            ("Under Review", base_query.filter(
                Application.status.in_([
                    ApplicationStatus.PENDING_REVIEW,
                    ApplicationStatus.UNDER_REVIEW,
                    ApplicationStatus.PENDING_APPROVAL
                ])
            ).count()),
            ("Approved", base_query.filter(
                Application.status == ApplicationStatus.APPROVED
            ).count()),
            ("Completed", base_query.filter(
                Application.status == ApplicationStatus.COMPLETED
            ).count())
        ]
        
        return [
            ProcessingPipelineData(
                stage=stage_name,
                count=count,
                percentage=round((count / total_submitted * 100), 1) if total_submitted > 0 else 0
            )
            for stage_name, count in stages
        ]
    
    def get_system_health(self, db: Session) -> Dict[str, Any]:
        """Get current system health metrics"""
        # Note: In a real implementation, these would come from monitoring systems
        # For now, we'll return mock data with some real database metrics
        
        # Get some real database metrics
        try:
            # Count active connections (this would be database-specific)
            active_connections = db.execute(text("SELECT COUNT(*) FROM pg_stat_activity")).scalar()
        except:
            active_connections = 10  # fallback
        
        return {
            "api_performance": {
                "avg_response_time_ms": 245,
                "uptime_percentage": 99.7,
                "error_rate_percentage": 0.3,
                "requests_per_minute": 150
            },
            "database": {
                "connection_pool_usage": 65,
                "query_performance_score": 96,
                "active_connections": active_connections,
                "slow_query_count": 2
            },
            "storage": {
                "disk_usage_percentage": 72,
                "document_storage_gb": 145.7,
                "backup_status": "healthy",
                "last_backup": datetime.utcnow() - timedelta(hours=6)
            },
            "services": {
                "biomini_agent_status": "online",
                "print_service_status": "online",
                "notification_service_status": "online",
                "background_jobs_pending": 12
            }
        }
    
    def get_recent_activity(self, db: Session, limit: int = 20, offset: int = 0) -> List[ActivityItem]:
        """Get recent system activity"""
        # In a real implementation, this would come from an audit log or activity table
        # For now, we'll generate some sample activities based on recent database changes
        
        activities = []
        
        # Get recent applications
        recent_apps = db.query(Application).order_by(desc(Application.created_at)).limit(5).all()
        for app in recent_apps:
            activities.append(ActivityItem(
                id=f"app_{app.id}",
                type="application_submitted",
                title="New application submitted",
                description=f"{app.application_type.value} application submitted",
                location=f"Location {app.location_id}",
                timestamp=app.created_at,
                severity="info"
            ))
        
        # Get recent licenses
        recent_licenses = db.query(License).order_by(desc(License.created_at)).limit(3).all()
        for license in recent_licenses:
            activities.append(ActivityItem(
                id=f"license_{license.id}",
                type="license_issued",
                title="License issued",
                description=f"License {license.license_number} issued",
                location=f"Location {license.issued_location_id}",
                timestamp=license.created_at,
                severity="info"
            ))
        
        # Sort by timestamp and apply pagination
        activities.sort(key=lambda x: x.timestamp, reverse=True)
        return activities[offset:offset + limit]
    
    def get_location_performance(self, db: Session, filters: AnalyticsFilters) -> List[LocationPerformance]:
        """Get performance metrics by location"""
        start_date, end_date = self._get_date_range_filter(filters)
        
        # This would typically join with a locations table
        # For now, we'll group by location_id and aggregate metrics
        
        results = db.query(
            Application.location_id,
            func.count(Application.id).label('applications_processed'),
            func.avg(
                extract('day', Application.updated_at - Application.created_at)
            ).label('avg_processing_days')
        ).filter(
            Application.created_at >= start_date,
            Application.created_at <= end_date,
            Application.status == ApplicationStatus.COMPLETED
        ).group_by(Application.location_id).all()
        
        location_data = []
        for result in results:
            # Get print jobs and revenue for this location
            print_jobs = db.query(PrintJob).filter(
                PrintJob.location_id == result.location_id,
                PrintJob.created_at >= start_date,
                PrintJob.created_at <= end_date
            ).count()
            
            revenue = db.query(func.sum(Transaction.amount)).filter(
                Transaction.location_id == result.location_id,
                Transaction.created_at >= start_date,
                Transaction.created_at <= end_date,
                Transaction.status == TransactionStatus.COMPLETED
            ).scalar() or Decimal('0')
            
            location_data.append(LocationPerformance(
                location_id=result.location_id,
                location_name=f"Location {result.location_id}",  # Would come from locations table
                applications_processed=result.applications_processed,
                cards_printed=print_jobs,
                revenue_generated=revenue,
                average_processing_time=float(result.avg_processing_days or 0),
                success_rate=95.0  # Would be calculated from success/failure rates
            ))
        
        return location_data


# Create instance
crud_analytics = CRUDAnalytics()
