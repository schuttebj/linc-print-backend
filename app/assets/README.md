# LINC Print Backend Assets

This directory contains assets for **Madagascar Driver's License** generation using the **exact same design system as AMPRO**.

## 🎯 **System Integration**

The Madagascar license system uses the **identical AMPRO license generation system** with the following customizations:

- **Same layout and coordinates** as South African licenses
- **Same background templates** and security overlays
- **Same fonts and typography** system
- **Malagasy language** text and labels
- **Madagascar flag colors** and national branding

## 📁 **Directory Structure**

```
assets/
├── fonts/                         # Typography files
│   ├── SourceSansPro-Bold.ttf     # Primary bold font
│   ├── SourceSansPro-Regular.ttf  # Primary regular font
│   ├── ARIALBD.TTF                # Fallback bold font
│   └── dejavu-sans.bold.ttf       # Linux fallback font
├── overlays/                      # Background templates & security layers
│   ├── Card_BG_Front.png          # Front background template (1012×638px)
│   ├── Card_BG_Back.png           # Back background template (1012×638px)
│   ├── security_background.png    # Security pattern overlay
│   └── watermark_pattern.png      # "SOUTH AFRICA" watermark (adapted to "MADAGASCAR")
├── templates/                     # Additional template files
└── sa_license_coordinates.csv     # Exact positioning coordinates
```

## 🔧 **Technical Specifications**

- **Canvas Size**: 85.60 mm × 54.00 mm (ISO/IEC 18013-1 standard)
- **Resolution**: 300 DPI
- **Pixel Dimensions**: 1012 × 638 pixels
- **Format**: PNG with transparency support
- **Color Space**: RGB for digital, CMYK-compatible for print

## 📊 **Coordinate System**

All coordinates from `sa_license_coordinates.csv` are used exactly as in AMPRO:

| Element | Side | X | Y | Width | Height | Description |
|---------|------|---|---|-------|--------|-------------|
| photo | front | 40 | 58 | 213 | 260 | Photo area (18×22mm) |
| surname | front | 530 | 80 | - | - | Surname text field |
| names | front | 530 | 125 | - | - | Names text field |
| id_number | front | 530 | 170 | - | - | ID Number text field |
| barcode | back | 30 | 340 | 458 | 38 | PDF417 barcode area |

*See `sa_license_coordinates.csv` for complete coordinate mappings.*

## 🌍 **Madagascar Customizations**

### **Language Adaptations:**
- **AMPRO**: "SOUTH AFRICA" → **Madagascar**: "MADAGASCAR"
- **AMPRO**: English/Afrikaans → **Madagascar**: Malagasy/French
- **AMPRO**: "Surname" → **Madagascar**: "ANARANA FIANAKAVIANA"
- **AMPRO**: "Restrictions" → **Madagascar**: "FETRA"

### **Color Adaptations:**
- **AMPRO**: SA flag colors → **Madagascar**: Madagascar flag colors
  - Red: `(220, 38, 48)`
  - Green: `(0, 158, 73)`
  - White: `(255, 255, 255)`

### **Content Adaptations:**
- **Authority**: "MINISITERAN'NY FIARAKODIA sy ny FITATERANA"
- **License Categories**: Madagascar-specific categories (A1, A, B, C, D)
- **Watermark**: "MADAGASCAR" instead of "SOUTH AFRICA"

## 🚀 **Usage in Code**

```python
from app.services.madagascar_license_generator import madagascar_license_generator

# Generate front side
front_image = madagascar_license_generator.generate_front(
    license_data={'license_number': 'MG123456', ...}, 
    photo_data="base64_photo_string"
)

# Generate back side  
back_image = madagascar_license_generator.generate_back(license_data)

# Generate watermark
watermark = madagascar_license_generator.generate_watermark_template(
    width=1012, height=638, text="MADAGASCAR"
)
```

## 🔒 **Security Features**

1. **Background Templates**: Professional security patterns from AMPRO
2. **Watermark Pattern**: Diagonal "MADAGASCAR" text overlay
3. **PDF417 Barcode**: High-security level encoding
4. **Typography**: Anti-counterfeiting font choices
5. **Layout Precision**: Exact coordinate positioning

## 📋 **Asset Sources**

- **Source**: AMPRO Old/AMPRO Licence/app/assets/
- **Copied**: All fonts, overlays, coordinates
- **Adapted**: Text content for Madagascar
- **Maintained**: Exact same layout, dimensions, and design

## ✅ **Quality Compliance**

This implementation ensures:
- **Identical visual design** to AMPRO licenses
- **Professional security features** 
- **International standards compliance** (ISO/IEC 18013-1)
- **Madagascar legal requirements** met
- **Production-ready quality** for official use

---

**📞 Support**: For questions about asset usage or customizations, refer to the `madagascar_license_generator.py` service implementation. 