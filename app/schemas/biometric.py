"""
Pydantic schemas for Biometric Template Management API
Handles fingerprint enrollment, verification, and identification requests/responses
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID
import base64


# Fingerprint Enrollment Schemas

class FingerprintEnrollRequest(BaseModel):
    """Request to enroll a new fingerprint template"""
    
    person_id: UUID = Field(..., description="UUID of the person")
    application_id: Optional[UUID] = Field(None, description="Associated application ID")
    finger_position: int = Field(..., ge=1, le=10, description="ISO finger position (1-10)")
    template_base64: str = Field(..., description="Base64-encoded template from WebAgent")
    template_format: str = Field("ISO19794-2", description="Template format")
    quality_level: Optional[int] = Field(6, ge=1, le=11, description="Quality level used during extraction")
    quality_score: Optional[int] = Field(None, ge=0, le=100, description="Quality score from scanner")
    capture_device: Optional[str] = Field(None, max_length=100, description="BioMini device model")
    capture_software: Optional[str] = Field("WebAgent", max_length=100, description="Capture software")
    scanner_serial: Optional[str] = Field(None, max_length=50, description="Scanner serial number")
    encrypted_key: Optional[str] = Field(None, max_length=100, description="Encryption key if used")

    @validator('template_base64')
    def validate_base64(cls, v):
        try:
            base64.b64decode(v)
            return v
        except Exception:
            raise ValueError('Invalid Base64 template data')

    @validator('template_format')
    def validate_format(cls, v):
        valid_formats = ['ISO19794-2', 'ANSI-378', 'XPERIX']
        if v not in valid_formats:
            raise ValueError(f'Template format must be one of: {valid_formats}')
        return v

    class Config:
        schema_extra = {
            "example": {
                "person_id": "123e4567-e89b-12d3-a456-426614174000",
                "finger_position": 2,
                "template_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA...",
                "template_format": "ISO19794-2",
                "quality_level": 6,
                "quality_score": 85,
                "capture_device": "BioMini Slim 2",
                "scanner_serial": "BMK12345"
            }
        }


class FingerprintEnrollResponse(BaseModel):
    """Response after successful fingerprint enrollment"""
    
    template_id: UUID = Field(..., description="Generated template ID")
    person_id: UUID = Field(..., description="Person ID")
    finger_position: int = Field(..., description="Finger position")
    template_format: str = Field(..., description="Template format")
    template_size: int = Field(..., description="Template size in bytes")
    quality_score: Optional[int] = Field(None, description="Quality score")
    template_hash: str = Field(..., description="SHA-256 hash of template")
    enrolled_at: datetime = Field(..., description="Enrollment timestamp")
    message: str = Field(..., description="Success message")

    class Config:
        schema_extra = {
            "example": {
                "template_id": "789e4567-e89b-12d3-a456-426614174001",
                "person_id": "123e4567-e89b-12d3-a456-426614174000",
                "finger_position": 2,
                "template_format": "ISO19794-2",
                "template_size": 488,
                "quality_score": 85,
                "template_hash": "a1b2c3d4e5f6...",
                "enrolled_at": "2024-01-01T12:00:00Z",
                "message": "Fingerprint template enrolled successfully"
            }
        }


# Fingerprint Verification Schemas (1:1)

class FingerprintVerifyRequest(BaseModel):
    """Request to verify a fingerprint against a stored template"""
    
    template_id: UUID = Field(..., description="ID of stored template to verify against")
    probe_template_base64: str = Field(..., description="Base64-encoded probe template")
    application_id: Optional[UUID] = Field(None, description="Associated application ID")
    security_level: Optional[int] = Field(4, ge=1, le=7, description="Security level (1-7)")
    use_webagent_matching: bool = Field(True, description="Use WebAgent for matching vs server-side")

    @validator('probe_template_base64')
    def validate_probe_base64(cls, v):
        try:
            base64.b64decode(v)
            return v
        except Exception:
            raise ValueError('Invalid Base64 probe template data')

    class Config:
        schema_extra = {
            "example": {
                "template_id": "789e4567-e89b-12d3-a456-426614174001",
                "probe_template_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA...",
                "security_level": 4,
                "use_webagent_matching": True
            }
        }


class FingerprintVerifyResponse(BaseModel):
    """Response after fingerprint verification"""
    
    template_id: UUID = Field(..., description="Template ID that was verified against")
    person_id: UUID = Field(..., description="Person ID")
    finger_position: int = Field(..., description="Finger position")
    match_found: bool = Field(..., description="Whether a match was found")
    match_score: Optional[int] = Field(None, description="Matching score (0-100)")
    security_level: int = Field(..., description="Security level used")
    matcher_engine: str = Field(..., description="Matching engine used")
    verification_time_ms: int = Field(..., description="Verification time in milliseconds")
    message: str = Field(..., description="Result message")

    class Config:
        schema_extra = {
            "example": {
                "template_id": "789e4567-e89b-12d3-a456-426614174001",
                "person_id": "123e4567-e89b-12d3-a456-426614174000",
                "finger_position": 2,
                "match_found": True,
                "match_score": 92,
                "security_level": 4,
                "matcher_engine": "webagent",
                "verification_time_ms": 150,
                "message": "Verification completed successfully"
            }
        }


# Fingerprint Identification Schemas (1:N)

class FingerprintIdentifyRequest(BaseModel):
    """Request to identify a person from a fingerprint"""
    
    probe_template_base64: str = Field(..., description="Base64-encoded probe template")
    finger_position: Optional[int] = Field(None, ge=1, le=10, description="Filter by finger position")
    candidate_person_ids: Optional[List[UUID]] = Field(None, description="Limit search to specific persons")
    max_candidates: Optional[int] = Field(1000, ge=1, le=10000, description="Maximum templates to check")
    max_results: Optional[int] = Field(10, ge=1, le=100, description="Maximum results to return")
    security_level: Optional[int] = Field(4, ge=1, le=7, description="Security level (1-7)")
    return_all_matches: bool = Field(False, description="Return all matches vs first match only")
    use_webagent_matching: bool = Field(False, description="Use WebAgent for matching")
    application_id: Optional[UUID] = Field(None, description="Associated application ID")

    @validator('probe_template_base64')
    def validate_probe_base64(cls, v):
        try:
            base64.b64decode(v)
            return v
        except Exception:
            raise ValueError('Invalid Base64 probe template data')

    class Config:
        schema_extra = {
            "example": {
                "probe_template_base64": "UklGRiQAAABXQVZFZm10IBAAAAABAAEA...",
                "finger_position": 2,
                "max_candidates": 1000,
                "max_results": 5,
                "security_level": 4,
                "return_all_matches": False
            }
        }


class FingerprintMatch(BaseModel):
    """Individual match result from identification"""
    
    template_id: UUID = Field(..., description="Matched template ID")
    person_id: UUID = Field(..., description="Matched person ID")
    finger_position: int = Field(..., description="Finger position")
    match_score: Optional[int] = Field(None, description="Match score")
    template_quality: Optional[int] = Field(None, description="Template quality score")


class FingerprintIdentifyResponse(BaseModel):
    """Response after fingerprint identification"""
    
    matches_found: int = Field(..., description="Number of matches found")
    matches: List[FingerprintMatch] = Field(..., description="List of matches (sorted by score)")
    candidates_checked: int = Field(..., description="Number of templates checked")
    search_time_ms: int = Field(..., description="Search time in milliseconds")
    security_level: int = Field(..., description="Security level used")
    message: str = Field(..., description="Result message")

    class Config:
        schema_extra = {
            "example": {
                "matches_found": 1,
                "matches": [
                    {
                        "template_id": "789e4567-e89b-12d3-a456-426614174001",
                        "person_id": "123e4567-e89b-12d3-a456-426614174000",
                        "finger_position": 2,
                        "match_score": 95,
                        "template_quality": 85
                    }
                ],
                "candidates_checked": 1000,
                "search_time_ms": 250,
                "security_level": 4,
                "message": "Identification completed: 1 matches found"
            }
        }


# Template Information Schemas

class FingerprintTemplateInfo(BaseModel):
    """Information about a stored fingerprint template"""
    
    template_id: UUID = Field(..., description="Template ID")
    person_id: UUID = Field(..., description="Person ID")
    finger_position: int = Field(..., description="Finger position")
    template_format: str = Field(..., description="Template format")
    template_size: int = Field(..., description="Template size in bytes")
    quality_score: Optional[int] = Field(None, description="Quality score")
    is_verified: bool = Field(..., description="Whether template is verified")
    enrolled_at: datetime = Field(..., description="Enrollment timestamp")
    captured_by: Optional[UUID] = Field(None, description="User who captured template")

    class Config:
        schema_extra = {
            "example": {
                "template_id": "789e4567-e89b-12d3-a456-426614174001",
                "person_id": "123e4567-e89b-12d3-a456-426614174000",
                "finger_position": 2,
                "template_format": "ISO19794-2",
                "template_size": 488,
                "quality_score": 85,
                "is_verified": True,
                "enrolled_at": "2024-01-01T12:00:00Z",
                "captured_by": "456e4567-e89b-12d3-a456-426614174002"
            }
        }


# System Statistics Schema

class BiometricSystemStats(BaseModel):
    """System-wide biometric statistics"""
    
    total_templates: int = Field(..., description="Total active templates")
    total_persons_enrolled: int = Field(..., description="Total persons with templates")
    total_verifications: int = Field(..., description="Total verification attempts")
    verifications_24h: int = Field(..., description="Verifications in last 24 hours")
    system_status: str = Field(..., description="System operational status")

    class Config:
        schema_extra = {
            "example": {
                "total_templates": 15420,
                "total_persons_enrolled": 12350,
                "total_verifications": 45890,
                "verifications_24h": 234,
                "system_status": "operational"
            }
        }


# Frontend Integration Schemas (for React app)

class WebAgentCaptureRequest(BaseModel):
    """Request to initiate WebAgent capture workflow"""
    
    person_id: UUID = Field(..., description="Person ID")
    finger_positions: List[int] = Field(..., description="Finger positions to capture (1-10)")
    template_format: str = Field("ISO19794-2", description="Template format")
    quality_level: int = Field(6, ge=1, le=11, description="Quality level")
    capture_session_id: Optional[str] = Field(None, description="Session ID for tracking")

    class Config:
        schema_extra = {
            "example": {
                "person_id": "123e4567-e89b-12d3-a456-426614174000",
                "finger_positions": [2, 7],
                "template_format": "ISO19794-2",
                "quality_level": 6,
                "capture_session_id": "session_123"
            }
        }


class WebAgentCaptureResponse(BaseModel):
    """Response with capture instructions for frontend"""
    
    session_id: str = Field(..., description="Capture session ID")
    instructions: str = Field(..., description="Instructions for user")
    webagent_config: Dict[str, Any] = Field(..., description="WebAgent configuration")
    expected_templates: int = Field(..., description="Number of templates expected")

    class Config:
        schema_extra = {
            "example": {
                "session_id": "session_123",
                "instructions": "Please scan right index finger, then left index finger",
                "webagent_config": {
                    "template_type": 2,
                    "quality_level": 6,
                    "security_level": 4
                },
                "expected_templates": 2
            }
        }
