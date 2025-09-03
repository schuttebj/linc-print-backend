"""
Lookup Endpoints for Madagascar License System
Provides standardized dropdown data from backend enums
"""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.transaction import FeeStructure
from app.models.enums import (
    MadagascarIDType, PersonNature, AddressType, LanguageCode,
    NationalityCode, PhoneCountryCode, CountryCode, ProvinceCode,
    UserStatus, OfficeType, UserType, LicenseCategory, ApplicationType,
    ApplicationStatus, ProfessionalPermitCategory,
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


@router.get("/license-categories", response_model=List[Dict[str, Any]])
async def get_license_categories() -> List[Dict[str, Any]]:
    """Get all available license categories with descriptions"""
    # License category descriptions
    category_descriptions = {
        # Motorcycles
        LicenseCategory.A1: "Small motorcycles and mopeds (<125cc, 16+ years)",
        LicenseCategory.A2: "Mid-range motorcycles (power limited, up to 35kW, 18+ years)",
        LicenseCategory.A: "Unlimited motorcycles (no power restriction, 18+ years)",
        
        # Light Vehicles
        LicenseCategory.B1: "Light quadricycles (motorized tricycles/quadricycles, 16+ years)",
        LicenseCategory.B: "Standard passenger cars and light vehicles (up to 3.5t, 18+ years)",
        LicenseCategory.B2: "Taxis or commercial passenger vehicles (21+ years)",
        LicenseCategory.BE: "Category B with trailer exceeding 750kg (18+ years)",
        
        # Heavy Goods Vehicles
        LicenseCategory.C1: "Medium-sized goods vehicles (3.5-7.5t, 18+ years)",
        LicenseCategory.C: "Heavy goods vehicles (over 7.5t, 21+ years)",
        LicenseCategory.C1E: "C1 category vehicles with heavy trailer (18+ years)",
        LicenseCategory.CE: "Full heavy combination vehicles (21+ years)",
        
        # Passenger Transport
        LicenseCategory.D1: "Small buses (up to 16 passengers, 21+ years)",
        LicenseCategory.D: "Standard buses and coaches (over 16 passengers, 24+ years)",
        LicenseCategory.D2: "Specialized public transport (articulated buses, 24+ years)",
        
        # Learner's permits
        LicenseCategory.L1: "Motor cycles, motor tricycles and motor quadricycles with engine of any capacity",
        LicenseCategory.L2: "Light motor vehicles, other than motor cycles, motor tricycles or motor quadricycles",
        LicenseCategory.L3: "Any motor vehicle other than motor cycles, motor tricycles or motor quadricycles"
    }
    
    return [
        {
            "value": category.value,
            "label": f"Code {category.value}" if category.value in ["1", "2", "3"] else category.value,
            "description": category_descriptions.get(category, category.value),
            "minimum_age": _get_minimum_age_for_category(category)
        }
        for category in LicenseCategory
    ]

def _get_minimum_age_for_category(category: LicenseCategory) -> int:
    """Get minimum age requirement for a license category"""
    age_requirements = {
        # Motorcycles
        LicenseCategory.A1: 16,
        LicenseCategory.A2: 18,
        LicenseCategory.A: 18,
        
        # Light Vehicles
        LicenseCategory.B1: 16,
        LicenseCategory.B: 18,
        LicenseCategory.B2: 21,
        LicenseCategory.BE: 18,
        
        # Heavy Goods Vehicles
        LicenseCategory.C1: 18,
        LicenseCategory.C: 21,
        LicenseCategory.C1E: 18,
        LicenseCategory.CE: 21,
        
        # Passenger Transport
        LicenseCategory.D1: 21,
        LicenseCategory.D: 24,
        LicenseCategory.D2: 24,
        
        # Learner's permits
        LicenseCategory.L1: 16,
        LicenseCategory.L2: 16,
        LicenseCategory.L3: 16,
    }
    return age_requirements.get(category, 18)  # Default to 18 if not found


@router.get("/application-types", response_model=List[Dict[str, str]])
async def get_application_types() -> List[Dict[str, str]]:
    """Get all available application types with user-friendly labels"""
    # Custom mapping for user-friendly labels matching frontend requirements
    type_labels = {
        ApplicationType.LEARNERS_PERMIT: "Learner's Licence Application",
        ApplicationType.NEW_LICENSE: "Driving Licence Application", 
        ApplicationType.RENEWAL: "Renew Driving Licence Card",
        ApplicationType.PROFESSIONAL_LICENSE: "Professional Driving Licence Application",
        ApplicationType.TEMPORARY_LICENSE: "Temporary Driving Licence Application",
        ApplicationType.FOREIGN_CONVERSION: "Convert Foreign Driving Licence",
        ApplicationType.INTERNATIONAL_PERMIT: "International Driving Permit Application",
        ApplicationType.DRIVERS_LICENSE_CAPTURE: "Driver's License Capture",
        ApplicationType.LEARNERS_PERMIT_CAPTURE: "Learner's Permit Capture",
        # Note: LEARNERS_PERMIT_DUPLICATE is handled in frontend logic only
    }
    
    # Filter out REPLACEMENT as it's been removed from frontend
    filtered_types = [app_type for app_type in ApplicationType if app_type != ApplicationType.REPLACEMENT]
    
    return [
        {
            "value": app_type.value,
            "label": type_labels.get(app_type, app_type.value.replace('_', ' ').title())
        }
        for app_type in filtered_types
    ]


@router.get("/professional-permit-categories", response_model=List[Dict[str, Any]])
async def get_professional_permit_categories() -> List[Dict[str, Any]]:
    """Get all available professional permit categories with age requirements"""
    # Custom mapping for detailed descriptions
    category_descriptions = {
        ProfessionalPermitCategory.P: "Passengers (21 years minimum)",
        ProfessionalPermitCategory.D: "Dangerous goods (25 years minimum) - automatically includes G",
        ProfessionalPermitCategory.G: "Goods (18 years minimum)"
    }
    
    age_requirements = {
        ProfessionalPermitCategory.G: 18,
        ProfessionalPermitCategory.P: 21,
        ProfessionalPermitCategory.D: 25,
    }
    
    return [
        {
            "value": category.value,
            "label": category.value,
            "description": category_descriptions.get(category, category.value),
            "minimum_age": age_requirements.get(category, 18),
            "auto_includes": ["G"] if category == ProfessionalPermitCategory.D else []
        }
        for category in ProfessionalPermitCategory
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
            "fee_type": fee.fee_type.value if hasattr(fee.fee_type, 'value') else fee.fee_type,
            "display_name": fee.display_name,
            "description": fee.description,
            "amount": float(fee.amount),
            "currency": fee.currency,
            "is_active": fee.is_active,
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
                "label": f"Code {category.value}" if category.value in ["1", "2", "3"] else category.value,
                "description": {
                    # Motorcycles
                    LicenseCategory.A1: "Small motorcycles and mopeds (<125cc, 16+ years)",
                    LicenseCategory.A2: "Mid-range motorcycles (power limited, up to 35kW, 18+ years)",
                    LicenseCategory.A: "Unlimited motorcycles (no power restriction, 18+ years)",
                    
                    # Light Vehicles
                    LicenseCategory.B1: "Light quadricycles (motorized tricycles/quadricycles, 16+ years)",
                    LicenseCategory.B: "Standard passenger cars and light vehicles (up to 3.5t, 18+ years)",
                    LicenseCategory.B2: "Taxis or commercial passenger vehicles (21+ years)",
                    LicenseCategory.BE: "Category B with trailer exceeding 750kg (18+ years)",
                    
                    # Heavy Goods Vehicles
                    LicenseCategory.C1: "Medium-sized goods vehicles (3.5-7.5t, 18+ years)",
                    LicenseCategory.C: "Heavy goods vehicles (over 7.5t, 21+ years)",
                    LicenseCategory.C1E: "C1 category vehicles with heavy trailer (18+ years)",
                    LicenseCategory.CE: "Full heavy combination vehicles (21+ years)",
                    
                    # Passenger Transport
                    LicenseCategory.D1: "Small buses (up to 16 passengers, 21+ years)",
                    LicenseCategory.D: "Standard buses and coaches (over 16 passengers, 24+ years)",
                    LicenseCategory.D2: "Specialized public transport (articulated buses, 24+ years)",
                    
                    # Learner's permits
                    LicenseCategory.L1: "Motor cycles, motor tricycles and motor quadricycles with engine of any capacity",
                    LicenseCategory.L2: "Light motor vehicles, other than motor cycles, motor tricycles or motor quadricycles",
                    LicenseCategory.L3: "Any motor vehicle other than motor cycles, motor tricycles or motor quadricycles"
                }.get(category, category.value),
                "minimum_age": {
                    # Motorcycles
                    LicenseCategory.A1: 16, LicenseCategory.A2: 18, LicenseCategory.A: 18,
                    
                    # Light Vehicles
                    LicenseCategory.B1: 16, LicenseCategory.B: 18, LicenseCategory.B2: 21, LicenseCategory.BE: 18,
                    
                    # Heavy Goods Vehicles
                    LicenseCategory.C1: 18, LicenseCategory.C: 21, LicenseCategory.C1E: 18, LicenseCategory.CE: 21,
                    
                    # Passenger Transport
                    LicenseCategory.D1: 21, LicenseCategory.D: 24, LicenseCategory.D2: 24,
                    
                    # Learner's permits
                    LicenseCategory.L1: 16, LicenseCategory.L2: 16, LicenseCategory.L3: 16,
                }.get(category, 18)
            }
            for category in LicenseCategory
        ],
        "application_types": [
            {
                "value": app_type.value,
                "label": {
                    ApplicationType.LEARNERS_PERMIT: "Learner's Licence Application",
                    ApplicationType.NEW_LICENSE: "Driving Licence Application", 
                    ApplicationType.RENEWAL: "Renew Driving Licence Card",
                    ApplicationType.PROFESSIONAL_LICENSE: "Professional Driving Licence Application",
                    ApplicationType.TEMPORARY_LICENSE: "Temporary Driving Licence Application",
                    ApplicationType.FOREIGN_CONVERSION: "Convert Foreign Driving Licence",
                    ApplicationType.INTERNATIONAL_PERMIT: "International Driving Permit Application",
                    ApplicationType.DRIVERS_LICENSE_CAPTURE: "Driver's License Capture",
                    ApplicationType.LEARNERS_PERMIT_CAPTURE: "Learner's Permit Capture",
                }.get(app_type, app_type.value.replace('_', ' ').title())
            }
            for app_type in ApplicationType if app_type != ApplicationType.REPLACEMENT
        ],
        "professional_permit_categories": [
            {
                "value": category.value,
                "label": category.value,
                "description": {
                    ProfessionalPermitCategory.P: "Passengers (21 years minimum)",
                    ProfessionalPermitCategory.D: "Dangerous goods (25 years minimum) - automatically includes G",
                    ProfessionalPermitCategory.G: "Goods (18 years minimum)"
                }.get(category, category.value),
                "minimum_age": {
                    ProfessionalPermitCategory.G: 18,
                    ProfessionalPermitCategory.P: 21,
                    ProfessionalPermitCategory.D: 25,
                }.get(category, 18),
                "auto_includes": ["G"] if category == ProfessionalPermitCategory.D else []
            }
            for category in ProfessionalPermitCategory
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
                "fee_type": fee.fee_type.value if hasattr(fee.fee_type, 'value') else fee.fee_type,
                "display_name": fee.display_name,
                "description": fee.description,
                "amount": float(fee.amount),
                "currency": fee.currency,
                "is_active": fee.is_active,
                "effective_from": fee.effective_from.isoformat() if fee.effective_from else None,
                "effective_until": fee.effective_until.isoformat() if fee.effective_until else None
            }
            for fee in fee_structures
        ]
    } 