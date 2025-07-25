"""
Test Card Design Endpoints for Local Development
Allows testing the Madagascar license card design and layout
"""

import base64
import io
import os
import tempfile
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Response, Query, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.services.card_generator import madagascar_card_generator, get_license_specifications
from app.core.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# Sample test data for Madagascar license
SAMPLE_LICENSE_DATA = {
    "first_name": "Rakoto",
    "last_name": "Andriamamy", 
    "surname": "Andriamamy",
    "names": "Rakoto",
    "birth_date": "15/05/1990",
    "date_of_birth": "15/05/1990",
    "gender": "M",
    "id_number": "301901500123",
    "license_number": "MG2024001234",
    "category": "B",
    "categories": ["B"],
    "restrictions": "0",
    "issue_date": "15/01/2024",
    "expiry_date": "15/01/2034",
    "first_issue_date": "15/01/2024",
    "issued_location": "Madagascar",
    "issuing_location": "Madagascar",
    "country": "Madagascar",
    "card_number": "T0100001234",
}

@router.get("/test-card/front", summary="Generate Test Card Front")
def generate_test_card_front(
    name: Optional[str] = Query(None, description="Override first name"),
    surname: Optional[str] = Query(None, description="Override last name"),
    license_number: Optional[str] = Query(None, description="Override license number")
) -> Response:
    """
    Generate a test card front image with sample data
    """
    try:
        # Create test data with any overrides
        test_data = SAMPLE_LICENSE_DATA.copy()
        if name:
            test_data["first_name"] = name
            test_data["names"] = name
        if surname:
            test_data["last_name"] = surname
            test_data["surname"] = surname
        if license_number:
            test_data["license_number"] = license_number
        
        # Generate front card image (no photo for basic test)
        front_base64 = madagascar_card_generator.generate_front(test_data, None)
        
        # Convert base64 to bytes
        image_bytes = base64.b64decode(front_base64)
        
        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": "inline; filename=test_card_front.png",
                "Cache-Control": "no-cache"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating test card front: {str(e)}")

@router.get("/test-card/back", summary="Generate Test Card Back")
def generate_test_card_back(
    license_number: Optional[str] = Query(None, description="Override license number")
) -> Response:
    """
    Generate a test card back image with sample data
    """
    try:
        # Create test data with any overrides
        test_data = SAMPLE_LICENSE_DATA.copy()
        if license_number:
            test_data["license_number"] = license_number
        
        # Generate back card image with enhanced barcode
        back_base64 = madagascar_card_generator.generate_back(test_data)
        
        # Convert base64 to bytes
        image_bytes = base64.b64decode(back_base64)
        
        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": "inline; filename=test_card_back.png",
                "Cache-Control": "no-cache"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating test card back: {str(e)}")

@router.get("/test-card/watermark", summary="Generate Test Watermark")
def generate_test_watermark() -> Response:
    """
    Generate a test watermark image
    """
    try:
        # Generate watermark image
        watermark_base64 = madagascar_card_generator.generate_watermark_template(1012, 638, "MADAGASCAR")
        
        # Convert base64 to bytes
        image_bytes = base64.b64decode(watermark_base64)
        
        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": "inline; filename=test_watermark.png",
                "Cache-Control": "no-cache"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating test watermark: {str(e)}")

@router.get("/test-card/viewer", response_class=HTMLResponse, summary="Card Design Viewer")
def card_design_viewer(
    name: Optional[str] = Query("Rakoto", description="First name"),
    surname: Optional[str] = Query("Andriamamy", description="Last name"),
    license_number: Optional[str] = Query("MG2024001234", description="License number")
):
    """
    HTML viewer to see both front and back cards side by side
    """
    
    # URL encode parameters for the image requests
    from urllib.parse import quote
    name_encoded = quote(name) if name else "Rakoto"
    surname_encoded = quote(surname) if surname else "Andriamamy" 
    license_encoded = quote(license_number) if license_number else "MG2024001234"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Madagascar License Card Design Test</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 2.5rem;
                font-weight: 300;
            }}
            .header p {{
                margin: 10px 0 0;
                opacity: 0.9;
                font-size: 1.1rem;
            }}
            .cards-container {{
                padding: 40px;
                display: flex;
                justify-content: center;
                gap: 40px;
                flex-wrap: wrap;
            }}
            .card-section {{
                text-align: center;
                background: #f8f9fa;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.08);
                transition: transform 0.3s ease;
            }}
            .card-section:hover {{
                transform: translateY(-5px);
            }}
            .card-section h2 {{
                margin-top: 0;
                color: #2c3e50;
                font-size: 1.5rem;
                margin-bottom: 20px;
            }}
            .card-image {{
                border: 3px solid #dee2e6;
                border-radius: 8px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                transition: transform 0.3s ease;
                max-width: 100%;
                height: auto;
            }}
            .card-image:hover {{
                transform: scale(1.05);
            }}
            .controls {{
                background: #f1f3f4;
                padding: 30px;
                border-top: 1px solid #dee2e6;
            }}
            .controls h3 {{
                margin-top: 0;
                color: #2c3e50;
                text-align: center;
                margin-bottom: 25px;
            }}
            .form-row {{
                display: flex;
                gap: 20px;
                margin-bottom: 20px;
                justify-content: center;
                flex-wrap: wrap;
            }}
            .form-group {{
                flex: 1;
                min-width: 200px;
                max-width: 300px;
            }}
            .form-group label {{
                display: block;
                margin-bottom: 8px;
                font-weight: 600;
                color: #495057;
            }}
            .form-group input {{
                width: 100%;
                padding: 12px;
                border: 2px solid #dee2e6;
                border-radius: 6px;
                font-size: 16px;
                transition: border-color 0.3s ease;
                box-sizing: border-box;
            }}
            .form-group input:focus {{
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }}
            .btn-container {{
                text-align: center;
                margin-top: 25px;
            }}
            .btn {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 15px 30px;
                font-size: 16px;
                border-radius: 25px;
                cursor: pointer;
                transition: all 0.3s ease;
                margin: 0 10px;
                box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
            }}
            .btn:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
            }}
            .specs {{
                background: #e3f2fd;
                padding: 20px;
                margin: 20px 0;
                border-radius: 8px;
                border-left: 4px solid #2196f3;
            }}
            .specs h4 {{
                margin-top: 0;
                color: #1976d2;
            }}
            .refresh-note {{
                text-align: center;
                margin-top: 20px;
                color: #6c757d;
                font-style: italic;
            }}
            @media (max-width: 768px) {{
                .cards-container {{
                    flex-direction: column;
                    gap: 20px;
                }}
                .form-row {{
                    flex-direction: column;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🇲🇬 Madagascar License Card Design</h1>
                <p>AMPRO-Based Design System with Madagascar Customizations</p>
            </div>
            
            <div class="cards-container">
                <div class="card-section">
                    <h2>📄 Front Side</h2>
                    <img src="/api/v1/test-card/front?name={name_encoded}&surname={surname_encoded}&license_number={license_encoded}" 
                         alt="Card Front" class="card-image" id="front-image">
                </div>
                
                <div class="card-section">
                    <h2>📄 Back Side</h2>
                    <img src="/api/v1/test-card/back?license_number={license_encoded}" 
                         alt="Card Back" class="card-image" id="back-image">
                </div>
            </div>
            
            <div class="controls">
                <h3>🎛️ Customize Test Data</h3>
                <form id="card-form">
                    <div class="form-row">
                        <div class="form-group">
                            <label for="name">First Name (Anarana):</label>
                            <input type="text" id="name" name="name" value="{name}" placeholder="Rakoto">
                        </div>
                        <div class="form-group">
                            <label for="surname">Last Name (Fianakaviana):</label>
                            <input type="text" id="surname" name="surname" value="{surname}" placeholder="Andriamamy">
                        </div>
                        <div class="form-group">
                            <label for="license_number">License Number:</label>
                            <input type="text" id="license_number" name="license_number" value="{license_number}" placeholder="MG2024001234">
                        </div>
                    </div>
                    <div class="btn-container">
                        <button type="submit" class="btn">🔄 Update Cards</button>
                        <button type="button" class="btn" onclick="resetForm()">🔄 Reset to Default</button>
                    </div>
                </form>
                
                <div class="specs">
                    <h4>📐 Technical Specifications</h4>
                    <ul>
                        <li><strong>Dimensions:</strong> 85.60 mm × 54.00 mm (ISO/IEC 18013-1)</li>
                        <li><strong>Resolution:</strong> 300 DPI (1012 × 638 pixels)</li>
                        <li><strong>Design System:</strong> AMPRO-based with Madagascar customizations</li>
                        <li><strong>Languages:</strong> Malagasy primary, French secondary</li>
                        <li><strong>Security:</strong> PDF417 barcode, watermark, flag colors</li>
                    </ul>
                </div>
                
                <div class="refresh-note">
                    <p>💡 Images are generated in real-time. Click "Update Cards" to see changes.</p>
                </div>
            </div>
        </div>
        
        <script>
            document.getElementById('card-form').addEventListener('submit', function(e) {{
                e.preventDefault();
                
                const name = encodeURIComponent(document.getElementById('name').value || 'Rakoto');
                const surname = encodeURIComponent(document.getElementById('surname').value || 'Andriamamy');
                const license_number = encodeURIComponent(document.getElementById('license_number').value || 'MG2024001234');
                
                // Update image sources with cache busting
                const timestamp = new Date().getTime();
                document.getElementById('front-image').src = 
                    `/api/v1/test-card/front?name=${{name}}&surname=${{surname}}&license_number=${{license_number}}&t=${{timestamp}}`;
                document.getElementById('back-image').src = 
                    `/api/v1/test-card/back?license_number=${{license_number}}&t=${{timestamp}}`;
                
                // Update URL without page reload
                const newUrl = `/api/v1/test-card/viewer?name=${{name}}&surname=${{surname}}&license_number=${{license_number}}`;
                window.history.pushState({{path: newUrl}}, '', newUrl);
            }});
            
            function resetForm() {{
                document.getElementById('name').value = 'Rakoto';
                document.getElementById('surname').value = 'Andriamamy';
                document.getElementById('license_number').value = 'MG2024001234';
                document.getElementById('card-form').dispatchEvent(new Event('submit'));
            }}
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)

@router.get("/test-card/specs", summary="Get Card Specifications")
def get_card_specifications():
    """
    Get technical specifications for the Madagascar license cards
    """
    try:
        specs = get_license_specifications()
        return {
            "status": "success",
            "specifications": specs,
            "sample_data": SAMPLE_LICENSE_DATA,
            "generator_version": madagascar_card_generator.version
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting specifications: {str(e)}")

@router.delete("/test-card/cleanup", summary="Cleanup Test Files")
def cleanup_test_files():
    """
    Clean up any temporary test files (placeholder for now)
    """
    try:
        # For now, this is just a placeholder since we're serving images directly
        # In the future, if we save test files to disk, we could clean them up here
        
        return {
            "status": "success",
            "message": "Test cleanup completed (no files to clean - images served directly from memory)",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during cleanup: {str(e)}") 

@router.get("/test-card/application/{application_id}", summary="Generate Test Card from Application")
def generate_test_card_from_application(
    application_id: str,
    side: str = Query("front", description="Card side: front, back, or both"),
    db: Session = Depends(get_db)
) -> Response:
    """
    Generate test card using real application data
    """
    try:
        from app.models.application import Application
        from app.models.license import License
        from sqlalchemy.orm import joinedload
        
        # Look up application with related data
        application = db.query(Application).options(
            joinedload(Application.person),
            joinedload(Application.biometric_data)
        ).filter(Application.id == application_id).first()
        
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application not found with ID: {application_id}"
            )
        
        # Use the application data to create license data
        license_data = {
            "first_name": application.person.first_name,
            "last_name": application.person.last_name,
            "surname": application.person.last_name,
            "names": application.person.first_name,
            "birth_date": application.person.birth_date.strftime("%d/%m/%Y") if application.person.birth_date else "N/A",
            "date_of_birth": application.person.birth_date.strftime("%d/%m/%Y") if application.person.birth_date else "N/A",
            "gender": application.person.gender or "M",
            "id_number": application.person.id_number,
            "license_number": f"MG{application.application_number}",
            "category": application.license_category.value if application.license_category else "B",
            "restrictions": "0",
            "driver_restrictions": "0",
            "vehicle_restrictions": "0",
            "issue_date": datetime.now().strftime("%d/%m/%Y"),
            "expiry_date": (datetime.now().replace(year=datetime.now().year + 10)).strftime("%d/%m/%Y"),
            "first_issue_date": datetime.now().strftime("%d/%m/%Y"),
            "issuing_location": "Madagascar",
            "country": "Madagascar",
        }
        
        # Add photo data for barcode if available
        if application.biometric_data and application.biometric_data.photo_base64:
            license_data["photo_base64"] = application.biometric_data.photo_base64
        
        # Get photo data as bytes for front image if available
        photo_data = None
        if application.biometric_data and application.biometric_data.photo_base64:
            try:
                photo_data = base64.b64decode(application.biometric_data.photo_base64)
            except Exception as e:
                logger.warning(f"Could not decode photo data: {e}")
        
        if side == "front":
            card_base64 = madagascar_card_generator.generate_front(license_data, photo_data)
            filename = f"application_{application_id}_front.png"
        elif side == "back":
            card_base64 = madagascar_card_generator.generate_back(license_data)
            filename = f"application_{application_id}_back.png"
        else:
            raise HTTPException(status_code=400, detail="Side must be 'front' or 'back'")
        
        # Convert base64 to bytes
        image_bytes = base64.b64decode(card_base64)
        
        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": f"inline; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating card from application: {str(e)}")

@router.get("/test-card/license/{license_id}", summary="Generate Test Card from License")
def generate_test_card_from_license(
    license_id: str,
    side: str = Query("front", description="Card side: front, back, or both"),
    db: Session = Depends(get_db)
) -> Response:
    """
    Generate test card using real license data
    """
    try:
        from app.models.license import License
        from app.models.application import Application
        from sqlalchemy.orm import joinedload
        
        # Look up license with related data
        license_obj = db.query(License).options(
            joinedload(License.person),
            joinedload(License.primary_application).joinedload(Application.biometric_data)
        ).filter(License.id == license_id).first()
        
        if not license_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"License not found with ID: {license_id}"
            )
        
        # Use the license data
        license_data = {
            "first_name": license_obj.person.first_name,
            "last_name": license_obj.person.last_name,
            "surname": license_obj.person.last_name,
            "names": license_obj.person.first_name,
            "birth_date": license_obj.person.birth_date.strftime("%d/%m/%Y") if license_obj.person.birth_date else "N/A",
            "date_of_birth": license_obj.person.birth_date.strftime("%d/%m/%Y") if license_obj.person.birth_date else "N/A",
            "gender": license_obj.person.gender or "M",
            "id_number": license_obj.person.id_number,
            "license_number": license_obj.license_number,
            "category": license_obj.category.value if license_obj.category else "B",
            "restrictions": license_obj.restrictions or "0",
            "issue_date": license_obj.issue_date.strftime("%d/%m/%Y") if license_obj.issue_date else "N/A",
            "expiry_date": license_obj.expiry_date.strftime("%d/%m/%Y") if license_obj.expiry_date else "N/A",
            "issuing_location": "Madagascar",
            "country": "Madagascar",
        }
        
        # Add photo data for barcode if available
        if (license_obj.primary_application and 
            license_obj.primary_application.biometric_data and 
            license_obj.primary_application.biometric_data.photo_base64):
            license_data["photo_base64"] = license_obj.primary_application.biometric_data.photo_base64
        
        # Get photo data as bytes for front image if available
        photo_data = None
        if (license_obj.primary_application and 
            license_obj.primary_application.biometric_data and 
            license_obj.primary_application.biometric_data.photo_base64):
            try:
                photo_data = base64.b64decode(license_obj.primary_application.biometric_data.photo_base64)
            except Exception as e:
                logger.warning(f"Could not decode photo data: {e}")
        
        if side == "front":
            card_base64 = madagascar_card_generator.generate_front(license_data, photo_data)
            filename = f"license_{license_id}_front.png"
        elif side == "back":
            card_base64 = madagascar_card_generator.generate_back(license_data)
            filename = f"license_{license_id}_back.png"
        else:
            raise HTTPException(status_code=400, detail="Side must be 'front' or 'back'")
        
        # Convert base64 to bytes
        image_bytes = base64.b64decode(card_base64)
        
        return Response(
            content=image_bytes,
            media_type="image/png",
            headers={
                "Content-Disposition": f"inline; filename={filename}",
                "Cache-Control": "no-cache"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating card from license: {str(e)}")

@router.get("/test-card/viewer-real", response_class=HTMLResponse, summary="Real Data Card Viewer")
def real_data_card_viewer(
    application_id: Optional[str] = Query(None, description="Application ID"),
    license_id: Optional[str] = Query(None, description="License ID"),
    db: Session = Depends(get_db)
):
    """
    HTML viewer for real application or license data
    """
    
    if not application_id and not license_id:
        return HTMLResponse(content="""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Real Data Card Viewer</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 20px; }
                .form-group { margin: 10px 0; }
                label { display: block; margin-bottom: 5px; }
                input { padding: 8px; width: 300px; }
                button { padding: 10px 20px; background: #007bff; color: white; border: none; cursor: pointer; }
            </style>
        </head>
        <body>
            <h1>Real Data Card Viewer</h1>
            <p>View license cards using real application or license data from the database.</p>
            
            <h3>Option 1: View by Application ID</h3>
            <form method="get">
                <div class="form-group">
                    <label>Application ID:</label>
                    <input type="text" name="application_id" placeholder="Enter application ID (UUID)">
                </div>
                <button type="submit">View Application Card</button>
            </form>
            
            <h3>Option 2: View by License ID</h3>
            <form method="get">
                <div class="form-group">
                    <label>License ID:</label>
                    <input type="text" name="license_id" placeholder="Enter license ID (UUID)">
                </div>
                <button type="submit">View License Card</button>
            </form>
        </body>
        </html>
        """)
    
    # Determine data source and build viewer
    data_type = "application" if application_id else "license"
    data_id = application_id or license_id
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Madagascar License Card - Real Data</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 15px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 2.5rem;
                font-weight: 300;
            }}
            .header p {{
                margin: 10px 0 0;
                opacity: 0.9;
                font-size: 1.1rem;
            }}
            .cards-container {{
                padding: 40px;
                display: flex;
                justify-content: center;
                gap: 40px;
                flex-wrap: wrap;
            }}
            .card-section {{
                text-align: center;
                background: #f8f9fa;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            }}
            .card-section h2 {{
                margin-top: 0;
                color: #2c3e50;
                font-size: 1.5rem;
                margin-bottom: 20px;
            }}
            .card-image {{
                border: 3px solid #dee2e6;
                border-radius: 8px;
                box-shadow: 0 8px 25px rgba(0,0,0,0.15);
                max-width: 100%;
                height: auto;
            }}
            .info {{
                background: #e3f2fd;
                padding: 20px;
                margin: 20px 0;
                border-radius: 8px;
                border-left: 4px solid #2196f3;
            }}
            .info h4 {{
                margin-top: 0;
                color: #1976d2;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🇲🇬 Madagascar License Card - Real Data</h1>
                <p>Using {data_type.title()} ID: {data_id}</p>
            </div>
            
            <div class="cards-container">
                <div class="card-section">
                    <h2>📄 Front Side</h2>
                    <img src="/api/v1/test-card/{data_type}/{data_id}?side=front" 
                         alt="Card Front" class="card-image">
                </div>
                
                <div class="card-section">
                    <h2>📄 Back Side</h2>
                    <img src="/api/v1/test-card/{data_type}/{data_id}?side=back" 
                         alt="Card Back" class="card-image">
                </div>
            </div>
            
            <div class="info">
                <h4>📋 Real Data Features</h4>
                <ul>
                    <li><strong>Actual Person Data:</strong> Names, ID number, birth date from database</li>
                    <li><strong>Real Photo:</strong> Uses biometric photo if available</li>
                    <li><strong>License Information:</strong> Actual categories, issue/expiry dates</li>
                    <li><strong>Enhanced Barcode:</strong> Contains all person and license information</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content) 