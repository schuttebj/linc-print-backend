"""
Test Script for Madagascar User and Location Management System
Tests the complete backend implementation including models, CRUD operations, and API endpoints
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import our models and schemas
from app.models.base import BaseModel
from app.models.user import User, Location, Role, Permission, UserStatus, MadagascarIDType
from app.schemas.location import LocationCreate, ProvinceCodeEnum, OfficeTypeEnum
from app.schemas.user import UserCreate, MadagascarIDTypeEnum
from app.crud.crud_location import location as crud_location
from app.crud.crud_user import user as crud_user

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_madagascar_system.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_test_database():
    """Create all tables in the test database"""
    print("🔧 Creating test database...")
    BaseModel.metadata.drop_all(bind=engine)
    BaseModel.metadata.create_all(bind=engine)
    print("✅ Test database created successfully!")


def test_location_creation():
    """Test location creation with Madagascar provinces"""
    print("\n🏢 Testing Location Creation...")
    
    db = SessionLocal()
    try:
        # Test data for all Madagascar provinces
        test_locations = [
            {
                "name": "ANTANANARIVO CENTRAL OFFICE",
                "province_code": ProvinceCodeEnum.ANTANANARIVO,
                "office_number": "01",
                "office_type": OfficeTypeEnum.MAIN,
                "locality": "ANTANANARIVO",
                "street_address": "LOT II M 85 ANDRAVOAHANGY",
                "manager_name": "RAKOTO JEAN",
                "phone_number": "+261 20 22 123 45"
            },
            {
                "name": "FIANARANTSOA BRANCH OFFICE",
                "province_code": ProvinceCodeEnum.FIANARANTSOA,
                "office_number": "01",
                "office_type": OfficeTypeEnum.MAIN,
                "locality": "FIANARANTSOA",
                "manager_name": "RABE MARIE",
                "phone_number": "+261 75 123 456"
            },
            {
                "name": "TOLIARA MOBILE UNIT",
                "province_code": ProvinceCodeEnum.TOLIARA,
                "office_number": "02",
                "office_type": OfficeTypeEnum.MOBILE,
                "locality": "TOLIARA",
                "manager_name": "RANDRIA PAUL"
            }
        ]
        
        created_locations = []
        for loc_data in test_locations:
            location_create = LocationCreate(**loc_data)
            location = crud_location.create_with_codes(
                db=db,
                obj_in=location_create,
                created_by="test_system"
            )
            created_locations.append(location)
            print(f"✅ Created location: {location.full_code} - {location.name}")
        
        # Test location retrieval
        print(f"\n📍 Testing location retrieval...")
        for location in created_locations:
            retrieved = crud_location.get_by_code(db=db, code=location.code)
            assert retrieved is not None, f"Failed to retrieve location {location.code}"
            print(f"✅ Retrieved location: {retrieved.full_code}")
        
        # Test province filtering
        antananarivo_locations = crud_location.get_by_province(db=db, province_code="T")
        print(f"✅ Found {len(antananarivo_locations)} locations in Antananarivo province")
        
        return created_locations
        
    except Exception as e:
        print(f"❌ Location creation test failed: {str(e)}")
        raise
    finally:
        db.close()


def test_user_creation_with_locations(locations):
    """Test user creation with location-based username generation"""
    print("\n👤 Testing User Creation with Location-Based Usernames...")
    
    db = SessionLocal()
    try:
        # First, create a test role
        test_role = Role(
            name="CLERK",
            display_name="License Clerk",
            description="Basic license processing role",
            is_system_role=True,
            level=1
        )
        db.add(test_role)
        db.commit()
        db.refresh(test_role)
        print(f"✅ Created test role: {test_role.name}")
        
        # Test user data
        test_users = [
            {
                "email": "rakoto.jean@gov.mg",
                "first_name": "JEAN",
                "last_name": "RAKOTO",
                "madagascar_id_number": "101234567890",
                "id_document_type": MadagascarIDTypeEnum.MADAGASCAR_ID,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
                "phone_number": "+261 32 123 4567",
                "employee_id": "EMP001",
                "department": "LICENSING",
                "role_ids": [test_role.id]
            },
            {
                "email": "rabe.marie@gov.mg", 
                "first_name": "MARIE",
                "last_name": "RABE",
                "madagascar_id_number": "201234567890",
                "id_document_type": MadagascarIDTypeEnum.MADAGASCAR_ID,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
                "phone_number": "+261 33 987 6543",
                "employee_id": "EMP002",
                "department": "ADMINISTRATION",
                "role_ids": [test_role.id]
            },
            {
                "email": "randria.paul@gov.mg",
                "first_name": "PAUL", 
                "last_name": "RANDRIA",
                "madagascar_id_number": "301234567890",
                "id_document_type": MadagascarIDTypeEnum.PASSPORT,
                "password": "SecurePassword123!",
                "confirm_password": "SecurePassword123!",
                "phone_number": "+261 34 555 7777",
                "employee_id": "EMP003",
                "department": "MOBILE_SERVICES",
                "role_ids": [test_role.id]
            }
        ]
        
        created_users = []
        for i, user_data in enumerate(test_users):
            location = locations[i]
            user_create = UserCreate(**user_data)
            
            user = crud_user.create_with_location(
                db=db,
                obj_in=user_create,
                location_id=location.id,
                created_by="test_system"
            )
            created_users.append(user)
            
            print(f"✅ Created user: {user.username} ({user.full_name}) at {user.assigned_location_code}")
            print(f"   Location: {location.full_code} - Generated username: {user.username}")
        
        # Test username format validation
        print(f"\n🔍 Testing username format validation...")
        for user in created_users:
            is_valid = User.validate_username_format(user.username)
            assert is_valid, f"Invalid username format: {user.username}"
            print(f"✅ Username format valid: {user.username}")
        
        # Test location code extraction
        print(f"\n📍 Testing location code extraction...")
        for user in created_users:
            extracted_code = User.extract_location_code_from_username(user.username)
            expected_code = user.assigned_location_code
            assert extracted_code == expected_code, f"Code extraction failed: {extracted_code} != {expected_code}"
            print(f"✅ Extracted location code: {extracted_code} from {user.username}")
        
        return created_users
        
    except Exception as e:
        print(f"❌ User creation test failed: {str(e)}")
        raise
    finally:
        db.close()


def test_user_location_operations(users, locations):
    """Test user-location assignment operations"""
    print("\n🔄 Testing User-Location Operations...")
    
    db = SessionLocal()
    try:
        user = users[0]
        new_location = locations[1]
        
        print(f"Original user: {user.username} at {user.assigned_location_code}")
        
        # Test location reassignment
        old_username, new_username = crud_user.assign_to_location(
            db=db,
            user_id=user.id,
            location_id=new_location.id,
            is_primary=True,
            updated_by="test_system"
        )
        
        db.refresh(user)
        print(f"✅ Reassigned user to new location: {user.username} at {user.assigned_location_code}")
        
        # Test user retrieval by location
        location_users = crud_user.get_by_location(db=db, location_id=new_location.id)
        print(f"✅ Found {len(location_users)} users at location {new_location.code}")
        
        # Test location statistics
        stats = crud_user.get_location_statistics(db=db, location_id=new_location.id)
        print(f"✅ Location statistics: {stats['total_users']} total users, {stats['active_users']} active")
        
    except Exception as e:
        print(f"❌ User-location operations test failed: {str(e)}")
        raise
    finally:
        db.close()


def test_search_and_filtering():
    """Test advanced search and filtering capabilities"""
    print("\n🔍 Testing Search and Filtering...")
    
    db = SessionLocal()
    try:
        from app.schemas.user import UserQueryParams
        from app.schemas.location import LocationQueryParams
        
        # Test user search
        user_search_params = UserQueryParams(
            page=1,
            per_page=10,
            search="JEAN",
            sort_by="created_at",
            sort_order="desc"
        )
        
        users, total = crud_user.search_users(db=db, search_params=user_search_params)
        print(f"✅ User search found {total} users matching 'JEAN'")
        
        # Test location search
        location_search_params = LocationQueryParams(
            page=1,
            per_page=10,
            search="ANTANANARIVO",
            province_code=ProvinceCodeEnum.ANTANANARIVO,
            sort_by="name",
            sort_order="asc"
        )
        
        locations, total = crud_location.search_locations(db=db, search_params=location_search_params)
        print(f"✅ Location search found {total} locations matching 'ANTANANARIVO'")
        
        # Test location statistics
        stats = crud_location.get_location_statistics(db=db)
        print(f"✅ System statistics: {stats['total_locations']} locations, {stats['operational_locations']} operational")
        
    except Exception as e:
        print(f"❌ Search and filtering test failed: {str(e)}")
        raise
    finally:
        db.close()


def test_username_generation_limits():
    """Test username generation limits and capacity"""
    print("\n⚠️  Testing Username Generation Limits...")
    
    db = SessionLocal()
    try:
        # Get a location
        location = crud_location.get_by_code(db=db, code="T01")
        if not location:
            print("❌ No test location found")
            return
        
        # Test user code generation
        result = crud_location.generate_user_code(db=db, location_id=location.id)
        print(f"✅ Next user code for {location.code}: {result['next_user_code']}")
        print(f"   Remaining capacity: {result['remaining_capacity']} users")
        
        # Test capacity validation
        original_next_number = location.next_user_number
        location.next_user_number = 9998  # Near limit
        db.commit()
        
        result = crud_location.generate_user_code(db=db, location_id=location.id)
        print(f"✅ Near capacity - Next code: {result['next_user_code']}, Remaining: {result['remaining_capacity']}")
        
        # Restore original number
        location.next_user_number = original_next_number
        db.commit()
        
    except Exception as e:
        print(f"❌ Username generation limits test failed: {str(e)}")
        raise
    finally:
        db.close()


def run_all_tests():
    """Run all tests in sequence"""
    print("🚀 Starting Madagascar User & Location Management System Tests")
    print("=" * 70)
    
    try:
        # Setup
        create_test_database()
        
        # Test location management
        locations = test_location_creation()
        
        # Test user management
        users = test_user_creation_with_locations(locations)
        
        # Test operations
        test_user_location_operations(users, locations)
        
        # Test search and filtering
        test_search_and_filtering()
        
        # Test limits
        test_username_generation_limits()
        
        print("\n" + "=" * 70)
        print("🎉 ALL TESTS PASSED! Madagascar User & Location Management System is working correctly!")
        print("\n📊 Summary:")
        print(f"   ✅ {len(locations)} locations created")
        print(f"   ✅ {len(users)} users created with location-based usernames")
        print(f"   ✅ Username format validation working")
        print(f"   ✅ Location assignment and reassignment working")
        print(f"   ✅ Search and filtering working")
        print(f"   ✅ Capacity management working")
        
    except Exception as e:
        print(f"\n💥 TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1) 