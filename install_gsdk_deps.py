#!/usr/bin/env python3
"""
G-SDK Dependencies Installation Script
Installs required packages for G-SDK server-side biometric matching
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a shell command and handle errors"""
    print(f"\n🔧 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        if result.stdout:
            print(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed: {e}")
        if e.stdout:
            print(f"Output: {e.stdout}")
        if e.stderr:
            print(f"Error: {e.stderr}")
        return False

def main():
    print("🚀 G-SDK Dependencies Installation")
    print("=" * 50)
    
    # Install G-SDK dependencies
    if not run_command("pip install -r requirements_gsdk.txt", "Installing G-SDK dependencies"):
        sys.exit(1)
    
    # Copy G-SDK Python client to app directory
    gsdk_source = "../g-sdk-master/client/python"
    gsdk_dest = "app/gsdk"
    
    if os.path.exists(gsdk_source):
        if not run_command(f"xcopy /E /I /Y \"{gsdk_source}\" \"{gsdk_dest}\"" if sys.platform == "win32" else f"cp -r {gsdk_source} {gsdk_dest}", "Copying G-SDK Python client"):
            print("⚠️ Failed to copy G-SDK client, continuing anyway...")
    else:
        print(f"⚠️ G-SDK source not found at {gsdk_source}")
    
    print("\n🎉 G-SDK setup completed!")
    print("\nNext steps:")
    print("1. Install and run the Device Gateway")
    print("2. Connect your BioStar device to the gateway")
    print("3. Test the G-SDK integration endpoints")

if __name__ == "__main__":
    main()
