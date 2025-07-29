"""
Madagascar License Card Generation Service
Unified AMPRO-based system with production file management
"""

import io
import base64
import json
import os
import csv
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, date
from pathlib import Path
import uuid

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import pdf417gen
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from app.services.card_file_manager import card_file_manager

logger = logging.getLogger(__name__)

# ---------- AMPRO CONSTANTS ----------
DPI = 300
MM_TO_INCH = 1/25.4
CARD_W_MM = 85.60
CARD_H_MM = 54.00
CARD_W_PX = int(CARD_W_MM * MM_TO_INCH * DPI)   # 1012
CARD_H_PX = int(CARD_H_MM * MM_TO_INCH * DPI)   # 638

# Font sizes (in points) - Same as AMPRO
FONT_SIZES = {
    "title": 36,
    "subtitle": 24,
    "field_label": 22,    # Bold font for labels
    "field_value": 22,    # Regular font for values
    "small": 15,
    "tiny": 12,
}

# Colors - Adapted for Madagascar
COLORS = {
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "red": (220, 38, 48),      # Madagascar flag red
    "green": (0, 158, 73),     # Madagascar flag green
    "dark_blue": (0, 32, 91),  # Dark blue for official text
    "gray": (128, 128, 128),
    "light_gray": (240, 240, 240),
}

# Grid system constants (Same as AMPRO)
GUTTER_PX = 23.6
BLEED_PX = 23.6  # 2mm bleed
GRID_COLS = 6
GRID_ROWS = 6

def calculate_grid_positions():
    """Calculate grid cell positions based on 6x6 grid system (Same as AMPRO)"""
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

# Calculate grid positions
GRID_POSITIONS, CELL_WIDTH, CELL_HEIGHT = calculate_grid_positions()

# ACTUAL AMPRO COORDINATES (from real AMPRO code)
FRONT_COORDINATES = {
    # Photo area: Columns 1-2, Rows 2-5 (2x4 grid cells)
    "photo": (
        GRID_POSITIONS["r2c1"][0],  # x
        GRID_POSITIONS["r2c1"][1],  # y
        GRID_POSITIONS["r2c2"][0] + GRID_POSITIONS["r2c2"][2] - GRID_POSITIONS["r2c1"][0],  # width (2 columns)
        GRID_POSITIONS["r5c1"][1] + GRID_POSITIONS["r5c1"][3] - GRID_POSITIONS["r2c1"][1]   # height (4 rows)
    ),
    
    # Information area: Columns 3-6, Rows 2-5
    "labels_column_x": GRID_POSITIONS["r2c3"][0],  # Labels in column 3
    "values_column_x": GRID_POSITIONS["r2c4"][0],  # Values in column 4-6
    "info_start_y": GRID_POSITIONS["r2c3"][1],
    "line_height": 37,  # Exact AMPRO spacing
    
    # Signature area: Row 6, Columns 1-6
    "signature": (
        GRID_POSITIONS["r6c1"][0],
        GRID_POSITIONS["r6c1"][1],
        GRID_POSITIONS["r6c6"][0] + GRID_POSITIONS["r6c6"][2] - GRID_POSITIONS["r6c1"][0],
        GRID_POSITIONS["r6c1"][3]
    ),
}

BACK_COORDINATES = {
    # PDF417 barcode area - Rows 1-2, all 6 columns (increased height)
    "barcode": (
        GRID_POSITIONS["r1c1"][0],  # x
        GRID_POSITIONS["r1c1"][1],  # y
        GRID_POSITIONS["r1c6"][0] + GRID_POSITIONS["r1c6"][2] - GRID_POSITIONS["r1c1"][0],  # width (6 columns)
        GRID_POSITIONS["r2c1"][1] + GRID_POSITIONS["r2c1"][3] - GRID_POSITIONS["r1c1"][1]   # height (2 rows)
    ),
    
    # Fingerprint area - Bottom RIGHT corner (330x205 pixels, 23px from edges)
    "fingerprint": (
        CARD_W_PX - BLEED_PX - 330,  # x - 23px from right edge, 330px width
        CARD_H_PX - BLEED_PX - 205,  # y - 23px from bottom edge, 205px height
        330,  # width
        205   # height
    ),
}

# Load coordinates from CSV file (Fallback only)
def load_coordinates_from_csv():
    """Load coordinate mappings from CSV file (fallback - not used with AMPRO coordinates)"""
    # Return AMPRO coordinates instead of CSV
    return {
        'photo': {'side': 'front', 'x': FRONT_COORDINATES["photo"][0], 'y': FRONT_COORDINATES["photo"][1], 
                 'width': FRONT_COORDINATES["photo"][2], 'height': FRONT_COORDINATES["photo"][3]},
        'barcode': {'side': 'back', 'x': BACK_COORDINATES["barcode"][0], 'y': BACK_COORDINATES["barcode"][1], 
                   'width': BACK_COORDINATES["barcode"][2], 'height': BACK_COORDINATES["barcode"][3]},
    }

# Load coordinates (now using AMPRO coordinates)
COORDINATES = load_coordinates_from_csv()

class MadagascarCardGenerator:
    """
    Unified Madagascar License Card Generator using AMPRO design system
    Combines image generation and production file management
    """
    
    def __init__(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.assets_path = os.path.join(self.base_path, "..", "assets")
        self.fonts = self._load_fonts()
        self.version = "3.0-MG-AMPRO-UNIFIED"
    
    def _load_fonts(self) -> Dict[str, ImageFont.FreeTypeFont]:
        """Load fonts with fallbacks (Same as AMPRO)"""
        fonts = {}
        
        # Font search paths
        font_paths = [
            # Custom fonts directory
            os.path.join(self.assets_path, "fonts"),
            # System fonts
            "C:/Windows/Fonts",  # Windows
            "/System/Library/Fonts",  # macOS
            "/usr/share/fonts/truetype/dejavu",  # Linux
        ]
        
        # Bold font options for labels
        bold_font_options = [
            "SourceSansPro-Bold.ttf",
            "ARIALBD.TTF",
            "dejavu-sans.bold.ttf",
            "Arial-Bold.ttf",
            "DejaVuSans-Bold.ttf",
        ]
        
        # Regular font options for values
        regular_font_options = [
            "SourceSansPro-Regular.ttf",
            "arial.ttf",
            "Arial.ttf", 
            "DejaVuSans.ttf",
        ]
        
        # Load fonts for each size
        for font_name, size in FONT_SIZES.items():
            font_loaded = False
            
            # Determine if this is a label font (uses bold)
            is_label_font = font_name in ["field_label", "title", "subtitle"]
            font_options = bold_font_options if is_label_font else regular_font_options
            
            for font_path in font_paths:
                if font_loaded:
                    break
                    
                for font_file in font_options:
                    try:
                        full_path = os.path.join(font_path, font_file)
                        if os.path.exists(full_path):
                            fonts[font_name] = ImageFont.truetype(full_path, size)
                            logger.info(f"Loaded font {font_name}: {full_path}")
                            font_loaded = True
                            break
                    except Exception as e:
                        continue
            
            # Fallback to default font if no custom font found
            if not font_loaded:
                try:
                    fonts[font_name] = ImageFont.load_default()
                    logger.warning(f"Using default font for {font_name}")
                except:
                    # Ultimate fallback
                    fonts[font_name] = None
                    logger.error(f"Could not load any font for {font_name}")
        
        return fonts
    
    def _create_security_background(self, width: int, height: int, side: str = "front") -> Image.Image:
        """Create security background pattern using AMPRO assets"""
        # Try to load the exact AMPRO template first
        if side == "front":
            template_path = os.path.join(self.assets_path, "overlays", "Card_BG_Front.png")
        else:
            template_path = os.path.join(self.assets_path, "overlays", "Card_BG_Back.png")
            
        if os.path.exists(template_path):
            try:
                background = Image.open(template_path).convert('RGBA')
                # Resize to exact dimensions if needed
                if background.size != (width, height):
                    background = background.resize((width, height), Image.Resampling.LANCZOS)
                logger.info(f"Loaded {side} background template: {template_path}")
                return background
            except Exception as e:
                logger.warning(f"Could not load {side} template: {e}")
        
        # Fallback: Create white background
        background = Image.new('RGBA', (width, height), COLORS["white"] + (255,))
        return background
    
    def _create_watermark_pattern(self, width: int, height: int, text: str = "MADAGASCAR") -> Image.Image:
        """Create diagonal watermark pattern using AMPRO assets"""
        # Try to load watermark from AMPRO assets first
        watermark_path = os.path.join(self.assets_path, "overlays", "watermark_pattern.png")
        if os.path.exists(watermark_path):
            try:
                watermark = Image.open(watermark_path).convert('RGBA')
                # Resize to exact dimensions if needed
                if watermark.size != (width, height):
                    watermark = watermark.resize((width, height), Image.Resampling.LANCZOS)
                logger.info(f"Loaded watermark from AMPRO assets: {watermark_path}")
                return watermark
            except Exception as e:
                logger.warning(f"Could not load watermark overlay: {e}")
        
        # Fallback: Create programmatic watermark with "MADAGASCAR"
        logger.info(f"Creating programmatic Madagascar watermark: {width}x{height}")
        
        pattern_width = width * 2
        pattern_height = height * 2
        watermark = Image.new('RGBA', (pattern_width, pattern_height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark)
        
        font = self.fonts["title"]
        
        # Calculate text dimensions
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Create diagonal pattern
        spacing_x = text_width + 60
        spacing_y = text_height + 40
        
        # Madagascar colors - use green for watermark
        watermark_color = COLORS["green"] + (60,)
        
        # Draw diagonal pattern
        for y in range(-text_height, pattern_height + text_height, spacing_y):
            for x in range(-text_width, pattern_width + text_width, spacing_x):
                # Rotate text 45 degrees
                rotated_x = x + (y * 0.5)
                draw.text((rotated_x, y), text, fill=watermark_color, font=font)
        
        # Crop to desired size
        watermark = watermark.crop((0, 0, width, height))
        return watermark
    
    def _process_photo_data(self, photo_data: Optional[bytes], target_width: int, target_height: int) -> Optional[Image.Image]:
        """Process photo data for license (Same as AMPRO)"""
        if not photo_data:
            return None
        
        try:
            logger.info(f"Processing photo data: target_width={target_width}, target_height={target_height}")
            
            # Handle base64 data
            if isinstance(photo_data, str) and (photo_data.startswith('data:') or len(photo_data) > 1000):
                logger.info("Decoding base64 data string")
                # Check if it's a data URI format (data:image/jpeg;base64,<data>)
                if photo_data.startswith('data:') and ',' in photo_data:
                    photo_data = base64.b64decode(photo_data.split(',')[1])
                else:
                    # Raw base64 string without data URI prefix
                    photo_data = base64.b64decode(photo_data)
            
            # Decode base64
            photo_bytes = photo_data
            logger.info(f"Photo bytes length: {len(photo_bytes) if photo_bytes else 0}")
            
            # Open image
            photo = Image.open(io.BytesIO(photo_bytes))
            logger.info(f"Opened image: mode={photo.mode}, size={photo.size}")
            
            # Convert to RGB if needed
            if photo.mode != 'RGB':
                photo = photo.convert('RGB')
                logger.info("Converted image to RGB")
            
            # ISO specifications for photo (Same as AMPRO)
            # target_width = 213   # 18mm at 300 DPI
            # target_height = 260  # 22mm at 300 DPI
            
            # Resize maintaining aspect ratio
            logger.info(f"Resizing photo to thumbnail: {target_width}x{target_height}")
            photo.thumbnail((target_width, target_height), Image.Resampling.LANCZOS)
            logger.info(f"Photo size after thumbnail: {photo.size}")
            
            # Create final image with exact dimensions
            final_photo = Image.new('RGB', (target_width, target_height), (255, 255, 255))
            
            # Center the photo
            x_offset = (target_width - photo.width) // 2
            y_offset = (target_height - photo.height) // 2
            logger.info(f"Centering photo at offset: ({x_offset}, {y_offset})")
            final_photo.paste(photo, (x_offset, y_offset))
            
            logger.info("Photo processing completed successfully")
            return final_photo
            
        except Exception as e:
            logger.error(f"Error processing photo: {e}")
            logger.error(f"Error type: {type(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _generate_pdf417_barcode(self, data: str) -> Image.Image:
        """Generate PDF417 barcode (Same as AMPRO)"""
        try:
            # Generate PDF417 barcode
            codes = pdf417gen.encode(data, security_level=2)
            image = pdf417gen.render_image(codes, scale=3, ratio=3)
            
            # Convert to RGB
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            return image
            
        except Exception as e:
            logger.error(f"Error generating PDF417 barcode: {e}")
            # Fallback: Create simple text
            img = Image.new('RGB', (400, 50), COLORS["white"])
            draw = ImageDraw.Draw(img)
            font = self.fonts["small"]
            draw.text((10, 10), "BARCODE DATA", fill=COLORS["black"], font=font)
            return img
    
    def _extract_photo_from_person_data(self, person_data: Dict[str, Any]) -> Optional[bytes]:
        """Extract photo data from person data with multiple fallback paths"""
        try:
            logger.info(f"Extracting photo from person data. Available keys: {list(person_data.keys())}")
            
            # Log biometric data structure if available
            if "biometric_data" in person_data:
                biometric_data = person_data["biometric_data"]
                logger.info(f"Biometric data found with keys: {list(biometric_data.keys()) if isinstance(biometric_data, dict) else type(biometric_data)}")
                if isinstance(biometric_data, dict):
                    for key, value in biometric_data.items():
                        if value:
                            logger.info(f"  {key}: {type(value)} - {str(value)[:100]}...")
                        else:
                            logger.info(f"  {key}: None/empty")
            else:
                logger.info("No biometric_data key found in person_data")
            
            # Try different ways to get photo data
            photo_sources = [
                # Direct photo data
                person_data.get("photo_data"),
                person_data.get("photo_base64"),
                # File paths from biometric data
                person_data.get("biometric_data", {}).get("photo_path"),
                person_data.get("biometric_data", {}).get("photo_url"),
                # Legacy paths
                person_data.get("photo_path"),
                person_data.get("photo_url"),
            ]
            
            for i, photo_source in enumerate(photo_sources):
                logger.info(f"Checking photo source {i}: {type(photo_source)} - {str(photo_source)[:100] if photo_source else 'None'}...")
                
                if photo_source:
                    # If it's already base64 data, return it
                    if isinstance(photo_source, str):
                        if photo_source.startswith('data:image/'):
                            # Extract base64 part from data URL
                            logger.info(f"Found data URL photo source")
                            return photo_source.split(',')[1] if ',' in photo_source else photo_source
                        elif len(photo_source) > 1000 and not ('/' in photo_source or '\\' in photo_source):
                            # Looks like raw base64 data
                            logger.info(f"Found raw base64 photo data")
                            return photo_source
                        elif photo_source.endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')) or ('/' in photo_source or '\\' in photo_source):
                            # This looks like a file path - try to read it
                            logger.info(f"Attempting to read photo from file path: {photo_source}")
                            try:
                                from app.services.card_file_manager import card_file_manager
                                photo_data = card_file_manager.read_file_as_base64(photo_source)
                                if photo_data:
                                    logger.info(f"Successfully read photo from file: {photo_source} ({len(photo_data)} chars base64)")
                                    return photo_data
                                else:
                                    logger.warning(f"Could not read photo file: {photo_source}")
                            except Exception as e:
                                logger.warning(f"Failed to read photo file {photo_source}: {e}")
                                continue
            
            logger.info("No usable photo data found, will use placeholder")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting photo: {e}")
            return None
    
    def _extract_signature_from_person_data(self, person_data: Dict[str, Any]) -> Optional[bytes]:
        """Extract signature data from person data with multiple fallback paths"""
        try:
            logger.info(f"Extracting signature from person data")
            
            # Try different ways to get signature data
            signature_sources = [
                # Direct signature data
                person_data.get("signature_data"),
                person_data.get("signature_base64"),
                # File paths from biometric data
                person_data.get("biometric_data", {}).get("signature_path"),
                person_data.get("biometric_data", {}).get("signature_url"),
                # Legacy paths
                person_data.get("signature_path"),
                person_data.get("signature_url"),
            ]
            
            for i, signature_source in enumerate(signature_sources):
                logger.info(f"Checking signature source {i}: {type(signature_source)} - {str(signature_source)[:100] if signature_source else 'None'}...")
                
                if signature_source:
                    # If it's already base64 data, return it
                    if isinstance(signature_source, str):
                        if signature_source.startswith('data:image/'):
                            # Extract base64 part from data URL
                            logger.info(f"Found data URL signature source")
                            return signature_source.split(',')[1] if ',' in signature_source else signature_source
                        elif len(signature_source) > 1000 and not ('/' in signature_source or '\\' in signature_source):
                            # Looks like raw base64 data
                            logger.info(f"Found raw base64 signature data")
                            return signature_source
                        elif signature_source.endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')) or ('/' in signature_source or '\\' in signature_source):
                            # This looks like a file path - try to read it
                            logger.info(f"Attempting to read signature from file path: {signature_source}")
                            try:
                                from app.services.card_file_manager import card_file_manager
                                signature_data = card_file_manager.read_file_as_base64(signature_source)
                                if signature_data:
                                    logger.info(f"Successfully read signature from file: {signature_source} ({len(signature_data)} chars base64)")
                                    return signature_data
                                else:
                                    logger.warning(f"Could not read signature file: {signature_source}")
                            except Exception as e:
                                logger.warning(f"Failed to read signature file {signature_source}: {e}")
                                continue
            
            logger.info("No usable signature data found, will use placeholder")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting signature: {e}")
            return None
        
        logger.info("No usable signature data found, will use placeholder")
        return None
    
    def _extract_fingerprint_from_person_data(self, person_data: Dict[str, Any]) -> Optional[bytes]:
        """Extract fingerprint data from person data with multiple fallback paths"""
        try:
            logger.info(f"Extracting fingerprint from person data")
            
            # Try different ways to get fingerprint data
            fingerprint_sources = [
                # Direct fingerprint data
                person_data.get("fingerprint_data"),
                person_data.get("biometric_data", {}).get("fingerprint_url"),
                person_data.get("biometric_data", {}).get("fingerprint_path"),
                # Legacy paths
                person_data.get("fingerprint_url"),
                person_data.get("fingerprint_path"),
                person_data.get("fingerprint_file_path"),
            ]
            
            for i, fingerprint_source in enumerate(fingerprint_sources):
                logger.info(f"Checking fingerprint source {i}: {type(fingerprint_source)} - {str(fingerprint_source)[:100] if fingerprint_source else 'None'}...")
                
                if fingerprint_source:
                    # Handle different data types
                    if isinstance(fingerprint_source, str):
                        if fingerprint_source.startswith('data:image/'):
                            # Data URL format
                            fingerprint_data = fingerprint_source.split(',')[1] if ',' in fingerprint_source else fingerprint_source
                            logger.info(f"Found data URL fingerprint")
                            return fingerprint_data
                        elif len(fingerprint_source) > 1000 and not ('/' in fingerprint_source or '\\' in fingerprint_source):
                            # Likely base64 data
                            logger.info(f"Found raw base64 fingerprint data")
                            return fingerprint_source
                        elif fingerprint_source.endswith(('.jpg', '.jpeg', '.png', '.bmp', '.gif')) or ('/' in fingerprint_source or '\\' in fingerprint_source):
                            # File path
                            logger.info(f"Attempting to read fingerprint from file path: {fingerprint_source}")
                            try:
                                from app.services.card_file_manager import card_file_manager
                                fingerprint_data = card_file_manager.read_file_as_base64(fingerprint_source)
                                if fingerprint_data:
                                    logger.info(f"Successfully read fingerprint from file: {fingerprint_source} ({len(fingerprint_data)} chars base64)")
                                    return fingerprint_data
                                else:
                                    logger.warning(f"Could not read fingerprint file: {fingerprint_source}")
                            except Exception as e:
                                logger.warning(f"Failed to read fingerprint file {fingerprint_source}: {e}")
                                continue
                    elif isinstance(fingerprint_source, bytes):
                        # Direct bytes data
                        return base64.b64encode(fingerprint_source).decode('utf-8')
                    
        except Exception as e:
            logger.error(f"Error extracting fingerprint: {e}")
            return None
        
        logger.info("No usable fingerprint data found, will use placeholder")
        return None
    
    def _draw_fingerprint_pattern(self, draw, fp_x, fp_y, fp_w, fp_h):
        """Draw fingerprint pattern placeholder"""
        # Generate a realistic fingerprint-like pattern
        for i in range(5, fp_w - 5, 4):
            for j in range(5, fp_h - 5, 4):
                # Create concentric oval-like patterns
                center_x = fp_w // 2
                center_y = fp_h // 2
                distance_from_center = ((i - center_x) ** 2 + (j - center_y) ** 2) ** 0.5
                
                # Create ridges and valleys pattern
                if int(distance_from_center) % 8 < 4:  # Adjust for ridge spacing
                    draw.point((fp_x + i, fp_y + j), fill=COLORS["black"])

    def generate_front(self, license_data: Dict[str, Any], photo_data: Optional[bytes] = None) -> str:
        """Generate Madagascar license front side using exact AMPRO coordinates"""
        
        # Create base image with AMPRO front background
        license_img = self._create_security_background(CARD_W_PX, CARD_H_PX, "front")
        draw = ImageDraw.Draw(license_img)
        
        # Process and add photo using AMPRO grid coordinates (Columns 1-2, Rows 2-5)
        photo_pos = FRONT_COORDINATES["photo"]
        logger.info(f"Photo position coordinates: {photo_pos}")
        
        if photo_data:
            try:
                photo_img = self._process_photo_data(photo_data, photo_pos[2], photo_pos[3])
                if photo_img:
                    license_img.paste(photo_img, (photo_pos[0], photo_pos[1]))
                    logger.info(f"Successfully added photo at position ({photo_pos[0]}, {photo_pos[1]})")
                else:
                    logger.warning("Photo processing returned None")
            except Exception as e:
                logger.warning(f"Failed to process photo: {e}")
                # Fallback: Draw photo placeholder
                draw.rectangle([photo_pos[0], photo_pos[1], photo_pos[0] + photo_pos[2], photo_pos[1] + photo_pos[3]], 
                             fill=(240, 240, 240), outline=(180, 180, 180), width=2)
                photo_center_x = photo_pos[0] + photo_pos[2] // 2
                photo_center_y = photo_pos[1] + photo_pos[3] // 2
                draw.text((photo_center_x, photo_center_y), "SARY", 
                         fill=(100, 100, 100), font=self.fonts["field_value"], anchor="mm")
        else:
            # Draw photo placeholder
            draw.rectangle([photo_pos[0], photo_pos[1], photo_pos[0] + photo_pos[2], photo_pos[1] + photo_pos[3]], 
                         fill=(240, 240, 240), outline=(180, 180, 180), width=2)
            photo_center_x = photo_pos[0] + photo_pos[2] // 2
            photo_center_y = photo_pos[1] + photo_pos[3] // 2
            draw.text((photo_center_x, photo_center_y), "SARY", 
                     fill=(100, 100, 100), font=self.fonts["field_value"], anchor="mm")
        
        # Add signature area using AMPRO grid coordinates - width adjusted to match photo width
        sig_coords = FRONT_COORDINATES["signature"]
        photo_width = FRONT_COORDINATES["photo"][2]  # Get photo width
        
        sig_x = sig_coords[0]
        sig_y = sig_coords[1]
        sig_w = photo_width  # Use photo width instead of full width
        sig_h = sig_coords[3]
        
        # Process and add signature if available
        signature_data = license_data.get("signature_base64")
        if signature_data:
            try:
                logger.info(f"Processing signature data for front card")
                signature_img = self._process_photo_data(signature_data, sig_w, sig_h)
                if signature_img:
                    license_img.paste(signature_img, (sig_x, sig_y))
                    logger.info(f"Successfully added signature at position ({sig_x}, {sig_y})")
                else:
                    logger.warning("Signature processing returned None")
                    # Draw signature placeholder
                    draw.rectangle([sig_x, sig_y, sig_x + sig_w, sig_y + sig_h], 
                                  fill=(240, 240, 240), outline=(180, 180, 180), width=1)
                    sig_center_x = sig_x + sig_w // 2
                    sig_center_y = sig_y + sig_h // 2
                    draw.text((sig_center_x, sig_center_y), "SONIA", 
                             fill=(100, 100, 100), font=self.fonts["small"], anchor="mm")
            except Exception as e:
                logger.warning(f"Failed to process signature: {e}")
                # Draw signature placeholder
                draw.rectangle([sig_x, sig_y, sig_x + sig_w, sig_y + sig_h], 
                              fill=(240, 240, 240), outline=(180, 180, 180), width=1)
                sig_center_x = sig_x + sig_w // 2
                sig_center_y = sig_y + sig_h // 2
                draw.text((sig_center_x, sig_center_y), "SONIA", 
                         fill=(100, 100, 100), font=self.fonts["small"], anchor="mm")
        else:
            # Draw signature placeholder
            draw.rectangle([sig_x, sig_y, sig_x + sig_w, sig_y + sig_h], 
                          fill=(240, 240, 240), outline=(180, 180, 180), width=1)
            sig_center_x = sig_x + sig_w // 2
            sig_center_y = sig_y + sig_h // 2
            draw.text((sig_center_x, sig_center_y), "SONIA", 
                     fill=(100, 100, 100), font=self.fonts["small"], anchor="mm")
        
        # REMOVED: Title and subtitle (no "REPOBLIKAN'I MADAGASIKARA" or subtitle)
        
        # Information area using AMPRO grid coordinates (Columns 3-6, Rows 2-5)
        labels_x = FRONT_COORDINATES["labels_column_x"]
        values_x = FRONT_COORDINATES["values_column_x"] + 50  # Move values 50px to the right
        info_y = FRONT_COORDINATES["info_start_y"]
        line_height = FRONT_COORDINATES["line_height"]
        
        # Information fields with English labels (like AMPRO) - all requested data
        info_fields = [
            ("Initials and Surname", f"{license_data.get('first_name', 'N/A')} {license_data.get('surname', 'N/A')}"),
            ("ID Number", license_data.get('id_number', 'N/A')),
            ("Card Number", license_data.get('card_number', 'N/A')),
            ("Driver Restrictions", license_data.get('restrictions', '0')),
            ("Sex", license_data.get('gender', 'N/A')),
            ("Date of Birth", license_data.get('birth_date', 'N/A')),
            ("Valid", f"{license_data.get('issue_date', 'N/A')} - {license_data.get('expiry_date', 'N/A')}"),
            ("Codes", license_data.get('category', 'N/A')),
            ("Vehicle Restrictions", license_data.get('vehicle_restrictions', license_data.get('restrictions', '0'))),
            ("First Issue", license_data.get('first_issue_date', license_data.get('issue_date', 'N/A'))),
        ]
        
        # Draw information fields using exact AMPRO column layout
        current_y = info_y
        for label, value in info_fields:
            # Draw label in labels column (bold)
            draw.text((labels_x, current_y), label, 
                     fill=COLORS["black"], font=self.fonts["field_label"])
            
            # Draw value in values column (regular)
            draw.text((values_x, current_y), str(value), 
                     fill=COLORS["black"], font=self.fonts["field_value"])
            
            current_y += line_height
        
        # Add signature area using AMPRO grid coordinates - width adjusted to match photo width
        sig_coords = FRONT_COORDINATES["signature"]
        photo_width = FRONT_COORDINATES["photo"][2]  # Get photo width
        
        sig_x = sig_coords[0]
        sig_y = sig_coords[1]
        sig_w = photo_width  # Use photo width instead of full width
        sig_h = sig_coords[3]
        
        # Convert to base64
        buffer = io.BytesIO()
        # Convert back to RGB for compatibility
        if license_img.mode == 'RGBA':
            rgb_img = Image.new('RGB', license_img.size, (255, 255, 255))
            rgb_img.paste(license_img, mask=license_img.split()[-1] if len(license_img.split()) == 4 else None)
            license_img = rgb_img
        
        license_img.save(buffer, format="PNG", dpi=(DPI, DPI))
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    def generate_back(self, license_data: Dict[str, Any]) -> str:
        """Generate Madagascar license back side using AMPRO coordinates - SIMPLIFIED to only show PDF417 barcode"""
        
        # Create base image with AMPRO back background
        license_img = self._create_security_background(CARD_W_PX, CARD_H_PX, "back")
        draw = ImageDraw.Draw(license_img)
        
        # Enhanced Barcode Data: Include front information + 8-bit image in barcode
        barcode_data = {
            "surname": license_data.get('surname', license_data.get('last_name', 'N/A')),
            "first_name": license_data.get('first_name', license_data.get('names', 'N/A')),
            "birth_date": license_data.get('birth_date', 'N/A'),
            "restrictions": license_data.get('restrictions', '0'),
            "gender": license_data.get('gender', 'N/A'),
            "issuing_authority": "Madagascar Department of Transport",
            "card_number": license_data.get('card_number', 'N/A')
        }
        
        # Use existing license_ready 8-bit image if available (from image_service.py processing)
        license_ready_photo = license_data.get('license_ready_photo_base64')
        if license_ready_photo:
            barcode_data["photo_8bit"] = license_ready_photo
            logger.info("Added existing license_ready 8-bit photo data to barcode")
        else:
            logger.info("No license_ready 8-bit photo available for barcode")
        
        # Generate barcode with JSON data
        barcode_json = json.dumps(barcode_data, separators=(',', ':'))  # Compact JSON
        barcode_img = self._generate_pdf417_barcode(barcode_json)
        
        # Use AMPRO coordinates for barcode (Row 1, all 6 columns)
        barcode_coords = BACK_COORDINATES["barcode"]
        barcode_x = barcode_coords[0]
        barcode_y = barcode_coords[1]
        barcode_w = barcode_coords[2]
        barcode_h = barcode_coords[3]
        
        # Resize barcode to fit the exact AMPRO area
        barcode_resized = barcode_img.resize((barcode_w, barcode_h), Image.Resampling.LANCZOS)
        license_img.paste(barcode_resized, (barcode_x, barcode_y))
        
        # Add fingerprint area in bottom left corner
        fp_coords = BACK_COORDINATES["fingerprint"]
        fp_x = fp_coords[0]
        fp_y = fp_coords[1]
        fp_w = fp_coords[2]
        fp_h = fp_coords[3]
        
        # Draw fingerprint border
        draw.rectangle([fp_x, fp_y, fp_x + fp_w, fp_y + fp_h], 
                      outline=COLORS["black"], width=2)
        
        # Process and add fingerprint if available  
        fingerprint_data = license_data.get("fingerprint_base64")
        if fingerprint_data:
            try:
                logger.info(f"Processing fingerprint data for back card")
                fingerprint_img = self._process_photo_data(fingerprint_data, fp_w - 4, fp_h - 4)  # Leave border space
                if fingerprint_img:
                    # Ensure coordinates are integers
                    paste_x = int(fp_x + 2)
                    paste_y = int(fp_y + 2)
                    license_img.paste(fingerprint_img, (paste_x, paste_y))
                    logger.info(f"Successfully added fingerprint at position ({paste_x}, {paste_y})")
                else:
                    logger.warning("Fingerprint processing returned None")
                    # Create fingerprint pattern (simple dot pattern for visual effect)
                    self._draw_fingerprint_pattern(draw, fp_x, fp_y, fp_w, fp_h)
            except Exception as e:
                logger.warning(f"Failed to process fingerprint: {e}")
                # Create fingerprint pattern (simple dot pattern for visual effect)
                self._draw_fingerprint_pattern(draw, fp_x, fp_y, fp_w, fp_h)
        else:
            # Create fingerprint pattern (simple dot pattern for visual effect)
            self._draw_fingerprint_pattern(draw, fp_x, fp_y, fp_w, fp_h)
        
        # Add fingerprint label below the area
        fp_label_x = fp_x + fp_w // 2
        fp_label_y = fp_y + fp_h + 10
        draw.text((fp_label_x, fp_label_y), "RIGHT THUMB", 
                 fill=COLORS["black"], font=self.fonts["tiny"], anchor="mm")
        
        # REMOVED: All categories, restrictions, government info, and flag
        # Back side now only contains the PDF417 barcode and fingerprint area as requested
        
        # Convert to base64
        buffer = io.BytesIO()
        # Convert back to RGB for compatibility
        if license_img.mode == 'RGBA':
            rgb_img = Image.new('RGB', license_img.size, (255, 255, 255))
            rgb_img.paste(license_img, mask=license_img.split()[-1] if len(license_img.split()) == 4 else None)
            license_img = rgb_img
        
        license_img.save(buffer, format="PNG", dpi=(DPI, DPI))
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    def generate_watermark_template(self, width: int, height: int, text: str = "MADAGASCAR") -> str:
        """Generate watermark template using AMPRO system"""
        watermark_img = self._create_watermark_pattern(width, height, text)
        
        # Convert to base64
        buffer = io.BytesIO()
        # Convert back to RGB for compatibility
        if watermark_img.mode == 'RGBA':
            rgb_img = Image.new('RGB', watermark_img.size, (255, 255, 255))
            rgb_img.paste(watermark_img, mask=watermark_img.split()[-1] if len(watermark_img.split()) == 4 else None)
            watermark_img = rgb_img
        
        watermark_img.save(buffer, format="PNG", dpi=(DPI, DPI))
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    def generate_card_files(self, print_job_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Generate complete card package with proper LINC data mapping
        
        Args:
            print_job_data: Print job information including license_data and person_data
            
        Returns:
            Dictionary with file paths and metadata
        """
        try:
            # Extract data from print job
            license_data = print_job_data.get("license_data", {})
            person_data = print_job_data.get("person_data", {})
            print_job_id = print_job_data.get("print_job_id")
            
            logger.info(f"Generating card files for print job {print_job_id} using unified AMPRO system")
            logger.info(f"License data keys: {list(license_data.keys())}")
            logger.info(f"Person data keys: {list(person_data.keys())}")
            
            # Convert LINC data format to AMPRO format
            ampro_license_data = self._convert_linc_to_ampro_format(license_data, person_data)
            
            # Extract biometric data with multiple fallback paths
            photo_data = self._extract_photo_from_person_data(person_data)
            signature_data = self._extract_signature_from_person_data(person_data)
            fingerprint_data = self._extract_fingerprint_from_person_data(person_data)
            
            # Add extracted biometric data to ampro_license_data for card generation
            if photo_data:
                ampro_license_data["photo_base64"] = photo_data
            if signature_data:
                ampro_license_data["signature_base64"] = signature_data
            if fingerprint_data:
                ampro_license_data["fingerprint_base64"] = fingerprint_data
            
            # Generate front and back images using integrated AMPRO system
            front_base64 = self.generate_front(ampro_license_data, photo_data)
            back_base64 = self.generate_back(ampro_license_data)
            
            # Generate watermark
            watermark_base64 = self.generate_watermark_template(
                width=1012, height=638, text="MADAGASCAR"
            )
            
            # Convert base64 to bytes for PDF generation
            front_bytes = base64.b64decode(front_base64)
            back_bytes = base64.b64decode(back_base64)
            watermark_bytes = base64.b64decode(watermark_base64)
            
            # Generate PDFs
            front_pdf = self._generate_pdf_from_image(front_bytes, "Madagascar License - Front")
            back_pdf = self._generate_pdf_from_image(back_bytes, "Madagascar License - Back")
            combined_pdf = self._generate_combined_pdf(front_bytes, back_bytes, ampro_license_data)
            
            # Prepare file data for saving to disk
            card_files_data = {
                "front_image": front_base64,
                "back_image": back_base64,
                "watermark_image": watermark_base64,
                "front_pdf": base64.b64encode(front_pdf).decode('utf-8'),
                "back_pdf": base64.b64encode(back_pdf).decode('utf-8'),
                "combined_pdf": base64.b64encode(combined_pdf).decode('utf-8')
            }
            
            # Save files to disk using card file manager
            file_paths = card_file_manager.save_card_files(
                print_job_id=print_job_id,
                card_files_data=card_files_data,
                created_at=datetime.utcnow()
            )
            
            # Return file paths and metadata (no base64 data for database storage)
            result = {
                "file_paths": file_paths,
                "card_number": ampro_license_data.get("card_number", ""),
                "generation_timestamp": datetime.utcnow().isoformat(),
                "generator_version": self.version,
                "files_generated": True,
                "files_saved_to_disk": True,
                "ampro_system_used": True,
                "file_sizes": {
                    "front_image_bytes": len(front_bytes),
                    "back_image_bytes": len(back_bytes),
                    "watermark_image_bytes": len(watermark_bytes),
                    "front_pdf_bytes": len(front_pdf),
                    "back_pdf_bytes": len(back_pdf),
                    "combined_pdf_bytes": len(combined_pdf),
                    "total_bytes": (len(front_bytes) + len(back_bytes) + len(watermark_bytes) + 
                                   len(front_pdf) + len(back_pdf) + len(combined_pdf))
                }
            }
            
            logger.info(f"Successfully generated card files for print job {print_job_id} "
                       f"({result['file_sizes']['total_bytes']:,} bytes total)")
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating card files for print job {print_job_data.get('print_job_id')}: {e}")
            raise Exception(f"Card generation failed: {str(e)}")
    
    def _convert_linc_to_ampro_format(self, license_data: Dict[str, Any], person_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert LINC data format to AMPRO format with comprehensive mapping
        This ensures all LINC fields are properly mapped to AMPRO expectations
        """
        
        # Helper function to safely extract license categories 
        def extract_categories(license_data):
            # Try different paths for license categories
            if "licenses" in license_data and isinstance(license_data["licenses"], list):
                # Extract categories from licenses array
                categories = []
                for license in license_data["licenses"]:
                    if "category" in license:
                        categories.append(license["category"])
                return categories
            elif "category" in license_data:
                # Single category
                return [license_data["category"]]
            elif "categories" in license_data:
                # Direct categories array
                return license_data["categories"]
            else:
                return ["B"]  # Default fallback
        
        # Helper function to safely extract dates
        def extract_dates(license_data):
            issue_date = None
            expiry_date = None
            first_issue_date = None
            
            # Try to extract from licenses array first
            if "licenses" in license_data and isinstance(license_data["licenses"], list):
                for license in license_data["licenses"]:
                    if license.get("issue_date"):
                        issue_date = license["issue_date"]
                    if license.get("expiry_date"):
                        expiry_date = license["expiry_date"]
                    if license.get("first_issue_date"):
                        first_issue_date = license["first_issue_date"]
                    if issue_date and expiry_date:
                        break
            
            # Fallback to direct fields
            if not issue_date:
                issue_date = license_data.get("issue_date")
            if not expiry_date:
                expiry_date = license_data.get("expiry_date")
            if not first_issue_date:
                first_issue_date = license_data.get("first_issue_date", issue_date)
            
            return issue_date, expiry_date, first_issue_date
        
        # Helper function to extract restrictions
        def extract_restrictions(license_data):
            # Try different paths for restrictions
            restrictions = (
                license_data.get("restrictions") or 
                license_data.get("driver_restrictions") or 
                license_data.get("vehicle_restrictions") or 
                "0"
            )
            return str(restrictions)
        
        # Convert dates to YYYY-MM-DD format (as requested)
        def format_date(date_val):
            if isinstance(date_val, datetime):
                return date_val.strftime('%Y-%m-%d')
            elif isinstance(date_val, date):
                return date_val.strftime('%Y-%m-%d')
            elif isinstance(date_val, str) and date_val:
                # Try to parse common date formats and convert to YYYY-MM-DD
                try:
                    # Try ISO format first (YYYY-MM-DD) - already correct
                    if len(date_val) == 10 and date_val.count('-') == 2:
                        return date_val  # Already in correct format
                    # Try DD/MM/YYYY format
                    elif len(date_val) == 10 and date_val.count('/') == 2:
                        parsed_date = datetime.strptime(date_val, '%d/%m/%Y')
                        return parsed_date.strftime('%Y-%m-%d')
                    # Try other common formats
                    elif 'T' in date_val:  # ISO datetime format
                        parsed_date = datetime.fromisoformat(date_val.replace('Z', '+00:00'))
                        return parsed_date.strftime('%Y-%m-%d')
                    return date_val
                except:
                    return date_val
            return str(date_val) if date_val else "N/A"
        
        # Extract license categories
        categories = extract_categories(license_data)
        category_str = ", ".join(categories) if isinstance(categories, list) else str(categories)
        
        # Extract dates
        issue_date, expiry_date, first_issue_date = extract_dates(license_data)
        
        # Extract person information with comprehensive fallbacks
        first_name = (
            person_data.get('first_name') or 
            person_data.get('name') or 
            person_data.get('names') or 
            'N/A'
        )
        last_name = (
            person_data.get('last_name') or 
            person_data.get('surname') or 
            person_data.get('family_name') or 
            'N/A'
        )
        birth_date = (
            person_data.get('birth_date') or 
            person_data.get('date_of_birth') or 
            person_data.get('dob') or 
            person_data.get('birthdate')
        )
        id_number = (
            person_data.get('id_number') or 
            person_data.get('person_id') or 
            person_data.get('national_id') or 
            person_data.get('passport_number') or 
            'N/A'
        )
        raw_gender = (
            person_data.get('gender') or 
            person_data.get('sex') or 
            person_data.get('person_nature') or 
            'M'
        )
        
        # Map gender codes to text
        def map_gender_code(gender_code):
            """Map numeric gender codes to text"""
            if isinstance(gender_code, str):
                code_lower = gender_code.lower().strip()
                if code_lower in ['01', '1', 'm', 'male']:
                    return 'MALE'
                elif code_lower in ['02', '2', 'f', 'female']:
                    return 'FEMALE'
            return 'MALE'  # Default fallback
        
        gender = map_gender_code(raw_gender)
        
        # Calculate card expiry date (5 years from now, regardless of license expiry)
        from datetime import datetime, timedelta
        card_creation_date = datetime.now()
        card_expiry_date = card_creation_date + timedelta(days=365 * 5)  # 5 years for card
        
        # Use card expiry for display, not license expiry
        expiry_date = card_expiry_date.isoformat()
        
        # Format dates properly
        formatted_issue_date = format_date(issue_date)
        formatted_expiry_date = format_date(expiry_date)
        formatted_first_issue = format_date(first_issue_date)
        formatted_birth_date = format_date(birth_date)
        
        # Extract restrictions
        restrictions = extract_restrictions(license_data)
        
        # Create AMPRO-compatible data structure with all required fields
        ampro_data = {
            # Person information
            'first_name': first_name,
            'last_name': last_name,
            'surname': last_name,  # AMPRO uses 'surname'
            'names': first_name,   # AMPRO uses 'names'
            'birth_date': formatted_birth_date,
            'date_of_birth': formatted_birth_date,
            'gender': gender.upper() if gender else 'M',
            'id_number': id_number,
            
            # License information
            'category': category_str,
            'categories': categories,
            'restrictions': restrictions,
            'driver_restrictions': restrictions,  # Same as restrictions for front card
            'vehicle_restrictions': restrictions, # Same as restrictions for front card
            'issue_date': formatted_issue_date,
            'expiry_date': formatted_expiry_date,
            'first_issue_date': formatted_first_issue,
            'issued_location': 'Madagascar',
            'issuing_location': 'Madagascar',
            
            # Additional metadata
            'country': 'Madagascar',
            'card_number': license_data.get('card_number', ''),
            
            # Photo data (if available)
            'photo_base64': license_data.get('photo_base64', ''),
        }
        
        logger.info(f"Enhanced LINC to AMPRO data conversion:")
        logger.info(f"  - Full Name: {ampro_data['first_name']} {ampro_data['last_name']}")
        logger.info(f"  - Categories/Codes: {ampro_data['category']}")
        logger.info(f"  - ID Number: {ampro_data['id_number']}")
        logger.info(f"  - Birth Date: {ampro_data['birth_date']}")
        logger.info(f"  - Gender/Sex: {ampro_data['gender']}")
        logger.info(f"  - Restrictions: {ampro_data['restrictions']}")
        logger.info(f"  - Valid Period: {ampro_data['issue_date']} - {ampro_data['expiry_date']}")
        logger.info(f"  - First Issue: {ampro_data['first_issue_date']}")
        
        return ampro_data
    
    def _generate_pdf_from_image(self, image_bytes: bytes, title: str) -> bytes:
        """Generate PDF from image bytes using ReportLab"""
        pdf_buffer = io.BytesIO()
        
        # Create PDF with exact card dimensions
        page_width = 1012 * 72 / 300  # Convert pixels to points (72 DPI)
        page_height = 638 * 72 / 300
        
        c = canvas.Canvas(pdf_buffer, pagesize=(page_width, page_height))
        c.setTitle(title)
        c.setAuthor("Madagascar License System - AMPRO")
        c.setSubject("Official Madagascar Driver's License")
        c.setCreator("Madagascar License System v3.0")
        
        # Create temporary image file for ReportLab
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
        """Generate combined PDF with both front and back using ReportLab"""
        pdf_buffer = io.BytesIO()
        
        # Create PDF with exact card dimensions
        page_width = 1012 * 72 / 300  # Convert pixels to points (72 DPI)
        page_height = 638 * 72 / 300
        
        c = canvas.Canvas(pdf_buffer, pagesize=(page_width, page_height))
        c.setTitle(f"Madagascar Driver's License - {license_data.get('card_number', 'Card')}")
        c.setAuthor("Madagascar License System - AMPRO")
        c.setSubject("Official Madagascar Driver's License")
        c.setCreator("Madagascar License System v3.0")
        
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


def get_license_specifications() -> Dict[str, Any]:
    """Get Madagascar license specifications and coordinates"""
    return {
        "dimensions": {
            "width_mm": CARD_W_MM,
            "height_mm": CARD_H_MM,
            "width_px": CARD_W_PX,
            "height_px": CARD_H_PX,
            "dpi": DPI,
        },
        "coordinates": COORDINATES,
        "font_sizes": FONT_SIZES,
        "colors": COLORS,
    }


# Service instances for dependency injection
madagascar_card_generator = MadagascarCardGenerator()

# Legacy compatibility aliases
card_generator = madagascar_card_generator
madagascar_license_generator = madagascar_card_generator 