"""
Madagascar License Card Generation Service
Adapted from AMPRO license generation system for Madagascar driver's licenses
"""

import io
import base64
import json
import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, date
from pathlib import Path
import uuid

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import pdf417gen
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm

logger = logging.getLogger(__name__)

# ---------- CONSTANTS ----------
DPI = 300
MM_TO_INCH = 1/25.4
CARD_W_MM = 85.60
CARD_H_MM = 54.00
CARD_W_PX = int(CARD_W_MM * MM_TO_INCH * DPI)   # 1012
CARD_H_PX = int(CARD_H_MM * MM_TO_INCH * DPI)   # 638

# Font sizes (in points) - Optimized for readability
FONT_SIZES = {
    "title": 36,
    "subtitle": 24,
    "field_label": 22,    # Bold font for labels
    "field_value": 22,    # Regular font for values
    "small": 15,
    "tiny": 12,
}

# Colors for Madagascar license design
COLORS = {
    "mg_red": (196, 40, 28),          # Madagascar flag red
    "mg_green": (0, 122, 51),         # Madagascar flag green  
    "mg_white": (255, 255, 255),      # Madagascar flag white
    "text_dark": (33, 33, 33),        # Dark text
    "text_light": (255, 255, 255),    # Light text
    "security_overlay": (255, 240, 245), # Light pink security background
    "border": (100, 100, 100),        # Border color
}

# Grid system constants for layout
GUTTER_PX = 23.6
BLEED_PX = 23.6  # 2mm bleed
GRID_COLS = 6
GRID_ROWS = 6

def calculate_grid_positions():
    """Calculate grid cell positions based on 6x6 grid system"""
    available_width = CARD_W_PX - (2 * BLEED_PX) - (5 * GUTTER_PX)
    available_height = CARD_H_PX - (2 * BLEED_PX) - (5 * GUTTER_PX)
    
    cell_width = available_width / GRID_COLS
    cell_height = available_height / GRID_ROWS
    
    grid_positions = {}
    
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            x = BLEED_PX + (col * (cell_width + GUTTER_PX))
            y = BLEED_PX + (row * (cell_height + GUTTER_PX))
            grid_positions[f"r{row+1}c{col+1}"] = (int(x), int(y), int(cell_width), int(cell_height))
    
    return grid_positions, cell_width, cell_height

# Layout coordinates for front side
GRID_POSITIONS, CELL_WIDTH, CELL_HEIGHT = calculate_grid_positions()

FRONT_COORDINATES = {
    "photo": GRID_POSITIONS["r2c1"],  # Photo in top-left grid area (extended to r5c2)
    "title_x": GRID_POSITIONS["r1c3"][0],
    "title_y": GRID_POSITIONS["r1c3"][1],
    "info_start_y": GRID_POSITIONS["r2c3"][1],
    "labels_column_x": GRID_POSITIONS["r2c3"][0],
    "values_column_x": GRID_POSITIONS["r2c5"][0],
    "line_height": 35,
    "signature_area": GRID_POSITIONS["r5c5"],  # Bottom right for signature
    "barcode_area": GRID_POSITIONS["r4c1"],   # Bottom left for barcode
}

# Layout coordinates for back side
BACK_COORDINATES = {
    "restrictions_start_y": GRID_POSITIONS["r2c1"][1],
    "restrictions_x": GRID_POSITIONS["r2c1"][0],
    "issuing_authority_y": GRID_POSITIONS["r5c1"][1],
    "issuing_authority_x": GRID_POSITIONS["r5c1"][0],
    "watermark_center": (CARD_W_PX // 2, CARD_H_PX // 2),
}

class MadagascarCardGenerator:
    """
    Main card generator for Madagascar driver's licenses
    Adapted from AMPRO's SA license generator
    """
    
    def __init__(self):
        """Initialize the card generator with fonts and assets"""
        self.fonts = self._load_fonts()
        self.assets_loaded = False
        self.version = "1.0-MG"
        
    def _load_fonts(self) -> Dict[str, ImageFont.FreeTypeFont]:
        """Load fonts with fallback to default fonts"""
        fonts = {}
        
        # Font paths to try (in order of preference)
        font_paths = [
            # Primary fonts
            "SourceSansPro-Regular.ttf",
            "SourceSansPro-Bold.ttf",
            # Fallback fonts
            "arial.ttf",
            "Arial.ttf",
            "DejaVuSans.ttf",
            # System paths (Linux/Windows)
            "/System/Library/Fonts/Arial.ttf",  # macOS
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
            "C:/Windows/Fonts/arial.ttf",  # Windows
        ]
        
        def load_font_with_fallback(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
            """Load font with size, trying multiple paths"""
            for font_path in font_paths:
                try:
                    # Skip regular fonts if we need bold, and vice versa
                    if bold and "Regular" in font_path:
                        continue
                    if not bold and "Bold" in font_path:
                        continue
                        
                    return ImageFont.truetype(font_path, size)
                except (IOError, OSError):
                    continue
            
            # Final fallback to default font
            try:
                return ImageFont.load_default()
            except:
                return ImageFont.load_default()
        
        # Load fonts for different purposes
        fonts["title"] = load_font_with_fallback(FONT_SIZES["title"], bold=True)
        fonts["subtitle"] = load_font_with_fallback(FONT_SIZES["subtitle"], bold=True)
        fonts["field_label"] = load_font_with_fallback(FONT_SIZES["field_label"], bold=True)
        fonts["field_value"] = load_font_with_fallback(FONT_SIZES["field_value"], bold=False)
        fonts["small"] = load_font_with_fallback(FONT_SIZES["small"], bold=False)
        fonts["tiny"] = load_font_with_fallback(FONT_SIZES["tiny"], bold=False)
        
        return fonts

    def _create_security_background(self, width: int, height: int) -> Image.Image:
        """Create security background pattern for Madagascar license"""
        # Create base image with white background
        img = Image.new('RGB', (width, height), COLORS["mg_white"])
        draw = ImageDraw.Draw(img)
        
        # Add subtle security pattern
        pattern_color = COLORS["security_overlay"]
        
        # Diagonal lines pattern
        line_spacing = 20
        for i in range(0, width + height, line_spacing):
            draw.line([(i, 0), (i - height, height)], fill=pattern_color, width=1)
        
        # Add Madagascar flag colors as header
        header_height = 40
        stripe_height = header_height // 3
        
        # Red stripe
        draw.rectangle([0, 0, width, stripe_height], fill=COLORS["mg_red"])
        # White stripe  
        draw.rectangle([0, stripe_height, width, stripe_height * 2], fill=COLORS["mg_white"])
        # Green stripe
        draw.rectangle([0, stripe_height * 2, width, header_height], fill=COLORS["mg_green"])
        
        return img

    def _process_photo_data(self, photo_data: Optional[str]) -> Optional[Image.Image]:
        """Process base64 photo data into PIL Image"""
        if not photo_data:
            return None
            
        try:
            # Remove data URL prefix if present
            if photo_data.startswith('data:image'):
                photo_data = photo_data.split(',')[1]
            
            # Decode base64 image
            image_bytes = base64.b64decode(photo_data)
            photo = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB if necessary
            if photo.mode != 'RGB':
                photo = photo.convert('RGB')
            
            # Enhance image quality
            enhancer = ImageEnhance.Contrast(photo)
            photo = enhancer.enhance(1.1)
            
            enhancer = ImageEnhance.Sharpness(photo)
            photo = enhancer.enhance(1.2)
            
            return photo
            
        except Exception as e:
            logger.error(f"Error processing photo data: {e}")
            return None

    def _generate_pdf417_barcode(self, data: str, width: int, height: int) -> Image.Image:
        """Generate PDF417 barcode for license data"""
        try:
            # Create PDF417 barcode
            codes = pdf417gen.encode(
                data,
                security_level=5,  # High security level
                columns=6,  # Number of columns
            )
            
            # Convert to image
            image = pdf417gen.render_image(codes, scale=2, ratio=3)
            
            # Resize to fit the specified dimensions
            if image.size != (width, height):
                image = image.resize((width, height), Image.Resampling.LANCZOS)
            
            return image
            
        except Exception as e:
            logger.error(f"Error generating PDF417 barcode: {e}")
            # Return placeholder image
            placeholder = Image.new('RGB', (width, height), COLORS["mg_white"])
            draw = ImageDraw.Draw(placeholder)
            draw.rectangle([0, 0, width-1, height-1], outline=COLORS["border"], width=2)
            draw.text((width//2, height//2), "BARCODE", fill=COLORS["text_dark"], 
                     font=self.fonts["small"], anchor="mm")
            return placeholder

    def generate_front(self, license_data: Dict[str, Any], person_data: Dict[str, Any], 
                      photo_data: Optional[str] = None) -> str:
        """Generate front side of Madagascar license card"""
        
        # Create base image with security background
        license_img = self._create_security_background(CARD_W_PX, CARD_H_PX)
        draw = ImageDraw.Draw(license_img)
        
        # Process and add photo
        photo = self._process_photo_data(photo_data)
        photo_pos = FRONT_COORDINATES["photo"]
        
        # Extend photo area to cover r2c1 to r5c2 (larger photo area)
        photo_width = int(CELL_WIDTH * 2 + GUTTER_PX)
        photo_height = int(CELL_HEIGHT * 3 + GUTTER_PX * 2)
        
        if photo:
            # Resize photo to fit the area
            photo_resized = photo.resize((photo_width, photo_height), Image.Resampling.LANCZOS)
            license_img.paste(photo_resized, (photo_pos[0], photo_pos[1]))
        else:
            # Photo placeholder
            draw.rectangle([photo_pos[0], photo_pos[1], 
                          photo_pos[0] + photo_width, photo_pos[1] + photo_height], 
                         fill=(240, 240, 240), outline=COLORS["border"], width=2)
            photo_center_x = photo_pos[0] + photo_width // 2
            photo_center_y = photo_pos[1] + photo_height // 2
            draw.text((photo_center_x, photo_center_y), "PHOTO", 
                     fill=COLORS["text_dark"], font=self.fonts["field_value"], anchor="mm")
        
        # Title section
        title_x = FRONT_COORDINATES["title_x"]
        title_y = FRONT_COORDINATES["title_y"]
        
        draw.text((title_x, title_y), "REPUBLIQUE DE MADAGASCAR", 
                 fill=COLORS["mg_red"], font=self.fonts["title"])
        draw.text((title_x, title_y + 40), "PERMIS DE CONDUIRE", 
                 fill=COLORS["mg_green"], font=self.fonts["subtitle"])
        
        # Personal information section
        labels_x = FRONT_COORDINATES["labels_column_x"]
        values_x = FRONT_COORDINATES["values_column_x"]
        info_y = FRONT_COORDINATES["info_start_y"]
        line_height = FRONT_COORDINATES["line_height"]
        
        # License information fields
        info_fields = [
            ("1. NOM/LAST NAME", person_data.get("last_name", "").upper()),
            ("2. PRÉNOMS/FIRST NAME", person_data.get("first_name", "").upper()),
            ("3. DATE DE NAISSANCE/DOB", self._format_date(person_data.get("birth_date"))),
            ("4. LIEU DE NAISSANCE/POB", person_data.get("birth_place", "MADAGASCAR")),
            ("5. CATÉGORIES/CATEGORIES", self._format_license_categories(license_data.get("categories", []))),
            ("9. NOM PERMIS/LICENSE NO", license_data.get("license_number", "")),
        ]
        
        current_y = info_y
        for label, value in info_fields:
            # Draw label
            draw.text((labels_x, current_y), label, 
                     fill=COLORS["text_dark"], font=self.fonts["field_label"])
            
            # Draw value
            draw.text((labels_x, current_y + 22), str(value), 
                     fill=COLORS["text_dark"], font=self.fonts["field_value"])
            
            current_y += line_height
        
        # Barcode area
        barcode_data = self._prepare_barcode_data(license_data, person_data)
        barcode_pos = FRONT_COORDINATES["barcode_area"]
        barcode_img = self._generate_pdf417_barcode(barcode_data, 150, 60)
        license_img.paste(barcode_img, (barcode_pos[0], barcode_pos[1]))
        
        # Convert to base64 for return
        buffer = io.BytesIO()
        license_img.save(buffer, format="PNG", dpi=(DPI, DPI))
        buffer.seek(0)
        
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def generate_back(self, license_data: Dict[str, Any], person_data: Dict[str, Any]) -> str:
        """Generate back side of Madagascar license card"""
        
        # Create base image with security background
        license_img = self._create_security_background(CARD_W_PX, CARD_H_PX)
        draw = ImageDraw.Draw(license_img)
        
        # Add watermark
        self._add_watermark(draw, "MADAGASIKARA")
        
        # Restrictions section
        restrictions_x = BACK_COORDINATES["restrictions_x"]
        restrictions_y = BACK_COORDINATES["restrictions_start_y"]
        
        draw.text((restrictions_x, restrictions_y), "RESTRICTIONS/RESTRICTIONS:", 
                 fill=COLORS["text_dark"], font=self.fonts["field_label"])
        
        # Format restrictions for display
        restrictions_text = self._format_restrictions(license_data.get("restrictions", {}))
        
        # Multi-line restrictions text
        current_y = restrictions_y + 30
        line_height = 25
        
        for line in restrictions_text.split('\n'):
            if line.strip():
                draw.text((restrictions_x, current_y), line.strip(), 
                         fill=COLORS["text_dark"], font=self.fonts["small"])
                current_y += line_height
        
        # Issuing authority section
        auth_x = BACK_COORDINATES["issuing_authority_x"]
        auth_y = BACK_COORDINATES["issuing_authority_y"]
        
        draw.text((auth_x, auth_y), "DÉLIVRÉ PAR/ISSUED BY:", 
                 fill=COLORS["text_dark"], font=self.fonts["field_label"])
        draw.text((auth_x, auth_y + 25), "MINISTÈRE DES TRANSPORTS", 
                 fill=COLORS["text_dark"], font=self.fonts["small"])
        draw.text((auth_x, auth_y + 45), "RÉPUBLIQUE DE MADAGASCAR", 
                 fill=COLORS["text_dark"], font=self.fonts["small"])
        
        # Issue and expiry dates
        issue_date = self._format_date(license_data.get("issue_date"))
        expiry_date = self._format_date(license_data.get("expiry_date"))
        
        draw.text((auth_x + 300, auth_y), f"DÉLIVRÉ LE/ISSUED: {issue_date}", 
                 fill=COLORS["text_dark"], font=self.fonts["small"])
        draw.text((auth_x + 300, auth_y + 25), f"VALABLE JUSQU'AU/VALID UNTIL: {expiry_date}", 
                 fill=COLORS["text_dark"], font=self.fonts["small"])
        
        # Convert to base64 for return
        buffer = io.BytesIO()
        license_img.save(buffer, format="PNG", dpi=(DPI, DPI))
        buffer.seek(0)
        
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def _add_watermark(self, draw: ImageDraw.Draw, text: str):
        """Add diagonal watermark text to the background"""
        center_x, center_y = BACK_COORDINATES["watermark_center"]
        
        # Create semi-transparent watermark
        for i in range(-2, 3):
            for j in range(-2, 3):
                x = center_x + i * 200
                y = center_y + j * 100
                draw.text((x, y), text, fill=(200, 200, 200, 100), 
                         font=self.fonts["title"], anchor="mm")

    def _format_license_categories(self, categories: List[str]) -> str:
        """Format license categories for display, excluding learners permits"""
        if not categories:
            return ""
        
        # Filter out learners permits (not printed on cards)
        card_categories = [cat for cat in categories if cat != "LEARNERS_PERMIT"]
        
        return ", ".join(card_categories)

    def _format_restrictions(self, restrictions: Dict[str, List[str]]) -> str:
        """Format restrictions for display on card back"""
        if not restrictions:
            return "AUCUNE/NONE"
        
        formatted_lines = []
        
        # Driver restrictions
        driver_restrictions = restrictions.get("driver_restrictions", [])
        if driver_restrictions:
            # Filter out "00" codes (no restrictions)
            filtered_driver = [r for r in driver_restrictions if r != "00"]
            if filtered_driver:
                formatted_lines.append(f"CONDUCTEUR/DRIVER: {', '.join(filtered_driver)}")
        
        # Vehicle restrictions  
        vehicle_restrictions = restrictions.get("vehicle_restrictions", [])
        if vehicle_restrictions:
            # Filter out "00" codes (no restrictions)
            filtered_vehicle = [r for r in vehicle_restrictions if r != "00"]
            if filtered_vehicle:
                formatted_lines.append(f"VÉHICULE/VEHICLE: {', '.join(filtered_vehicle)}")
        
        return "\n".join(formatted_lines) if formatted_lines else "AUCUNE/NONE"

    def _format_date(self, date_input) -> str:
        """Format date for display on license"""
        if not date_input:
            return ""
        
        try:
            if isinstance(date_input, str):
                # Parse ISO date string
                if 'T' in date_input:
                    date_obj = datetime.fromisoformat(date_input.replace('Z', '+00:00')).date()
                else:
                    date_obj = datetime.strptime(date_input, '%Y-%m-%d').date()
            elif isinstance(date_input, datetime):
                date_obj = date_input.date()
            elif isinstance(date_input, date):
                date_obj = date_input
            else:
                return str(date_input)
            
            # Format as DD.MM.YYYY (European style common in Madagascar)
            return date_obj.strftime('%d.%m.%Y')
            
        except Exception as e:
            logger.error(f"Error formatting date {date_input}: {e}")
            return str(date_input)

    def _prepare_barcode_data(self, license_data: Dict[str, Any], person_data: Dict[str, Any]) -> str:
        """Prepare data string for PDF417 barcode"""
        # Create compact data string with essential information
        barcode_data = {
            "license_number": license_data.get("license_number", ""),
            "name": f"{person_data.get('first_name', '')} {person_data.get('last_name', '')}",
            "birth_date": person_data.get("birth_date", ""),
            "categories": license_data.get("categories", []),
            "issue_date": license_data.get("issue_date", ""),
            "expiry_date": license_data.get("expiry_date", ""),
            "country": "MG"  # Madagascar country code
        }
        
        # Convert to JSON string for barcode
        return json.dumps(barcode_data, separators=(',', ':'))


class MadagascarCardProductionGenerator:
    """
    Production-ready wrapper for Madagascar card generation with file management
    Adapted from AMPRO's ProductionLicenseGenerator
    """
    
    def __init__(self):
        self.card_generator = MadagascarCardGenerator()
        self.version = "1.0-MG-PROD"
        
    def generate_card_files(self, print_job_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate complete card package (front, back, combined PDF) for print job
        
        Args:
            print_job_data: Print job information including license_data and person_data
            
        Returns:
            Dictionary with file paths and metadata
        """
        try:
            license_data = print_job_data.get("license_data", {})
            person_data = print_job_data.get("person_data", {})
            photo_data = person_data.get("photo_path")  # Base64 photo data
            print_job_id = print_job_data.get("print_job_id")
            
            # Generate front and back images
            front_base64 = self.card_generator.generate_front(
                license_data, person_data, photo_data
            )
            back_base64 = self.card_generator.generate_back(
                license_data, person_data
            )
            
            # Convert base64 to bytes for PDF generation
            front_bytes = base64.b64decode(front_base64)
            back_bytes = base64.b64decode(back_base64)
            
            # Generate PDFs
            front_pdf = self._generate_pdf(front_bytes, "Madagascar License - Front")
            back_pdf = self._generate_pdf(back_bytes, "Madagascar License - Back")
            combined_pdf = self._generate_combined_pdf(front_bytes, back_bytes, license_data)
            
            # Prepare file data for saving to disk
            card_files_data = {
                "front_image": front_base64,
                "back_image": back_base64,
                "front_pdf": base64.b64encode(front_pdf).decode('utf-8'),
                "back_pdf": base64.b64encode(back_pdf).decode('utf-8'),
                "combined_pdf": base64.b64encode(combined_pdf).decode('utf-8')
            }
            
            # Save files to disk using file manager
            from app.services.card_file_manager import card_file_manager
            from datetime import datetime
            
            file_paths = card_file_manager.save_card_files(
                print_job_id=print_job_id,
                card_files_data=card_files_data,
                created_at=datetime.utcnow()
            )
            
            # Return file paths and metadata (no base64 data for database storage)
            return {
                "file_paths": file_paths,
                "card_number": license_data.get("card_number", ""),
                "license_number": license_data.get("license_number", ""),
                "generation_timestamp": datetime.utcnow().isoformat(),
                "generator_version": self.version,
                "files_generated": True,
                "file_sizes": {
                    "front_image_bytes": len(front_bytes),
                    "back_image_bytes": len(back_bytes),
                    "front_pdf_bytes": len(front_pdf),
                    "back_pdf_bytes": len(back_pdf),
                    "combined_pdf_bytes": len(combined_pdf),
                    "total_bytes": len(front_bytes) + len(back_bytes) + len(front_pdf) + len(back_pdf) + len(combined_pdf)
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating card files: {e}")
            raise Exception(f"Card generation failed: {str(e)}")

    def _generate_pdf(self, image_bytes: bytes, title: str) -> bytes:
        """Generate PDF from image bytes"""
        pdf_buffer = io.BytesIO()
        
        # Create PDF with exact card dimensions
        page_width = CARD_W_PX * 72 / 300  # Convert to points (72 DPI)
        page_height = CARD_H_PX * 72 / 300
        
        c = canvas.Canvas(pdf_buffer, pagesize=(page_width, page_height))
        c.setTitle(title)
        c.setAuthor("Madagascar License System")
        c.setSubject("Official Madagascar Driver's License")
        
        # Create temporary image for PDF
        temp_img_path = f"/tmp/temp_img_{uuid.uuid4()}.png"
        try:
            with open(temp_img_path, 'wb') as f:
                f.write(image_bytes)
            
            # Add image to PDF
            c.drawImage(
                temp_img_path, 0, 0,
                width=page_width, height=page_height,
                preserveAspectRatio=True
            )
            
            c.save()
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(temp_img_path)
            except Exception:
                pass
        
        return pdf_buffer.getvalue()

    def _generate_combined_pdf(self, front_bytes: bytes, back_bytes: bytes, 
                              license_data: Dict[str, Any]) -> bytes:
        """Generate combined PDF with both front and back"""
        pdf_buffer = io.BytesIO()
        
        # Create PDF with exact card dimensions
        page_width = CARD_W_PX * 72 / 300  # Convert to points (72 DPI)
        page_height = CARD_H_PX * 72 / 300
        
        c = canvas.Canvas(pdf_buffer, pagesize=(page_width, page_height))
        c.setTitle(f"Madagascar Driver's License - {license_data.get('license_number', '')}")
        c.setAuthor("Madagascar License System")
        c.setSubject("Official Madagascar Driver's License")
        
        # Create temporary files
        front_temp = f"/tmp/temp_front_{uuid.uuid4()}.png"
        back_temp = f"/tmp/temp_back_{uuid.uuid4()}.png"
        
        try:
            # Save temporary files
            with open(front_temp, 'wb') as f:
                f.write(front_bytes)
            with open(back_temp, 'wb') as f:
                f.write(back_bytes)
            
            # Front page
            c.drawImage(
                front_temp, 0, 0,
                width=page_width, height=page_height,
                preserveAspectRatio=True
            )
            c.showPage()
            
            # Back page
            c.drawImage(
                back_temp, 0, 0,
                width=page_width, height=page_height,
                preserveAspectRatio=True
            )
            
            c.save()
            
        finally:
            # Clean up temporary files
            for temp_file in [front_temp, back_temp]:
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass
        
        return pdf_buffer.getvalue()


# Service instance for dependency injection
madagascar_card_generator = MadagascarCardProductionGenerator() 