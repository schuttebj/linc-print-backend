#!/usr/bin/env python3
"""
Database Migration Script: License Capture Implementation
=========================================================

This script migrates the database to support the new license capture functionality:

1. Updates ApplicationType enum:
   - Removes CONVERSION 
   - Adds DRIVERS_LICENSE_CAPTURE and LEARNERS_PERMIT_CAPTURE

2. Adds license_capture column to applications table:
   - JSON column to store captured license data

3. Updates any existing CONVERSION applications to DRIVERS_LICENSE_CAPTURE

Author: AI Assistant
Date: 2024-12-19
"""

import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variables
os.environ['DATABASE_URL'] = os.environ.get('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/madagascar_license_system')

from sqlalchemy import create_engine, text, MetaData, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError, ProgrammingError
import logging
from datetime import datetime
import uuid

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'license_capture_migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")
    return database_url

def create_backup_table(engine):
    """Create backup of applications table before migration"""
    try:
        logger.info("Creating backup of applications table...")
        
        backup_table_name = f"applications_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        with engine.connect() as conn:
            # Create backup table
            conn.execute(text(f"""
                CREATE TABLE {backup_table_name} AS 
                SELECT * FROM applications;
            """))
            
            # Get record count
            result = conn.execute(text(f"SELECT COUNT(*) FROM {backup_table_name}"))
            record_count = result.scalar()
            
            conn.commit()
            
        logger.info(f"✅ Backup table '{backup_table_name}' created with {record_count} records")
        return backup_table_name
        
    except Exception as e:
        logger.error(f"❌ Failed to create backup: {e}")
        raise

def check_enum_exists(engine, enum_name):
    """Check if enum type exists in database"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_type 
                    WHERE typname = :enum_name
                )
            """), {"enum_name": enum_name})
            return result.scalar()
    except Exception as e:
        logger.error(f"Error checking enum existence: {e}")
        return False

def get_enum_values(engine, enum_name):
    """Get current values of an enum type"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid FROM pg_type WHERE typname = :enum_name
                )
                ORDER BY enumsortorder
            """), {"enum_name": enum_name})
            return [row[0] for row in result.fetchall()]
    except Exception as e:
        logger.error(f"Error getting enum values: {e}")
        return []

def update_application_type_enum(engine):
    """Update the ApplicationType enum"""
    try:
        logger.info("Updating ApplicationType enum...")
        
        # Check if enum exists
        if not check_enum_exists(engine, 'applicationtype'):
            logger.error("ApplicationType enum not found!")
            raise Exception("ApplicationType enum not found in database")
        
        # Get current values
        current_values = get_enum_values(engine, 'applicationtype')
        logger.info(f"Current ApplicationType values: {current_values}")
        
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            
            try:
                # Step 1: Add new enum values if they don't exist
                if 'DRIVERS_LICENSE_CAPTURE' not in current_values:
                    logger.info("Adding DRIVERS_LICENSE_CAPTURE to enum...")
                    conn.execute(text("ALTER TYPE applicationtype ADD VALUE 'DRIVERS_LICENSE_CAPTURE'"))
                
                if 'LEARNERS_PERMIT_CAPTURE' not in current_values:
                    logger.info("Adding LEARNERS_PERMIT_CAPTURE to enum...")
                    conn.execute(text("ALTER TYPE applicationtype ADD VALUE 'LEARNERS_PERMIT_CAPTURE'"))
                
                # Step 2: Update existing CONVERSION applications to DRIVERS_LICENSE_CAPTURE
                if 'CONVERSION' in current_values:
                    logger.info("Updating existing CONVERSION applications to DRIVERS_LICENSE_CAPTURE...")
                    result = conn.execute(text("""
                        UPDATE applications 
                        SET application_type = 'DRIVERS_LICENSE_CAPTURE' 
                        WHERE application_type = 'CONVERSION'
                    """))
                    updated_count = result.rowcount
                    logger.info(f"Updated {updated_count} applications from CONVERSION to DRIVERS_LICENSE_CAPTURE")
                
                # Step 3: Remove CONVERSION value (this is tricky in PostgreSQL)
                # We can't directly remove enum values in PostgreSQL < 12
                # For safety, we'll leave it but document that it should not be used
                if 'CONVERSION' in current_values:
                    logger.info("Note: CONVERSION enum value left in database for safety (PostgreSQL limitation)")
                    logger.info("All existing CONVERSION applications have been migrated to DRIVERS_LICENSE_CAPTURE")
                
                # Commit transaction
                trans.commit()
                logger.info("✅ ApplicationType enum updated successfully")
                
            except Exception as e:
                trans.rollback()
                raise e
                
    except Exception as e:
        logger.error(f"❌ Failed to update ApplicationType enum: {e}")
        raise

def add_license_capture_column(engine):
    """Add license_capture column to applications table"""
    try:
        logger.info("Adding license_capture column to applications table...")
        
        # Check if column already exists
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('applications')]
        
        if 'license_capture' in columns:
            logger.info("license_capture column already exists, skipping...")
            return
        
        with engine.connect() as conn:
            # Add license_capture column
            conn.execute(text("""
                ALTER TABLE applications 
                ADD COLUMN license_capture JSON NULL
            """))
            
            # Add comment to column
            conn.execute(text("""
                COMMENT ON COLUMN applications.license_capture IS 
                'Captured existing license data for capture applications'
            """))
            
            conn.commit()
        
        logger.info("✅ license_capture column added successfully")
        
    except Exception as e:
        logger.error(f"❌ Failed to add license_capture column: {e}")
        raise

def verify_migration(engine):
    """Verify that the migration was successful"""
    try:
        logger.info("Verifying migration...")
        
        with engine.connect() as conn:
            # Check enum values
            result = conn.execute(text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid FROM pg_type WHERE typname = 'applicationtype'
                )
                ORDER BY enumsortorder
            """))
            enum_values = [row[0] for row in result.fetchall()]
            logger.info(f"ApplicationType enum values: {enum_values}")
            
            # Check that new values exist
            required_values = ['DRIVERS_LICENSE_CAPTURE', 'LEARNERS_PERMIT_CAPTURE']
            for value in required_values:
                if value not in enum_values:
                    raise Exception(f"Missing required enum value: {value}")
            
            # Check license_capture column exists
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('applications')]
            
            if 'license_capture' not in columns:
                raise Exception("license_capture column not found")
            
            # Check that no CONVERSION applications remain
            result = conn.execute(text("""
                SELECT COUNT(*) FROM applications 
                WHERE application_type = 'CONVERSION'
            """))
            conversion_count = result.scalar()
            
            if conversion_count > 0:
                logger.warning(f"Warning: {conversion_count} applications still have CONVERSION type")
            else:
                logger.info("✅ No CONVERSION applications remaining")
            
            # Check new application types can be used
            result = conn.execute(text("""
                SELECT COUNT(*) FROM applications 
                WHERE application_type IN ('DRIVERS_LICENSE_CAPTURE', 'LEARNERS_PERMIT_CAPTURE')
            """))
            capture_count = result.scalar()
            logger.info(f"Found {capture_count} capture-type applications")
        
        logger.info("✅ Migration verification completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration verification failed: {e}")
        return False

def create_sample_capture_application(engine):
    """Create a sample capture application to test the new functionality"""
    try:
        logger.info("Creating sample capture application...")
        
        with engine.connect() as conn:
            # First, check if we have any persons to use
            result = conn.execute(text("SELECT id FROM persons LIMIT 1"))
            person_row = result.fetchone()
            
            if not person_row:
                logger.info("No persons found, skipping sample application creation")
                return
            
            person_id = person_row[0]
            
            # Check if we have any locations
            result = conn.execute(text("SELECT id FROM locations LIMIT 1"))
            location_row = result.fetchone()
            
            if not location_row:
                logger.info("No locations found, skipping sample application creation")
                return
            
            location_id = location_row[0]
            
            # Generate application number
            app_number = f"CAPT{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Sample license capture data
            sample_capture_data = {
                "captured_licenses": [
                    {
                        "id": "sample-license-1",
                        "license_number": "DL123456789",
                        "license_category": "B",
                        "issue_date": "2020-01-15",
                        "expiry_date": "2025-01-15",
                        "issuing_location": "Antananarivo Central Office",
                        "verified": True,
                        "verification_notes": "Physical license verified by clerk"
                    }
                ],
                "application_type": "DRIVERS_LICENSE_CAPTURE"
            }
            
            # Insert sample application
            conn.execute(text("""
                INSERT INTO applications (
                    id, application_number, application_type, person_id, 
                    location_id, license_category, status, 
                    application_date, license_capture,
                    medical_certificate_required, parental_consent_required, 
                    requires_existing_license, created_at
                ) VALUES (
                    :id, :application_number, :application_type, :person_id,
                    :location_id, :license_category, :status,
                    :application_date, :license_capture,
                    :medical_certificate_required, :parental_consent_required,
                    :requires_existing_license, :created_at
                )
            """), {
                "id": str(uuid.uuid4()),
                "application_number": app_number,
                "application_type": "DRIVERS_LICENSE_CAPTURE",
                "person_id": person_id,
                "location_id": location_id,
                "license_category": "B",
                "status": "COMPLETED",
                "application_date": datetime.now(),
                "license_capture": sample_capture_data,
                "medical_certificate_required": False,
                "parental_consent_required": False,
                "requires_existing_license": False,
                "created_at": datetime.now()
            })
            
            conn.commit()
            
        logger.info(f"✅ Sample capture application created: {app_number}")
        
    except Exception as e:
        logger.error(f"❌ Failed to create sample application: {e}")
        # Don't raise - this is optional

def main():
    """Main migration function"""
    logger.info("=" * 60)
    logger.info("LICENSE CAPTURE MIGRATION SCRIPT")
    logger.info("=" * 60)
    logger.info(f"Started at: {datetime.now()}")
    
    try:
        # Get database connection
        database_url = get_database_url()
        logger.info(f"Connecting to database...")
        
        engine = create_engine(database_url)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            db_version = result.scalar()
            logger.info(f"Connected to: {db_version}")
        
        # Create backup
        backup_table = create_backup_table(engine)
        
        # Run migration steps
        logger.info("\n" + "=" * 40)
        logger.info("STARTING MIGRATION")
        logger.info("=" * 40)
        
        # Step 1: Update ApplicationType enum
        update_application_type_enum(engine)
        
        # Step 2: Add license_capture column
        add_license_capture_column(engine)
        
        # Step 3: Verify migration
        logger.info("\n" + "=" * 40)
        logger.info("VERIFICATION")
        logger.info("=" * 40)
        
        if verify_migration(engine):
            logger.info("✅ Migration completed successfully!")
            
            # Create sample application
            create_sample_capture_application(engine)
            
            logger.info("\n" + "=" * 60)
            logger.info("MIGRATION SUMMARY")
            logger.info("=" * 60)
            logger.info("✅ ApplicationType enum updated")
            logger.info("✅ license_capture column added")
            logger.info("✅ Existing CONVERSION applications migrated")
            logger.info(f"✅ Backup table created: {backup_table}")
            logger.info("\n🎉 License capture functionality is now ready!")
            
        else:
            logger.error("❌ Migration verification failed!")
            return 1
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return 1
    
    finally:
        logger.info(f"\nCompleted at: {datetime.now()}")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 