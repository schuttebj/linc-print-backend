"""
Location Management Endpoints for Madagascar License System
Handles location CRUD operations, search, and user code generation
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import math

from app.core.database import get_db
from app.models.user import User
from app.schemas.location import (
    LocationCreate, LocationUpdate, LocationResponse, LocationSummary,
    LocationListResponse, LocationStatsResponse, LocationQueryParams,
    UserCodeGenerationResponse, OfficeTypeEnum, ProvinceCodeEnum
)
from app.crud.crud_location import location as crud_location
from app.api.v1.endpoints.auth import get_current_user, log_user_action

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


@router.get("/", response_model=LocationListResponse, summary="List Locations")
async def list_locations(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term"),
    province_code: Optional[ProvinceCodeEnum] = Query(None, description="Filter by province"),
    office_type: Optional[OfficeTypeEnum] = Query(None, description="Filter by office type"),
    is_operational: Optional[bool] = Query(None, description="Filter by operational status"),
    sort_by: str = Query("name", description="Sort field"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="Sort order"),
    current_user: User = Depends(require_permission("locations.read")),
    db: Session = Depends(get_db)
):
    """
    Get paginated list of locations with filtering and search
    """
    search_params = LocationQueryParams(
        page=page,
        per_page=per_page,
        search=search,
        province_code=province_code,
        office_type=office_type,
        is_operational=is_operational,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    locations, total = crud_location.search_locations(db=db, search_params=search_params)
    
    # Calculate pagination info
    total_pages = math.ceil(total / per_page)
    
    # Log location list access
    log_user_action(
        db, current_user, "locations_list_accessed", request,
        details={
            "page": page,
            "per_page": per_page,
            "search": search,
            "filters": {
                "province_code": province_code.value if province_code else None,
                "office_type": office_type.value if office_type else None,
                "is_operational": is_operational
            },
            "total_results": total
        }
    )
    
    return LocationListResponse(
        locations=[LocationResponse.from_orm(location) for location in locations],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/summary", response_model=List[LocationSummary], summary="Get Location Summary")
async def get_locations_summary(
    operational_only: bool = Query(False, description="Only operational locations"),
    current_user: User = Depends(require_permission("locations.read")),
    db: Session = Depends(get_db)
):
    """
    Get location summary for dropdowns and selection lists
    """
    if operational_only:
        locations = crud_location.get_operational_locations(db=db)
    else:
        locations = crud_location.get_multi(db=db, skip=0, limit=1000)
    
    return [LocationSummary.from_orm(location) for location in locations]


@router.get("/statistics", response_model=LocationStatsResponse, summary="Get Location Statistics")
async def get_location_statistics(
    request: Request,
    current_user: User = Depends(require_permission("locations.read")),
    db: Session = Depends(get_db)
):
    """
    Get location statistics and metrics
    """
    stats = crud_location.get_location_statistics(db=db)
    
    # Log statistics access
    log_user_action(
        db, current_user, "location_statistics_accessed", request,
        details={"total_locations": stats["total_locations"]}
    )
    
    return LocationStatsResponse(**stats)


@router.get("/provinces", summary="Get Province Information")
async def get_provinces(
    current_user: User = Depends(require_permission("locations.read")),
    db: Session = Depends(get_db)
):
    """
    Get Madagascar province codes and names
    """
    provinces = [
        {"code": "T", "name": "ANTANANARIVO", "iso_code": "MG-T"},
        {"code": "D", "name": "ANTSIRANANA", "iso_code": "MG-D"},
        {"code": "F", "name": "FIANARANTSOA", "iso_code": "MG-F"},
        {"code": "M", "name": "MAHAJANGA", "iso_code": "MG-M"},
        {"code": "A", "name": "TOAMASINA", "iso_code": "MG-A"},
        {"code": "U", "name": "TOLIARA", "iso_code": "MG-U"}
    ]
    
    return {"provinces": provinces}


@router.get("/office-types", summary="Get Office Types")
async def get_office_types(
    current_user: User = Depends(require_permission("locations.read"))
):
    """
    Get available office types
    """
    office_types = [
        {"code": "MAIN", "name": "Main Office", "description": "Primary permanent office"},
        {"code": "MOBILE", "name": "Mobile Office", "description": "Mobile service unit"},
        {"code": "TEMPORARY", "name": "Temporary Office", "description": "Temporary service location"}
    ]
    
    return {"office_types": office_types}


@router.get("/{location_id}", response_model=LocationResponse, summary="Get Location")
async def get_location(
    location_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("locations.read")),
    db: Session = Depends(get_db)
):
    """
    Get location by ID
    """
    location = crud_location.get(db=db, id=location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    # Log location access
    log_user_action(
        db, current_user, "location_accessed", request,
        details={"location_id": str(location_id), "location_code": location.code}
    )
    
    return LocationResponse.from_orm(location)


@router.post("/", response_model=LocationResponse, summary="Create Location")
async def create_location(
    location_data: LocationCreate,
    request: Request,
    current_user: User = Depends(require_permission("locations.create")),
    db: Session = Depends(get_db)
):
    """
    Create new location
    """
    try:
        location = crud_location.create_with_codes(
            db=db,
            obj_in=location_data,
            created_by=str(current_user.id)
        )
        
        # Log location creation
        log_user_action(
            db, current_user, "location_created", request,
            details={
                "location_id": str(location.id),
                "location_code": location.code,
                "location_name": location.name
            }
        )
        
        return LocationResponse.from_orm(location)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create location: {str(e)}"
        )


@router.put("/{location_id}", response_model=LocationResponse, summary="Update Location")
async def update_location(
    location_id: uuid.UUID,
    location_data: LocationUpdate,
    request: Request,
    current_user: User = Depends(require_permission("locations.update")),
    db: Session = Depends(get_db)
):
    """
    Update location information
    """
    location = crud_location.get(db=db, id=location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    updated_location = crud_location.update(
        db=db,
        db_obj=location,
        obj_in=location_data,
        updated_by=str(current_user.id)
    )
    
    # Log location update
    log_user_action(
        db, current_user, "location_updated", request,
        details={
            "location_id": str(location_id),
            "location_code": updated_location.code,
            "changes": location_data.dict(exclude_unset=True)
        }
    )
    
    return LocationResponse.from_orm(updated_location)


@router.delete("/{location_id}", summary="Delete Location")
async def delete_location(
    location_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("locations.delete")),
    db: Session = Depends(get_db)
):
    """
    Soft delete location (set is_active=False)
    """
    location = crud_location.get(db=db, id=location_id)
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    # Check if location has active users
    if location.current_staff_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete location with active staff. Transfer staff first."
        )
    
    # Soft delete
    crud_location.update(
        db=db,
        db_obj=location,
        obj_in=LocationUpdate(is_operational=False),
        updated_by=str(current_user.id)
    )
    
    # Mark as inactive
    location.is_active = False
    db.commit()
    
    # Log location deletion
    log_user_action(
        db, current_user, "location_deleted", request,
        details={
            "location_id": str(location_id),
            "location_code": location.code,
            "location_name": location.name
        }
    )
    
    return {"message": "Location deleted successfully"}


@router.get("/{location_id}/generate-user-code", response_model=UserCodeGenerationResponse, summary="Generate User Code")
async def generate_user_code(
    location_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_permission("users.create")),
    db: Session = Depends(get_db)
):
    """
    Generate next user code for location
    """
    try:
        result = crud_location.generate_user_code(db=db, location_id=location_id)
        
        # Log user code generation
        log_user_action(
            db, current_user, "user_code_generated", request,
            details={
                "location_id": str(location_id),
                "generated_code": result["next_user_code"]
            }
        )
        
        return UserCodeGenerationResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/province/{province_code}", response_model=List[LocationResponse], summary="Get Locations by Province")
async def get_locations_by_province(
    province_code: ProvinceCodeEnum,
    current_user: User = Depends(require_permission("locations.read")),
    db: Session = Depends(get_db)
):
    """
    Get all locations in a specific province
    """
    locations = crud_location.get_by_province(db=db, province_code=province_code.value)
    return [LocationResponse.from_orm(location) for location in locations]


@router.get("/code/{location_code}", response_model=LocationResponse, summary="Get Location by Code")
async def get_location_by_code(
    location_code: str,
    request: Request,
    current_user: User = Depends(require_permission("locations.read")),
    db: Session = Depends(get_db)
):
    """
    Get location by code (e.g., T01 or MG-T01)
    """
    # Handle both formats (T01 and MG-T01)
    if location_code.startswith("MG-"):
        location = crud_location.get_by_full_code(db=db, full_code=location_code)
    else:
        location = crud_location.get_by_code(db=db, code=location_code)
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found"
        )
    
    # Log location access
    log_user_action(
        db, current_user, "location_accessed_by_code", request,
        details={"location_code": location_code, "location_id": str(location.id)}
    )
    
    return LocationResponse.from_orm(location) 