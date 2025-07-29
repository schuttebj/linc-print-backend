#!/usr/bin/env python3
"""
Install barcode dependencies for Madagascar License System
Run this script to install the required libraries for barcode generation
"""

import subprocess
import sys

def install_package(package):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✅ Successfully installed {package}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install {package}: {e}")
        return False

def main():
    """Install all barcode dependencies"""
    print("🔧 Installing barcode dependencies for Madagascar License System...")
    
    packages = [
        "reportlab>=4.0.0",    # PDF417 barcode generation
        "Pillow>=10.0.0",      # Image processing
        "qrcode[pil]>=7.0.0"   # QR code fallback
    ]
    
    success_count = 0
    for package in packages:
        if install_package(package):
            success_count += 1
    
    print(f"\n📊 Installation Summary:")
    print(f"✅ {success_count}/{len(packages)} packages installed successfully")
    
    if success_count == len(packages):
        print("\n🎉 All dependencies installed! Restart your server to generate real barcodes.")
        print("📋 You can now generate actual PDF417 barcodes that can be scanned.")
    elif success_count > 0:
        print("\n⚠️  Some packages failed to install. QR codes will be available as fallback.")
    else:
        print("\n❌ Installation failed. Barcode generation will remain in simulation mode.")
    
    print("\n🧪 Test your barcode generation with:")
    print("POST /api/v1/barcode/test")

if __name__ == "__main__":
    main() 