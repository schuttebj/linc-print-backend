"""
Shared Enums for Madagascar License System
Standardized enumerations used across multiple modules
"""

from enum import Enum as PythonEnum


class MadagascarIDType(PythonEnum):
    """
    Standardized Madagascar ID document types
    Used across both Person and User modules for consistency
    """
    MADAGASCAR_ID = "MADAGASCAR_ID"  # CIN/CNI - Carte d'Identité Nationale (Madagascar National ID)
    PASSPORT = "PASSPORT"            # Passport (any nationality)
    FOREIGN_ID = "FOREIGN_ID"        # Foreign national ID document


class PersonNature(PythonEnum):
    """
    Person nature - Natural persons only (no organizations)
    Based on gender for Madagascar system
    """
    MALE = "01"                 # Male (natural person)
    FEMALE = "02"               # Female (natural person)


class AddressType(PythonEnum):
    """Madagascar address types"""
    RESIDENTIAL = "RESIDENTIAL"  # Physical residence
    POSTAL = "POSTAL"           # Postal/mailing address


class UserStatus(PythonEnum):
    """User account status for Madagascar License System"""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE" 
    SUSPENDED = "SUSPENDED"
    LOCKED = "LOCKED"
    PENDING_ACTIVATION = "PENDING_ACTIVATION"


class UserType(PythonEnum):
    """
    User types for Madagascar License System
    Determines username format and access scope
    """
    SYSTEM_USER = "SYSTEM_USER"          # S001 - System Admin (You + Head of Traffic Dept)
    NATIONAL_ADMIN = "NATIONAL_ADMIN"    # N001 - National Admin
    PROVINCIAL_ADMIN = "PROVINCIAL_ADMIN" # T007 - Provincial Admin  
    LOCATION_USER = "LOCATION_USER"      # T010001 - Office roles (Supervisor, Clerk, Printer)


class RoleHierarchy(PythonEnum):
    """
    Role hierarchy levels for Madagascar License System
    Higher numbers can create lower numbered roles
    """
    SYSTEM_ADMIN = 4        # Technical system administrator (can create all roles)
    NATIONAL_ADMIN = 3      # National administrator (can create Office Supervisor, Clerk)
    OFFICE_SUPERVISOR = 2   # Office supervisor (can create Clerk only)
    CLERK = 1              # Cannot create other users


class ProvinceCode(PythonEnum):
    """Madagascar province codes (ISO 3166-2:MG)"""
    ANTANANARIVO = "T"      # MG-T - Antananarivo
    ANTSIRANANA = "D"       # MG-D - Antsiranana (Diego Suarez)
    FIANARANTSOA = "F"      # MG-F - Fianarantsoa
    MAHAJANGA = "M"         # MG-M - Mahajanga (Majunga)
    TOAMASINA = "A"         # MG-A - Toamasina (Tamatave)
    TOLIARA = "U"           # MG-U - Toliara (Tuléar)


class OfficeType(PythonEnum):
    """Office types for locations"""
    MAIN = "MAIN"           # Main office
    BRANCH = "BRANCH"       # Branch office
    KIOSK = "KIOSK"         # Service kiosk
    MOBILE = "MOBILE"       # Mobile unit
    TEMPORARY = "TEMPORARY" # Temporary office


class EquipmentStatus(PythonEnum):
    """Equipment status for locations"""
    OPERATIONAL = "OPERATIONAL"  # Fully operational
    MAINTENANCE = "MAINTENANCE"  # Under maintenance
    OFFLINE = "OFFLINE"          # Offline/not working


class LanguageCode(PythonEnum):
    """Madagascar supported languages"""
    MALAGASY = "MG"         # Malagasy (official language)
    FRENCH = "FR"           # French (official language)
    ENGLISH = "EN"          # English (international)


class NationalityCode(PythonEnum):
    """Nationality codes for Madagascar system"""
    MADAGASCAR = "MG"       # Malagasy nationality
    FRANCE = "FR"           # French nationality
    UNITED_STATES = "US"    # American nationality
    UNITED_KINGDOM = "GB"   # British nationality
    SOUTH_AFRICA = "ZA"     # South African nationality
    OTHER = "OTHER"         # Other nationalities


class PhoneCountryCode(PythonEnum):
    """Phone country codes for Madagascar system"""
    MADAGASCAR = "+261"     # Madagascar
    SOUTH_AFRICA = "+27"    # South Africa
    FRANCE = "+33"          # France
    USA = "+1"              # United States
    UK = "+44"              # United Kingdom


class CountryCode(PythonEnum):
    """Country codes for document issuance"""
    MADAGASCAR = "MG"       # Madagascar
    FRANCE = "FR"           # France
    UNITED_STATES = "US"    # United States
    UNITED_KINGDOM = "GB"   # United Kingdom
    SOUTH_AFRICA = "ZA"     # South Africa
    OTHER = "OTHER"         # Other countries


# Province display names mapping for frontend
PROVINCE_DISPLAY_NAMES = {
    ProvinceCode.ANTANANARIVO: "ANTANANARIVO",
    ProvinceCode.ANTSIRANANA: "ANTSIRANANA (DIEGO SUAREZ)",
    ProvinceCode.FIANARANTSOA: "FIANARANTSOA", 
    ProvinceCode.MAHAJANGA: "MAHAJANGA",
    ProvinceCode.TOAMASINA: "TOAMASINA",
    ProvinceCode.TOLIARA: "TOLIARA",
}

# User type display names mapping for frontend
USER_TYPE_DISPLAY_NAMES = {
    UserType.SYSTEM_USER: "SYSTEM USER",
    UserType.NATIONAL_ADMIN: "NATIONAL ADMIN",
    UserType.PROVINCIAL_ADMIN: "PROVINCIAL ADMIN",
    UserType.LOCATION_USER: "LOCATION USER",
}

# Role hierarchy display names mapping for frontend
ROLE_HIERARCHY_DISPLAY_NAMES = {
    RoleHierarchy.SYSTEM_ADMIN: "SYSTEM ADMINISTRATOR",
    RoleHierarchy.NATIONAL_ADMIN: "NATIONAL ADMINISTRATOR",
    RoleHierarchy.OFFICE_SUPERVISOR: "OFFICE SUPERVISOR", 
    RoleHierarchy.CLERK: "CLERK",
}

# Office type display names mapping for frontend
OFFICE_TYPE_DISPLAY_NAMES = {
    OfficeType.MAIN: "MAIN OFFICE",
    OfficeType.BRANCH: "BRANCH OFFICE",
    OfficeType.KIOSK: "SERVICE KIOSK",
    OfficeType.MOBILE: "MOBILE UNIT",
    OfficeType.TEMPORARY: "TEMPORARY OFFICE",
}

# Equipment status display names mapping for frontend
EQUIPMENT_STATUS_DISPLAY_NAMES = {
    EquipmentStatus.OPERATIONAL: "OPERATIONAL",
    EquipmentStatus.MAINTENANCE: "MAINTENANCE",
    EquipmentStatus.OFFLINE: "OFFLINE",
}

# User status display names mapping for frontend
USER_STATUS_DISPLAY_NAMES = {
    UserStatus.ACTIVE: "ACTIVE",
    UserStatus.INACTIVE: "INACTIVE",
    UserStatus.SUSPENDED: "SUSPENDED",
    UserStatus.LOCKED: "LOCKED",
    UserStatus.PENDING_ACTIVATION: "PENDING ACTIVATION",
}

# Language display names mapping for frontend
LANGUAGE_DISPLAY_NAMES = {
    LanguageCode.MALAGASY: "MALAGASY",
    LanguageCode.FRENCH: "FRANÇAIS",
    LanguageCode.ENGLISH: "ENGLISH",
}

# Nationality display names mapping for frontend
NATIONALITY_DISPLAY_NAMES = {
    NationalityCode.MADAGASCAR: "MALAGASY",
    NationalityCode.FRANCE: "FRENCH",
    NationalityCode.UNITED_STATES: "AMERICAN",
    NationalityCode.UNITED_KINGDOM: "BRITISH",
    NationalityCode.SOUTH_AFRICA: "SOUTH AFRICAN",
    NationalityCode.OTHER: "OTHER",
}

# Phone country code display names mapping for frontend
PHONE_COUNTRY_DISPLAY_NAMES = {
    PhoneCountryCode.MADAGASCAR: "MADAGASCAR",
    PhoneCountryCode.SOUTH_AFRICA: "SOUTH AFRICA", 
    PhoneCountryCode.FRANCE: "FRANCE",
    PhoneCountryCode.USA: "USA",
    PhoneCountryCode.UK: "UK",
}

# Country display names mapping for frontend
COUNTRY_DISPLAY_NAMES = {
    CountryCode.MADAGASCAR: "MADAGASCAR",
    CountryCode.FRANCE: "FRANCE",
    CountryCode.UNITED_STATES: "UNITED STATES", 
    CountryCode.UNITED_KINGDOM: "UNITED KINGDOM",
    CountryCode.SOUTH_AFRICA: "SOUTH AFRICA",
    CountryCode.OTHER: "OTHER",
}

# Document type display names and requirements
DOCUMENT_TYPE_INFO = {
    MadagascarIDType.MADAGASCAR_ID: {
        "label": "MADAGASCAR ID (CIN/CNI)",
        "requires_expiry": False,
    },
    MadagascarIDType.PASSPORT: {
        "label": "PASSPORT", 
        "requires_expiry": True,
    },
    MadagascarIDType.FOREIGN_ID: {
        "label": "FOREIGN ID",
        "requires_expiry": True,
    },
}

# Person nature display names
PERSON_NATURE_DISPLAY_NAMES = {
    PersonNature.MALE: "MALE (LEHILAHY)",
    PersonNature.FEMALE: "FEMALE (VEHIVAVY)",
} 