"""
Location Management Schemas for Madagascar License System
Handles location creation, updates, and responses
"""

from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List, Dict, Any
from enum import Enum
import uuid
from datetime import datetime

from app.models.enums import ProvinceCode, OfficeType


class DaySchedule(BaseModel):
    """Schema for individual day operational schedule"""
    day: str = Field(..., description="Day of the week")
    is_open: bool = Field(..., description="Whether location is open on this day")
    open_time: Optional[str] = Field(None, pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$", description="Opening time (HH:MM)")
    close_time: Optional[str] = Field(None, pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$", description="Closing time (HH:MM)")
    
    @validator('day')
    def validate_day(cls, v):
        valid_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        if v not in valid_days:
            raise ValueError(f'Day must be one of: {", ".join(valid_days)}')
        return v


class OfficeTypeEnum(str, Enum):
    """Office type enum for API"""
    MAIN = "MAIN"
    MOBILE = "MOBILE"
    TEMPORARY = "TEMPORARY"


class ProvinceCodeEnum(str, Enum):
    """Madagascar province code enum"""
    ANTANANARIVO = "T"
    ANTSIRANANA = "D"
    FIANARANTSOA = "F"
    MAHAJANGA = "M"
    TOAMASINA = "A"
    TOLIARA = "U"


class LocationBase(BaseModel):
    """Base location schema with common fields"""
    name: str = Field(..., min_length=1, max_length=200, description="Location name")
    province_code: ProvinceCodeEnum = Field(..., description="Madagascar province code")
    office_number: str = Field(..., min_length=2, max_length=2, pattern="^[0-9]{2}$", description="Office number (01-99)")
    office_type: OfficeTypeEnum = Field(default=OfficeTypeEnum.MAIN, description="Office type")
    
    # Address information
    locality: str = Field(..., min_length=1, max_length=100, description="City/town/locality")
    street_address: Optional[str] = Field(None, max_length=255, description="Street address")
    postal_code: Optional[str] = Field(None, max_length=10, description="Postal code")
    
    # Contact information
    phone_number: Optional[str] = Field(None, max_length=20, description="Office phone number")
    email: Optional[str] = Field(None, max_length=100, description="Office email address")
    manager_name: Optional[str] = Field(None, max_length=100, description="Office manager name")
    
    # Operational settings
    is_operational: bool = Field(default=True, description="Whether office is operational")
    accepts_applications: bool = Field(default=True, description="Accepts new applications")
    accepts_renewals: bool = Field(default=True, description="Accepts renewals")
    accepts_collections: bool = Field(default=True, description="Accepts collections")
    
    # Capacity settings
    max_daily_capacity: int = Field(default=50, ge=1, le=500, description="Maximum applications per day")
    max_staff_capacity: int = Field(default=10, ge=1, le=50, description="Maximum staff capacity")
    
    # Notes
    operating_hours: Optional[str] = Field(None, description="Legacy operating hours (JSON string)")
    operational_schedule: Optional[List[DaySchedule]] = Field(None, description="Structured operational schedule")
    special_notes: Optional[str] = Field(None, description="Special notes or instructions")

    @validator('name')
    def validate_name(cls, v):
        """Validate and capitalize location name"""
        return v.strip().upper()

    @validator('locality')
    def validate_locality(cls, v):
        """Validate and capitalize locality"""
        return v.strip().upper()

    @validator('street_address')
    def validate_street_address(cls, v):
        """Validate and capitalize street address"""
        if v:
            return v.strip().upper()
        return v

    @validator('manager_name')
    def validate_manager_name(cls, v):
        """Validate and capitalize manager name"""
        if v:
            return v.strip().upper()
        return v
    
    # operational_schedule serialization handled in CRUD layer for database storage


class LocationCreate(LocationBase):
    """Schema for creating a new location"""
    pass


class LocationUpdate(BaseModel):
    """Schema for updating location information"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    office_type: Optional[OfficeTypeEnum] = None
    
    # Address information
    locality: Optional[str] = Field(None, min_length=1, max_length=100)
    street_address: Optional[str] = Field(None, max_length=255)
    postal_code: Optional[str] = Field(None, max_length=10)
    
    # Contact information
    phone_number: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    manager_name: Optional[str] = Field(None, max_length=100)
    
    # Operational settings
    is_operational: Optional[bool] = None
    accepts_applications: Optional[bool] = None
    accepts_renewals: Optional[bool] = None
    accepts_collections: Optional[bool] = None
    
    # Capacity settings
    max_daily_capacity: Optional[int] = Field(None, ge=1, le=500)
    max_staff_capacity: Optional[int] = Field(None, ge=1, le=50)
    
    # Notes
    operating_hours: Optional[str] = None
    operational_schedule: Optional[List[DaySchedule]] = None
    special_notes: Optional[str] = None

    @validator('name')
    def validate_name(cls, v):
        if v:
            return v.strip().upper()
        return v

    @validator('locality')
    def validate_locality(cls, v):
        if v:
            return v.strip().upper()
        return v

    @validator('street_address')
    def validate_street_address(cls, v):
        if v:
            return v.strip().upper()
        return v

    @validator('manager_name')
    def validate_manager_name(cls, v):
        if v:
            return v.strip().upper()
        return v
    
    # operational_schedule validation handled in CRUD layer for JSON serialization


class LocationResponse(BaseModel):
    """Schema for location response"""
    id: uuid.UUID
    name: str
    code: str
    full_code: str
    province_code: str
    province_name: str
    office_number: str
    office_type: str
    
    # Address information
    locality: str
    street_address: Optional[str]
    postal_code: Optional[str]
    
    # Contact information
    phone_number: Optional[str]
    email: Optional[str]
    manager_name: Optional[str]
    
    # Operational settings
    is_operational: bool
    accepts_applications: bool
    accepts_renewals: bool
    accepts_collections: bool
    
    # Capacity information
    max_daily_capacity: int
    current_staff_count: int
    max_staff_capacity: int
    next_user_number: int
    
    # Timestamps
    created_at: datetime
    updated_at: datetime
    
    # Notes
    operating_hours: Optional[str]
    operational_schedule: Optional[List[DaySchedule]]
    special_notes: Optional[str]
    
    # Computed properties
    display_code: str
    user_code_prefix: str
    
    model_config = ConfigDict(from_attributes=True)
    
    @validator('operational_schedule', pre=True)
    def parse_operational_schedule(cls, v):
        """Parse operational schedule from JSON string to structured format"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                import json
                parsed = json.loads(v)
                return [DaySchedule(**day) for day in parsed] if parsed else None
            except (json.JSONDecodeError, TypeError, ValueError):
                return None
        return v


class LocationSummary(BaseModel):
    """Summary location information for lists and dropdowns"""
    id: uuid.UUID
    name: str
    code: str
    full_code: str
    province_name: str
    office_type: str
    locality: str
    is_operational: bool
    current_staff_count: int
    max_staff_capacity: int
    
    model_config = ConfigDict(from_attributes=True)


class LocationListResponse(BaseModel):
    """Schema for paginated location list response"""
    locations: List[LocationResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class LocationStatsResponse(BaseModel):
    """Location statistics response"""
    total_locations: int
    operational_locations: int
    locations_by_province: Dict[str, int]
    locations_by_type: Dict[str, int]
    total_staff_capacity: int
    total_current_staff: int
    capacity_utilization: float


class LocationQueryParams(BaseModel):
    """Query parameters for location search"""
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    search: Optional[str] = None
    province_code: Optional[ProvinceCodeEnum] = None
    office_type: Optional[OfficeTypeEnum] = None
    is_operational: Optional[bool] = None
    sort_by: str = Field(default="name")
    sort_order: str = Field(default="asc", pattern="^(asc|desc)$")


class UserCodeGenerationRequest(BaseModel):
    """Request to generate next user code for location"""
    location_id: uuid.UUID


class UserCodeGenerationResponse(BaseModel):
    """Response with generated user code"""
    location_id: uuid.UUID
    location_code: str
    next_user_code: str
    user_number: int
    remaining_capacity: int 