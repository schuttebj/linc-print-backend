#!/usr/bin/env python3
"""
Madagascar License System Test Script
Tests basic functionality of the user management system
"""

import sys
import os
import asyncio
import httpx
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

async def test_api_endpoints():
    """Test the API endpoints"""
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        print("🧪 Testing Madagascar License System API")
        print("=" * 50)
        
        # Test health endpoint
        print("1. Testing health endpoint...")
        try:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                health_data = response.json()
                print(f"   ✓ Health check passed: {health_data['status']}")
            else:
                print(f"   ❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ Could not connect to server: {e}")
            print("   Make sure the server is running with: python -m uvicorn app.main:app --reload")
            return False
        
        # Test login with admin credentials
        print("\n2. Testing admin login...")
        login_data = {
            "username": "admin",
            "password": "MadagascarAdmin2024!"
        }
        
        try:
            response = await client.post(f"{base_url}/api/v1/auth/login", json=login_data)
            if response.status_code == 200:
                auth_data = response.json()
                access_token = auth_data["access_token"]
                user_data = auth_data["user"]
                print(f"   ✓ Admin login successful")
                print(f"   ✓ User: {user_data['username']} ({user_data['full_name']})")
                print(f"   ✓ Roles: {[role['name'] for role in user_data['roles']]}")
            else:
                print(f"   ❌ Admin login failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print(f"   ❌ Login request failed: {e}")
            return False
        
        # Set up authorization header
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Test user list endpoint
        print("\n3. Testing user list endpoint...")
        try:
            response = await client.get(f"{base_url}/api/v1/users/", headers=headers)
            if response.status_code == 200:
                users_data = response.json()
                print(f"   ✓ Found {users_data['total']} users")
                for user in users_data['users']:
                    print(f"   - {user['username']}: {user['full_name']} ({user['status']})")
            else:
                print(f"   ❌ User list failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ User list request failed: {e}")
            return False
        
        # Test roles endpoint
        print("\n4. Testing roles endpoint...")
        try:
            response = await client.get(f"{base_url}/api/v1/roles/", headers=headers)
            if response.status_code == 200:
                roles_data = response.json()
                print(f"   ✓ Found {len(roles_data)} roles")
                for role in roles_data:
                    print(f"   - {role['name']}: {role['display_name']}")
            else:
                print(f"   ❌ Roles list failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ Roles request failed: {e}")
            return False
        
        # Test permissions endpoint
        print("\n5. Testing permissions endpoint...")
        try:
            response = await client.get(f"{base_url}/api/v1/permissions/by-category", headers=headers)
            if response.status_code == 200:
                permissions_data = response.json()
                print(f"   ✓ Found {len(permissions_data)} permission categories")
                for category, perms in permissions_data.items():
                    print(f"   - {category}: {len(perms)} permissions")
            else:
                print(f"   ❌ Permissions list failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ Permissions request failed: {e}")
            return False
        
        # Test current user endpoint
        print("\n6. Testing current user endpoint...")
        try:
            response = await client.get(f"{base_url}/api/v1/auth/me", headers=headers)
            if response.status_code == 200:
                user_data = response.json()
                print(f"   ✓ Current user: {user_data['username']}")
                print(f"   ✓ Madagascar ID: {user_data['madagascar_id_number']}")
                print(f"   ✓ Timezone: {user_data['timezone']}")
                print(f"   ✓ Currency: {user_data['currency']}")
            else:
                print(f"   ❌ Current user failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ Current user request failed: {e}")
            return False
        
        # Test clerk login
        print("\n7. Testing clerk login...")
        clerk_login_data = {
            "username": "clerk1",
            "password": "Clerk123!"
        }
        
        try:
            response = await client.post(f"{base_url}/api/v1/auth/login", json=clerk_login_data)
            if response.status_code == 200:
                clerk_auth_data = response.json()
                clerk_user = clerk_auth_data["user"]
                print(f"   ✓ Clerk login successful: {clerk_user['username']}")
                print(f"   ✓ Clerk roles: {[role['name'] for role in clerk_user['roles']]}")
            else:
                print(f"   ❌ Clerk login failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ Clerk login request failed: {e}")
            return False
        
        print("\n" + "=" * 50)
        print("✅ All tests passed! Madagascar License System is working correctly.")
        print("\nSystem Summary:")
        print("- Backend API: Running and responsive")
        print("- Database: Connected and initialized")
        print("- Authentication: Working with JWT tokens")
        print("- User Management: Complete with role-based access")
        print("- Madagascar Features: CIN/CNI support, localization")
        print("\nNext steps:")
        print("1. Deploy to production (Render.com)")
        print("2. Build frontend (React/TypeScript)")
        print("3. Implement additional modules (Persons, Applications, etc.)")
        
        return True

def test_database_connection():
    """Test database connection"""
    print("🗄️ Testing database connection...")
    
    try:
        from app.core.database import SessionLocal
        from app.models.user import User
        
        db = SessionLocal()
        try:
            # Simple query to test connection
            user_count = db.query(User).count()
            print(f"   ✓ Database connected, found {user_count} users")
            return True
        finally:
            db.close()
            
    except Exception as e:
        print(f"   ❌ Database connection failed: {e}")
        print("   Make sure to run: python init_madagascar_system.py")
        return False

def main():
    """Main test function"""
    print("🇲🇬 Testing Madagascar Driver's License System")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 50)
    
    # Test database connection first
    if not test_database_connection():
        sys.exit(1)
    
    # Test API endpoints
    try:
        success = asyncio.run(test_api_endpoints())
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 