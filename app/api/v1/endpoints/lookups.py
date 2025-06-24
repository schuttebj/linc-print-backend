"""
Lookup Endpoints for Madagascar License System
Provides standardized dropdown data from backend enums
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends

from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.enums import (
    MadagascarIDType, PersonNature, AddressType, LanguageCode,
    NationalityCode, PhoneCountryCode, CountryCode, ProvinceCode,
    PROVINCE_DISPLAY_NAMES, LANGUAGE_DISPLAY_NAMES, NATIONALITY_DISPLAY_NAMES,
    PHONE_COUNTRY_DISPLAY_NAMES, COUNTRY_DISPLAY_NAMES, DOCUMENT_TYPE_INFO,
    PERSON_NATURE_DISPLAY_NAMES
)

router = APIRouter()


@router.get("/document-types", response_model=List[Dict[str, Any]])
async def get_document_types(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    """Get all available document types with display information"""
    return [
        {
            "value": doc_type.value,
            "label": DOCUMENT_TYPE_INFO[doc_type]["label"],
            "requires_expiry": DOCUMENT_TYPE_INFO[doc_type]["requires_expiry"]
        }
        for doc_type in MadagascarIDType
    ]


@router.get("/person-natures", response_model=List[Dict[str, str]])
async def get_person_natures(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, str]]:
    """Get all available person nature/gender options"""
    return [
        {
            "value": nature.value,
            "label": PERSON_NATURE_DISPLAY_NAMES[nature]
        }
        for nature in PersonNature
    ]


@router.get("/address-types", response_model=List[Dict[str, str]])
async def get_address_types(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, str]]:
    """Get all available address types"""
    return [
        {
            "value": addr_type.value,
            "label": addr_type.value.title()
        }
        for addr_type in AddressType
    ]


@router.get("/languages", response_model=List[Dict[str, str]])
async def get_languages(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, str]]:
    """Get all supported languages"""
    return [
        {
            "value": lang.value,
            "label": LANGUAGE_DISPLAY_NAMES[lang]
        }
        for lang in LanguageCode
    ]


@router.get("/nationalities", response_model=List[Dict[str, str]])
async def get_nationalities(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, str]]:
    """Get all supported nationality codes"""
    return [
        {
            "value": nationality.value,
            "label": NATIONALITY_DISPLAY_NAMES[nationality]
        }
        for nationality in NationalityCode
    ]


@router.get("/phone-country-codes", response_model=List[Dict[str, str]])
async def get_phone_country_codes(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, str]]:
    """Get all supported phone country codes"""
    return [
        {
            "value": code.value,
            "label": f"{code.value} ({PHONE_COUNTRY_DISPLAY_NAMES[code]})"
        }
        for code in PhoneCountryCode
    ]


@router.get("/countries", response_model=List[Dict[str, str]])
async def get_countries(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, str]]:
    """Get all supported country codes"""
    return [
        {
            "value": country.value,
            "label": COUNTRY_DISPLAY_NAMES[country]
        }
        for country in CountryCode
    ]


@router.get("/provinces", response_model=List[Dict[str, str]])
async def get_provinces(
    current_user: User = Depends(get_current_user)
) -> List[Dict[str, str]]:
    """Get all Madagascar province codes"""
    return [
        {
            "code": province.value,
            "name": PROVINCE_DISPLAY_NAMES[province]
        }
        for province in ProvinceCode
    ]


@router.get("/all", response_model=Dict[str, Any])
async def get_all_lookups(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get all lookup data in a single request for efficiency"""
    return {
        "document_types": [
            {
                "value": doc_type.value,
                "label": DOCUMENT_TYPE_INFO[doc_type]["label"],
                "requires_expiry": DOCUMENT_TYPE_INFO[doc_type]["requires_expiry"]
            }
            for doc_type in MadagascarIDType
        ],
        "person_natures": [
            {
                "value": nature.value,
                "label": PERSON_NATURE_DISPLAY_NAMES[nature]
            }
            for nature in PersonNature
        ],
        "address_types": [
            {
                "value": addr_type.value,
                "label": addr_type.value.title()
            }
            for addr_type in AddressType
        ],
        "languages": [
            {
                "value": lang.value,
                "label": LANGUAGE_DISPLAY_NAMES[lang]
            }
            for lang in LanguageCode
        ],
        "nationalities": [
            {
                "value": nationality.value,
                "label": NATIONALITY_DISPLAY_NAMES[nationality]
            }
            for nationality in NationalityCode
        ],
        "phone_country_codes": [
            {
                "value": code.value,
                "label": f"{code.value} ({PHONE_COUNTRY_DISPLAY_NAMES[code]})"
            }
            for code in PhoneCountryCode
        ],
        "countries": [
            {
                "value": country.value,
                "label": COUNTRY_DISPLAY_NAMES[country]
            }
            for country in CountryCode
        ],
        "provinces": [
            {
                "code": province.value,
                "name": PROVINCE_DISPLAY_NAMES[province]
            }
            for province in ProvinceCode
        ]
    } 