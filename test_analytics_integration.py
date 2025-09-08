#!/usr/bin/env python3
"""
Analytics Integration Test Script
Quick test to verify that analytics endpoints are working correctly
"""

import requests
import json
from datetime import datetime
import sys
import os

# Configuration
BACKEND_URL = "http://localhost:8000"  # Adjust if your backend runs on different port
TEST_USER_EMAIL = "admin@example.com"  # Adjust to your test admin user
TEST_USER_PASSWORD = "admin123"  # Adjust to your test admin password

def get_auth_token():
    """Get authentication token for API calls"""
    login_url = f"{BACKEND_URL}/api/v1/auth/login"
    
    login_data = {
        "username": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD
    }
    
    try:
        response = requests.post(login_url, data=login_data)
        response.raise_for_status()
        
        token_data = response.json()
        return token_data.get("access_token")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to authenticate: {e}")
        return None

def test_analytics_endpoint(endpoint, token, params=None):
    """Test a specific analytics endpoint"""
    url = f"{BACKEND_URL}/api/v1/analytics{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ {endpoint} - Success")
        print(f"   Response keys: {list(data.keys())}")
        
        if "data" in data:
            if isinstance(data["data"], dict):
                print(f"   Data keys: {list(data['data'].keys())}")
            elif isinstance(data["data"], list):
                print(f"   Data length: {len(data['data'])}")
        
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ {endpoint} - Failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"   Error details: {error_data}")
            except:
                print(f"   Response text: {e.response.text}")
        return False

def main():
    """Run analytics integration tests"""
    print("🔍 Analytics Integration Test")
    print("=" * 50)
    
    # Test authentication
    print("\n1. Testing Authentication...")
    token = get_auth_token()
    if not token:
        print("❌ Cannot proceed without authentication")
        sys.exit(1)
    
    print(f"✅ Authentication successful")
    
    # Test analytics endpoints
    print("\n2. Testing Analytics Endpoints...")
    
    test_params = {
        "date_range": "30days",
        "location_id": None
    }
    
    endpoints_to_test = [
        "/kpi/summary",
        "/kpi/applications", 
        "/kpi/licenses",
        "/kpi/printing",
        "/kpi/financial",
        "/charts/applications/trends",
        "/charts/applications/types", 
        "/charts/applications/pipeline",
        "/system/health",
        "/activity/recent",
        "/locations/performance"
    ]
    
    results = {}
    for endpoint in endpoints_to_test:
        success = test_analytics_endpoint(endpoint, token, test_params)
        results[endpoint] = success
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    successful = sum(1 for success in results.values() if success)
    total = len(results)
    
    for endpoint, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {endpoint}")
    
    print(f"\nOverall: {successful}/{total} endpoints working")
    
    if successful == total:
        print("🎉 All analytics endpoints are working correctly!")
        return 0
    else:
        print("⚠️  Some endpoints need attention")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
