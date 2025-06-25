"""
Location Management Endpoints for Madagascar License System
Handles location CRUD operations, search, and user code generation
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
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
    
    # Calculate skip for pagination
    skip = (page - 1) * per_page
    
    # Call CRUD method with individual parameters
    locations, total = crud_location.search_locations(
        db=db,
        search=search,
        province_code=province_code.value if province_code else None,
        office_type=office_type.value if office_type else None,
        is_operational=is_operational,
        skip=skip,
        limit=per_page
    )
    
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


@router.get("/next-code/{province_code}", summary="Generate Next Sequential Location Code")
async def get_next_location_code(
    province_code: ProvinceCodeEnum,
    current_user: User = Depends(require_permission("locations.create")),
    db: Session = Depends(get_db)
):
    """
    Generate the next sequential location code for a province
    Returns the next available code like T01, T02, A01, etc.
    """
    try:
        # Get all locations for this province
        existing_locations = crud_location.get_by_province(
            db=db, 
            province_code=province_code.value,
            skip=0,
            limit=1000
        )
        
        # Extract numbers from existing codes
        existing_numbers = []
        for location in existing_locations:
            if location.code and location.code.startswith(province_code.value):
                try:
                    # Extract number part from codes like T01, T02, etc.
                    number_part = location.code[1:]  # Remove province letter
                    existing_numbers.append(int(number_part))
                except ValueError:
                    # Skip invalid codes
                    continue
        
        # Find next available number
        next_number = 1
        if existing_numbers:
            existing_numbers.sort()
            # Find the first gap or increment from the highest
            for i, num in enumerate(existing_numbers):
                if i + 1 != num:
                    next_number = i + 1
                    break
            else:
                next_number = max(existing_numbers) + 1
        
        # Format as two digits with leading zero
        next_code = f"{province_code.value}{next_number:02d}"
        
        return {
            "code": next_code,
            "province_code": province_code.value,
            "sequence_number": next_number,
            "existing_count": len(existing_numbers)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate next location code: {str(e)}"
        )


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
    Get location by code (e.g., T01, MG-T01)
    """
    # Handle both short code (T01) and full code (MG-T01)
    if location_code.startswith("MG-"):
        location = crud_location.get_by_full_code(db=db, full_code=location_code)
    else:
        location = crud_location.get_by_code(db=db, code=location_code)
    
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Location with code '{location_code}' not found"
        )
    
    # Log location access
    log_user_action(
        db, current_user, "location_accessed_by_code", request,
        details={"location_code": location_code, "location_id": str(location.id)}
    )
    
    return LocationResponse.from_orm(location)


# ENHANCED LOCATION MANAGEMENT - Madagascar Analysis Requirements

@router.get("/province/{province_code}/statistics", summary="Get Province Location Statistics")
async def get_province_location_statistics(
    province_code: ProvinceCodeEnum,
    request: Request = Request,
    current_user: User = Depends(require_permission("locations.view_statistics")),
    db: Session = Depends(get_db)
):
    """
    Get detailed location statistics for a specific province
    (For Traffic Department Head oversight)
    """
    from app.models.user import User as UserModel
    
    # Get all locations in this province
    locations = crud_location.get_by_province(
        db=db, 
        province_code=province_code.value, 
        skip=0, 
        limit=1000
    )
    
    # Calculate province statistics
    total_locations = len(locations)
    operational_locations = len([l for l in locations if l.is_operational])
    
    # Office type breakdown
    office_types = {}
    for location in locations:
        office_types[location.office_type] = office_types.get(location.office_type, 0) + 1
    
    # Capacity analysis
    total_capacity = sum(l.max_staff_capacity for l in locations)
    current_staff = sum(l.current_staff_count for l in locations)
    daily_capacity = sum(l.max_daily_capacity for l in locations)
    
    # Service capability analysis
    accepts_applications = len([l for l in locations if l.accepts_applications])
    accepts_renewals = len([l for l in locations if l.accepts_renewals])
    accepts_collections = len([l for l in locations if l.accepts_collections])
    
    # User distribution
    province_users = db.query(UserModel).filter(
        UserModel.is_active == True,
        UserModel.province == province_code.value
    ).count()
    
    # Location details
    location_details = []
    for location in locations:
        location_details.append({
            "id": str(location.id),
            "name": location.name,
            "code": location.code,
            "locality": location.locality,
            "office_type": location.office_type,
            "is_operational": location.is_operational,
            "staff_count": location.current_staff_count,
            "staff_capacity": location.max_staff_capacity,
            "daily_capacity": location.max_daily_capacity,
            "utilization": (location.current_staff_count / location.max_staff_capacity * 100) if location.max_staff_capacity > 0 else 0,
            "services": {
                "applications": location.accepts_applications,
                "renewals": location.accepts_renewals,
                "collections": location.accepts_collections
            }
        })
    
    # Log access
    log_user_action(
        db, current_user, "province_location_statistics_accessed", request,
        details={"province_code": province_code.value, "total_locations": total_locations}
    )
    
    return {
        "province_code": province_code.value,
        "province_name": {
            "T": "ANTANANARIVO",
            "A": "TOAMASINA", 
            "D": "ANTSIRANANA",
            "F": "FIANARANTSOA",
            "M": "MAHAJANGA",
            "U": "TOLIARA"
        }.get(province_code.value, "UNKNOWN"),
        "summary": {
            "total_locations": total_locations,
            "operational_locations": operational_locations,
            "total_staff_capacity": total_capacity,
            "current_staff": current_staff,
            "total_daily_capacity": daily_capacity,
            "capacity_utilization": round((current_staff / total_capacity * 100) if total_capacity > 0 else 0, 2),
            "province_users": province_users
        },
        "service_coverage": {
            "accepts_applications": accepts_applications,
            "accepts_renewals": accepts_renewals,
            "accepts_collections": accepts_collections,
            "coverage_percentage": round((operational_locations / total_locations * 100) if total_locations > 0 else 0, 2)
        },
        "office_types": office_types,
        "locations": location_details
    }


@router.post("/province/{province_code}/validate-expansion", summary="Validate Province Expansion Plan")
async def validate_province_expansion(
    province_code: ProvinceCodeEnum,
    expansion_plan: Dict[str, Any],
    request: Request = Request,
    current_user: User = Depends(require_permission("locations.create")),
    db: Session = Depends(get_db)
):
    """
    Validate a province expansion plan for new offices
    (For Traffic Department Head planning)
    """
    # Get current locations in province
    current_locations = crud_location.get_by_province(
        db=db, 
        province_code=province_code.value,
        skip=0,
        limit=1000
    )
    
    current_office_numbers = {loc.office_number for loc in current_locations}
    
    # Validate proposed new offices
    validation_results = []
    proposed_offices = expansion_plan.get("new_offices", [])
    
    for office in proposed_offices:
        office_number = office.get("office_number")
        office_name = office.get("name")
        locality = office.get("locality")
        
        validation = {
            "office_number": office_number,
            "name": office_name,
            "locality": locality,
            "is_valid": True,
            "issues": []
        }
        
        # Check if office number is already used
        if office_number in current_office_numbers:
            validation["is_valid"] = False
            validation["issues"].append(f"Office number {office_number} already exists in {province_code.value}")
        
        # Check office number format
        if not office_number or len(office_number) != 2 or not office_number.isdigit():
            validation["is_valid"] = False
            validation["issues"].append("Office number must be 2 digits (01-99)")
        
        # Check for duplicate localities
        existing_localities = {loc.locality.upper() for loc in current_locations}
        if locality and locality.upper() in existing_localities:
            validation["issues"].append(f"Warning: Locality '{locality}' already has an office")
        
        validation_results.append(validation)
    
    # Overall validation summary
    valid_offices = [v for v in validation_results if v["is_valid"]]
    total_proposed = len(proposed_offices)
    
    # Calculate capacity impact
    total_new_capacity = sum(office.get("max_staff_capacity", 10) for office in proposed_offices if office.get("office_number") not in current_office_numbers)
    current_capacity = sum(loc.max_staff_capacity for loc in current_locations)
    
    # Log validation
    log_user_action(
        db, current_user, "province_expansion_validated", request,
        details={
            "province_code": province_code.value,
            "proposed_offices": total_proposed,
            "valid_offices": len(valid_offices)
        }
    )
    
    return {
        "province_code": province_code.value,
        "validation_summary": {
            "total_proposed": total_proposed,
            "valid_offices": len(valid_offices),
            "invalid_offices": total_proposed - len(valid_offices),
            "can_proceed": len(valid_offices) > 0
        },
        "capacity_impact": {
            "current_capacity": current_capacity,
            "additional_capacity": total_new_capacity,
            "total_capacity_after": current_capacity + total_new_capacity,
            "capacity_increase_percentage": round((total_new_capacity / current_capacity * 100) if current_capacity > 0 else 0, 2)
        },
        "validation_results": validation_results,
        "next_available_numbers": [f"{i:02d}" for i in range(1, 100) if f"{i:02d}" not in current_office_numbers][:10]
    }


@router.get("/capacity-analysis", summary="Get System-wide Capacity Analysis")
async def get_capacity_analysis(
    request: Request = Request,
    current_user: User = Depends(require_permission("locations.view_statistics")),
    db: Session = Depends(get_db)
):
    """
    Get system-wide capacity analysis across all provinces
    (For National Admin oversight)
    """
    from app.models.user import User as UserModel
    
    # Get all locations
    all_locations = crud_location.get_multi(db=db, skip=0, limit=1000)
    
    # Province-level analysis
    province_analysis = {}
    total_system_capacity = 0
    total_system_staff = 0
    total_system_daily_capacity = 0
    
    provinces = ["T", "A", "D", "F", "M", "U"]
    province_names = {
        "T": "ANTANANARIVO",
        "A": "TOAMASINA", 
        "D": "ANTSIRANANA",
        "F": "FIANARANTSOA",
        "M": "MAHAJANGA",
        "U": "TOLIARA"
    }
    
    for province_code in provinces:
        province_locations = [l for l in all_locations if l.province_code == province_code]
        
        if province_locations:
            staff_capacity = sum(l.max_staff_capacity for l in province_locations)
            current_staff = sum(l.current_staff_count for l in province_locations)
            daily_capacity = sum(l.max_daily_capacity for l in province_locations)
            operational = len([l for l in province_locations if l.is_operational])
            
            # Get user count for this province
            province_users = db.query(UserModel).filter(
                UserModel.is_active == True,
                UserModel.province == province_code
            ).count()
            
            province_analysis[province_code] = {
                "name": province_names[province_code],
                "locations": len(province_locations),
                "operational_locations": operational,
                "staff_capacity": staff_capacity,
                "current_staff": current_staff,
                "daily_capacity": daily_capacity,
                "users": province_users,
                "utilization": round((current_staff / staff_capacity * 100) if staff_capacity > 0 else 0, 2),
                "coverage": round((operational / len(province_locations) * 100) if province_locations else 0, 2)
            }
            
            total_system_capacity += staff_capacity
            total_system_staff += current_staff
            total_system_daily_capacity += daily_capacity
    
    # Office type distribution
    office_type_stats = {}
    for location in all_locations:
        office_type_stats[location.office_type] = office_type_stats.get(location.office_type, 0) + 1
    
    # Service coverage analysis
    service_stats = {
        "applications": len([l for l in all_locations if l.accepts_applications]),
        "renewals": len([l for l in all_locations if l.accepts_renewals]),
        "collections": len([l for l in all_locations if l.accepts_collections])
    }
    
    # Log access
    log_user_action(
        db, current_user, "system_capacity_analysis_accessed", request,
        details={"total_locations": len(all_locations)}
    )
    
    return {
        "system_summary": {
            "total_locations": len(all_locations),
            "operational_locations": len([l for l in all_locations if l.is_operational]),
            "total_staff_capacity": total_system_capacity,
            "current_staff": total_system_staff,
            "total_daily_capacity": total_system_daily_capacity,
            "system_utilization": round((total_system_staff / total_system_capacity * 100) if total_system_capacity > 0 else 0, 2)
        },
        "province_analysis": province_analysis,
        "office_type_distribution": office_type_stats,
        "service_coverage": service_stats,
        "capacity_recommendations": {
            "underutilized_provinces": [
                code for code, data in province_analysis.items() 
                if data["utilization"] < 50 and data["staff_capacity"] > 0
            ],
            "overutilized_provinces": [
                code for code, data in province_analysis.items() 
                if data["utilization"] > 90
            ],
            "expansion_candidates": [
                code for code, data in province_analysis.items() 
                if data["locations"] < 5 and data["utilization"] > 80
            ]
        }
    } 