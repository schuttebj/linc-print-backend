"""
G-SDK Server-Side Biometric API Endpoints
Provides REST API for server-side fingerprint matching using G-SDK Device Gateway
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import logging

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.services.gsdk_biometric_service import get_gsdk_service, GSdkBiometricService
from app.schemas.biometric import (
    FingerprintEnrollRequest, 
    FingerprintEnrollResponse,
    FingerprintVerifyRequest,
    FingerprintVerifyResponse,
    FingerprintIdentifyRequest,
    FingerprintIdentifyResponse,
    BiometricSystemStats
)

router = APIRouter()

@router.get("/status")
async def get_gsdk_status(
    gsdk_service: GSdkBiometricService = Depends(get_gsdk_service),
    current_user: User = Depends(get_current_user)
):
    """Get G-SDK system status"""
    try:
        status = await gsdk_service.get_system_status()
        return {
            "success": True,
            "status": status,
            "message": "G-SDK status retrieved successfully"
        }
    except Exception as e:
        logging.error(f"Failed to get G-SDK status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@router.post("/initialize")
async def initialize_gsdk(
    gateway_ip: str = "127.0.0.1",
    gateway_port: int = 4000,
    device_ip: str = "192.168.0.110",
    device_port: int = 51211,
    gsdk_service: GSdkBiometricService = Depends(get_gsdk_service),
    current_user: User = Depends(get_current_user)
):
    """Initialize G-SDK connection to gateway and device"""
    try:
        # Initialize gateway connection
        if not await gsdk_service.initialize():
            raise HTTPException(status_code=500, detail="Failed to connect to G-SDK gateway")
        
        # Connect to device
        if not await gsdk_service.connect_device(device_ip, device_port):
            raise HTTPException(status_code=500, detail="Failed to connect to BioStar device")
        
        # Enable server matching
        if not await gsdk_service.enable_server_matching():
            logging.warning("Failed to enable server matching, continuing anyway")
        
        return {
            "success": True,
            "message": "G-SDK initialized successfully",
            "device_id": gsdk_service.device_id,
            "device_info": str(gsdk_service.device_info)
        }
        
    except Exception as e:
        logging.error(f"G-SDK initialization failed: {e}")
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")

@router.post("/capture")
async def capture_fingerprint(
    template_format: int = 0,  # SUPREMA format
    quality_threshold: int = 40,
    gsdk_service: GSdkBiometricService = Depends(get_gsdk_service),
    current_user: User = Depends(get_current_user)
):
    """Capture fingerprint using G-SDK device"""
    try:
        if not gsdk_service.is_connected:
            raise HTTPException(status_code=400, detail="G-SDK device not connected. Call /initialize first.")
        
        template_base64, image_bytes = await gsdk_service.capture_fingerprint(
            template_format=template_format,
            quality_threshold=quality_threshold
        )
        
        return {
            "success": True,
            "template_base64": template_base64,
            "template_size": len(template_base64),
            "image_size": len(image_bytes),
            "message": "Fingerprint captured successfully using G-SDK"
        }
        
    except Exception as e:
        logging.error(f"G-SDK fingerprint capture failed: {e}")
        raise HTTPException(status_code=500, detail=f"Capture failed: {str(e)}")

@router.post("/enroll", response_model=Dict[str, Any])
async def enroll_fingerprint_gsdk(
    person_id: str,
    finger_position: int = 1,
    template_format: int = 0,
    quality_threshold: int = 40,
    gsdk_service: GSdkBiometricService = Depends(get_gsdk_service),
    current_user: User = Depends(get_current_user)
):
    """Enroll fingerprint using G-SDK server-side processing"""
    try:
        if not gsdk_service.is_connected:
            raise HTTPException(status_code=400, detail="G-SDK device not connected. Call /initialize first.")
        
        # Capture fingerprint
        template_base64, image_bytes = await gsdk_service.capture_fingerprint(
            template_format=template_format,
            quality_threshold=quality_threshold
        )
        
        # Enroll template
        template_id = await gsdk_service.enroll_template(
            person_id=person_id,
            template_base64=template_base64,
            finger_position=finger_position
        )
        
        return {
            "success": True,
            "template_id": template_id,
            "person_id": person_id,
            "finger_position": finger_position,
            "template_size": len(template_base64),
            "matcher_engine": "gsdk_server",
            "message": "Fingerprint enrolled successfully using G-SDK"
        }
        
    except Exception as e:
        logging.error(f"G-SDK fingerprint enrollment failed: {e}")
        raise HTTPException(status_code=500, detail=f"Enrollment failed: {str(e)}")

@router.post("/verify", response_model=Dict[str, Any])
async def verify_fingerprint_gsdk(
    template_id: str,
    template_format: int = 0,
    quality_threshold: int = 40,
    gsdk_service: GSdkBiometricService = Depends(get_gsdk_service),
    current_user: User = Depends(get_current_user)
):
    """Verify fingerprint using G-SDK server-side matching"""
    try:
        if not gsdk_service.is_connected:
            raise HTTPException(status_code=400, detail="G-SDK device not connected. Call /initialize first.")
        
        # Capture fingerprint
        template_base64, image_bytes = await gsdk_service.capture_fingerprint(
            template_format=template_format,
            quality_threshold=quality_threshold
        )
        
        # Verify against stored template
        result = await gsdk_service.verify_fingerprint(
            template_base64=template_base64,
            stored_template_id=template_id
        )
        
        return {
            "success": True,
            "verified": result['verified'],
            "match_score": result['score'],
            "person_id": result.get('person_id'),
            "template_id": template_id,
            "matcher_engine": result['matcher_engine'],
            "message": result['message']
        }
        
    except Exception as e:
        logging.error(f"G-SDK fingerprint verification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

@router.post("/identify", response_model=Dict[str, Any])
async def identify_fingerprint_gsdk(
    max_results: int = 10,
    template_format: int = 0,
    quality_threshold: int = 40,
    gsdk_service: GSdkBiometricService = Depends(get_gsdk_service),
    current_user: User = Depends(get_current_user)
):
    """Perform 1:N identification using G-SDK server-side matching"""
    try:
        if not gsdk_service.is_connected:
            raise HTTPException(status_code=400, detail="G-SDK device not connected. Call /initialize first.")
        
        # Capture fingerprint
        template_base64, image_bytes = await gsdk_service.capture_fingerprint(
            template_format=template_format,
            quality_threshold=quality_threshold
        )
        
        # Perform 1:N identification
        result = await gsdk_service.identify_fingerprint(
            template_base64=template_base64,
            max_results=max_results
        )
        
        return {
            "success": True,
            "matches_found": result['matches_found'],
            "matches": result['matches'],
            "candidates_checked": result['candidates_checked'],
            "matcher_engine": result['matcher_engine'],
            "message": result['message']
        }
        
    except Exception as e:
        logging.error(f"G-SDK fingerprint identification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Identification failed: {str(e)}")

@router.get("/templates")
async def get_gsdk_templates(
    gsdk_service: GSdkBiometricService = Depends(get_gsdk_service),
    current_user: User = Depends(get_current_user)
):
    """Get all templates stored in G-SDK system"""
    try:
        templates = await gsdk_service.get_all_templates()
        
        return {
            "success": True,
            "templates": templates,
            "total_count": len(templates),
            "message": "G-SDK templates retrieved successfully"
        }
        
    except Exception as e:
        logging.error(f"Failed to get G-SDK templates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get templates: {str(e)}")

@router.delete("/templates/{template_id}")
async def delete_gsdk_template(
    template_id: str,
    gsdk_service: GSdkBiometricService = Depends(get_gsdk_service),
    current_user: User = Depends(get_current_user)
):
    """Delete a template from G-SDK system"""
    try:
        if template_id in gsdk_service.templates_cache:
            del gsdk_service.templates_cache[template_id]
            return {
                "success": True,
                "message": f"Template {template_id} deleted successfully"
            }
        else:
            raise HTTPException(status_code=404, detail="Template not found")
        
    except Exception as e:
        logging.error(f"Failed to delete G-SDK template: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete template: {str(e)}")

@router.post("/disconnect")
async def disconnect_gsdk(
    gsdk_service: GSdkBiometricService = Depends(get_gsdk_service),
    current_user: User = Depends(get_current_user)
):
    """Disconnect from G-SDK device and gateway"""
    try:
        await gsdk_service.disconnect()
        
        return {
            "success": True,
            "message": "G-SDK disconnected successfully"
        }
        
    except Exception as e:
        logging.error(f"G-SDK disconnect failed: {e}")
        raise HTTPException(status_code=500, detail=f"Disconnect failed: {str(e)}")

@router.get("/compare/systems")
async def compare_biometric_systems(
    gsdk_service: GSdkBiometricService = Depends(get_gsdk_service),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Compare WebAgent vs G-SDK system performance and capabilities"""
    try:
        # Get G-SDK status
        gsdk_status = await gsdk_service.get_system_status()
        gsdk_templates = await gsdk_service.get_all_templates()
        
        # Get WebAgent/PostgreSQL stats (simplified)
        from app.models.biometric import FingerprintTemplate
        webagent_templates_count = db.query(FingerprintTemplate).filter(
            FingerprintTemplate.is_active == True
        ).count()
        
        comparison = {
            "webagent_system": {
                "name": "WebAgent Client-Side",
                "templates_stored": webagent_templates_count,
                "storage": "PostgreSQL",
                "matching": "Client-side UFMatcher",
                "scalability": "Limited (client downloads all templates)",
                "cost": "Free",
                "pros": ["No server setup", "Uses existing hardware", "Proven technology"],
                "cons": ["Client-side bottleneck", "Network transfer overhead", "Limited scalability"]
            },
            "gsdk_system": {
                "name": "G-SDK Server-Side", 
                "templates_stored": len(gsdk_templates),
                "storage": "Memory/Database",
                "matching": "Server-side processing",
                "scalability": "High (server-side processing)",
                "cost": "Free (Device Gateway)",
                "device_connected": gsdk_status['connected'],
                "pros": ["Server-side processing", "Scalable architecture", "No client downloads"],
                "cons": ["Requires gateway setup", "Additional infrastructure", "Development complexity"]
            },
            "recommendation": {
                "current_scale": "WebAgent system sufficient for < 10K records",
                "large_scale": "G-SDK system recommended for > 10K records",
                "hybrid_approach": "Use both systems for comparison and gradual migration"
            }
        }
        
        return {
            "success": True,
            "comparison": comparison,
            "message": "System comparison completed"
        }
        
    except Exception as e:
        logging.error(f"System comparison failed: {e}")
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")

@router.post("/admin/clear-cache")
async def clear_gsdk_cache(
    gsdk_service: GSdkBiometricService = Depends(get_gsdk_service),
    current_user: User = Depends(get_current_user)
):
    """Clear G-SDK template cache (for testing)"""
    try:
        gsdk_service.templates_cache.clear()
        
        return {
            "success": True,
            "message": "G-SDK template cache cleared successfully"
        }
        
    except Exception as e:
        logging.error(f"Failed to clear G-SDK cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")
