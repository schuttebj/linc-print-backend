"""
Document Generation Test API Endpoints
Test endpoints for A4 document generation and preview
"""

from typing import Dict, Any, Optional
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Response, Query, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.services.document_generator import document_generator

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/templates", summary="Get Available Templates")
async def get_available_templates(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get list of available document templates
    """
    return {
        "templates": document_generator.get_supported_templates(),
        "generator_version": document_generator.version,
        "timestamp": datetime.now().isoformat()
    }

@router.get("/sample-pdf/{template_type}", summary="Generate Sample PDF by Template")
async def generate_sample_pdf(
    template_type: str = Path(..., description="Template type (receipt, card_order_confirmation)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a sample PDF for any template type
    
    Returns a PDF file that can be previewed and printed from the frontend.
    This is a test endpoint to validate the document generation system.
    """
    try:
        logger.info(f"Generating sample {template_type} PDF for user: {current_user.email}")
        
        # Validate template type
        if template_type not in document_generator.get_supported_templates():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported template type: {template_type}"
            )
        
        # Get sample data
        sample_data = document_generator.get_sample_data(template_type)
        
        # Add current user info if applicable
        if template_type == "receipt":
            sample_data['processed_by'] = f"{current_user.first_name} {current_user.last_name}" if current_user.first_name else current_user.email
        
        # Generate PDF
        pdf_bytes = document_generator.generate_document(template_type, sample_data)
        
        logger.info(f"Successfully generated sample {template_type} PDF ({len(pdf_bytes)} bytes)")
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=sample_{template_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                "Content-Length": str(len(pdf_bytes)),
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating sample {template_type} PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate sample {template_type}: {str(e)}"
        )

@router.get("/sample-data/{template_type}", summary="Get Sample Data by Template")
async def get_sample_data(
    template_type: str = Path(..., description="Template type (receipt, card_order_confirmation)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get sample data for any template type
    
    Returns the data structure used for document generation.
    Useful for understanding the expected data format.
    """
    try:
        logger.info(f"Retrieving sample {template_type} data for user: {current_user.email}")
        
        # Validate template type
        if template_type not in document_generator.get_supported_templates():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported template type: {template_type}"
            )
        
        sample_data = document_generator.get_sample_data(template_type)
        
        # Add current user info if applicable
        if template_type == "receipt":
            sample_data['processed_by'] = f"{current_user.first_name} {current_user.last_name}" if current_user.first_name else current_user.email
        
        return {
            "success": True,
            "template_type": template_type,
            "data": sample_data,
            "generator_version": document_generator.version,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error retrieving sample {template_type} data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve sample data: {str(e)}"
        )

@router.post("/custom-receipt-pdf", summary="Generate Custom Receipt PDF")
async def generate_custom_receipt_pdf(
    receipt_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a custom receipt PDF with provided data
    
    Allows testing with custom data to validate different scenarios.
    """
    try:
        logger.info(f"Generating custom receipt PDF for user: {current_user.email}")
        
        # Add metadata
        receipt_data['generated_by'] = current_user.email
        receipt_data['generation_timestamp'] = datetime.now().isoformat()
        
        # Generate PDF
        pdf_bytes = document_generator.generate_receipt(receipt_data)
        
        logger.info(f"Successfully generated custom receipt PDF ({len(pdf_bytes)} bytes)")
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=custom_receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                "Content-Length": str(len(pdf_bytes)),
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating custom receipt PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate custom receipt: {str(e)}"
        )

@router.get("/generator-info", summary="Get Document Generator Information")
async def get_generator_info(
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get information about the document generator service
    """
    return {
        "service": "Document Generator",
        "version": document_generator.version,
        "status": "active",
        "supported_formats": ["pdf"],
        "supported_templates": ["receipt"],
        "timestamp": datetime.now().isoformat()
    }
