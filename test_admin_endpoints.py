#!/usr/bin/env python3
"""
Test script for Madagascar License System Admin Endpoints
Tests the new location and user management initialization endpoints
"""

import requests
import json
import time
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
ADMIN_ENDPOINTS = {
    "drop_tables": "/admin/drop-tables",
    "init_tables": "/admin/init-tables", 
    "init_users": "/admin/init-users",
    "init_locations": "/admin/init-locations",
    "init_location_users": "/admin/init-location-users",
    "reset_database": "/admin/reset-database"
}

def make_request(endpoint: str) -> Dict[str, Any]:
    """Make a POST request to an admin endpoint"""
    url = f"{BASE_URL}{endpoint}"
    try:
        print(f"\n{'='*60}")
        print(f"Testing: {endpoint}")
        print(f"URL: {url}")
        print(f"{'='*60}")
        
        start_time = time.time()
        response = requests.post(url, timeout=30)
        duration = time.time() - start_time
        
        print(f"Status Code: {response.status_code}")
        print(f"Duration: {duration:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Status: {data.get('status', 'unknown')}")
            print(f"Message: {data.get('message', 'No message')}")
            
            # Print specific details based on endpoint
            if 'created_locations' in data:
                print(f"Locations Created: {len(data['created_locations'])}")
                for loc in data['created_locations'][:3]:  # Show first 3
                    print(f"  - {loc.get('code', 'N/A')}: {loc.get('name', 'N/A')}")
                if len(data['created_locations']) > 3:
                    print(f"  ... and {len(data['created_locations']) - 3} more")
                    
            if 'created_users' in data:
                print(f"Users Created: {len(data['created_users'])}")
                for user in data['created_users'][:3]:  # Show first 3
                    print(f"  - {user.get('username', 'N/A')}: {user.get('email', 'N/A')}")
                if len(data['created_users']) > 3:
                    print(f"  ... and {len(data['created_users']) - 3} more")
            
            if 'admin_credentials' in data:
                creds = data['admin_credentials']
                print(f"Admin Username: {creds.get('username', 'N/A')}")
                print(f"Admin Email: {creds.get('email', 'N/A')}")
            
            if 'summary' in data:
                summary = data['summary']
                print("Summary:")
                for key, value in summary.items():
                    print(f"  {key}: {value}")
            
            return data
        else:
            print(f"Error Response: {response.text}")
            return {"status": "error", "response": response.text}
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return {"status": "error", "exception": str(e)}
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return {"status": "error", "json_error": str(e)}

def test_individual_endpoints():
    """Test each endpoint individually"""
    print("TESTING INDIVIDUAL ADMIN ENDPOINTS")
    print("=" * 80)
    
    results = {}
    
    # Test each endpoint
    for name, endpoint in ADMIN_ENDPOINTS.items():
        if name == "reset_database":  # Skip reset for individual tests
            continue
            
        result = make_request(endpoint)
        results[name] = result
        time.sleep(2)  # Brief pause between requests
    
    return results

def test_complete_reset():
    """Test the complete database reset endpoint"""
    print("\n\nTESTING COMPLETE DATABASE RESET")
    print("=" * 80)
    
    result = make_request(ADMIN_ENDPOINTS["reset_database"])
    return result

def test_health_check():
    """Test the health check endpoint"""
    print("\n\nTESTING HEALTH CHECK")
    print("=" * 80)
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print(f"Health Status: {data.get('status', 'unknown')}")
            print(f"System: {data.get('system', 'unknown')}")
            print(f"Version: {data.get('version', 'unknown')}")
            return True
        else:
            print(f"Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"Health check error: {e}")
        return False

def main():
    """Main test function"""
    print("MADAGASCAR LICENSE SYSTEM - ADMIN ENDPOINTS TEST")
    print("=" * 80)
    print(f"Base URL: {BASE_URL}")
    print(f"Test Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if server is running
    if not test_health_check():
        print("\nERROR: Server is not responding. Please start the server first.")
        print("Run: python -m uvicorn app.main:app --reload")
        return
    
    print("\nChoose test option:")
    print("1. Test individual endpoints")
    print("2. Test complete database reset")
    print("3. Test all (individual + reset)")
    print("4. Exit")
    
    try:
        choice = input("\nEnter choice (1-4): ").strip()
        
        if choice == "1":
            test_individual_endpoints()
        elif choice == "2":
            test_complete_reset()
        elif choice == "3":
            print("Testing individual endpoints first...")
            test_individual_endpoints()
            print("\nNow testing complete reset...")
            test_complete_reset()
        elif choice == "4":
            print("Exiting...")
            return
        else:
            print("Invalid choice. Exiting...")
            return
            
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    except Exception as e:
        print(f"Test error: {e}")
    
    print(f"\nTest completed at: {time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main() 