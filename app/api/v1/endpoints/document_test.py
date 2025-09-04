"""
Document Generation Test API Endpoints
Test endpoints for A4 document generation and preview
"""

from typing import Dict, Any, Optional
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.models.user import User
from app.services.document_generator import document_generator

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/sample-receipt-pdf", summary="Generate Sample Receipt PDF")
async def generate_sample_receipt_pdf(
    format: str = Query("pdf", description="Output format: pdf"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a sample receipt PDF for testing document generation
    
    Returns a PDF file that can be previewed and printed from the frontend.
    This is a test endpoint to validate the document generation system.
    """
    try:
        logger.info(f"Generating sample receipt PDF for user: {current_user.email}")
        
        # Get sample data
        sample_data = document_generator.get_sample_receipt_data()
        
        # Add current user info
        sample_data['processed_by'] = f"{current_user.first_name} {current_user.last_name}" if current_user.first_name else current_user.email
        
        # Generate PDF
        pdf_bytes = document_generator.generate_receipt(sample_data)
        
        logger.info(f"Successfully generated sample receipt PDF ({len(pdf_bytes)} bytes)")
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename=sample_receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                "Content-Length": str(len(pdf_bytes)),
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating sample receipt PDF: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate sample receipt: {str(e)}"
        )

@router.get("/sample-receipt-data", summary="Get Sample Receipt Data")
async def get_sample_receipt_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get sample receipt data for testing
    
    Returns the data structure used for receipt generation.
    Useful for understanding the expected data format.
    """
    try:
        logger.info(f"Retrieving sample receipt data for user: {current_user.email}")
        
        sample_data = document_generator.get_sample_receipt_data()
        
        # Add current user info
        sample_data['processed_by'] = f"{current_user.first_name} {current_user.last_name}" if current_user.first_name else current_user.email
        
        return {
            "success": True,
            "data": sample_data,
            "generator_version": document_generator.version,
            "generated_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error retrieving sample receipt data: {e}")
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
