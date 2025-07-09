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


# Application-specific enums
class LicenseCategory(PythonEnum):
    """SADC driver's license categories"""
    # Motorcycles and Mopeds
    A1 = "A1"               # Small motorcycles and mopeds (<125cc, 16+)
    A2 = "A2"               # Mid-range motorcycles (power limited, up to 35kW, 18+)
    A = "A"                 # Unlimited motorcycles (no power restriction, 18+)
    
    # Light Vehicles
    B1 = "B1"               # Light quadricycles (motorized tricycles/quadricycles, 16+)
    B = "B"                 # Standard passenger cars and light vehicles (up to 3.5t, 18+)
    B2 = "B2"               # Taxis or commercial passenger vehicles (21+)
    BE = "BE"               # Category B with trailer exceeding 750kg (18+)
    
    # Heavy Goods Vehicles
    C1 = "C1"               # Medium-sized goods vehicles (3.5-7.5t, 18+)
    C = "C"                 # Heavy goods vehicles (over 7.5t, 21+)
    C1E = "C1E"             # C1 category vehicles with heavy trailer (18+)
    CE = "CE"               # Full heavy combination vehicles (21+)
    
    # Passenger Transport (Public Transport)
    D1 = "D1"               # Small buses (up to 16 passengers, 21+)
    D = "D"                 # Standard buses and coaches (over 16 passengers, 24+)
    D2 = "D2"               # Specialized public transport (articulated buses, 24+)
    
    # Learner's Permit Categories
    LEARNERS_1 = "1"        # Motor cycles, motor tricycles and motor quadricycles with engine of any capacity
    LEARNERS_2 = "2"        # Light motor vehicles, other than motor cycles, motor tricycles or motor quadricycles  
    LEARNERS_3 = "3"        # Any motor vehicle other than motor cycles, motor tricycles or motor quadricycles


class ApplicationType(PythonEnum):
    """Types of license applications in Madagascar"""
    NEW_LICENSE = "NEW_LICENSE"                         # First-time license application
    LEARNERS_PERMIT = "LEARNERS_PERMIT"                 # Learner's permit after theory test
    RENEWAL = "RENEWAL"                                 # License renewal (5-year cycle)
    REPLACEMENT = "REPLACEMENT"                         # Replacement for lost/stolen/damaged license
    TEMPORARY_LICENSE = "TEMPORARY_LICENSE"             # Emergency permit (90-day validity)
    INTERNATIONAL_PERMIT = "INTERNATIONAL_PERMIT"       # IDP for travel abroad
    DRIVERS_LICENSE_CAPTURE = "DRIVERS_LICENSE_CAPTURE" # Capture existing driver's licenses
    LEARNERS_PERMIT_CAPTURE = "LEARNERS_PERMIT_CAPTURE" # Capture existing learner's permits
    PROFESSIONAL_LICENSE = "PROFESSIONAL_LICENSE"       # Professional driving licence application
    FOREIGN_CONVERSION = "FOREIGN_CONVERSION"           # Convert foreign driving licence


class ApplicationStatus(PythonEnum):
    """Complete application workflow status (17 stages)"""
    DRAFT = "DRAFT"                           # Application saved but not submitted
    SUBMITTED = "SUBMITTED"                   # Application submitted for review
    ON_HOLD = "ON_HOLD"                       # Application held (not sent to printer)
    DOCUMENTS_PENDING = "DOCUMENTS_PENDING"   # Missing required documents
    THEORY_TEST_REQUIRED = "THEORY_TEST_REQUIRED"  # Ready for theory exam
    THEORY_PASSED = "THEORY_PASSED"          # Theory test completed successfully
    THEORY_FAILED = "THEORY_FAILED"          # Theory test failed
    PRACTICAL_TEST_REQUIRED = "PRACTICAL_TEST_REQUIRED"  # Ready for practical exam
    PRACTICAL_PASSED = "PRACTICAL_PASSED"    # Practical test completed successfully
    PRACTICAL_FAILED = "PRACTICAL_FAILED"    # Practical test failed
    APPROVED = "APPROVED"                     # Application approved, ready for printing
    SENT_TO_PRINTER = "SENT_TO_PRINTER"      # Printing job created
    CARD_PRODUCTION = "CARD_PRODUCTION"       # Card being manufactured by CIM
    READY_FOR_COLLECTION = "READY_FOR_COLLECTION"  # Card available for pickup
    COMPLETED = "COMPLETED"                   # Card collected, process complete
    REJECTED = "REJECTED"                     # Application rejected
    CANCELLED = "CANCELLED"                   # Application cancelled


class PaymentStatus(PythonEnum):
    """Payment status for application fees"""
    PENDING = "PENDING"             # Payment not yet made
    PAID = "PAID"                   # Payment completed
    REFUNDED = "REFUNDED"           # Payment refunded
    FAILED = "FAILED"               # Payment failed


class BiometricDataType(PythonEnum):
    """Types of biometric data captured"""
    PHOTO = "PHOTO"                 # ISO-compliant passport photo
    SIGNATURE = "SIGNATURE"         # Digital signature
    FINGERPRINT = "FINGERPRINT"     # Fingerprint scan
    IRIS = "IRIS"                   # Iris scan (future use)


class MedicalCertificateStatus(PythonEnum):
    """Medical certificate verification status"""
    NOT_REQUIRED = "NOT_REQUIRED"   # Not required for this application
    PENDING_UPLOAD = "PENDING_UPLOAD"  # Required but not yet uploaded
    UPLOADED = "UPLOADED"           # File uploaded, awaiting verification
    VERIFIED = "VERIFIED"           # Verified by authorized personnel
    REJECTED = "REJECTED"           # Rejected - resubmission required
    CONFIRMED_WITHOUT_UPLOAD = "CONFIRMED_WITHOUT_UPLOAD"  # Confirmed via checkbox


class ParentalConsentStatus(PythonEnum):
    """Parental consent status for minors (16-17 years applying for A′)"""
    NOT_REQUIRED = "NOT_REQUIRED"   # Not required (18+ years)
    REQUIRED = "REQUIRED"           # Required but not provided
    PROVIDED = "PROVIDED"           # Parental consent provided
    VERIFIED = "VERIFIED"           # Consent verified by authorities


class TestAttemptType(PythonEnum):
    """Types of license tests"""
    THEORY = "THEORY"               # Theory examination
    PRACTICAL = "PRACTICAL"         # Practical driving test


class TestResult(PythonEnum):
    """Test result outcomes"""
    PENDING = "PENDING"             # Test not yet taken
    PASSED = "PASSED"               # Test passed
    FAILED = "FAILED"               # Test failed
    NO_SHOW = "NO_SHOW"             # Applicant did not appear


class ReplacementReason(PythonEnum):
    """Reasons for license replacement"""
    LOST = "LOST"                   # License lost
    STOLEN = "STOLEN"               # License stolen (requires police report)
    DAMAGED = "DAMAGED"             # License damaged
    NAME_CHANGE = "NAME_CHANGE"     # Name change
    ADDRESS_CHANGE = "ADDRESS_CHANGE"  # Address change
    OTHER = "OTHER"                 # Other reason


class ProfessionalPermitCategory(PythonEnum):
    """Professional Driving Permit Categories"""
    P = "P"                         # Passengers (21 years minimum)
    D = "D"                         # Dangerous goods (25 years minimum) - automatically includes G
    G = "G"                         # Goods (18 years minimum)


class ProfessionalPermitCategory(PythonEnum):
    """Professional driving permit categories for Madagascar"""
    P = "P"  # Professional permit P
    D = "D"  # Professional permit D  
    G = "G"  # Professional permit G


class LicenseRestrictionCode(PythonEnum):
    """License restriction codes for Madagascar driver's licenses"""
    
    # Driver Physical Restrictions
    CORRECTIVE_LENSES = "01"           # Driver must wear corrective lenses
    PROSTHETICS = "02"                 # Driver uses prosthetics
    
    # Vehicle Type Restrictions  
    AUTOMATIC_TRANSMISSION = "03"      # Automatic transmission vehicles only
    ELECTRIC_POWERED = "04"            # Electric powered vehicles only
    PHYSICAL_DISABLED = "05"           # Vehicles adapted for physical disabilities
    TRACTOR_ONLY = "06"               # Tractor vehicles only
    INDUSTRIAL_AGRICULTURE = "07"      # Industrial/agriculture vehicles only


class LicenseRestrictionCategory(PythonEnum):
    """Categories of license restrictions"""
    DRIVER = "DRIVER"           # Restrictions on the driver
    VEHICLE = "VEHICLE"         # Restrictions on vehicle type
    OPERATIONAL = "OPERATIONAL" # Operational restrictions (time, location, etc.)


# Restriction mapping for easy lookup
LICENSE_RESTRICTION_MAPPING = {
    # Driver restrictions
    LicenseRestrictionCode.CORRECTIVE_LENSES: {
        "code": "01",
        "description": "Driver must wear corrective lenses",
        "category": LicenseRestrictionCategory.DRIVER,
        "display_name": "Corrective Lenses Required"
    },
    LicenseRestrictionCode.PROSTHETICS: {
        "code": "02", 
        "description": "Driver uses prosthetics",
        "category": LicenseRestrictionCategory.DRIVER,
        "display_name": "Prosthetics"
    },
    
    # Vehicle restrictions
    LicenseRestrictionCode.AUTOMATIC_TRANSMISSION: {
        "code": "03",
        "description": "Automatic transmission vehicles only", 
        "category": LicenseRestrictionCategory.VEHICLE,
        "display_name": "Automatic Transmission Only"
    },
    LicenseRestrictionCode.ELECTRIC_POWERED: {
        "code": "04",
        "description": "Electric powered vehicles only",
        "category": LicenseRestrictionCategory.VEHICLE, 
        "display_name": "Electric Vehicles Only"
    },
    LicenseRestrictionCode.PHYSICAL_DISABLED: {
        "code": "05",
        "description": "Vehicles adapted for physical disabilities",
        "category": LicenseRestrictionCategory.VEHICLE,
        "display_name": "Disability Adapted Vehicles"
    },
    LicenseRestrictionCode.TRACTOR_ONLY: {
        "code": "06", 
        "description": "Tractor vehicles only",
        "category": LicenseRestrictionCategory.VEHICLE,
        "display_name": "Tractor Vehicles Only"
    },
    LicenseRestrictionCode.INDUSTRIAL_AGRICULTURE: {
        "code": "07",
        "description": "Industrial/agriculture vehicles only", 
        "category": LicenseRestrictionCategory.VEHICLE,
        "display_name": "Industrial/Agriculture Only"
    }
}

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