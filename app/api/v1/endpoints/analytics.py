"""
Analytics API Endpoints for Madagascar License System
Comprehensive analytics and dashboard data endpoints
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.enums import RoleHierarchy
from app.crud.crud_analytics import crud_analytics
from app.schemas.analytics import (
    AnalyticsFilters, AnalyticsResponse, ChartDataResponse,
    KPISummary, ApplicationKPI, LicenseKPI, PrintingKPI, FinancialKPI,
    ApplicationTrendDataPoint, LicenseTrendDataPoint, PrintingTrendDataPoint,
    FinancialTrendDataPoint, ApplicationTypeDistribution, LicenseCategoryDistribution,
    ProcessingPipelineData, PaymentMethodDistribution, SystemHealth,
    ActivityFeed, ActivityItem, ErrorAnalytics, LocationPerformance,
    ExportRequest, ExportStatus
)

logger = logging.getLogger(__name__)
router = APIRouter()


def check_analytics_access(current_user: User) -> bool:
    """Check if user has access to analytics data"""
    # Managers and above can access analytics
    return current_user.role.hierarchy_level >= RoleHierarchy.MANAGER.value


@router.get("/kpi/summary", response_model=AnalyticsResponse)
async def get_kpi_summary(
    date_range: str = Query("30days", regex="^(7days|30days|90days|6months|1year)$"),
    location_id: Optional[int] = Query(None, description="Location ID, null for all locations"),
    start_date: Optional[datetime] = Query(None, description="Custom start date"),
    end_date: Optional[datetime] = Query(None, description="Custom end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive KPI summary with all key metrics
    
    Returns application, license, printing, and financial KPIs for the specified period
    """
    if not check_analytics_access(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to access analytics data"
        )
    
    # Apply user location restrictions for non-admin users
    if current_user.role.hierarchy_level < RoleHierarchy.ADMIN.value:
        if location_id is None:
            location_id = current_user.primary_location_id
        elif location_id != current_user.primary_location_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to other location's data"
            )
    
    try:
        filters = AnalyticsFilters(
            date_range=date_range,
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        logger.info(f"Getting KPI summary with filters: {filters}")
        
        # Get all KPI data with error handling
        applications_kpi = crud_analytics.get_application_kpi(db, filters)
        licenses_kpi = crud_analytics.get_license_kpi(db, filters)
        printing_kpi = crud_analytics.get_printing_kpi(db, filters)
        financial_kpi = crud_analytics.get_financial_kpi(db, filters)
        
        logger.info(f"KPI data retrieved: apps={applications_kpi.total}, licenses={licenses_kpi.total}")
        
        kpi_summary = KPISummary(
            applications=applications_kpi,
            licenses=licenses_kpi,
            printing=printing_kpi,
            financial=financial_kpi,
            last_updated=datetime.utcnow()
        )
        
        return AnalyticsResponse(
            success=True,
            data=kpi_summary,
            last_updated=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error fetching KPI summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch KPI summary"
        )


@router.get("/kpi/applications", response_model=AnalyticsResponse)
async def get_application_kpi(
    date_range: str = Query("30days", regex="^(7days|30days|90days|6months|1year)$"),
    location_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get application-specific KPI metrics"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    # Apply location restrictions
    if current_user.role.hierarchy_level < RoleHierarchy.ADMIN.value:
        location_id = current_user.primary_location_id
    
    try:
        filters = AnalyticsFilters(
            date_range=date_range,
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        kpi_data = crud_analytics.get_application_kpi(db, filters)
        
        return AnalyticsResponse(
            success=True,
            data=kpi_data,
            last_updated=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error fetching application KPI: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch application KPI"
        )


@router.get("/kpi/licenses", response_model=AnalyticsResponse)
async def get_license_kpi(
    date_range: str = Query("30days", regex="^(7days|30days|90days|6months|1year)$"),
    location_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get license-specific KPI metrics"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    # Apply location restrictions
    if current_user.role.hierarchy_level < RoleHierarchy.ADMIN.value:
        location_id = current_user.primary_location_id
    
    try:
        filters = AnalyticsFilters(
            date_range=date_range,
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        kpi_data = crud_analytics.get_license_kpi(db, filters)
        
        return AnalyticsResponse(
            success=True,
            data=kpi_data,
            last_updated=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error fetching license KPI: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch license KPI"
        )


@router.get("/kpi/printing", response_model=AnalyticsResponse)
async def get_printing_kpi(
    date_range: str = Query("30days", regex="^(7days|30days|90days|6months|1year)$"),
    location_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get printing job KPI metrics"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    # Apply location restrictions
    if current_user.role.hierarchy_level < RoleHierarchy.ADMIN.value:
        location_id = current_user.primary_location_id
    
    try:
        filters = AnalyticsFilters(
            date_range=date_range,
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        kpi_data = crud_analytics.get_printing_kpi(db, filters)
        
        return AnalyticsResponse(
            success=True,
            data=kpi_data,
            last_updated=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error fetching printing KPI: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch printing KPI"
        )


@router.get("/kpi/financial", response_model=AnalyticsResponse)
async def get_financial_kpi(
    date_range: str = Query("30days", regex="^(7days|30days|90days|6months|1year)$"),
    location_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get financial KPI metrics"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    # Apply location restrictions
    if current_user.role.hierarchy_level < RoleHierarchy.ADMIN.value:
        location_id = current_user.primary_location_id
    
    try:
        filters = AnalyticsFilters(
            date_range=date_range,
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        kpi_data = crud_analytics.get_financial_kpi(db, filters)
        
        return AnalyticsResponse(
            success=True,
            data=kpi_data,
            last_updated=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error fetching financial KPI: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch financial KPI"
        )


@router.get("/charts/applications/trends", response_model=ChartDataResponse)
async def get_application_trends(
    date_range: str = Query("30days", regex="^(7days|30days|90days|6months|1year)$"),
    location_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get application trends over time"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    # Apply location restrictions
    if current_user.role.hierarchy_level < RoleHierarchy.ADMIN.value:
        location_id = current_user.primary_location_id
    
    try:
        filters = AnalyticsFilters(
            date_range=date_range,
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        trend_data = crud_analytics.get_application_trends(db, filters)
        
        return ChartDataResponse(
            success=True,
            data=trend_data,
            metadata={
                "total_records": len(trend_data),
                "date_range": date_range,
                "location_id": location_id
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching application trends: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch application trends"
        )


@router.get("/charts/applications/types", response_model=ChartDataResponse)
async def get_application_type_distribution(
    date_range: str = Query("30days", regex="^(7days|30days|90days|6months|1year)$"),
    location_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get application type distribution"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    # Apply location restrictions
    if current_user.role.hierarchy_level < RoleHierarchy.ADMIN.value:
        location_id = current_user.primary_location_id
    
    try:
        filters = AnalyticsFilters(
            date_range=date_range,
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        distribution_data = crud_analytics.get_application_type_distribution(db, filters)
        
        return ChartDataResponse(
            success=True,
            data=distribution_data,
            metadata={
                "total_types": len(distribution_data),
                "date_range": date_range,
                "location_id": location_id
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching application type distribution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch application type distribution"
        )


@router.get("/charts/applications/pipeline", response_model=ChartDataResponse)
async def get_processing_pipeline(
    date_range: str = Query("30days", regex="^(7days|30days|90days|6months|1year)$"),
    location_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get processing pipeline funnel data"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    # Apply location restrictions
    if current_user.role.hierarchy_level < RoleHierarchy.ADMIN.value:
        location_id = current_user.primary_location_id
    
    try:
        filters = AnalyticsFilters(
            date_range=date_range,
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        pipeline_data = crud_analytics.get_processing_pipeline_data(db, filters)
        
        return ChartDataResponse(
            success=True,
            data=pipeline_data,
            metadata={
                "stages": len(pipeline_data),
                "date_range": date_range,
                "location_id": location_id
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching processing pipeline: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch processing pipeline"
        )


@router.get("/system/health", response_model=AnalyticsResponse)
async def get_system_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get current system health metrics"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    try:
        health_data = crud_analytics.get_system_health(db)
        
        return AnalyticsResponse(
            success=True,
            data=health_data,
            last_updated=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error fetching system health: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch system health"
        )


@router.get("/activity/recent", response_model=AnalyticsResponse)
async def get_recent_activity(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get recent system activity"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    try:
        activities = crud_analytics.get_recent_activity(db, limit=limit, offset=offset)
        
        # Calculate pagination info
        has_more = len(activities) == limit  # Simple check, would be more sophisticated in production
        
        activity_feed = ActivityFeed(
            activities=activities,
            total=len(activities) + offset,  # Approximate, would be exact count in production
            page=offset // limit + 1,
            per_page=limit,
            has_more=has_more
        )
        
        return AnalyticsResponse(
            success=True,
            data=activity_feed,
            last_updated=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error fetching recent activity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch recent activity"
        )


@router.get("/locations/performance", response_model=ChartDataResponse)
async def get_location_performance(
    date_range: str = Query("30days", regex="^(7days|30days|90days|6months|1year)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get performance metrics by location (admin only)"""
    if current_user.role.hierarchy_level < RoleHierarchy.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required for location performance data"
        )
    
    try:
        filters = AnalyticsFilters(
            date_range=date_range,
            location_id=None,  # All locations for admin
            start_date=start_date,
            end_date=end_date
        )
        
        performance_data = crud_analytics.get_location_performance(db, filters)
        
        return ChartDataResponse(
            success=True,
            data=performance_data,
            metadata={
                "locations": len(performance_data),
                "date_range": date_range
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching location performance: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch location performance"
        )


@router.post("/export", response_model=AnalyticsResponse)
async def export_analytics_data(
    export_request: ExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Export analytics data (placeholder for future implementation)"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    # Apply location restrictions
    if current_user.role.hierarchy_level < RoleHierarchy.ADMIN.value:
        export_request.location_id = current_user.primary_location_id
    
    # Generate a unique export ID
    import uuid
    export_id = str(uuid.uuid4())
    
    # In a real implementation, this would:
    # 1. Queue a background job to generate the export
    # 2. Return the export ID for status polling
    # 3. Send email when complete (if requested)
    
    export_status = ExportStatus(
        export_id=export_id,
        status="processing",
        download_url=None,
        estimated_completion=datetime.utcnow() + timedelta(minutes=5),
        progress_percentage=0
    )
    
    return AnalyticsResponse(
        success=True,
        data=export_status,
        message="Export request queued successfully"
    )


@router.get("/api-performance", response_model=AnalyticsResponse)
async def get_api_performance_analytics(
    hours: int = Query(24, ge=1, le=168, description="Analysis period in hours"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get API request analytics and performance metrics for Analytics Dashboard"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    try:
        from sqlalchemy import func, desc
        from app.models.user import ApiRequestLog
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # Base query for the time period
        base_query = db.query(ApiRequestLog).filter(
            ApiRequestLog.created_at >= start_time,
            ApiRequestLog.created_at <= end_time
        )
        
        # Total requests
        total_requests = base_query.count()
        
        if total_requests == 0:
            # Return empty analytics if no data
            api_analytics = {
                "period": {
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "hours": hours
                },
                "overview": {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "success_rate_percent": 0,
                    "average_response_time_ms": 0
                },
                "top_endpoints": [],
                "status_code_distribution": [],
                "slowest_endpoints": [],
                "most_active_users": [],
                "error_analysis": []
            }
        else:
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
            
            # Error analysis
            error_analysis = db.query(
                ApiRequestLog.endpoint,
                func.count(ApiRequestLog.id).label('total_requests'),
                func.sum(func.case([(ApiRequestLog.status_code >= 400, 1)], else_=0)).label('error_requests')
            ).filter(
                ApiRequestLog.created_at >= start_time,
                ApiRequestLog.created_at <= end_time
            ).group_by(
                ApiRequestLog.endpoint
            ).having(
                func.sum(func.case([(ApiRequestLog.status_code >= 400, 1)], else_=0)) > 0
            ).order_by(
                desc('error_requests')
            ).limit(10).all()
            
            # Calculate error rates
            error_analysis_with_rates = []
            for error in error_analysis:
                error_rate = (error.error_requests / error.total_requests * 100) if error.total_requests > 0 else 0
                error_analysis_with_rates.append({
                    "endpoint": error.endpoint,
                    "total_requests": error.total_requests,
                    "error_requests": error.error_requests,
                    "error_rate_percent": round(error_rate, 1)
                })
            
            api_analytics = {
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
                "error_analysis": error_analysis_with_rates
            }
        
        return AnalyticsResponse(
            success=True,
            data=api_analytics,
            last_updated=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error fetching API performance analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch API performance analytics"
        )


@router.get("/charts/licenses/trends", response_model=ChartDataResponse)
async def get_license_trends(
    date_range: str = Query("30days", regex="^(7days|30days|90days|6months|1year)$"),
    location_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get license trends over time"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    # Apply location restrictions
    if current_user.role.hierarchy_level < RoleHierarchy.ADMIN.value:
        location_id = current_user.primary_location_id
    
    try:
        from app.models.license import License
        
        filters = AnalyticsFilters(
            date_range=date_range,
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        start_date_filter, end_date_filter = crud_analytics._get_date_range_filter(filters)
        
        # Base query with location filter
        base_query = db.query(License)
        if filters.location_id:
            base_query = base_query.filter(License.issued_location_id == filters.location_id)
        
        # Group by date for trend data
        from sqlalchemy import func
        results = base_query.filter(
            License.issued_date >= start_date_filter,
            License.issued_date <= end_date_filter
        ).with_entities(
            func.date(License.issued_date).label('date'),
            func.count(License.id).label('count')
        ).group_by(
            func.date(License.issued_date)
        ).all()
        
        # Convert to trend data points
        trend_data = [
            {
                "date": result.date.isoformat(),
                "licenses_issued": result.count,
                "active": result.count,  # For compatibility
                "expired": 0,  # Would need additional logic
                "expiring": 0  # Would need additional logic
            }
            for result in results
        ]
        
        return ChartDataResponse(
            success=True,
            data=trend_data,
            metadata={
                "total_records": len(trend_data),
                "date_range": date_range,
                "location_id": location_id
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching license trends: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch license trends"
        )


@router.get("/charts/printing/trends", response_model=ChartDataResponse)
async def get_printing_trends(
    date_range: str = Query("30days", regex="^(7days|30days|90days|6months|1year)$"),
    location_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get printing job trends over time"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    # Apply location restrictions
    if current_user.role.hierarchy_level < RoleHierarchy.ADMIN.value:
        location_id = current_user.primary_location_id
    
    try:
        from app.models.printing import PrintJob
        
        filters = AnalyticsFilters(
            date_range=date_range,
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        start_date_filter, end_date_filter = crud_analytics._get_date_range_filter(filters)
        
        # Base query with location filter
        base_query = db.query(PrintJob)
        if filters.location_id:
            base_query = base_query.filter(PrintJob.print_location_id == filters.location_id)
        
        # Group by date and status for trend data
        from sqlalchemy import func
        results = base_query.filter(
            PrintJob.created_at >= start_date_filter,
            PrintJob.created_at <= end_date_filter
        ).with_entities(
            func.date(PrintJob.created_at).label('date'),
            PrintJob.status,
            func.count(PrintJob.id).label('count')
        ).group_by(
            func.date(PrintJob.created_at),
            PrintJob.status
        ).all()
        
        # Process results into daily data points
        daily_data = {}
        current = start_date_filter.date()
        end = end_date_filter.date()
        
        # Initialize all dates with zero values
        while current <= end:
            daily_data[current] = {
                'total_jobs': 0,
                'completed': 0,
                'pending': 0,
                'failed': 0
            }
            current += timedelta(days=1)
        
        # Fill in actual data
        from app.models.printing import PrintJobStatus
        for result in results:
            date = result.date
            status = result.status
            count = result.count
            
            if date in daily_data:
                daily_data[date]['total_jobs'] += count
                
                if status == PrintJobStatus.COMPLETED:
                    daily_data[date]['completed'] = count
                elif status in [PrintJobStatus.QUEUED, PrintJobStatus.ASSIGNED, PrintJobStatus.PRINTING]:
                    daily_data[date]['pending'] += count
                elif status in [PrintJobStatus.FAILED, PrintJobStatus.CANCELLED]:
                    daily_data[date]['failed'] += count
        
        # Convert to list of data points
        trend_data = [
            {
                "date": date.isoformat(),
                "total_jobs": data['total_jobs'],
                "completed": data['completed'],
                "pending": data['pending'],
                "failed": data['failed']
            }
            for date, data in sorted(daily_data.items())
        ]
        
        return ChartDataResponse(
            success=True,
            data=trend_data,
            metadata={
                "total_records": len(trend_data),
                "date_range": date_range,
                "location_id": location_id
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching printing trends: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch printing trends"
        )


@router.get("/charts/financial/trends", response_model=ChartDataResponse)
async def get_financial_trends(
    date_range: str = Query("30days", regex="^(7days|30days|90days|6months|1year)$"),
    location_id: Optional[int] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get financial trends over time"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    # Apply location restrictions
    if current_user.role.hierarchy_level < RoleHierarchy.ADMIN.value:
        location_id = current_user.primary_location_id
    
    try:
        from app.models.transaction import Transaction, TransactionStatus
        
        filters = AnalyticsFilters(
            date_range=date_range,
            location_id=location_id,
            start_date=start_date,
            end_date=end_date
        )
        
        start_date_filter, end_date_filter = crud_analytics._get_date_range_filter(filters)
        
        # Base query for successful transactions with location filter
        base_query = db.query(Transaction).filter(
            Transaction.status == TransactionStatus.PAID
        )
        if filters.location_id:
            base_query = base_query.filter(Transaction.location_id == filters.location_id)
        
        # Group by date for trend data
        from sqlalchemy import func
        results = base_query.filter(
            Transaction.created_at >= start_date_filter,
            Transaction.created_at <= end_date_filter
        ).with_entities(
            func.date(Transaction.created_at).label('date'),
            func.sum(Transaction.amount).label('total_revenue'),
            func.count(Transaction.id).label('transaction_count')
        ).group_by(
            func.date(Transaction.created_at)
        ).all()
        
        # Convert to trend data points
        trend_data = [
            {
                "date": result.date.isoformat(),
                "total_revenue": float(result.total_revenue or 0),
                "transaction_count": result.transaction_count,
                "application_fees": float(result.total_revenue or 0) * 0.6,  # Estimated breakdown
                "card_fees": float(result.total_revenue or 0) * 0.3,
                "other_fees": float(result.total_revenue or 0) * 0.1
            }
            for result in results
        ]
        
        return ChartDataResponse(
            success=True,
            data=trend_data,
            metadata={
                "total_records": len(trend_data),
                "date_range": date_range,
                "location_id": location_id,
                "currency": "MGA"
            }
        )
        
    except Exception as e:
        logger.error(f"Error fetching financial trends: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch financial trends"
        )


@router.get("/export/{export_id}/status", response_model=AnalyticsResponse)
async def get_export_status(
    export_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get export status (placeholder for future implementation)"""
    if not check_analytics_access(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    # In a real implementation, this would check the export job status
    export_status = ExportStatus(
        export_id=export_id,
        status="completed",
        download_url=f"/api/v1/analytics/export/{export_id}/download",
        estimated_completion=None,
        progress_percentage=100
    )
    
    return AnalyticsResponse(
        success=True,
        data=export_status
    )
