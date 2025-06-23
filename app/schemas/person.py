"""
Person Management Schemas - Madagascar Implementation
Pydantic schemas for API request/response validation
Simplified for Madagascar natural persons only
"""

from pydantic import BaseModel, Field, validator, EmailStr
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID
import re


# Enums for validation
class IdentificationType(str):
    MADAGASCAR_ID = "MG_ID"
    PASSPORT = "PASSPORT"


class PersonNature(str):
    MALE = "01"
    FEMALE = "02"


class AddressType(str):
    RESIDENTIAL = "residential"
    POSTAL = "postal"


# Base schemas
class PersonAliasBase(BaseModel):
    """Base schema for person identification documents"""
    document_type: str = Field(..., description="Document type: MG_ID or PASSPORT")
    document_number: str = Field(..., min_length=1, max_length=50, description="ID/passport number")
    country_of_issue: str = Field(default="MG", max_length=3, description="Country code of issuing country")
    name_in_document: Optional[str] = Field(None, max_length=200, description="Name as appears in document")
    is_primary: bool = Field(default=False, description="Primary identification document")
    is_current: bool = Field(default=True, description="Current/active document")
    issue_date: Optional[date] = Field(None, description="Document issue date")
    expiry_date: Optional[date] = Field(None, description="Document expiry date (required for passports)")

    @validator('document_type')
    def validate_document_type(cls, v):
        if v not in [IdentificationType.MADAGASCAR_ID, IdentificationType.PASSPORT]:
            raise ValueError('Document type must be MG_ID or PASSPORT')
        return v

    @validator('expiry_date')
    def validate_passport_expiry(cls, v, values):
        if values.get('document_type') == IdentificationType.PASSPORT and not v:
            raise ValueError('Expiry date is required for passport documents')
        return v

    @validator('document_number')
    def validate_document_number(cls, v, values):
        """
        TODO: Add Madagascar-specific ID validation rules
        - Madagascar ID format validation
        - Passport format validation by country
        """
        if not v or len(v.strip()) == 0:
            raise ValueError('Document number cannot be empty')
        return v.strip().upper()


class PersonAliasCreate(PersonAliasBase):
    """Schema for creating person aliases/documents"""
    pass


class PersonAliasUpdate(BaseModel):
    """Schema for updating person aliases/documents"""
    document_type: Optional[str] = None
    document_number: Optional[str] = None
    country_of_issue: Optional[str] = None
    name_in_document: Optional[str] = None
    is_primary: Optional[bool] = None
    is_current: Optional[bool] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None


class PersonAliasResponse(PersonAliasBase):
    """Schema for person alias responses"""
    id: UUID
    person_id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    updated_by: Optional[str] = None

    class Config:
        from_attributes = True


class PersonAddressBase(BaseModel):
    """Base schema for person addresses"""
    address_type: str = Field(..., description="Address type: residential or postal")
    is_primary: bool = Field(default=False, description="Primary address of this type")
    street_line1: Optional[str] = Field(None, max_length=100, description="Lot/parcel details or P.O. Box")
    street_line2: Optional[str] = Field(None, max_length=100, description="Additional street detail or neighborhood")
    locality: str = Field(..., max_length=100, description="Village, quartier, city")
    postal_code: str = Field(..., min_length=3, max_length=3, description="3-digit Madagascar postal code")
    town: str = Field(..., max_length=100, description="Town/city name for postal delivery")
    country: str = Field(default="MADAGASCAR", max_length=50, description="Country name")
    province_code: Optional[str] = Field(None, max_length=10, description="Madagascar province/region code")
    is_verified: bool = Field(default=False, description="Address verified by postal service")

    @validator('address_type')
    def validate_address_type(cls, v):
        if v not in [AddressType.RESIDENTIAL, AddressType.POSTAL]:
            raise ValueError('Address type must be residential or postal')
        return v

    @validator('postal_code')
    def validate_postal_code(cls, v):
        """Validate Madagascar postal code format (3 digits)"""
        if not re.match(r'^\d{3}$', v):
            raise ValueError('Madagascar postal code must be exactly 3 digits')
        return v

    @validator('locality', 'town')
    def validate_required_fields(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('This field cannot be empty')
        return v.strip()


class PersonAddressCreate(PersonAddressBase):
    """Schema for creating person addresses"""
    pass


class PersonAddressUpdate(BaseModel):
    """Schema for updating person addresses"""
    address_type: Optional[str] = None
    is_primary: Optional[bool] = None
    street_line1: Optional[str] = None
    street_line2: Optional[str] = None
    locality: Optional[str] = None
    postal_code: Optional[str] = None
    town: Optional[str] = None
    country: Optional[str] = None
    province_code: Optional[str] = None
    is_verified: Optional[bool] = None


class PersonAddressResponse(PersonAddressBase):
    """Schema for person address responses"""
    id: UUID
    person_id: UUID
    verified_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    formatted_address: str

    class Config:
        from_attributes = True


class PersonBase(BaseModel):
    """Base schema for person data"""
    surname: str = Field(..., min_length=1, max_length=50, description="Family name/surname")
    first_name: str = Field(..., min_length=1, max_length=50, description="First/given name")
    middle_name: Optional[str] = Field(None, max_length=50, description="Middle name(s)")
    person_nature: str = Field(..., description="Person nature: 01=Male, 02=Female")
    birth_date: Optional[date] = Field(None, description="Date of birth")
    nationality_code: str = Field(default="MG", max_length=3, description="Country code (MG=Madagascar)")
    preferred_language: str = Field(default="mg", max_length=10, description="mg=Malagasy, fr=French, en=English")
    email_address: Optional[EmailStr] = Field(None, description="Email address")
    work_phone: Optional[str] = Field(None, max_length=20, description="Work phone number")
    cell_phone_country_code: str = Field(default="+261", max_length=5, description="Cell phone country code")
    cell_phone: Optional[str] = Field(None, max_length=15, description="Cell phone number (local format)")
    is_active: bool = Field(default=True, description="Active status")

    @validator('person_nature')
    def validate_person_nature(cls, v):
        if v not in [PersonNature.MALE, PersonNature.FEMALE]:
            raise ValueError('Person nature must be 01 (Male) or 02 (Female)')
        return v

    @validator('surname', 'first_name')
    def validate_required_names(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('This field cannot be empty')
        return v.strip().title()

    @validator('middle_name')
    def validate_middle_name(cls, v):
        if v:
            return v.strip().title()
        return v

    @validator('preferred_language')
    def validate_language(cls, v):
        valid_languages = ['mg', 'fr', 'en']  # Malagasy, French, English
        if v not in valid_languages:
            raise ValueError('Language must be mg (Malagasy), fr (French), or en (English)')
        return v

    @validator('cell_phone')
    def validate_cell_phone(cls, v, values):
        """
        Validate Madagascar phone number format
        Local: 0AA BB BB BBB (10 digits)
        TODO: Add comprehensive Madagascar phone validation
        """
        if v:
            # Remove spaces and dashes
            cleaned = re.sub(r'[\s\-]', '', v)
            if not re.match(r'^0\d{9}$', cleaned):
                raise ValueError('Madagascar cell phone must be 10 digits starting with 0 (format: 0AA BB BB BBB)')
            return cleaned
        return v

    @validator('work_phone')
    def validate_work_phone(cls, v):
        """TODO: Add work phone validation (landline format may differ)"""
        if v:
            # Basic validation for now
            cleaned = re.sub(r'[\s\-\+]', '', v)
            if len(cleaned) < 7 or len(cleaned) > 15:
                raise ValueError('Work phone must be between 7 and 15 digits')
            return v.strip()
        return v


class PersonCreate(PersonBase):
    """Schema for creating persons"""
    aliases: Optional[List[PersonAliasCreate]] = Field(default=[], description="Initial identification documents")
    addresses: Optional[List[PersonAddressCreate]] = Field(default=[], description="Initial addresses")

    @validator('aliases')
    def validate_aliases(cls, v):
        """Ensure at least one primary document and no duplicate primaries"""
        if not v:
            return v
        
        primary_count = sum(1 for alias in v if alias.is_primary)
        if primary_count == 0:
            raise ValueError('At least one identification document must be marked as primary')
        if primary_count > 1:
            raise ValueError('Only one identification document can be marked as primary')
        return v

    @validator('addresses')
    def validate_addresses(cls, v):
        """Validate address primary constraints per type"""
        if not v:
            return v
        
        # Check for multiple primaries per address type
        residential_primaries = sum(1 for addr in v if addr.address_type == AddressType.RESIDENTIAL and addr.is_primary)
        postal_primaries = sum(1 for addr in v if addr.address_type == AddressType.POSTAL and addr.is_primary)
        
        if residential_primaries > 1:
            raise ValueError('Only one residential address can be marked as primary')
        if postal_primaries > 1:
            raise ValueError('Only one postal address can be marked as primary')
        
        return v


class PersonUpdate(BaseModel):
    """Schema for updating persons"""
    surname: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    person_nature: Optional[str] = None
    birth_date: Optional[date] = None
    nationality_code: Optional[str] = None
    preferred_language: Optional[str] = None
    email_address: Optional[EmailStr] = None
    work_phone: Optional[str] = None
    cell_phone_country_code: Optional[str] = None
    cell_phone: Optional[str] = None
    is_active: Optional[bool] = None


class PersonResponse(PersonBase):
    """Schema for person responses"""
    id: UUID
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    aliases: List[PersonAliasResponse] = []
    addresses: List[PersonAddressResponse] = []

    class Config:
        from_attributes = True


class PersonSummary(BaseModel):
    """Schema for person summary (list views)"""
    id: UUID
    surname: str
    first_name: str
    middle_name: Optional[str] = None
    person_nature: str
    birth_date: Optional[date] = None
    nationality_code: str
    is_active: bool
    primary_document: Optional[str] = None  # Primary document number
    primary_document_type: Optional[str] = None  # Primary document type

    class Config:
        from_attributes = True


class PersonSearchRequest(BaseModel):
    """Schema for person search requests"""
    surname: Optional[str] = Field(None, description="Search by surname (partial match)")
    first_name: Optional[str] = Field(None, description="Search by first name (partial match)")
    document_number: Optional[str] = Field(None, description="Search by document number (exact match)")
    document_type: Optional[str] = Field(None, description="Filter by document type")
    birth_date: Optional[date] = Field(None, description="Search by birth date (exact match)")
    nationality_code: Optional[str] = Field(None, description="Filter by nationality")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    locality: Optional[str] = Field(None, description="Search by address locality (partial match)")
    phone_number: Optional[str] = Field(None, description="Search by phone number (partial match)")
    
    # Pagination
    skip: int = Field(default=0, ge=0, description="Number of records to skip")
    limit: int = Field(default=50, ge=1, le=100, description="Number of records to return")


class PersonDuplicateCheckResponse(BaseModel):
    """
    Schema for duplicate detection results
    TODO: Implement when duplicate detection service is ready
    """
    person_id: UUID
    potential_duplicates: List[dict]  # Will contain person summaries with similarity scores
    similarity_threshold: float = 70.0

    class Config:
        from_attributes = True


# TODO: Add bulk import schemas when needed
# class PersonBulkImportRequest(BaseModel):
#     """Schema for bulk person import"""
#     persons: List[PersonCreate]
#     validate_duplicates: bool = True
#     duplicate_threshold: float = 70.0

# class PersonBulkImportResponse(BaseModel):
#     """Schema for bulk import results"""
#     successful_imports: int
#     failed_imports: int
#     duplicate_warnings: List[dict]
#     errors: List[dict] 