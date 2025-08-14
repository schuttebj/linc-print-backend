"""
Biometric Template Storage Models for Production Fingerprint System
Implements secure storage and matching of fingerprint templates

Based on BioMini WebAgent documentation and best practices:
- Stores ISO 19794-2 templates for vendor independence
- Raw template bytes for AFIS compatibility
- Proper indexing for 1:N identification scaling
- Audit trail for security compliance
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, LargeBinary, SmallInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime
from typing import Optional

Base = declarative_base()


class FingerprintTemplate(Base):
    """
    Production fingerprint template storage
    Stores raw template bytes for AFIS compatibility and vendor independence
    """
    __tablename__ = "fingerprint_templates"

    # Primary key and timestamps
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Template unique identifier")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="Creation timestamp")
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="Last update timestamp")

    # Core identification
    person_id = Column(UUID(as_uuid=True), ForeignKey('persons.id'), nullable=False, index=True, comment="Person this template belongs to")
    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=True, index=True, comment="Application where template was captured")
    
    # Finger position (ISO/IEC 19794-2 standard)
    finger_position = Column(SmallInteger, nullable=False, comment="ISO finger position code (1-10: R thumb, R index, R middle, R ring, R little, L thumb, L index, L middle, L ring, L little)")
    
    # Template data and format
    template_format = Column(String(20), nullable=False, comment="Template format: ISO19794-2, ANSI-378, or XPERIX")
    template_bytes = Column(LargeBinary, nullable=False, comment="Raw template bytes (Base64-decoded from WebAgent)")
    template_size = Column(Integer, nullable=False, comment="Template size in bytes")
    
    # Quality and capture metadata
    quality_level = Column(SmallInteger, nullable=True, comment="Quality level used during extraction (1-11)")
    quality_score = Column(SmallInteger, nullable=True, comment="Quality score returned by scanner (0-100)")
    
    # Capture information
    capture_device = Column(String(100), nullable=True, comment="BioMini device model/serial")
    capture_software = Column(String(100), nullable=True, comment="WebAgent version")
    scanner_serial = Column(String(50), nullable=True, comment="Scanner serial number")
    
    # Processing flags
    is_active = Column(Boolean, nullable=False, default=True, comment="Template is active for matching")
    is_verified = Column(Boolean, nullable=False, default=False, comment="Template has been verified by operator")
    
    # Security and audit
    encrypted_key = Column(String(100), nullable=True, comment="Encryption key if template was encrypted by WebAgent")
    template_hash = Column(String(64), nullable=True, comment="SHA-256 hash of template bytes for integrity")
    
    # Audit trail
    captured_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who captured template")
    verified_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who verified template")
    verified_at = Column(DateTime, nullable=True, comment="Verification timestamp")
    
    # Relationships
    person = relationship("Person", backref="fingerprint_templates")
    application = relationship("Application", backref="fingerprint_templates")
    captured_by_user = relationship("User", foreign_keys=[captured_by])
    verified_by_user = relationship("User", foreign_keys=[verified_by])
    
    # Additional indexes for performance
    __table_args__ = (
        {'comment': 'Production fingerprint template storage with ISO standards compliance'}
    )

    def __repr__(self):
        return f"<FingerprintTemplate(person_id={self.person_id}, finger={self.finger_position}, format='{self.template_format}')>"


class FingerprintVerificationLog(Base):
    """
    Audit log for fingerprint verification attempts
    Tracks all 1:1 and 1:N matching attempts for security and compliance
    """
    __tablename__ = "fingerprint_verification_logs"

    # Primary key and timestamps
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Log entry unique identifier")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="Creation timestamp")
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="Last update timestamp")

    # Verification context
    verification_type = Column(String(10), nullable=False, comment="Type: 1:1 (verify) or 1:N (identify)")
    person_id = Column(UUID(as_uuid=True), ForeignKey('persons.id'), nullable=True, index=True, comment="Person being verified (for 1:1)")
    application_id = Column(UUID(as_uuid=True), ForeignKey('applications.id'), nullable=True, comment="Related application")
    
    # Template information
    probe_template_id = Column(UUID(as_uuid=True), ForeignKey('fingerprint_templates.id'), nullable=True, comment="Template being matched against")
    finger_position = Column(SmallInteger, nullable=False, comment="Finger position of probe")
    
    # Verification results
    match_found = Column(Boolean, nullable=False, comment="Whether a match was found")
    match_score = Column(Integer, nullable=True, comment="Matching score from engine")
    security_level = Column(SmallInteger, nullable=True, comment="Security level used (1-7)")
    matcher_engine = Column(String(50), nullable=False, comment="Matching engine used (WebAgent, AFIS, etc.)")
    
    # Performance metrics
    verification_time_ms = Column(Integer, nullable=True, comment="Time taken for verification in milliseconds")
    candidates_checked = Column(Integer, nullable=True, comment="Number of templates checked (for 1:N)")
    
    # System information
    client_ip = Column(String(45), nullable=True, comment="Client IP address")
    user_agent = Column(String(500), nullable=True, comment="Client user agent")
    session_id = Column(String(100), nullable=True, comment="Session identifier")
    
    # Audit
    performed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who performed verification")
    
    # Relationships
    person = relationship("Person")
    application = relationship("Application")
    template = relationship("FingerprintTemplate")
    performed_by_user = relationship("User", foreign_keys=[performed_by])

    def __repr__(self):
        return f"<FingerprintVerificationLog(type='{self.verification_type}', match={self.match_found}, score={self.match_score})>"


class BiometricSystemConfig(Base):
    """
    System configuration for biometric matching parameters
    Allows runtime adjustment of security levels and matching thresholds
    """
    __tablename__ = "biometric_system_config"

    # Primary key and timestamps
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Config entry unique identifier")
    created_at = Column(DateTime, nullable=False, default=func.now(), comment="Creation timestamp")
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now(), comment="Last update timestamp")

    # Configuration key and value
    config_key = Column(String(100), nullable=False, unique=True, comment="Configuration parameter name")
    config_value = Column(String(500), nullable=False, comment="Configuration parameter value")
    config_type = Column(String(20), nullable=False, comment="Data type: string, integer, boolean, float")
    
    # Metadata
    description = Column(Text, nullable=True, comment="Human-readable description of parameter")
    category = Column(String(50), nullable=True, comment="Configuration category")
    is_active = Column(Boolean, nullable=False, default=True, comment="Configuration is active")
    
    # Audit
    updated_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True, comment="User who last updated")
    
    # Relationship
    updated_by_user = relationship("User", foreign_keys=[updated_by])

    def __repr__(self):
        return f"<BiometricSystemConfig(key='{self.config_key}', value='{self.config_value}')>"


# ISO/IEC 19794-2 Finger Position Codes (for reference)
ISO_FINGER_POSITIONS = {
    1: "Right Thumb",
    2: "Right Index", 
    3: "Right Middle",
    4: "Right Ring",
    5: "Right Little",
    6: "Left Thumb",
    7: "Left Index",
    8: "Left Middle", 
    9: "Left Ring",
    10: "Left Little"
}

# Template format constants
TEMPLATE_FORMATS = {
    'ISO19794_2': 'ISO19794-2',
    'ANSI_378': 'ANSI-378', 
    'XPERIX': 'XPERIX'
}
