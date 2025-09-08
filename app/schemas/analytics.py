"""
Analytics Schema Definitions for Madagascar License System
Pydantic schemas for analytics data structures and API responses
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal


# Base Analytics Filters
class AnalyticsFilters(BaseModel):
    """Base filters for analytics queries"""
    date_range: Optional[str] = Field("30days", description="Date range: 7days, 30days, 90days, 6months, 1year")
    location_id: Optional[int] = Field(None, description="Location ID, null for all locations")
    start_date: Optional[datetime] = Field(None, description="Custom start date (overrides date_range)")
    end_date: Optional[datetime] = Field(None, description="Custom end date (overrides date_range)")


# KPI Data Structures
class ApplicationKPI(BaseModel):
    """Application KPI metrics"""
    total: int = Field(description="Total applications")
    pending: int = Field(description="Pending applications")
    approved: int = Field(description="Approved applications")
    rejected: int = Field(description="Rejected applications")
    change_percent: float = Field(description="Percentage change from previous period")
    trend: str = Field(description="Trend direction: up, down, flat")


class LicenseKPI(BaseModel):
    """License KPI metrics"""
    total: int = Field(description="Total licenses")
    active: int = Field(description="Active licenses")
    expiring: int = Field(description="Licenses expiring soon")
    expired: int = Field(description="Expired licenses")
    change_percent: float = Field(description="Percentage change from previous period")
    trend: str = Field(description="Trend direction: up, down, flat")


class PrintingKPI(BaseModel):
    """Printing job KPI metrics"""
    total_jobs: int = Field(description="Total print jobs")
    completed: int = Field(description="Completed jobs")
    pending: int = Field(description="Pending jobs")
    failed: int = Field(description="Failed jobs")
    change_percent: float = Field(description="Percentage change from previous period")
    trend: str = Field(description="Trend direction: up, down, flat")


class FinancialKPI(BaseModel):
    """Financial KPI metrics"""
    total_revenue: Decimal = Field(description="Total revenue")
    application_fees: Decimal = Field(description="Revenue from application fees")
    license_fees: Decimal = Field(description="Revenue from license fees")
    card_fees: Decimal = Field(description="Revenue from card fees")
    other_fees: Decimal = Field(description="Revenue from other fees")
    change_percent: float = Field(description="Percentage change from previous period")
    trend: str = Field(description="Trend direction: up, down, flat")
    currency: str = Field(default="MGA", description="Currency code")


class KPISummary(BaseModel):
    """Complete KPI summary response"""
    applications: ApplicationKPI
    licenses: LicenseKPI
    printing: PrintingKPI
    financial: FinancialKPI
    last_updated: datetime


# Chart Data Structures
class TimeSeriesDataPoint(BaseModel):
    """Generic time series data point"""
    date: str = Field(description="Date in YYYY-MM-DD format")
    value: int = Field(description="Numeric value for the date")


class ApplicationTrendDataPoint(BaseModel):
    """Application trends data point"""
    date: str = Field(description="Date in YYYY-MM-DD format")
    new_applications: int = Field(description="New applications submitted")
    completed: int = Field(description="Applications completed")
    pending: int = Field(description="Applications pending")
    rejected: int = Field(description="Applications rejected")


class ApplicationTypeDistribution(BaseModel):
    """Application type distribution data"""
    type: str = Field(description="Application type enum value")
    label: str = Field(description="Human-readable label")
    count: int = Field(description="Number of applications")
    percentage: float = Field(description="Percentage of total")


class ProcessingPipelineData(BaseModel):
    """Processing pipeline funnel data"""
    stage: str = Field(description="Pipeline stage name")
    count: int = Field(description="Number of applications in this stage")
    percentage: float = Field(description="Percentage of total submitted")


class LicenseTrendDataPoint(BaseModel):
    """License trends data point"""
    date: str = Field(description="Date in YYYY-MM-DD format")
    issued: int = Field(description="Licenses issued")
    renewed: int = Field(description="Licenses renewed")
    expired: int = Field(description="Licenses expired")


class LicenseCategoryDistribution(BaseModel):
    """License category distribution data"""
    category: str = Field(description="License category code")
    label: str = Field(description="Human-readable label")
    count: int = Field(description="Number of licenses")
    percentage: float = Field(description="Percentage of total")


class PrintingTrendDataPoint(BaseModel):
    """Printing trends data point"""
    date: str = Field(description="Date in YYYY-MM-DD format")
    printed: int = Field(description="Cards printed")
    pending: int = Field(description="Jobs pending")
    failed: int = Field(description="Jobs failed")


class FinancialTrendDataPoint(BaseModel):
    """Financial trends data point"""
    date: str = Field(description="Date in YYYY-MM-DD format")
    revenue: Decimal = Field(description="Daily revenue")
    fees: Decimal = Field(description="Fee revenue")
    costs: Decimal = Field(description="Operational costs")


class PaymentMethodDistribution(BaseModel):
    """Payment method distribution data"""
    method: str = Field(description="Payment method name")
    count: int = Field(description="Number of transactions")
    amount: Decimal = Field(description="Total amount")
    percentage: float = Field(description="Percentage of total transactions")


# System Health Data Structures
class APIPerformance(BaseModel):
    """API performance metrics"""
    avg_response_time_ms: int = Field(description="Average response time in milliseconds")
    uptime_percentage: float = Field(description="System uptime percentage")
    error_rate_percentage: float = Field(description="Error rate percentage")
    requests_per_minute: int = Field(description="Average requests per minute")


class DatabaseHealth(BaseModel):
    """Database health metrics"""
    connection_pool_usage: int = Field(description="Connection pool usage percentage")
    query_performance_score: int = Field(description="Query performance score (0-100)")
    active_connections: int = Field(description="Current active connections")
    slow_query_count: int = Field(description="Number of slow queries in the last hour")


class StorageHealth(BaseModel):
    """Storage system health metrics"""
    disk_usage_percentage: int = Field(description="Disk usage percentage")
    document_storage_gb: float = Field(description="Document storage used in GB")
    backup_status: str = Field(description="Backup system status")
    last_backup: datetime = Field(description="Last successful backup timestamp")


class ServiceHealth(BaseModel):
    """External service health status"""
    biomini_agent_status: str = Field(description="BioMini agent status")
    print_service_status: str = Field(description="Print service status")
    notification_service_status: str = Field(description="Notification service status")
    background_jobs_pending: int = Field(description="Number of pending background jobs")


class SystemHealth(BaseModel):
    """Complete system health response"""
    api_performance: APIPerformance
    database: DatabaseHealth
    storage: StorageHealth
    services: ServiceHealth


class SystemTrendDataPoint(BaseModel):
    """System performance trends data point"""
    date: str = Field(description="Date in YYYY-MM-DD format")
    response_time: int = Field(description="Average response time in ms")
    uptime: float = Field(description="Uptime percentage")
    error_rate: float = Field(description="Error rate percentage")


class APITrendDataPoint(BaseModel):
    """API performance trends data point"""
    date: str = Field(description="Date in YYYY-MM-DD format")
    requests: int = Field(description="Total API requests")
    successful: int = Field(description="Successful requests")
    errors: int = Field(description="Error requests")


# Activity Feed Data Structures
class ActivityItem(BaseModel):
    """Individual activity feed item"""
    id: str = Field(description="Unique activity ID")
    type: str = Field(description="Activity type")
    title: str = Field(description="Activity title")
    description: str = Field(description="Activity description")
    location: str = Field(description="Location name or 'system'")
    timestamp: datetime = Field(description="Activity timestamp")
    severity: str = Field(description="Activity severity: info, warning, error")


class ActivityFeed(BaseModel):
    """Activity feed response"""
    activities: List[ActivityItem]
    total: int = Field(description="Total number of activities")
    page: int = Field(description="Current page number")
    per_page: int = Field(description="Items per page")
    has_more: bool = Field(description="Whether more items are available")


# Error Summary Data Structures
class ErrorSummary(BaseModel):
    """Error summary metrics"""
    total_errors: int = Field(description="Total errors in period")
    critical_errors: int = Field(description="Critical errors")
    warning_errors: int = Field(description="Warning errors")
    info_errors: int = Field(description="Info errors")


class TopError(BaseModel):
    """Top error occurrence"""
    message: str = Field(description="Error message")
    count: int = Field(description="Number of occurrences")
    severity: str = Field(description="Error severity")
    last_occurred: datetime = Field(description="Last occurrence timestamp")


class ErrorAnalytics(BaseModel):
    """Error analytics response"""
    error_summary: ErrorSummary
    error_trends: List[Dict[str, Any]] = Field(description="Daily error trends")
    top_errors: List[TopError] = Field(description="Most frequent errors")


# Location Performance Data Structures
class LocationPerformance(BaseModel):
    """Individual location performance metrics"""
    location_id: int = Field(description="Location ID")
    location_name: str = Field(description="Location name")
    applications_processed: int = Field(description="Applications processed")
    cards_printed: int = Field(description="Cards printed")
    revenue_generated: Decimal = Field(description="Revenue generated")
    average_processing_time: float = Field(description="Average processing time in days")
    success_rate: float = Field(description="Success rate percentage")


# Export Data Structures
class ExportRequest(BaseModel):
    """Export request parameters"""
    export_type: str = Field(description="Export format: csv, xlsx, pdf")
    data_types: List[str] = Field(description="Data types to export")
    date_range: Optional[str] = Field("30days", description="Date range filter")
    location_id: Optional[int] = Field(None, description="Location filter")
    email: Optional[str] = Field(None, description="Email for async export delivery")


class ExportStatus(BaseModel):
    """Export status response"""
    export_id: str = Field(description="Unique export ID")
    status: str = Field(description="Export status: processing, completed, failed")
    download_url: Optional[str] = Field(None, description="Download URL when completed")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    progress_percentage: Optional[int] = Field(None, description="Progress percentage")


# Response Wrappers
class AnalyticsResponse(BaseModel):
    """Generic analytics response wrapper"""
    success: bool = Field(True, description="Whether the request was successful")
    data: Any = Field(description="Response data")
    message: Optional[str] = Field(None, description="Optional message")
    last_updated: Optional[datetime] = Field(None, description="Data last updated timestamp")


class ChartDataResponse(BaseModel):
    """Chart data response with metadata"""
    success: bool = Field(True, description="Whether the request was successful")
    data: List[Any] = Field(description="Chart data points")
    metadata: Dict[str, Any] = Field(description="Additional metadata")


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""
    success: bool = Field(True, description="Whether the request was successful")
    data: List[Any] = Field(description="Response data items")
    pagination: Dict[str, Any] = Field(description="Pagination information")


# Real-time Update Schemas
class LiveUpdateMessage(BaseModel):
    """WebSocket live update message"""
    type: str = Field(description="Update type")
    data: Dict[str, Any] = Field(description="Update data")
    timestamp: datetime = Field(description="Update timestamp")


class KPIUpdate(BaseModel):
    """KPI update message data"""
    applications: Optional[Dict[str, Any]] = Field(None, description="Application KPI updates")
    licenses: Optional[Dict[str, Any]] = Field(None, description="License KPI updates")
    printing: Optional[Dict[str, Any]] = Field(None, description="Printing KPI updates")
    financial: Optional[Dict[str, Any]] = Field(None, description="Financial KPI updates")


class SystemAlert(BaseModel):
    """System alert message data"""
    severity: str = Field(description="Alert severity")
    message: str = Field(description="Alert message")
    component: str = Field(description="System component")
    timestamp: datetime = Field(description="Alert timestamp")
