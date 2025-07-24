#!/usr/bin/env python3
"""
Test script for Madagascar License Generator
Verifies that the AMPRO system integration works correctly
"""

import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_madagascar_license_generator():
    """Test the Madagascar license generator"""
    try:
        from app.services.madagascar_license_generator import madagascar_license_generator, get_license_specifications
        
        print("🔧 Testing Madagascar License Generator (AMPRO System)")
        print("=" * 60)
        
        # Test specifications
        specs = get_license_specifications()
        print(f"✅ License specifications loaded:")
        print(f"   - Dimensions: {specs['dimensions']['width_px']}×{specs['dimensions']['height_px']} pixels")
        print(f"   - Physical size: {specs['dimensions']['width_mm']}×{specs['dimensions']['height_mm']} mm")
        print(f"   - DPI: {specs['dimensions']['dpi']}")
        print(f"   - Coordinates loaded: {len(specs['coordinates'])} elements")
        
        # Sample license data
        license_data = {
            'license_number': 'MG2024001234',
            'first_name': 'Rakoto',
            'last_name': 'Andriamamy',
            'surname': 'Andriamamy',
            'names': 'Rakoto',
            'birth_date': '1990-05-15',
            'date_of_birth': '1990-05-15',
            'gender': 'M',
            'id_number': '301901500123',
            'category': 'B',
            'categories': ['B'],
            'restrictions': '0',
            'issue_date': '2024-01-15',
            'expiry_date': '2034-01-15',
            'issued_location': 'Madagascar',
            'issuing_location': 'Madagascar',
            'country': 'Madagascar',
        }
        
        print(f"\n🎨 Testing license generation for: {license_data['first_name']} {license_data['last_name']}")
        
        # Test front generation
        print("\n📄 Generating front side...")
        front_base64 = madagascar_license_generator.generate_front(license_data, None)
        print(f"   ✅ Front generated: {len(front_base64):,} characters (base64)")
        
        # Test back generation
        print("\n📄 Generating back side...")
        back_base64 = madagascar_license_generator.generate_back(license_data)
        print(f"   ✅ Back generated: {len(back_base64):,} characters (base64)")
        
        # Test watermark generation
        print("\n🌊 Generating watermark...")
        watermark_base64 = madagascar_license_generator.generate_watermark_template(1012, 638, "MADAGASCAR")
        print(f"   ✅ Watermark generated: {len(watermark_base64):,} characters (base64)")
        
        # Estimate file sizes
        import base64
        front_bytes = len(base64.b64decode(front_base64))
        back_bytes = len(base64.b64decode(back_base64))
        watermark_bytes = len(base64.b64decode(watermark_base64))
        
        print(f"\n📊 File sizes:")
        print(f"   - Front image: {front_bytes:,} bytes ({front_bytes/1024:.1f} KB)")
        print(f"   - Back image: {back_bytes:,} bytes ({back_bytes/1024:.1f} KB)")
        print(f"   - Watermark: {watermark_bytes:,} bytes ({watermark_bytes/1024:.1f} KB)")
        print(f"   - Total: {front_bytes + back_bytes + watermark_bytes:,} bytes ({(front_bytes + back_bytes + watermark_bytes)/1024:.1f} KB)")
        
        print(f"\n✅ All tests passed! Madagascar License Generator working correctly.")
        print(f"🎯 AMPRO system successfully integrated for Madagascar licenses.")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Madagascar license generator: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_card_generator_integration():
    """Test the card generator service integration"""
    try:
        from app.services.card_generator import madagascar_card_generator
        
        print("\n🔧 Testing Card Generator Integration")
        print("=" * 60)
        
        # Sample print job data
        print_job_data = {
            "print_job_id": "test-job-12345",
            "license_data": {
                'license_number': 'MG2024001234',
                'categories': ['B'],
                'restrictions': '0',
                'issue_date': '2024-01-15',
                'expiry_date': '2034-01-15',
                'card_number': 'MG2024001234',
            },
            "person_data": {
                'first_name': 'Rakoto',
                'last_name': 'Andriamamy',
                'birth_date': '1990-05-15',
                'gender': 'M',
                'id_number': '301901500123',
                'photo_data': None  # No photo for test
            }
        }
        
        print(f"🎨 Testing card generation service...")
        
        # Test the production generator (without actually saving files)
        generator = madagascar_card_generator
        ampro_data = generator._convert_to_ampro_format(
            print_job_data["license_data"], 
            print_job_data["person_data"]
        )
        
        print(f"   ✅ Data conversion successful")
        print(f"   📋 AMPRO format: license_number={ampro_data['license_number']}")
        print(f"   📋 Name: {ampro_data['first_name']} {ampro_data['last_name']}")
        print(f"   📋 Categories: {ampro_data['category']}")
        
        print(f"\n✅ Card generator integration test passed!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing card generator integration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Madagascar License System Test Suite")
    print("Testing AMPRO system integration for Madagascar licenses")
    print("=" * 80)
    
    success = True
    
    # Test the Madagascar license generator
    if not test_madagascar_license_generator():
        success = False
    
    # Test the card generator integration
    if not test_card_generator_integration():
        success = False
    
    print("\n" + "=" * 80)
    if success:
        print("🎉 ALL TESTS PASSED! Madagascar License System ready for deployment.")
    else:
        print("❌ SOME TESTS FAILED! Please check the errors above.")
        sys.exit(1) 