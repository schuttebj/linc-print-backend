"""
Pydantic schemas for request/response validation
"""

# Person schemas
from app.schemas.person import (
    PersonBase, PersonCreate, PersonUpdate, PersonResponse,
    PersonSummary, PersonSearchRequest, PersonDuplicateCheckResponse,
    PersonAliasCreate, PersonAliasUpdate, PersonAliasResponse,
    PersonAddressCreate, PersonAddressUpdate, PersonAddressResponse
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

# Biometric schemas
from app.schemas.biometric import (
    FingerprintEnrollRequest, FingerprintEnrollResponse,
    FingerprintVerifyRequest, FingerprintVerifyResponse,
    FingerprintIdentifyRequest, FingerprintIdentifyResponse,
    FingerprintTemplateInfo, BiometricSystemStats
) 