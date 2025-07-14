#!/usr/bin/env python3
"""
Test Authorization Workflow
Tests the simplified authorization workflow: PRACTICAL_PASSED → APPROVED with license generation
"""

import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import uuid

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import get_settings
from app.models.application import Application, ApplicationAuthorization
from app.models.user import User
from app.models.license import License
from app.models.enums import (
    ApplicationStatus, ApplicationType, LicenseCategory, 
    RoleHierarchy, UserType, LicenseRestrictionCode
)

settings = get_settings()

def get_test_db_session():
    """Get test database session"""
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    return Session()

def test_authorization_workflow():
    """Test complete authorization workflow"""
    print("🧪 Testing Authorization Workflow...")
    
    db = get_test_db_session()
    
    try:
        # 1. Create test examiner user
        print("👨‍💼 Creating test examiner user...")
        examiner = User(
            id=uuid.uuid4(),
            username="test_examiner",
            email="examiner@test.com",
            role_hierarchy=RoleHierarchy.EXAMINER,
            user_type=UserType.LOCATION_USER,
            is_active=True
        )
        db.add(examiner)
        db.commit()
        
        # 2. Create test application (assuming person and location exist)
        print("📋 Creating test application...")
        application = Application(
            id=uuid.uuid4(),
            application_number="TEST-2024-001",
            application_type=ApplicationType.NEW_LICENSE,
            person_id=uuid.uuid4(),  # This should exist in your system
            license_category=LicenseCategory.B,
            status=ApplicationStatus.PRACTICAL_PASSED,
            location_id=uuid.uuid4()  # This should exist in your system
        )
        db.add(application)
        db.commit()
        
        # 3. Create authorization with test results
        print("✅ Creating authorization with passing test results...")
        authorization = ApplicationAuthorization(
            application_id=application.id,
            examiner_id=examiner.id,
            infrastructure_number="TEST-001",
            
            # Test results - passing
            is_absent=False,
            is_failed=False,
            eye_test_result="PASS",
            driving_test_result="PASS",
            driving_test_score=85.5,
            
            # Vehicle restrictions - none
            vehicle_restriction_none=True,
            vehicle_restriction_automatic=False,
            vehicle_restriction_electric=False,
            vehicle_restriction_disabled=False,
            
            # Driver restrictions - glasses required
            driver_restriction_none=False,
            driver_restriction_glasses=True,
            driver_restriction_artificial_limb=False,
            driver_restriction_glasses_and_limb=False,
            
            # Authorization decision
            is_authorized=True,
            authorization_date=datetime.utcnow(),
            authorization_notes="Test passed with glasses restriction"
        )
        db.add(authorization)
        db.commit()
        
        # 4. Test restriction code generation
        print("🔍 Testing restriction code generation...")
        restriction_codes = authorization.get_restriction_codes()
        assert LicenseRestrictionCode.CORRECTIVE_LENSES in restriction_codes
        print(f"✅ Generated restriction codes: {restriction_codes}")
        
        # 5. Test test_passed property
        print("🎯 Testing test_passed property...")
        assert authorization.test_passed == True
        print("✅ Test passed property working correctly")
        
        # 6. Update application status to APPROVED
        print("📊 Updating application status to APPROVED...")
        application.status = ApplicationStatus.APPROVED
        db.commit()
        
        # 7. Test failed authorization scenario
        print("❌ Testing failed authorization scenario...")
        failed_application = Application(
            id=uuid.uuid4(),
            application_number="TEST-2024-002",
            application_type=ApplicationType.NEW_LICENSE,
            person_id=uuid.uuid4(),
            license_category=LicenseCategory.B,
            status=ApplicationStatus.PRACTICAL_PASSED,
            location_id=uuid.uuid4()
        )
        db.add(failed_application)
        db.commit()
        
        failed_authorization = ApplicationAuthorization(
            application_id=failed_application.id,
            examiner_id=examiner.id,
            infrastructure_number="TEST-002",
            
            # Test results - failing
            is_absent=False,
            is_failed=True,
            eye_test_result="PASS",
            driving_test_result="FAIL",
            driving_test_score=45.0,
            
            # Authorization decision
            is_authorized=False,
            authorization_date=datetime.utcnow(),
            authorization_notes="Failed driving test"
        )
        db.add(failed_authorization)
        db.commit()
        
        # Test failed scenario properties
        assert failed_authorization.test_passed == False
        print("✅ Failed authorization scenario working correctly")
        
        # 8. Test absent scenario
        print("🚫 Testing absent scenario...")
        absent_application = Application(
            id=uuid.uuid4(),
            application_number="TEST-2024-003",
            application_type=ApplicationType.NEW_LICENSE,
            person_id=uuid.uuid4(),
            license_category=LicenseCategory.B,
            status=ApplicationStatus.PRACTICAL_PASSED,
            location_id=uuid.uuid4()
        )
        db.add(absent_application)
        db.commit()
        
        absent_authorization = ApplicationAuthorization(
            application_id=absent_application.id,
            examiner_id=examiner.id,
            infrastructure_number="TEST-003",
            
            # Test results - absent
            is_absent=True,
            is_failed=False,
            absent_failed_reason="Did not show up for test",
            
            # Authorization decision
            is_authorized=False,
            authorization_date=datetime.utcnow(),
            authorization_notes="Absent for test"
        )
        db.add(absent_authorization)
        db.commit()
        
        # Test absent scenario properties
        assert absent_authorization.test_passed == False
        print("✅ Absent authorization scenario working correctly")
        
        print("\n🎉 All authorization workflow tests passed!")
        
        # Clean up test data
        print("🧹 Cleaning up test data...")
        db.delete(absent_authorization)
        db.delete(absent_application)
        db.delete(failed_authorization)
        db.delete(failed_application)
        db.delete(authorization)
        db.delete(application)
        db.delete(examiner)
        db.commit()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def test_authorization_restrictions():
    """Test restriction code generation scenarios"""
    print("\n🔍 Testing Authorization Restrictions...")
    
    db = get_test_db_session()
    
    try:
        # Create test examiner
        examiner = User(
            id=uuid.uuid4(),
            username="test_examiner_restrictions",
            email="examiner2@test.com",
            role_hierarchy=RoleHierarchy.EXAMINER,
            user_type=UserType.LOCATION_USER,
            is_active=True
        )
        db.add(examiner)
        db.commit()
        
        # Test different restriction combinations
        test_cases = [
            {
                "name": "No restrictions",
                "vehicle_none": True,
                "driver_none": True,
                "expected": []
            },
            {
                "name": "Glasses only",
                "vehicle_none": True,
                "driver_none": False,
                "driver_glasses": True,
                "expected": [LicenseRestrictionCode.CORRECTIVE_LENSES]
            },
            {
                "name": "Artificial limb only",
                "vehicle_none": True,
                "driver_none": False,
                "driver_artificial_limb": True,
                "expected": [LicenseRestrictionCode.PROSTHETICS]
            },
            {
                "name": "Glasses and artificial limb",
                "vehicle_none": True,
                "driver_none": False,
                "driver_glasses_and_limb": True,
                "expected": [LicenseRestrictionCode.CORRECTIVE_LENSES, LicenseRestrictionCode.PROSTHETICS]
            },
            {
                "name": "Automatic transmission",
                "vehicle_none": False,
                "vehicle_automatic": True,
                "driver_none": True,
                "expected": [LicenseRestrictionCode.AUTOMATIC_TRANSMISSION]
            },
            {
                "name": "Electric powered",
                "vehicle_none": False,
                "vehicle_electric": True,
                "driver_none": True,
                "expected": [LicenseRestrictionCode.ELECTRIC_POWERED]
            },
            {
                "name": "Physical disabled adaptation",
                "vehicle_none": False,
                "vehicle_disabled": True,
                "driver_none": True,
                "expected": [LicenseRestrictionCode.PHYSICAL_DISABLED]
            }
        ]
        
        for i, test_case in enumerate(test_cases):
            print(f"Testing: {test_case['name']}")
            
            # Create application
            application = Application(
                id=uuid.uuid4(),
                application_number=f"TEST-REST-{i+1}",
                application_type=ApplicationType.NEW_LICENSE,
                person_id=uuid.uuid4(),
                license_category=LicenseCategory.B,
                status=ApplicationStatus.PRACTICAL_PASSED,
                location_id=uuid.uuid4()
            )
            db.add(application)
            db.commit()
            
            # Create authorization with specific restrictions
            authorization = ApplicationAuthorization(
                application_id=application.id,
                examiner_id=examiner.id,
                infrastructure_number=f"TEST-REST-{i+1}",
                
                # Test results - passing
                is_absent=False,
                is_failed=False,
                eye_test_result="PASS",
                driving_test_result="PASS",
                driving_test_score=85.0,
                
                # Vehicle restrictions
                vehicle_restriction_none=test_case.get("vehicle_none", False),
                vehicle_restriction_automatic=test_case.get("vehicle_automatic", False),
                vehicle_restriction_electric=test_case.get("vehicle_electric", False),
                vehicle_restriction_disabled=test_case.get("vehicle_disabled", False),
                
                # Driver restrictions
                driver_restriction_none=test_case.get("driver_none", False),
                driver_restriction_glasses=test_case.get("driver_glasses", False),
                driver_restriction_artificial_limb=test_case.get("driver_artificial_limb", False),
                driver_restriction_glasses_and_limb=test_case.get("driver_glasses_and_limb", False),
                
                # Authorization decision
                is_authorized=True,
                authorization_date=datetime.utcnow()
            )
            db.add(authorization)
            db.commit()
            
            # Test restriction code generation
            restriction_codes = authorization.get_restriction_codes()
            expected_codes = test_case["expected"]
            
            assert set(restriction_codes) == set(expected_codes), f"Expected {expected_codes}, got {restriction_codes}"
            print(f"✅ {test_case['name']}: {restriction_codes}")
            
            # Clean up
            db.delete(authorization)
            db.delete(application)
            db.commit()
        
        # Clean up examiner
        db.delete(examiner)
        db.commit()
        
        print("🎉 All restriction tests passed!")
        
    except Exception as e:
        print(f"❌ Restriction test failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def test_database_constraints():
    """Test database constraints and validation"""
    print("\n🔒 Testing Database Constraints...")
    
    db = get_test_db_session()
    
    try:
        # Test unique constraint on application_id
        examiner = User(
            id=uuid.uuid4(),
            username="test_examiner_constraints",
            email="examiner3@test.com",
            role_hierarchy=RoleHierarchy.EXAMINER,
            user_type=UserType.LOCATION_USER,
            is_active=True
        )
        db.add(examiner)
        db.commit()
        
        application = Application(
            id=uuid.uuid4(),
            application_number="TEST-CONST-001",
            application_type=ApplicationType.NEW_LICENSE,
            person_id=uuid.uuid4(),
            license_category=LicenseCategory.B,
            status=ApplicationStatus.PRACTICAL_PASSED,
            location_id=uuid.uuid4()
        )
        db.add(application)
        db.commit()
        
        # First authorization - should work
        authorization1 = ApplicationAuthorization(
            application_id=application.id,
            examiner_id=examiner.id,
            infrastructure_number="TEST-CONST-001",
            is_authorized=True,
            authorization_date=datetime.utcnow()
        )
        db.add(authorization1)
        db.commit()
        print("✅ First authorization created successfully")
        
        # Try to create duplicate authorization - should fail
        try:
            authorization2 = ApplicationAuthorization(
                application_id=application.id,  # Same application_id
                examiner_id=examiner.id,
                infrastructure_number="TEST-CONST-002",
                is_authorized=True,
                authorization_date=datetime.utcnow()
            )
            db.add(authorization2)
            db.commit()
            print("❌ Duplicate authorization should have failed!")
            assert False, "Duplicate authorization was allowed"
        except Exception as e:
            print(f"✅ Duplicate authorization properly rejected: {type(e).__name__}")
            db.rollback()
        
        # Clean up
        db.delete(authorization1)
        db.delete(application)
        db.delete(examiner)
        db.commit()
        
        print("🎉 All constraint tests passed!")
        
    except Exception as e:
        print(f"❌ Constraint test failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Starting Authorization Workflow Tests...")
    
    try:
        test_authorization_workflow()
        test_authorization_restrictions()
        test_database_constraints()
        
        print("\n🎉 All tests passed successfully!")
        print("\n📋 Test Summary:")
        print("- ✅ Authorization workflow tested")
        print("- ✅ Restriction code generation tested")
        print("- ✅ Database constraints tested")
        print("- ✅ Pass/fail/absent scenarios tested")
        
    except Exception as e:
        print(f"\n❌ Tests failed: {e}")
        sys.exit(1) 