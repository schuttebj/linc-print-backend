"""
Person Management Models - Madagascar Simplified Implementation
Database models for natural persons only (no organizations)
Adapted for Madagascar ID system, address format, and phone structure
"""

from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Integer, Date, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime, date
from enum import Enum as PythonEnum
import uuid

from app.models.base import BaseModel


class IdentificationType(PythonEnum):
    """
    Madagascar ID Document Types - Simplified
    Only supporting Madagascar National ID and Passport for foreigners
    """
    MADAGASCAR_ID = "MG_ID"     # Madagascar National ID (CIN/CNI)
    PASSPORT = "PASSPORT"       # Passport (for foreigners)


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


class Person(BaseModel):
    """
    Person entity - Natural persons only for Madagascar License System
    Simplified from LINC Old to focus on essential fields
    """
    __tablename__ = "persons"
    
    # Core identity fields
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    # Personal names (simplified structure)
    surname = Column(String(50), nullable=False, comment="Family name/surname")
    first_name = Column(String(50), nullable=False, comment="First/given name")
    middle_name = Column(String(50), nullable=True, comment="Middle name(s)")
    
    # Person nature (gender-based for natural persons)
    person_nature = Column(String(2), nullable=False, comment="01=Male, 02=Female")
    
    # Personal details
    birth_date = Column(Date, nullable=True, comment="Date of birth")
    
    # Nationality and language
    nationality_code = Column(String(3), nullable=False, default="MG", comment="Country code (MG=Madagascar)")
    preferred_language = Column(String(10), nullable=False, default="mg", comment="mg=Malagasy, fr=French, en=English")
    
    # Contact information (simplified)
    email_address = Column(String(100), nullable=True, comment="Email address")
    work_phone = Column(String(20), nullable=True, comment="Work phone number")
    cell_phone_country_code = Column(String(5), nullable=False, default="+261", comment="Cell phone country code")
    cell_phone = Column(String(15), nullable=True, comment="Cell phone number (local format)")
    
    # Status and flags
    is_active = Column(Boolean, nullable=False, default=True, comment="Active status")
    
    # TODO: Add biometric data fields when Persons module expands
    # biometric_data = Column(JSON, nullable=True, comment="Fingerprint/photo data")
    
    # TODO: Add emergency contact fields if needed
    # emergency_contact_name = Column(String(100), nullable=True)
    # emergency_contact_phone = Column(String(20), nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)
    
    # Relationships
    aliases = relationship("PersonAlias", back_populates="person", cascade="all, delete-orphan")
    addresses = relationship("PersonAddress", back_populates="person", cascade="all, delete-orphan")
    # TODO: Add relationship to license applications when Applications module is implemented
    # license_applications = relationship("LicenseApplication", back_populates="person")
    
    def __repr__(self):
        return f"<Person(id={self.id}, name='{self.surname}, {self.first_name}', nature='{self.person_nature}')>"


class PersonAlias(BaseModel):
    """
    Person identification documents - Madagascar ID + Passport support
    Supports primary document selection and historical document tracking
    """
    __tablename__ = "person_aliases"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    person_id = Column(UUID(as_uuid=True), ForeignKey('persons.id'), nullable=False, index=True)
    
    # Document identification
    document_type = Column(String(20), nullable=False, comment="MG_ID or PASSPORT")
    document_number = Column(String(50), nullable=False, comment="ID/passport number")
    
    # Document details
    country_of_issue = Column(String(3), nullable=False, default="MG", comment="Country code of issuing country")
    name_in_document = Column(String(200), nullable=True, comment="Name as it appears in document")
    
    # Document status
    is_primary = Column(Boolean, nullable=False, default=False, comment="Primary identification document")
    is_current = Column(Boolean, nullable=False, default=True, comment="Current/active document")
    
    # Document validity (required for passports)
    issue_date = Column(Date, nullable=True, comment="Document issue date")
    expiry_date = Column(Date, nullable=True, comment="Document expiry date (required for passports)")
    
    # TODO: Add document image storage when file management is implemented
    # document_image_path = Column(String(500), nullable=True, comment="Path to document scan/photo")
    
    # Audit fields
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)
    
    # Relationships
    person = relationship("Person", back_populates="aliases")
    
    def __repr__(self):
        return f"<PersonAlias(id={self.id}, type='{self.document_type}', number='{self.document_number}', primary={self.is_primary})>"


class PersonAddress(BaseModel):
    """
    Person addresses - Madagascar address format
    Supports multiple addresses with primary selection per type
    """
    __tablename__ = "person_addresses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    person_id = Column(UUID(as_uuid=True), ForeignKey('persons.id'), nullable=False, index=True)
    
    # Address type and priority
    address_type = Column(String(20), nullable=False, comment="residential or postal")
    is_primary = Column(Boolean, nullable=False, default=False, comment="Primary address of this type")
    
    # Madagascar address structure
    street_line1 = Column(String(100), nullable=True, comment="Lot/parcel details or P.O. Box")
    street_line2 = Column(String(100), nullable=True, comment="Additional street detail or neighborhood")
    locality = Column(String(100), nullable=False, comment="Village, quartier, city")
    postal_code = Column(String(3), nullable=False, comment="3-digit Madagascar postal code")
    town = Column(String(100), nullable=False, comment="Town/city name for postal delivery")
    country = Column(String(50), nullable=False, default="MADAGASCAR", comment="Country name")
    
    # Geographic details
    province_code = Column(String(10), nullable=True, comment="Madagascar province/region code")
    
    # Address validation status
    is_verified = Column(Boolean, nullable=False, default=False, comment="Address verified by postal service")
    verified_date = Column(DateTime, nullable=True, comment="Date address was verified")
    
    # TODO: Add GPS coordinates when location services are implemented
    # latitude = Column(Numeric(10, 8), nullable=True, comment="GPS latitude")
    # longitude = Column(Numeric(11, 8), nullable=True, comment="GPS longitude")
    
    # TODO: Add address validation against Madagascar postal database
    # postal_validation_status = Column(String(20), nullable=True, comment="VALID/INVALID/PENDING")
    # postal_validation_date = Column(DateTime, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)
    
    # Relationships
    person = relationship("Person", back_populates="addresses")
    
    @property
    def formatted_address(self) -> str:
        """Format address according to Madagascar postal standards"""
        lines = []
        if self.street_line1:
            lines.append(self.street_line1)
        if self.street_line2:
            lines.append(self.street_line2)
        lines.append(self.locality)
        lines.append(f"{self.postal_code} {self.town}")
        lines.append(self.country)
        return "\n".join(lines)
    
    def __repr__(self):
        return f"<PersonAddress(id={self.id}, type='{self.address_type}', locality='{self.locality}', primary={self.is_primary})>"


# TODO: Add PersonDuplicateCheck model when duplicate detection is implemented
# class PersonDuplicateCheck(BaseModel):
#     """
#     Duplicate detection results and manual review tracking
#     """
#     __tablename__ = "person_duplicate_checks"
#     
#     id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     person_id = Column(UUID(as_uuid=True), ForeignKey('persons.id'), nullable=False)
#     potential_duplicate_id = Column(UUID(as_uuid=True), ForeignKey('persons.id'), nullable=False)
#     similarity_score = Column(Numeric(5, 2), nullable=False, comment="Similarity percentage (0-100)")
#     match_criteria = Column(JSON, nullable=True, comment="Fields that matched")
#     review_status = Column(String(20), nullable=False, default="PENDING", comment="PENDING/REVIEWED/CONFIRMED/DISMISSED")
#     reviewed_by = Column(String(100), nullable=True)
#     reviewed_at = Column(DateTime, nullable=True)
#     notes = Column(Text, nullable=True) 