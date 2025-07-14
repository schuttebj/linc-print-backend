#!/usr/bin/env python3
"""
Migration: Add Authorization System
- Add ApplicationAuthorization table for test results and examiner authorization
- Add Examiner role to role hierarchy
- Add authorization permissions
- Update application status workflow
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Add the project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import get_settings
from app.models.enums import RoleHierarchy

settings = get_settings()

def get_db_engine():
    """Get database engine"""
    return create_engine(settings.database_url)

def run_migration():
    """Run the authorization system migration"""
    engine = get_db_engine()
    
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        
        try:
            print("🚀 Starting Authorization System Migration...")
            
            # 1. Create ApplicationAuthorization table
            print("📋 Creating ApplicationAuthorization table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS application_authorizations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    application_id UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
                    examiner_id UUID NOT NULL REFERENCES users(id),
                    infrastructure_number VARCHAR(50),
                    examiner_signature_path VARCHAR(500),
                    
                    -- Test attendance and basic result
                    is_absent BOOLEAN NOT NULL DEFAULT FALSE,
                    is_failed BOOLEAN NOT NULL DEFAULT FALSE,
                    absent_failed_reason TEXT,
                    
                    -- Eye test results
                    eye_test_result VARCHAR(20),
                    eye_test_notes TEXT,
                    
                    -- Driving test results
                    driving_test_result VARCHAR(20),
                    driving_test_score DECIMAL(5,2),
                    driving_test_notes TEXT,
                    
                    -- Vehicle restrictions
                    vehicle_restriction_none BOOLEAN NOT NULL DEFAULT TRUE,
                    vehicle_restriction_automatic BOOLEAN NOT NULL DEFAULT FALSE,
                    vehicle_restriction_electric BOOLEAN NOT NULL DEFAULT FALSE,
                    vehicle_restriction_disabled BOOLEAN NOT NULL DEFAULT FALSE,
                    
                    -- Driver restrictions
                    driver_restriction_none BOOLEAN NOT NULL DEFAULT TRUE,
                    driver_restriction_glasses BOOLEAN NOT NULL DEFAULT FALSE,
                    driver_restriction_artificial_limb BOOLEAN NOT NULL DEFAULT FALSE,
                    driver_restriction_glasses_and_limb BOOLEAN NOT NULL DEFAULT FALSE,
                    
                    -- Applied restrictions
                    applied_restrictions JSONB,
                    
                    -- Authorization decision
                    is_authorized BOOLEAN NOT NULL DEFAULT FALSE,
                    authorization_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    authorization_notes TEXT,
                    
                    -- License generation tracking
                    license_generated BOOLEAN NOT NULL DEFAULT FALSE,
                    license_id UUID REFERENCES licenses(id),
                    license_generated_at TIMESTAMP WITH TIME ZONE,
                    
                    -- Quality assurance
                    reviewed_by UUID REFERENCES users(id),
                    reviewed_at TIMESTAMP WITH TIME ZONE,
                    review_notes TEXT,
                    
                    -- Standard fields
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    
                    -- Constraints
                    UNIQUE(application_id),
                    
                    -- Comments
                    CONSTRAINT application_authorizations_application_id_fkey FOREIGN KEY (application_id) REFERENCES applications(id) ON DELETE CASCADE,
                    CONSTRAINT application_authorizations_examiner_id_fkey FOREIGN KEY (examiner_id) REFERENCES users(id),
                    CONSTRAINT application_authorizations_license_id_fkey FOREIGN KEY (license_id) REFERENCES licenses(id),
                    CONSTRAINT application_authorizations_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES users(id)
                );
                
                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_application_authorizations_application_id ON application_authorizations(application_id);
                CREATE INDEX IF NOT EXISTS idx_application_authorizations_examiner_id ON application_authorizations(examiner_id);
                CREATE INDEX IF NOT EXISTS idx_application_authorizations_authorization_date ON application_authorizations(authorization_date);
                CREATE INDEX IF NOT EXISTS idx_application_authorizations_is_authorized ON application_authorizations(is_authorized);
                
                -- Comments
                COMMENT ON TABLE application_authorizations IS 'Authorization records for applications including test results and examiner decisions';
                COMMENT ON COLUMN application_authorizations.application_id IS 'Application ID (one authorization per application)';
                COMMENT ON COLUMN application_authorizations.examiner_id IS 'Examiner user ID';
                COMMENT ON COLUMN application_authorizations.infrastructure_number IS 'Infrastructure number and name';
                COMMENT ON COLUMN application_authorizations.examiner_signature_path IS 'Path to examiner signature file';
                COMMENT ON COLUMN application_authorizations.is_absent IS 'Applicant was absent for test';
                COMMENT ON COLUMN application_authorizations.is_failed IS 'Applicant failed the test';
                COMMENT ON COLUMN application_authorizations.absent_failed_reason IS 'Reason for absence or failure';
                COMMENT ON COLUMN application_authorizations.eye_test_result IS 'Eye test result: PASS/FAIL';
                COMMENT ON COLUMN application_authorizations.eye_test_notes IS 'Additional eye test notes';
                COMMENT ON COLUMN application_authorizations.driving_test_result IS 'Driving test result: PASS/FAIL';
                COMMENT ON COLUMN application_authorizations.driving_test_score IS 'Driving test score (percentage)';
                COMMENT ON COLUMN application_authorizations.driving_test_notes IS 'Driving test examiner notes';
                COMMENT ON COLUMN application_authorizations.vehicle_restriction_none IS 'No vehicle restrictions';
                COMMENT ON COLUMN application_authorizations.vehicle_restriction_automatic IS 'Automatic transmission only';
                COMMENT ON COLUMN application_authorizations.vehicle_restriction_electric IS 'Electric powered vehicles only';
                COMMENT ON COLUMN application_authorizations.vehicle_restriction_disabled IS 'Adapted for physically disabled person';
                COMMENT ON COLUMN application_authorizations.driver_restriction_none IS 'No driver restrictions';
                COMMENT ON COLUMN application_authorizations.driver_restriction_glasses IS 'Glasses or contact lenses required';
                COMMENT ON COLUMN application_authorizations.driver_restriction_artificial_limb IS 'Has artificial limb';
                COMMENT ON COLUMN application_authorizations.driver_restriction_glasses_and_limb IS 'Glasses and artificial limb';
                COMMENT ON COLUMN application_authorizations.applied_restrictions IS 'JSON array of applied LicenseRestrictionCode values';
                COMMENT ON COLUMN application_authorizations.is_authorized IS 'Application authorized for license generation';
                COMMENT ON COLUMN application_authorizations.authorization_date IS 'Date of authorization';
                COMMENT ON COLUMN application_authorizations.authorization_notes IS 'Examiner authorization notes';
                COMMENT ON COLUMN application_authorizations.license_generated IS 'License generated from this authorization';
                COMMENT ON COLUMN application_authorizations.license_id IS 'Generated license ID';
                COMMENT ON COLUMN application_authorizations.license_generated_at IS 'Date license was generated';
                COMMENT ON COLUMN application_authorizations.reviewed_by IS 'Supervisor who reviewed authorization';
                COMMENT ON COLUMN application_authorizations.reviewed_at IS 'Date authorization was reviewed';
                COMMENT ON COLUMN application_authorizations.review_notes IS 'Review notes';
            """))
            
            # 2. Simplified workflow - no new statuses needed
            print("📊 Simplified workflow - PRACTICAL_PASSED flows directly to APPROVED...")
            # No new statuses needed - applications move from PRACTICAL_PASSED directly to APPROVED
            
            # 3. Add Examiner role to role hierarchy
            print("👨‍💼 Adding Examiner role to role hierarchy...")
            conn.execute(text("""
                -- Add EXAMINER role to enum if it doesn't exist
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'EXAMINER' AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'rolehierarchy')) THEN
                        ALTER TYPE rolehierarchy ADD VALUE 'EXAMINER' AFTER 'OFFICE_SUPERVISOR';
                    END IF;
                END$$;
            """))
            
            # 4. Add authorization permissions
            print("🔐 Adding authorization permissions...")
            conn.execute(text("""
                -- Add applications.authorize permission
                INSERT INTO permissions (
                    permission_key, 
                    name, 
                    description, 
                    resource_type, 
                    action, 
                    is_system_permission,
                    created_at,
                    updated_at
                ) VALUES (
                    'applications.authorize',
                    'Authorize Applications',
                    'Authorize applications after test completion',
                    'applications',
                    'authorize',
                    true,
                    NOW(),
                    NOW()
                ) ON CONFLICT (permission_key) DO NOTHING;
                
                -- Add applications.review_authorization permission
                INSERT INTO permissions (
                    permission_key, 
                    name, 
                    description, 
                    resource_type, 
                    action, 
                    is_system_permission,
                    created_at,
                    updated_at
                ) VALUES (
                    'applications.review_authorization',
                    'Review Authorization',
                    'Review and approve authorization decisions',
                    'applications',
                    'review_authorization',
                    true,
                    NOW(),
                    NOW()
                ) ON CONFLICT (permission_key) DO NOTHING;
            """))
            
            # 5. Create default role permissions for Examiner
            print("👥 Creating default role permissions for Examiner...")
            conn.execute(text("""
                -- Get role permissions for EXAMINER role
                INSERT INTO role_permissions (role_hierarchy, permission_key, is_granted, created_at, updated_at)
                SELECT 
                    'EXAMINER',
                    permission_key,
                    true,
                    NOW(),
                    NOW()
                FROM permissions
                WHERE permission_key IN (
                    'applications.read',
                    'applications.update',
                    'applications.authorize',
                    'applications.review_authorization',
                    'licenses.read',
                    'licenses.create',
                    'persons.read',
                    'locations.read'
                )
                ON CONFLICT (role_hierarchy, permission_key) DO NOTHING;
            """))
            
            # 6. Add trigger for updated_at timestamp
            print("⚡ Adding trigger for updated_at timestamp...")
            conn.execute(text("""
                CREATE OR REPLACE FUNCTION update_application_authorizations_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql;
                
                DROP TRIGGER IF EXISTS trigger_update_application_authorizations_updated_at ON application_authorizations;
                CREATE TRIGGER trigger_update_application_authorizations_updated_at
                    BEFORE UPDATE ON application_authorizations
                    FOR EACH ROW
                    EXECUTE FUNCTION update_application_authorizations_updated_at();
            """))
            
            # 7. Simplified workflow - no trigger needed
            print("🔄 Simplified workflow - examiners approve applications directly from PRACTICAL_PASSED...")
            # No trigger needed - applications remain in PRACTICAL_PASSED until examiner approves
            
            # 8. Add data validation constraints
            print("✅ Adding data validation constraints...")
            conn.execute(text("""
                -- Add constraint to ensure test results are valid
                ALTER TABLE application_authorizations 
                ADD CONSTRAINT chk_eye_test_result 
                CHECK (eye_test_result IN ('PASS', 'FAIL') OR eye_test_result IS NULL);
                
                ALTER TABLE application_authorizations 
                ADD CONSTRAINT chk_driving_test_result 
                CHECK (driving_test_result IN ('PASS', 'FAIL') OR driving_test_result IS NULL);
                
                -- Add constraint to ensure driving test score is between 0 and 100
                ALTER TABLE application_authorizations 
                ADD CONSTRAINT chk_driving_test_score 
                CHECK (driving_test_score >= 0 AND driving_test_score <= 100);
                
                -- Add constraint to ensure only one of vehicle restriction flags is true
                ALTER TABLE application_authorizations 
                ADD CONSTRAINT chk_vehicle_restrictions 
                CHECK (
                    (vehicle_restriction_none::int + vehicle_restriction_automatic::int + 
                     vehicle_restriction_electric::int + vehicle_restriction_disabled::int) <= 1
                );
                
                -- Add constraint to ensure only one of driver restriction flags is true
                ALTER TABLE application_authorizations 
                ADD CONSTRAINT chk_driver_restrictions 
                CHECK (
                    (driver_restriction_none::int + driver_restriction_glasses::int + 
                     driver_restriction_artificial_limb::int + driver_restriction_glasses_and_limb::int) <= 1
                );
            """))
            
            # Commit transaction
            trans.commit()
            
            print("✅ Authorization System Migration completed successfully!")
            print("\n📋 Summary:")
            print("- ✅ ApplicationAuthorization table created")
            print("- ✅ Simplified workflow - PRACTICAL_PASSED → APPROVED")
            print("- ✅ Examiner role added to role hierarchy")
            print("- ✅ Authorization permissions added")
            print("- ✅ Role permissions configured for Examiner")
            print("- ✅ Database constraints added")
            print("\n🎉 The system is now ready for simplified authorization workflow!")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            trans.rollback()
            raise
            
        finally:
            conn.close()

if __name__ == "__main__":
    run_migration() 