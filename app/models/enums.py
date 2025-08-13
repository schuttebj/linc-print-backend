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
    NATIONAL_ADMIN = 3      # National administrator (can create Office Supervisor, Clerk, Examiner)
    OFFICE_SUPERVISOR = 2   # Office supervisor (can create Clerk only)
    EXAMINER = 2           # License examiner (can authorize applications and create licenses)
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
    """Country codes for document issuance - ISO 3166-1 alpha-2 codes"""
    # Africa
    MADAGASCAR = "MG"       # Madagascar
    SOUTH_AFRICA = "ZA"     # South Africa
    ALGERIA = "DZ"          # Algeria
    ANGOLA = "AO"           # Angola
    BOTSWANA = "BW"         # Botswana
    CAMEROON = "CM"         # Cameroon
    EGYPT = "EG"            # Egypt
    ETHIOPIA = "ET"         # Ethiopia
    GHANA = "GH"            # Ghana
    KENYA = "KE"            # Kenya
    LIBYA = "LY"            # Libya
    MAURITIUS = "MU"        # Mauritius
    MOROCCO = "MA"          # Morocco
    MOZAMBIQUE = "MZ"       # Mozambique
    NAMIBIA = "NA"          # Namibia
    NIGERIA = "NG"          # Nigeria
    REUNION = "RE"          # Réunion
    SEYCHELLES = "SC"       # Seychelles
    TANZANIA = "TZ"         # Tanzania
    TUNISIA = "TN"          # Tunisia
    UGANDA = "UG"           # Uganda
    ZAMBIA = "ZM"           # Zambia
    ZIMBABWE = "ZW"         # Zimbabwe
    
    # Europe
    FRANCE = "FR"           # France
    UNITED_KINGDOM = "GB"   # United Kingdom
    GERMANY = "DE"          # Germany
    ITALY = "IT"            # Italy
    SPAIN = "ES"            # Spain
    BELGIUM = "BE"          # Belgium
    NETHERLANDS = "NL"      # Netherlands
    SWITZERLAND = "CH"      # Switzerland
    AUSTRIA = "AT"          # Austria
    PORTUGAL = "PT"         # Portugal
    GREECE = "GR"           # Greece
    NORWAY = "NO"           # Norway
    SWEDEN = "SE"           # Sweden
    DENMARK = "DK"          # Denmark
    FINLAND = "FI"          # Finland
    POLAND = "PL"           # Poland
    RUSSIA = "RU"           # Russia
    UKRAINE = "UA"          # Ukraine
    CZECH_REPUBLIC = "CZ"   # Czech Republic
    HUNGARY = "HU"          # Hungary
    ROMANIA = "RO"          # Romania
    BULGARIA = "BG"         # Bulgaria
    CROATIA = "HR"          # Croatia
    SERBIA = "RS"           # Serbia
    IRELAND = "IE"          # Ireland
    LUXEMBOURG = "LU"       # Luxembourg
    
    # North America
    UNITED_STATES = "US"    # United States
    CANADA = "CA"           # Canada
    MEXICO = "MX"           # Mexico
    
    # South America
    BRAZIL = "BR"           # Brazil
    ARGENTINA = "AR"        # Argentina
    CHILE = "CL"            # Chile
    COLOMBIA = "CO"         # Colombia
    PERU = "PE"             # Peru
    VENEZUELA = "VE"        # Venezuela
    URUGUAY = "UY"          # Uruguay
    ECUADOR = "EC"          # Ecuador
    BOLIVIA = "BO"          # Bolivia
    PARAGUAY = "PY"         # Paraguay
    GUYANA = "GY"           # Guyana
    SURINAME = "SR"         # Suriname
    
    # Asia
    CHINA = "CN"            # China
    INDIA = "IN"            # India
    JAPAN = "JP"            # Japan
    SOUTH_KOREA = "KR"      # South Korea
    THAILAND = "TH"         # Thailand
    VIETNAM = "VN"          # Vietnam
    MALAYSIA = "MY"         # Malaysia
    SINGAPORE = "SG"        # Singapore
    INDONESIA = "ID"        # Indonesia
    PHILIPPINES = "PH"      # Philippines
    BANGLADESH = "BD"       # Bangladesh
    PAKISTAN = "PK"         # Pakistan
    SRI_LANKA = "LK"        # Sri Lanka
    MYANMAR = "MM"          # Myanmar
    CAMBODIA = "KH"         # Cambodia
    LAOS = "LA"             # Laos
    NEPAL = "NP"            # Nepal
    BHUTAN = "BT"           # Bhutan
    MALDIVES = "MV"         # Maldives
    BRUNEI = "BN"           # Brunei
    TIMOR_LESTE = "TL"      # Timor-Leste
    MONGOLIA = "MN"         # Mongolia
    AFGHANISTAN = "AF"      # Afghanistan
    IRAN = "IR"             # Iran
    IRAQ = "IQ"             # Iraq
    ISRAEL = "IL"           # Israel
    JORDAN = "JO"           # Jordan
    LEBANON = "LB"          # Lebanon
    SYRIA = "SY"            # Syria
    TURKEY = "TR"           # Turkey
    SAUDI_ARABIA = "SA"     # Saudi Arabia
    UAE = "AE"              # United Arab Emirates
    QATAR = "QA"            # Qatar
    KUWAIT = "KW"           # Kuwait
    BAHRAIN = "BH"          # Bahrain
    OMAN = "OM"             # Oman
    YEMEN = "YE"            # Yemen
    
    # Oceania
    AUSTRALIA = "AU"        # Australia
    NEW_ZEALAND = "NZ"      # New Zealand
    FIJI = "FJ"             # Fiji
    PAPUA_NEW_GUINEA = "PG" # Papua New Guinea
    SOLOMON_ISLANDS = "SB"  # Solomon Islands
    VANUATU = "VU"          # Vanuatu
    NEW_CALEDONIA = "NC"    # New Caledonia
    FRENCH_POLYNESIA = "PF" # French Polynesia
    SAMOA = "WS"            # Samoa
    TONGA = "TO"            # Tonga
    PALAU = "PW"            # Palau
    MARSHALL_ISLANDS = "MH" # Marshall Islands
    MICRONESIA = "FM"       # Micronesia
    KIRIBATI = "KI"         # Kiribati
    TUVALU = "TV"           # Tuvalu
    NAURU = "NR"            # Nauru
    
    # Caribbean & Central America
    JAMAICA = "JM"          # Jamaica
    CUBA = "CU"             # Cuba
    HAITI = "HT"            # Haiti
    DOMINICAN_REPUBLIC = "DO" # Dominican Republic
    PUERTO_RICO = "PR"      # Puerto Rico
    TRINIDAD_AND_TOBAGO = "TT" # Trinidad and Tobago
    BARBADOS = "BB"         # Barbados
    BAHAMAS = "BS"          # Bahamas
    BELIZE = "BZ"           # Belize
    COSTA_RICA = "CR"       # Costa Rica
    EL_SALVADOR = "SV"      # El Salvador
    GUATEMALA = "GT"        # Guatemala
    HONDURAS = "HN"         # Honduras
    NICARAGUA = "NI"        # Nicaragua
    PANAMA = "PA"           # Panama
    
    # Other
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
    """Streamlined application workflow status with payment integration"""
    DRAFT = "DRAFT"                           # Application saved but not submitted
    SUBMITTED = "SUBMITTED"                   # Application submitted, awaiting payment
    PAID = "PAID"                            # Payment completed, ready for processing
    ON_HOLD = "ON_HOLD"                       # Application held for administrative reasons
    PASSED = "PASSED"                         # Test completed successfully
    FAILED = "FAILED"                         # Test failed (terminal - requires new application)
    ABSENT = "ABSENT"                         # Did not attend test (terminal - requires new application)
    CARD_PAYMENT_PENDING = "CARD_PAYMENT_PENDING"  # Test passed, awaiting card payment (NEW_LICENSE only)
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
    """Parental consent status for minors (16-17 years applying for A1)"""
    NOT_REQUIRED = "NOT_REQUIRED"   # Not required (18+ years)
    REQUIRED = "REQUIRED"           # Required but not provided
    PROVIDED = "PROVIDED"           # Parental consent provided
    VERIFIED = "VERIFIED"           # Consent verified by authorities


class TestAttemptType(PythonEnum):
    """Types of license tests"""
    THEORY = "THEORY"               # Theory examination
    PRACTICAL = "PRACTICAL"         # Practical driving test


class TestResult(PythonEnum):
    """Test result outcomes for new license applications"""
    PASSED = "PASSED"               # Test passed
    FAILED = "FAILED"               # Test failed (terminal - requires new application)
    ABSENT = "ABSENT"               # Did not attend test (terminal - requires new application)


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


class DriverRestrictionCode(PythonEnum):
    """Driver restriction codes for Madagascar driver's licenses"""
    
    NONE = "00"                    # No driver restrictions
    CORRECTIVE_LENSES = "01"       # Driver must wear corrective lenses
    PROSTHETICS = "02"             # Driver uses artificial limb/prosthetics


class VehicleRestrictionCode(PythonEnum):
    """Vehicle restriction codes for Madagascar driver's licenses"""
    
    NONE = "00"                    # No vehicle restrictions
    AUTOMATIC_TRANSMISSION = "01"  # Automatic transmission vehicles only
    ELECTRIC_POWERED = "02"        # Electric powered vehicles only
    PHYSICAL_DISABLED = "03"       # Vehicles adapted for physical disabilities
    TRACTOR_ONLY = "04"           # Tractor vehicles only
    INDUSTRIAL_AGRICULTURE = "05"  # Industrial/agriculture vehicles only


class LicenseRestrictionCategory(PythonEnum):
    """Categories of license restrictions"""
    DRIVER = "DRIVER"           # Restrictions on the driver
    VEHICLE = "VEHICLE"         # Restrictions on vehicle type
    OPERATIONAL = "OPERATIONAL" # Operational restrictions (time, location, etc.)


# Driver restriction mapping for easy lookup
DRIVER_RESTRICTION_MAPPING = {
    DriverRestrictionCode.NONE: {
        "code": "00",
        "description": "No driver restrictions",
        "category": LicenseRestrictionCategory.DRIVER,
        "display_name": "No Restrictions"
    },
    DriverRestrictionCode.CORRECTIVE_LENSES: {
        "code": "01",
        "description": "Driver must wear corrective lenses",
        "category": LicenseRestrictionCategory.DRIVER,
        "display_name": "Corrective Lenses Required"
    },
    DriverRestrictionCode.PROSTHETICS: {
        "code": "02", 
        "description": "Driver uses artificial limb/prosthetics",
        "category": LicenseRestrictionCategory.DRIVER,
        "display_name": "Artificial Limb/Prosthetics"
    }
}

# Vehicle restriction mapping for easy lookup
VEHICLE_RESTRICTION_MAPPING = {
    VehicleRestrictionCode.NONE: {
        "code": "00",
        "description": "No vehicle restrictions",
        "category": LicenseRestrictionCategory.VEHICLE,
        "display_name": "No Restrictions"
    },
    VehicleRestrictionCode.AUTOMATIC_TRANSMISSION: {
        "code": "01",
        "description": "Automatic transmission vehicles only", 
        "category": LicenseRestrictionCategory.VEHICLE,
        "display_name": "Automatic Transmission Only"
    },
    VehicleRestrictionCode.ELECTRIC_POWERED: {
        "code": "02",
        "description": "Electric powered vehicles only",
        "category": LicenseRestrictionCategory.VEHICLE, 
        "display_name": "Electric Vehicles Only"
    },
    VehicleRestrictionCode.PHYSICAL_DISABLED: {
        "code": "03",
        "description": "Vehicles adapted for physical disabilities",
        "category": LicenseRestrictionCategory.VEHICLE,
        "display_name": "Disability Adapted Vehicles"
    },
    VehicleRestrictionCode.TRACTOR_ONLY: {
        "code": "04", 
        "description": "Tractor vehicles only",
        "category": LicenseRestrictionCategory.VEHICLE,
        "display_name": "Tractor Vehicles Only"
    },
    VehicleRestrictionCode.INDUSTRIAL_AGRICULTURE: {
        "code": "05",
        "description": "Industrial/agriculture vehicles only", 
        "category": LicenseRestrictionCategory.VEHICLE,
        "display_name": "Industrial/Agriculture Only"
    }
}

# Combined mapping for backward compatibility during transition
LICENSE_RESTRICTION_MAPPING = {
    **DRIVER_RESTRICTION_MAPPING,
    **VEHICLE_RESTRICTION_MAPPING
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
    RoleHierarchy.EXAMINER: "LICENSE EXAMINER",
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
    # Africa
    CountryCode.MADAGASCAR: "Madagascar",
    CountryCode.SOUTH_AFRICA: "South Africa",
    CountryCode.ALGERIA: "Algeria",
    CountryCode.ANGOLA: "Angola",
    CountryCode.BOTSWANA: "Botswana",
    CountryCode.CAMEROON: "Cameroon",
    CountryCode.EGYPT: "Egypt",
    CountryCode.ETHIOPIA: "Ethiopia",
    CountryCode.GHANA: "Ghana",
    CountryCode.KENYA: "Kenya",
    CountryCode.LIBYA: "Libya",
    CountryCode.MAURITIUS: "Mauritius",
    CountryCode.MOROCCO: "Morocco",
    CountryCode.MOZAMBIQUE: "Mozambique",
    CountryCode.NAMIBIA: "Namibia",
    CountryCode.NIGERIA: "Nigeria",
    CountryCode.REUNION: "Réunion",
    CountryCode.SEYCHELLES: "Seychelles",
    CountryCode.TANZANIA: "Tanzania",
    CountryCode.TUNISIA: "Tunisia",
    CountryCode.UGANDA: "Uganda",
    CountryCode.ZAMBIA: "Zambia",
    CountryCode.ZIMBABWE: "Zimbabwe",
    
    # Europe
    CountryCode.FRANCE: "France",
    CountryCode.UNITED_KINGDOM: "United Kingdom",
    CountryCode.GERMANY: "Germany",
    CountryCode.ITALY: "Italy",
    CountryCode.SPAIN: "Spain",
    CountryCode.BELGIUM: "Belgium",
    CountryCode.NETHERLANDS: "Netherlands",
    CountryCode.SWITZERLAND: "Switzerland",
    CountryCode.AUSTRIA: "Austria",
    CountryCode.PORTUGAL: "Portugal",
    CountryCode.GREECE: "Greece",
    CountryCode.NORWAY: "Norway",
    CountryCode.SWEDEN: "Sweden",
    CountryCode.DENMARK: "Denmark",
    CountryCode.FINLAND: "Finland",
    CountryCode.POLAND: "Poland",
    CountryCode.RUSSIA: "Russia",
    CountryCode.UKRAINE: "Ukraine",
    CountryCode.CZECH_REPUBLIC: "Czech Republic",
    CountryCode.HUNGARY: "Hungary",
    CountryCode.ROMANIA: "Romania",
    CountryCode.BULGARIA: "Bulgaria",
    CountryCode.CROATIA: "Croatia",
    CountryCode.SERBIA: "Serbia",
    CountryCode.IRELAND: "Ireland",
    CountryCode.LUXEMBOURG: "Luxembourg",
    
    # North America
    CountryCode.UNITED_STATES: "United States",
    CountryCode.CANADA: "Canada",
    CountryCode.MEXICO: "Mexico",
    
    # South America
    CountryCode.BRAZIL: "Brazil",
    CountryCode.ARGENTINA: "Argentina",
    CountryCode.CHILE: "Chile",
    CountryCode.COLOMBIA: "Colombia",
    CountryCode.PERU: "Peru",
    CountryCode.VENEZUELA: "Venezuela",
    CountryCode.URUGUAY: "Uruguay",
    CountryCode.ECUADOR: "Ecuador",
    CountryCode.BOLIVIA: "Bolivia",
    CountryCode.PARAGUAY: "Paraguay",
    CountryCode.GUYANA: "Guyana",
    CountryCode.SURINAME: "Suriname",
    
    # Asia
    CountryCode.CHINA: "China",
    CountryCode.INDIA: "India",
    CountryCode.JAPAN: "Japan",
    CountryCode.SOUTH_KOREA: "South Korea",
    CountryCode.THAILAND: "Thailand",
    CountryCode.VIETNAM: "Vietnam",
    CountryCode.MALAYSIA: "Malaysia",
    CountryCode.SINGAPORE: "Singapore",
    CountryCode.INDONESIA: "Indonesia",
    CountryCode.PHILIPPINES: "Philippines",
    CountryCode.BANGLADESH: "Bangladesh",
    CountryCode.PAKISTAN: "Pakistan",
    CountryCode.SRI_LANKA: "Sri Lanka",
    CountryCode.MYANMAR: "Myanmar",
    CountryCode.CAMBODIA: "Cambodia",
    CountryCode.LAOS: "Laos",
    CountryCode.NEPAL: "Nepal",
    CountryCode.BHUTAN: "Bhutan",
    CountryCode.MALDIVES: "Maldives",
    CountryCode.BRUNEI: "Brunei",
    CountryCode.TIMOR_LESTE: "Timor-Leste",
    CountryCode.MONGOLIA: "Mongolia",
    CountryCode.AFGHANISTAN: "Afghanistan",
    CountryCode.IRAN: "Iran",
    CountryCode.IRAQ: "Iraq",
    CountryCode.ISRAEL: "Israel",
    CountryCode.JORDAN: "Jordan",
    CountryCode.LEBANON: "Lebanon",
    CountryCode.SYRIA: "Syria",
    CountryCode.TURKEY: "Turkey",
    CountryCode.SAUDI_ARABIA: "Saudi Arabia",
    CountryCode.UAE: "United Arab Emirates",
    CountryCode.QATAR: "Qatar",
    CountryCode.KUWAIT: "Kuwait",
    CountryCode.BAHRAIN: "Bahrain",
    CountryCode.OMAN: "Oman",
    CountryCode.YEMEN: "Yemen",
    
    # Oceania
    CountryCode.AUSTRALIA: "Australia",
    CountryCode.NEW_ZEALAND: "New Zealand",
    CountryCode.FIJI: "Fiji",
    CountryCode.PAPUA_NEW_GUINEA: "Papua New Guinea",
    CountryCode.SOLOMON_ISLANDS: "Solomon Islands",
    CountryCode.VANUATU: "Vanuatu",
    CountryCode.NEW_CALEDONIA: "New Caledonia",
    CountryCode.FRENCH_POLYNESIA: "French Polynesia",
    CountryCode.SAMOA: "Samoa",
    CountryCode.TONGA: "Tonga",
    CountryCode.PALAU: "Palau",
    CountryCode.MARSHALL_ISLANDS: "Marshall Islands",
    CountryCode.MICRONESIA: "Micronesia",
    CountryCode.KIRIBATI: "Kiribati",
    CountryCode.TUVALU: "Tuvalu",
    CountryCode.NAURU: "Nauru",
    
    # Caribbean & Central America
    CountryCode.JAMAICA: "Jamaica",
    CountryCode.CUBA: "Cuba",
    CountryCode.HAITI: "Haiti",
    CountryCode.DOMINICAN_REPUBLIC: "Dominican Republic",
    CountryCode.PUERTO_RICO: "Puerto Rico",
    CountryCode.TRINIDAD_AND_TOBAGO: "Trinidad and Tobago",
    CountryCode.BARBADOS: "Barbados",
    CountryCode.BAHAMAS: "Bahamas",
    CountryCode.BELIZE: "Belize",
    CountryCode.COSTA_RICA: "Costa Rica",
    CountryCode.EL_SALVADOR: "El Salvador",
    CountryCode.GUATEMALA: "Guatemala",
    CountryCode.HONDURAS: "Honduras",
    CountryCode.NICARAGUA: "Nicaragua",
    CountryCode.PANAMA: "Panama",
    
    # Other
    CountryCode.OTHER: "Other",
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

# Madagascar License Fee Constants (in Ariary)
# Keep fees simple and centralized to avoid complications
MADAGASCAR_LICENSE_FEES = {
    # Test Fees (used across multiple application types)
    "THEORY_TEST_LIGHT": 10000,      # Light vehicles (A1, A2, A, B1, B)
    "THEORY_TEST_HEAVY": 15000,      # Heavy vehicles (B2, BE, C1, C, C1E, CE, D1, D, D2)
    "PRACTICAL_TEST_LIGHT": 10000,   # Light vehicle practical test
    "PRACTICAL_TEST_HEAVY": 15000,   # Heavy vehicle practical test
    
    # Application-Type-Specific Fees (adjustable per application type)
    "NEW_LICENSE_FEE": 38000,        # New license application + card
    "LEARNERS_PERMIT_FEE": 0,        # Learners permit (test fees only, no additional fee)
    "RENEWAL_FEE": 38000,            # License renewal
    "REPLACEMENT_FEE": 38000,        # License replacement
    "TEMPORARY_LICENSE_FEE": 10000,  # Temporary license (simplified to 10,000 Ar)
    "INTERNATIONAL_PERMIT_FEE": 38000, # International permit (like renewal)
    "PROFESSIONAL_LICENSE_FEE": 38000, # Professional license (like renewal)
    "FOREIGN_CONVERSION_FEE": 38000,   # Foreign license conversion (like renewal)
    "DRIVERS_LICENSE_CAPTURE_FEE": 38000, # Capture existing license
    "LEARNERS_PERMIT_CAPTURE_FEE": 38000, # Capture existing learners permit
    
    # Calculated Totals for Quick Reference
    "NEW_LICENSE_LIGHT_TOTAL": 48000,  # Test (10,000) + Application+Card (38,000)
    "NEW_LICENSE_HEAVY_TOTAL": 53000,  # Test (15,000) + Application+Card (38,000)
    "LEARNERS_PERMIT_LIGHT_TOTAL": 10000, # Theory test only
    "LEARNERS_PERMIT_HEAVY_TOTAL": 15000, # Theory test only
}

# Fee display names for UI
MADAGASCAR_FEE_DISPLAY = {
    # Test fees
    "THEORY_TEST_LIGHT": "Theory Test (Light Vehicles)",
    "THEORY_TEST_HEAVY": "Theory Test (Heavy Vehicles)",
    "PRACTICAL_TEST_LIGHT": "Practical Test (Light Vehicles)",
    "PRACTICAL_TEST_HEAVY": "Practical Test (Heavy Vehicles)",
    
    # Application-specific fees
    "NEW_LICENSE_FEE": "New License - Application + Card",
    "LEARNERS_PERMIT_FEE": "Learners Permit - Additional Fee",
    "RENEWAL_FEE": "License Renewal",
    "REPLACEMENT_FEE": "License Replacement",
    "TEMPORARY_LICENSE_FEE": "Temporary License",
    "INTERNATIONAL_PERMIT_FEE": "International Driving Permit",
    "PROFESSIONAL_LICENSE_FEE": "Professional License",
    "FOREIGN_CONVERSION_FEE": "Foreign License Conversion",
    "DRIVERS_LICENSE_CAPTURE_FEE": "Driver's License Capture",
    "LEARNERS_PERMIT_CAPTURE_FEE": "Learner's Permit Capture",
    
    # Totals
    "NEW_LICENSE_LIGHT_TOTAL": "New License (Light Vehicle) - Total",
    "NEW_LICENSE_HEAVY_TOTAL": "New License (Heavy Vehicle) - Total",
    "LEARNERS_PERMIT_LIGHT_TOTAL": "Learner's Permit (Light Vehicle) - Total",
    "LEARNERS_PERMIT_HEAVY_TOTAL": "Learner's Permit (Heavy Vehicle) - Total",
} 