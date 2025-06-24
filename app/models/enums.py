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
    RESIDENTIAL = "residential"  # Physical residence
    POSTAL = "postal"           # Postal/mailing address


class UserStatus(PythonEnum):
    """User account status for Madagascar License System"""
    ACTIVE = "active"
    INACTIVE = "inactive" 
    SUSPENDED = "suspended"
    LOCKED = "locked"
    PENDING_ACTIVATION = "pending_activation"


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
    MOBILE = "MOBILE"       # Mobile unit
    TEMPORARY = "TEMPORARY" # Temporary office 