"""
Lookup Endpoints for Madagascar License System
Provides standardized dropdown data from backend enums
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.application import FeeStructure
from app.models.enums import (
    MadagascarIDType, PersonNature, AddressType, LanguageCode,
    NationalityCode, PhoneCountryCode, CountryCode, ProvinceCode,
    UserStatus, OfficeType, UserType, LicenseCategory, ApplicationType,
    ApplicationStatus,
    PROVINCE_DISPLAY_NAMES, LANGUAGE_DISPLAY_NAMES, NATIONALITY_DISPLAY_NAMES,
    PHONE_COUNTRY_DISPLAY_NAMES, COUNTRY_DISPLAY_NAMES, DOCUMENT_TYPE_INFO,
    PERSON_NATURE_DISPLAY_NAMES, OFFICE_TYPE_DISPLAY_NAMES,
    USER_STATUS_DISPLAY_NAMES, USER_TYPE_DISPLAY_NAMES
)

router = APIRouter()


@router.get("/document-types", response_model=List[Dict[str, Any]])
async def get_document_types() -> List[Dict[str, Any]]:
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
async def get_person_natures() -> List[Dict[str, str]]:
    """Get all available person nature/gender options"""
    return [
        {
            "value": nature.value,
            "label": PERSON_NATURE_DISPLAY_NAMES[nature]
        }
        for nature in PersonNature
    ]


@router.get("/address-types", response_model=List[Dict[str, str]])
async def get_address_types() -> List[Dict[str, str]]:
    """Get all available address types"""
    return [
        {
            "value": addr_type.value,
            "label": addr_type.value.title()
        }
        for addr_type in AddressType
    ]


@router.get("/languages", response_model=List[Dict[str, str]])
async def get_languages() -> List[Dict[str, str]]:
    """Get all supported languages"""
    return [
        {
            "value": lang.value,
            "label": LANGUAGE_DISPLAY_NAMES[lang]
        }
        for lang in LanguageCode
    ]


@router.get("/nationalities", response_model=List[Dict[str, str]])
async def get_nationalities() -> List[Dict[str, str]]:
    """Get all supported nationality codes"""
    return [
        {
            "value": nationality.value,
            "label": NATIONALITY_DISPLAY_NAMES[nationality]
        }
        for nationality in NationalityCode
    ]


@router.get("/phone-country-codes", response_model=List[Dict[str, str]])
async def get_phone_country_codes() -> List[Dict[str, str]]:
    """Get all supported phone country codes"""
    return [
        {
            "value": code.value,
            "label": f"{code.value} ({PHONE_COUNTRY_DISPLAY_NAMES[code]})"
        }
        for code in PhoneCountryCode
    ]


@router.get("/countries", response_model=List[Dict[str, str]])
async def get_countries() -> List[Dict[str, str]]:
    """Get all supported country codes"""
    return [
        {
            "value": country.value,
            "label": COUNTRY_DISPLAY_NAMES[country]
        }
        for country in CountryCode
    ]


@router.get("/provinces", response_model=List[Dict[str, str]])
async def get_provinces() -> List[Dict[str, str]]:
    """Get all Madagascar province codes"""
    return [
        {
            "code": province.value,
            "name": PROVINCE_DISPLAY_NAMES[province]
        }
        for province in ProvinceCode
    ]


@router.get("/user-statuses", response_model=List[Dict[str, str]])
async def get_user_statuses() -> List[Dict[str, str]]:
    """Get all user status options"""
    return [
        {
            "value": status.value,
            "label": USER_STATUS_DISPLAY_NAMES[status]
        }
        for status in UserStatus
    ]


@router.get("/user-types", response_model=List[Dict[str, str]])
async def get_user_types() -> List[Dict[str, str]]:
    """Get all user type options"""
    return [
        {
            "value": user_type.value,
            "label": USER_TYPE_DISPLAY_NAMES[user_type]
        }
        for user_type in UserType
    ]


@router.get("/office-types", response_model=List[Dict[str, str]])
async def get_office_types() -> List[Dict[str, str]]:
    """Get all office type options"""
    return [
        {
            "value": office_type.value,
            "label": OFFICE_TYPE_DISPLAY_NAMES[office_type]
        }
        for office_type in OfficeType
    ]


@router.get("/license-categories", response_model=List[Dict[str, str]])
async def get_license_categories() -> List[Dict[str, str]]:
    """Get all available license categories"""
    return [
        {
            "value": category.value,
            "label": f"{category.value} - {category.value}" 
        }
        for category in LicenseCategory
    ]


@router.get("/application-types", response_model=List[Dict[str, str]])
async def get_application_types() -> List[Dict[str, str]]:
    """Get all available application types with user-friendly labels"""
    # Custom mapping for user-friendly labels
    type_labels = {
        ApplicationType.LEARNERS_PERMIT: "Learner's Licence Application",
        ApplicationType.NEW_LICENSE: "Driving Licence Application", 
        ApplicationType.CONVERSION: "Driving Licence Conversion",
        ApplicationType.RENEWAL: "Renew Driving Licence Card",
        ApplicationType.PROFESSIONAL_LICENSE: "Professional Driving Licence Application",
        ApplicationType.TEMPORARY_LICENSE: "Temporary Driving Licence Application",
        ApplicationType.FOREIGN_CONVERSION: "Convert Foreign Driving Licence",
        ApplicationType.INTERNATIONAL_PERMIT: "International Driving Permit Application",
        ApplicationType.REPLACEMENT: "Replace Driving Licence Card"
    }
    
    return [
        {
            "value": app_type.value,
            "label": type_labels.get(app_type, app_type.value.replace('_', ' ').title())
        }
        for app_type in ApplicationType
    ]


@router.get("/application-statuses", response_model=List[Dict[str, str]])
async def get_application_statuses() -> List[Dict[str, str]]:
    """Get all available application statuses"""
    return [
        {
            "value": status.value,
            "label": status.value.replace('_', ' ').title()
        }
        for status in ApplicationStatus
    ]


@router.get("/fee-structures", response_model=List[Dict[str, Any]])
async def get_fee_structures(db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    """Get all active fee structures for applications"""
    fee_structures = db.query(FeeStructure).filter(
        FeeStructure.is_active == True
    ).all()
    
    return [
        {
            "fee_type": fee.fee_type,
            "display_name": fee.display_name,
            "description": fee.description,
            "amount": float(fee.amount),
            "currency": fee.currency,
            "applies_to_categories": fee.applies_to_categories,
            "applies_to_application_types": fee.applies_to_application_types,
            "is_mandatory": fee.is_mandatory,
            "effective_from": fee.effective_from.isoformat() if fee.effective_from else None,
            "effective_until": fee.effective_until.isoformat() if fee.effective_until else None
        }
        for fee in fee_structures
    ]


# Equipment status endpoints removed - no longer needed for location management
# Location operational status is handled by the is_operational boolean field


@router.get("/all", response_model=Dict[str, Any])
async def get_all_lookups(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get all lookup data in a single request for efficiency"""
    
    # Get fee structures from database
    fee_structures = db.query(FeeStructure).filter(
        FeeStructure.is_active == True
    ).all()
    
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
        ],
        "user_statuses": [
            {
                "value": status.value,
                "label": USER_STATUS_DISPLAY_NAMES[status]
            }
            for status in UserStatus
        ],
        "user_types": [
            {
                "value": user_type.value,
                "label": USER_TYPE_DISPLAY_NAMES[user_type]
            }
            for user_type in UserType
        ],
        "office_types": [
            {
                "value": office_type.value,
                "label": OFFICE_TYPE_DISPLAY_NAMES[office_type]
            }
            for office_type in OfficeType
        ],
        "license_categories": [
            {
                "value": category.value,
                "label": f"{category.value} - {category.value}" 
            }
            for category in LicenseCategory
        ],
        "application_types": [
            {
                "value": app_type.value,
                "label": app_type.value.replace('_', ' ').title()
            }
            for app_type in ApplicationType
        ],
        "application_statuses": [
            {
                "value": status.value,
                "label": status.value.replace('_', ' ').title()
            }
            for status in ApplicationStatus
        ],
        "fee_structures": [
            {
                "fee_type": fee.fee_type,
                "display_name": fee.display_name,
                "description": fee.description,
                "amount": float(fee.amount),
                "currency": fee.currency,
                "applies_to_categories": fee.applies_to_categories,
                "applies_to_application_types": fee.applies_to_application_types,
                "is_mandatory": fee.is_mandatory,
                "effective_from": fee.effective_from.isoformat() if fee.effective_from else None,
                "effective_until": fee.effective_until.isoformat() if fee.effective_until else None
            }
            for fee in fee_structures
        ]
    } 