#!/usr/bin/env python3
"""
Madagascar License Barcode System Test Script
Demonstrates barcode generation, encoding, and decoding functionality
"""

import json
import asyncio
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add the app directory to the path
sys.path.append(str(Path(__file__).parent / "app"))

from app.services.barcode_service import barcode_service, BarcodeGenerationError, BarcodeDecodingError


def test_sample_barcode_data():
    """Test generating barcode with sample data"""
    print("🔧 Testing Sample Barcode Generation")
    print("=" * 50)
    
    # Create sample data (simulating a real license)
    sample_data = {
        "ver": 1,
        "id": str(uuid.uuid4()),
        "dob": "1985-03-15",
        "sex": "F",
        "codes": ["B", "EB"],
        "valid_from": "2023-01-01",
        "valid_to": "2028-01-01",
        "first_issued": "2018-01-01",
        "country": "MG",
        "name": "RANDRIANARISOA Marie",
        "vehicle_restrictions": [],
        "driver_restrictions": ["glasses"],
        "card_num": "MG240001234"
    }
    
    try:
        # Generate PDF417 barcode
        barcode_image = barcode_service.generate_pdf417_barcode(sample_data)
        
        # Calculate sizes
        json_size = len(json.dumps(sample_data).encode('utf-8'))
        image_size = len(barcode_image) if isinstance(barcode_image, str) else 0
        
        print(f"✅ Sample barcode generated successfully!")
        print(f"📊 JSON Data Size: {json_size} bytes")
        print(f"🖼️  Barcode Image Size: {image_size} bytes (base64)")
        print(f"📝 License ID: {sample_data['id']}")
        print(f"👤 Name: {sample_data['name']}")
        print(f"🚗 Codes: {', '.join(sample_data['codes'])}")
        
        return sample_data, barcode_image
        
    except Exception as e:
        print(f"❌ Error generating sample barcode: {e}")
        return None, None


def test_barcode_decoding(sample_data):
    """Test decoding barcode data"""
    print("\n🔍 Testing Barcode Decoding")
    print("=" * 50)
    
    try:
        # Convert to JSON string (simulating barcode scan result)
        json_string = json.dumps(sample_data, separators=(',', ':'))
        
        # Decode the barcode data
        decoded_data = barcode_service.decode_barcode_data(json_string)
        
        # Generate comprehensive info
        license_info = barcode_service.generate_comprehensive_barcode_info(decoded_data)
        
        print(f"✅ Barcode decoded successfully!")
        print(f"👤 Full Name: {license_info['full_name']}")
        print(f"📅 Date of Birth: {license_info['date_of_birth']}")
        print(f"⚥  Sex: {license_info['sex']}")
        print(f"🚗 License Codes: {', '.join(license_info['license_codes'])}")
        print(f"🏳️  Country: {license_info['country']}")
        print(f"📋 Card Number: {license_info['card_number']}")
        print(f"✅ Valid: {license_info['is_valid']}")
        print(f"📏 Data Size: {license_info['data_size_bytes']} bytes")
        
        if license_info['driver_restrictions']:
            print(f"🚫 Driver Restrictions: {', '.join(license_info['driver_restrictions'])}")
        
        return decoded_data, license_info
        
    except Exception as e:
        print(f"❌ Error decoding barcode: {e}")
        return None, None


def test_with_photo():
    """Test barcode generation with photo data"""
    print("\n📸 Testing Barcode with Photo")
    print("=" * 50)
    
    try:
        # Generate sample photo
        sample_photo = barcode_service._generate_sample_photo()
        
        if sample_photo:
            # Create sample data with photo
            sample_data_with_photo = {
                "ver": 1,
                "id": str(uuid.uuid4()),
                "dob": "1990-05-12",
                "sex": "M",
                "codes": ["B"],
                "valid_from": "2023-06-01",
                "valid_to": "2028-06-01",
                "first_issued": "2020-06-01",
                "country": "MG",
                "name": "SMITH John",
                "vehicle_restrictions": ["auto"],
                "driver_restrictions": [],
                "card_num": "MG240005678",
                "photo": sample_photo
            }
            
            # Calculate sizes
            json_size = len(json.dumps(sample_data_with_photo).encode('utf-8'))
            photo_size = len(sample_photo)
            
            print(f"✅ Sample photo generated!")
            print(f"📸 Photo Size: {photo_size} bytes (base64)")
            print(f"📊 Total JSON Size: {json_size} bytes")
            
            # Check if within limits
            max_size = barcode_service.BARCODE_CONFIG['max_data_bytes']
            if json_size <= max_size:
                print(f"✅ Within size limit ({max_size} bytes)")
                
                # Generate barcode with photo
                barcode_image = barcode_service.generate_pdf417_barcode(sample_data_with_photo)
                print(f"✅ Barcode with photo generated successfully!")
                
                return sample_data_with_photo
            else:
                print(f"⚠️  Exceeds size limit by {json_size - max_size} bytes")
                
        else:
            print("⚠️  Could not generate sample photo (PIL not available)")
            
    except Exception as e:
        print(f"❌ Error testing with photo: {e}")
        
    return None


def display_api_endpoints():
    """Display available API endpoints for testing"""
    print("\n🌐 Available API Endpoints")
    print("=" * 50)
    
    endpoints = [
        ("POST", "/api/v1/barcode/generate", "Generate barcode from license ID"),
        ("POST", "/api/v1/barcode/decode", "Decode scanned barcode JSON"),
        ("POST", "/api/v1/barcode/test", "Generate test barcode with sample data"),
        ("POST", "/api/v1/barcode/decode/photo", "Extract photo from barcode"),
        ("GET", "/api/v1/barcode/scan-test", "Get sample barcode for scanner testing"),
        ("GET", "/api/v1/barcode/format", "Get barcode format specification")
    ]
    
    for method, endpoint, description in endpoints:
        print(f"{method:6} {endpoint:35} - {description}")
    
    print(f"\n📋 Test with curl:")
    print(f"curl -X GET http://localhost:8000/api/v1/barcode/scan-test")
    print(f"curl -X POST http://localhost:8000/api/v1/barcode/test \\")
    print(f'     -H "Content-Type: application/json" \\')
    print(f'     -d \'{{"person_name": "TEST USER", "date_of_birth": "1990-01-01", "sex": "M", "license_codes": ["B"]}}\'')


def create_scanner_test_json():
    """Create a JSON file for scanner testing"""
    print("\n📄 Creating Scanner Test Files")
    print("=" * 50)
    
    try:
        # Test data for scanning
        test_data = {
            "ver": 1,
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "dob": "1985-03-15",
            "sex": "F",
            "codes": ["B", "EB"],
            "valid_from": "2023-01-01",
            "valid_to": "2028-01-01",
            "first_issued": "2018-01-01",
            "country": "MG",
            "name": "RANDRIANARISOA Marie",
            "vehicle_restrictions": [],
            "driver_restrictions": ["glasses"],
            "card_num": "MG240001234"
        }
        
        # Save compact JSON for scanner testing
        scanner_json = json.dumps(test_data, separators=(',', ':'))
        
        with open("scanner_test_data.json", "w") as f:
            f.write(scanner_json)
        
        # Save pretty JSON for reference
        with open("scanner_test_data_readable.json", "w") as f:
            json.dump(test_data, f, indent=2)
        
        print(f"✅ Created scanner_test_data.json ({len(scanner_json)} bytes)")
        print(f"✅ Created scanner_test_data_readable.json")
        print(f"📋 Use the content of scanner_test_data.json to test decoding")
        
        return scanner_json
        
    except Exception as e:
        print(f"❌ Error creating scanner test files: {e}")
        return None


def main():
    """Main test function"""
    print("🇲🇬 Madagascar License Barcode System Test")
    print("=" * 60)
    print(f"⚙️  Barcode Service Version: {barcode_service.BARCODE_CONFIG['version']}")
    print(f"📏 Max Data Size: {barcode_service.BARCODE_CONFIG['max_data_bytes']} bytes")
    print(f"🔧 Error Correction: Level {barcode_service.BARCODE_CONFIG['error_correction_level']}")
    
    # Test 1: Sample barcode generation
    sample_data, barcode_image = test_sample_barcode_data()
    
    if sample_data:
        # Test 2: Barcode decoding
        decoded_data, license_info = test_barcode_decoding(sample_data)
        
        # Test 3: Barcode with photo
        photo_data = test_with_photo()
        
        # Create scanner test files
        scanner_json = create_scanner_test_json()
        
        # Display API endpoints
        display_api_endpoints()
        
        print(f"\n✅ All tests completed successfully!")
        print(f"🚀 Start the FastAPI server and test the endpoints")
        print(f"📝 Use the scanner test JSON to verify barcode scanning integration")
        
    else:
        print(f"\n❌ Tests failed!")


if __name__ == "__main__":
    main() 