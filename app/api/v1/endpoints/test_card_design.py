"""
Test Card Design Endpoints for Local Development
Allows testing the Madagascar license card design and layout
"""

import base64
import io
import os
import tempfile
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Response, Query
from fastapi.responses import HTMLResponse

from app.services.card_generator import madagascar_card_generator, get_license_specifications

router = APIRouter()

# Sample test data for Madagascar license
SAMPLE_LICENSE_DATA = {
    "first_name": "Rakoto",
    "last_name": "Andriamamy", 
    "surname": "Andriamamy",
    "names": "Rakoto",
    "birth_date": "1990-05-15",
    "date_of_birth": "1990-05-15",
    "gender": "M",
    "id_number": "301901500123",
    "license_number": "MG2024001234",
    "category": "B",
    "categories": ["B"],
    "restrictions": "0",
    "issue_date": "2024-01-15",
    "expiry_date": "2034-01-15",
    "first_issue_date": "2024-01-15",
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
        
        # Generate front card image
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
        
        # Generate back card image
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