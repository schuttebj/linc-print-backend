"""
Biometric Template Management API
Production endpoints for fingerprint enrollment, verification, and identification

Based on BioMini WebAgent best practices:
- Frontend captures via WebAgent (ISO 19794-2 templates)
- Backend stores raw bytes securely
- Supports both WebAgent and future AFIS matching
- Full audit trail for compliance
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, text
import base64
import hashlib
import json
import time
from datetime import datetime

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.models.person import Person
from app.models.application import Application
from app.models.biometric import FingerprintTemplate, FingerprintVerificationLog, BiometricSystemConfig
from app.schemas.biometric import (
    FingerprintEnrollRequest, FingerprintEnrollResponse,
    FingerprintVerifyRequest, FingerprintVerifyResponse,
    FingerprintIdentifyRequest, FingerprintIdentifyResponse,
    FingerprintTemplateInfo, BiometricSystemStats
)

router = APIRouter()
security = HTTPBearer()


@router.post("/fingerprint/enroll", response_model=FingerprintEnrollResponse)
async def enroll_fingerprint(
    request: FingerprintEnrollRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    http_request: Request = None
):
    """
    Enroll a fingerprint template for a person
    
    Workflow:
    1. Frontend captures fingerprint via WebAgent
    2. Frontend extracts ISO 19794-2 template (Base64)
    3. Backend stores raw template bytes securely
    4. Returns template ID for future verification
    """
    
    # Validate person exists
    person = db.query(Person).filter(Person.id == request.person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    
    # Validate application if provided
    application = None
    if request.application_id:
        application = db.query(Application).filter(Application.id == request.application_id).first()
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
    
    # Decode Base64 template to raw bytes
    try:
        template_bytes = base64.b64decode(request.template_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid Base64 template data: {str(e)}")
    
    # Calculate template hash for integrity
    template_hash = hashlib.sha256(template_bytes).hexdigest()
    
    # Check for duplicate template (same person, finger, hash)
    existing = db.query(FingerprintTemplate).filter(
        and_(
            FingerprintTemplate.person_id == request.person_id,
            FingerprintTemplate.finger_position == request.finger_position,
            FingerprintTemplate.template_hash == template_hash,
            FingerprintTemplate.is_active == True
        )
    ).first()
    
    if existing:
        raise HTTPException(status_code=409, detail="Identical template already exists for this finger")
    
    # Create new template record
    template = FingerprintTemplate(
        person_id=request.person_id,
        application_id=request.application_id,
        finger_position=request.finger_position,
        template_format=request.template_format,
        template_bytes=template_bytes,
        template_size=len(template_bytes),
        quality_level=request.quality_level,
        quality_score=request.quality_score,
        capture_device=request.capture_device,
        capture_software=request.capture_software,
        scanner_serial=request.scanner_serial,
        encrypted_key=request.encrypted_key,
        template_hash=template_hash,
        captured_by=current_user.id,
        is_active=True,
        is_verified=False
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return FingerprintEnrollResponse(
        template_id=template.id,
        person_id=template.person_id,
        finger_position=template.finger_position,
        template_format=template.template_format,
        template_size=template.template_size,
        quality_score=template.quality_score,
        template_hash=template.template_hash,
        enrolled_at=template.created_at,
        message="Fingerprint template enrolled successfully"
    )


@router.post("/fingerprint/verify", response_model=FingerprintVerifyResponse)
async def verify_fingerprint(
    request: FingerprintVerifyRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    http_request: Request = None
):
    """
    Verify a live fingerprint against a stored template (1:1 verification)
    
    Two modes:
    1. WebAgent mode: Send template to WebAgent for matching
    2. Server mode: Use server-side AFIS (future implementation)
    """
    
    start_time = time.time()
    
    # Get stored template
    template = db.query(FingerprintTemplate).filter(
        and_(
            FingerprintTemplate.id == request.template_id,
            FingerprintTemplate.is_active == True
        )
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found or inactive")
    
    # Decode probe template
    try:
        probe_bytes = base64.b64decode(request.probe_template_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid probe template: {str(e)}")
    
    verification_result = False
    match_score = None
    matcher_engine = "server"
    
    if request.use_webagent_matching:
        # Use WebAgent for matching (requires WebAgent to be running)
        try:
            verification_result, match_score = await _verify_with_webagent(
                template.template_bytes,
                probe_bytes,
                request.security_level or 4
            )
            matcher_engine = "webagent"
        except Exception as e:
            # Fallback to server matching if WebAgent fails
            verification_result, match_score = _verify_with_server(
                template.template_bytes,
                probe_bytes,
                request.security_level or 4
            )
            matcher_engine = "server_fallback"
    else:
        # Use server-side matching
        verification_result, match_score = _verify_with_server(
            template.template_bytes,
            probe_bytes,
            request.security_level or 4
        )
    
    verification_time = int((time.time() - start_time) * 1000)  # milliseconds
    
    # Log verification attempt
    background_tasks.add_task(
        _log_verification,
        db=db,
        verification_type="1:1",
        person_id=template.person_id,
        application_id=request.application_id,
        probe_template_id=template.id,
        finger_position=template.finger_position,
        match_found=verification_result,
        match_score=match_score,
        security_level=request.security_level,
        matcher_engine=matcher_engine,
        verification_time_ms=verification_time,
        performed_by=current_user.id,
        client_ip=http_request.client.host if http_request else None,
        user_agent=http_request.headers.get("user-agent") if http_request else None
    )
    
    return FingerprintVerifyResponse(
        template_id=template.id,
        person_id=template.person_id,
        finger_position=template.finger_position,
        match_found=verification_result,
        match_score=match_score,
        security_level=request.security_level or 4,
        matcher_engine=matcher_engine,
        verification_time_ms=verification_time,
        message="Verification completed successfully"
    )


@router.post("/fingerprint/identify", response_model=FingerprintIdentifyResponse)
async def identify_fingerprint(
    request: FingerprintIdentifyRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    http_request: Request = None
):
    """
    Identify a person from a fingerprint (1:N identification)
    
    Searches against all stored templates to find matching person
    Uses candidate reduction for performance with large databases
    """
    
    start_time = time.time()
    
    # Decode probe template
    try:
        probe_bytes = base64.b64decode(request.probe_template_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid probe template: {str(e)}")
    
    # Build query for candidate templates
    query = db.query(FingerprintTemplate).filter(
        FingerprintTemplate.is_active == True
    )
    
    # Filter by finger position if specified
    if request.finger_position:
        query = query.filter(FingerprintTemplate.finger_position == request.finger_position)
    
    # Filter by person IDs if specified (for restricted searches)
    if request.candidate_person_ids:
        query = query.filter(FingerprintTemplate.person_id.in_(request.candidate_person_ids))
    
    # Limit results for performance
    max_candidates = request.max_candidates or 1000
    candidates = query.limit(max_candidates).all()
    
    if not candidates:
        raise HTTPException(status_code=404, detail="No candidate templates found")
    
    # Perform matching against candidates
    matches = []
    candidates_checked = 0
    
    for template in candidates:
        candidates_checked += 1
        
        if request.use_webagent_matching:
            try:
                match_found, score = await _verify_with_webagent(
                    template.template_bytes,
                    probe_bytes,
                    request.security_level or 4
                )
            except:
                match_found, score = _verify_with_server(
                    template.template_bytes,
                    probe_bytes,
                    request.security_level or 4
                )
        else:
            match_found, score = _verify_with_server(
                template.template_bytes,
                probe_bytes,
                request.security_level or 4
            )
        
        if match_found:
            matches.append({
                'template_id': template.id,
                'person_id': template.person_id,
                'finger_position': template.finger_position,
                'match_score': score,
                'template_quality': template.quality_score
            })
            
            # Stop at first match for 1:1 mode, or collect all for ranking
            if not request.return_all_matches:
                break
    
    # Sort matches by score (highest first)
    matches.sort(key=lambda x: x['match_score'] or 0, reverse=True)
    
    verification_time = int((time.time() - start_time) * 1000)
    
    # Log identification attempt
    background_tasks.add_task(
        _log_verification,
        db=db,
        verification_type="1:N",
        person_id=matches[0]['person_id'] if matches else None,
        application_id=request.application_id,
        probe_template_id=matches[0]['template_id'] if matches else None,
        finger_position=request.finger_position,
        match_found=len(matches) > 0,
        match_score=matches[0]['match_score'] if matches else None,
        security_level=request.security_level,
        matcher_engine="server",
        verification_time_ms=verification_time,
        candidates_checked=candidates_checked,
        performed_by=current_user.id,
        client_ip=http_request.client.host if http_request else None,
        user_agent=http_request.headers.get("user-agent") if http_request else None
    )
    
    return FingerprintIdentifyResponse(
        matches_found=len(matches),
        matches=matches[:request.max_results or 10],
        candidates_checked=candidates_checked,
        search_time_ms=verification_time,
        security_level=request.security_level or 4,
        message=f"Identification completed: {len(matches)} matches found"
    )


@router.get("/fingerprint/templates/{person_id}", response_model=List[FingerprintTemplateInfo])
async def get_person_templates(
    person_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all fingerprint templates for a person"""
    
    templates = db.query(FingerprintTemplate).filter(
        and_(
            FingerprintTemplate.person_id == person_id,
            FingerprintTemplate.is_active == True
        )
    ).all()
    
    return [
        FingerprintTemplateInfo(
            template_id=t.id,
            person_id=t.person_id,
            finger_position=t.finger_position,
            template_format=t.template_format,
            template_size=t.template_size,
            quality_score=t.quality_score,
            is_verified=t.is_verified,
            enrolled_at=t.created_at,
            captured_by=t.captured_by
        )
        for t in templates
    ]


@router.get("/system/stats", response_model=BiometricSystemStats)
async def get_system_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get biometric system statistics"""
    
    total_templates = db.query(func.count(FingerprintTemplate.id)).filter(
        FingerprintTemplate.is_active == True
    ).scalar()
    
    total_persons = db.query(func.count(func.distinct(FingerprintTemplate.person_id))).filter(
        FingerprintTemplate.is_active == True
    ).scalar()
    
    total_verifications = db.query(func.count(FingerprintVerificationLog.id)).scalar()
    
    recent_verifications = db.query(func.count(FingerprintVerificationLog.id)).filter(
        FingerprintVerificationLog.created_at >= func.now() - text("interval '24 hours'")
    ).scalar()
    
    return BiometricSystemStats(
        total_templates=total_templates,
        total_persons_enrolled=total_persons,
        total_verifications=total_verifications,
        verifications_24h=recent_verifications,
        system_status="operational"
    )


@router.post("/admin/initialize-tables")
async def initialize_biometric_tables(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Initialize biometric tables for development
    Creates all required tables and default configuration
    """
    
    from sqlalchemy import text
    
    # SQL commands to create biometric tables
    sql_commands = [
        # Fingerprint Templates Table
        """
        CREATE TABLE IF NOT EXISTS fingerprint_templates (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            deleted_at TIMESTAMPTZ,
            deleted_by UUID REFERENCES users(id) ON DELETE SET NULL,
            
            -- Core identification
            person_id UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
            application_id UUID REFERENCES applications(id) ON DELETE SET NULL,
            
            -- Finger position (ISO/IEC 19794-2 standard)
            finger_position SMALLINT NOT NULL CHECK (finger_position BETWEEN 1 AND 10),
            
            -- Template data and format
            template_format VARCHAR(20) NOT NULL CHECK (template_format IN ('ISO19794-2', 'ANSI-378', 'XPERIX')),
            template_bytes BYTEA NOT NULL,
            template_size INTEGER NOT NULL,
            
            -- Quality and capture metadata
            quality_level SMALLINT CHECK (quality_level BETWEEN 1 AND 11),
            quality_score SMALLINT CHECK (quality_score BETWEEN 0 AND 100),
            
            -- Capture information
            capture_device VARCHAR(100),
            capture_software VARCHAR(100),
            scanner_serial VARCHAR(50),
            
            -- Processing flags
            is_verified BOOLEAN NOT NULL DEFAULT FALSE,
            
            -- Security and audit
            encrypted_key VARCHAR(100),
            template_hash VARCHAR(64),
            
            -- Audit trail
            captured_by UUID REFERENCES users(id) ON DELETE SET NULL,
            verified_by UUID REFERENCES users(id) ON DELETE SET NULL,
            verified_at TIMESTAMPTZ
        );
        """,
        
        # Fingerprint Verification Logs Table
        """
        CREATE TABLE IF NOT EXISTS fingerprint_verification_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            deleted_at TIMESTAMPTZ,
            deleted_by UUID REFERENCES users(id) ON DELETE SET NULL,
            
            -- Verification context
            verification_type VARCHAR(10) NOT NULL CHECK (verification_type IN ('1:1', '1:N')),
            person_id UUID REFERENCES persons(id) ON DELETE SET NULL,
            application_id UUID REFERENCES applications(id) ON DELETE SET NULL,
            
            -- Template information
            probe_template_id UUID REFERENCES fingerprint_templates(id) ON DELETE SET NULL,
            finger_position SMALLINT NOT NULL CHECK (finger_position BETWEEN 1 AND 10),
            
            -- Verification results
            match_found BOOLEAN NOT NULL,
            match_score INTEGER CHECK (match_score BETWEEN 0 AND 100),
            security_level SMALLINT CHECK (security_level BETWEEN 1 AND 7),
            matcher_engine VARCHAR(50) NOT NULL,
            
            -- Performance metrics
            verification_time_ms INTEGER,
            candidates_checked INTEGER,
            
            -- System information
            client_ip INET,
            user_agent VARCHAR(500),
            session_id VARCHAR(100),
            
            -- Audit
            performed_by UUID REFERENCES users(id) ON DELETE SET NULL
        );
        """,
        
        # Biometric System Config Table
        """
        CREATE TABLE IF NOT EXISTS biometric_system_config (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            deleted_at TIMESTAMPTZ,
            deleted_by UUID REFERENCES users(id) ON DELETE SET NULL,
            
            -- Configuration key and value
            config_key VARCHAR(100) NOT NULL UNIQUE,
            config_value VARCHAR(500) NOT NULL,
            config_type VARCHAR(20) NOT NULL CHECK (config_type IN ('string', 'integer', 'boolean', 'float')),
            
            -- Metadata
            description TEXT,
            category VARCHAR(50)
        );
        """,
        
        # Insert default configuration
        """
        INSERT INTO biometric_system_config (config_key, config_value, config_type, description, category) VALUES
        ('default_security_level', '4', 'integer', 'Default security level for fingerprint matching (1-7)', 'matching'),
        ('default_template_format', 'ISO19794-2', 'string', 'Default template format for new enrollments', 'capture'),
        ('max_verification_time_ms', '5000', 'integer', 'Maximum time allowed for verification in milliseconds', 'performance'),
        ('enable_audit_logging', 'true', 'boolean', 'Enable detailed audit logging of verification attempts', 'security')
        ON CONFLICT (config_key) DO NOTHING;
        """
    ]
    
    try:
        # Execute all SQL commands
        for sql in sql_commands:
            db.execute(text(sql))
        
        db.commit()
        
        # Verify tables were created
        result = db.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('fingerprint_templates', 'fingerprint_verification_logs', 'biometric_system_config')
            ORDER BY table_name;
        """))
        
        created_tables = [row[0] for row in result]
        
        return {
            "message": "Biometric tables initialized successfully",
            "tables_created": created_tables,
            "total_tables": len(created_tables),
            "status": "success"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to initialize tables: {str(e)}")


@router.delete("/admin/reset-tables")
async def reset_biometric_tables(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Reset biometric tables for development
    Drops and recreates all biometric tables
    """
    
    from sqlalchemy import text
    
    try:
        # Drop tables in correct order (handle foreign key constraints)
        drop_commands = [
            "DROP TABLE IF EXISTS fingerprint_verification_logs CASCADE;",
            "DROP TABLE IF EXISTS fingerprint_templates CASCADE;", 
            "DROP TABLE IF EXISTS biometric_system_config CASCADE;"
        ]
        
        for sql in drop_commands:
            db.execute(text(sql))
        
        db.commit()
        
        return {
            "message": "Biometric tables reset successfully",
            "status": "success",
            "note": "All biometric data has been cleared. Use /admin/initialize-tables to recreate."
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to reset tables: {str(e)}")


# Helper functions

async def _verify_with_webagent(stored_template: bytes, probe_template: bytes, security_level: int) -> tuple[bool, Optional[int]]:
    """
    Use WebAgent for template verification
    Requires WebAgent running on localhost
    """
    
    # Convert templates back to Base64 for WebAgent
    stored_b64 = base64.b64encode(stored_template).decode('utf-8')
    probe_b64 = base64.b64encode(probe_template).decode('utf-8')
    
    # This would call the WebAgent API (implementation depends on your proxy setup)
    # For now, return placeholder implementation
    raise NotImplementedError("WebAgent integration requires proxy configuration")


def _verify_with_server(stored_template: bytes, probe_template: bytes, security_level: int) -> tuple[bool, Optional[int]]:
    """
    Server-side template matching
    Placeholder for future AFIS integration
    """
    
    # Simple binary comparison for demonstration
    # In production, this would use a proper AFIS engine
    
    if len(stored_template) != len(probe_template):
        return False, 0
    
    # Calculate similarity (very basic)
    matches = sum(a == b for a, b in zip(stored_template, probe_template))
    similarity = int((matches / len(stored_template)) * 100)
    
    # Determine threshold based on security level
    thresholds = {1: 60, 2: 65, 3: 70, 4: 75, 5: 80, 6: 85, 7: 90}
    threshold = thresholds.get(security_level, 75)
    
    return similarity >= threshold, similarity


def _log_verification(
    db: Session,
    verification_type: str,
    person_id: Optional[str],
    application_id: Optional[str],
    probe_template_id: Optional[str],
    finger_position: int,
    match_found: bool,
    match_score: Optional[int],
    security_level: Optional[int],
    matcher_engine: str,
    verification_time_ms: int,
    performed_by: str,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    candidates_checked: Optional[int] = None
):
    """Log verification attempt to audit trail"""
    
    log_entry = FingerprintVerificationLog(
        verification_type=verification_type,
        person_id=person_id,
        application_id=application_id,
        probe_template_id=probe_template_id,
        finger_position=finger_position,
        match_found=match_found,
        match_score=match_score,
        security_level=security_level,
        matcher_engine=matcher_engine,
        verification_time_ms=verification_time_ms,
        candidates_checked=candidates_checked,
        client_ip=client_ip,
        user_agent=user_agent,
        performed_by=performed_by
    )
    
    db.add(log_entry)
    db.commit()
