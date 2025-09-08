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
        
        # Get all KPI data
        applications_kpi = crud_analytics.get_application_kpi(db, filters)
        licenses_kpi = crud_analytics.get_license_kpi(db, filters)
        printing_kpi = crud_analytics.get_printing_kpi(db, filters)
        financial_kpi = crud_analytics.get_financial_kpi(db, filters)
        
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
