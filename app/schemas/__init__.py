"""
Pydantic schemas for request/response validation
"""

# Person schemas
from app.schemas.person import (
    PersonBase, PersonCreate, PersonUpdate, PersonResponse,
    PersonListResponse, PersonSearchRequest, PersonSearchResponse
)

# User schemas  
from app.schemas.user import (
    UserBase, UserCreate, UserUpdate, UserResponse, UserListResponse,
    UserSummary, UserQueryParams, LoginRequest, LoginResponse,
    UserStatusEnum, MadagascarIDTypeEnum
)

# Location schemas
from app.schemas.location import (
    LocationBase, LocationCreate, LocationUpdate, LocationResponse,
    LocationSummary, LocationListResponse, LocationStatsResponse,
    LocationQueryParams, UserCodeGenerationResponse,
    OfficeTypeEnum, ProvinceCodeEnum
) 