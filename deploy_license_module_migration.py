#!/usr/bin/env python3
"""
Database Migration Script: License Module Implementation for Madagascar License System

This script creates the complete license management infrastructure:

1. License Management Tables:
   - licenses: Core license data with generated license numbers
   - license_cards: Physical cards with expiry dates
   - license_status_history: Status change audit trail
   - license_sequence_counter: Global sequence counter

2. License Number Generation:
   - Format: {ProvinceCode}{LocationNumber}{8SequentialDigits}{CheckDigit}
   - Example: T01000001231 (T01 + 00000123 + 1)
   - Uses Luhn algorithm for check digit validation

3. Features:
   - ISO 18013 and SADC compliance fields
   - Card production and collection tracking
   - Professional driving permit support
   - License restrictions and medical conditions
   - Complete audit trail

Dependencies: Requires Person, Application, User, and Location modules
"""

import os
import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine, text, MetaData, Table, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import uuid

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/madagascar_license_system')

def create_db_engine():
    """Create database engine with proper configuration"""
    try:
        engine = create_engine(
            DATABASE_URL,
            echo=False,  # Set to True for SQL debugging
            pool_pre_ping=True,
            pool_recycle=3600
        )
        return engine
    except Exception as e:
        logger.error(f"Failed to create database engine: {e}")
        raise


def check_dependencies(engine):
    """Check that required modules exist before creating license tables"""
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    
    required_tables = ['persons', 'applications', 'users', 'locations']
    missing_tables = [table for table in required_tables if table not in existing_tables]
    
    if missing_tables:
        logger.error(f"Missing required tables: {missing_tables}")
        logger.error("Please ensure Person, Application, User, and Location modules are deployed first")
        return False
    
    logger.info("✅ All required dependencies found")
    return True


def create_license_enums(engine):
    """Create license-specific enums"""
    logger.info("Creating license enums...")
    
    enums_sql = [
        # License Status Enum
        """
        DO $$ BEGIN
            CREATE TYPE licensestatus AS ENUM ('ACTIVE', 'SUSPENDED', 'CANCELLED');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """,
        
        # Card Status Enum
        """
        DO $$ BEGIN
            CREATE TYPE cardstatus AS ENUM (
                'PENDING_PRODUCTION', 'IN_PRODUCTION', 'READY_FOR_COLLECTION', 
                'COLLECTED', 'EXPIRED', 'DAMAGED', 'LOST', 'STOLEN'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
        """
    ]
    
    try:
        with engine.connect() as conn:
            for enum_sql in enums_sql:
                conn.execute(text(enum_sql))
                conn.commit()
        
        logger.info("✅ License enums created successfully")
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to create license enums: {e}")
        return False


def create_license_sequence_counter_table(engine):
    """Create the license sequence counter table"""
    logger.info("Creating license_sequence_counter table...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS license_sequence_counter (
        id INTEGER PRIMARY KEY DEFAULT 1,
        current_sequence INTEGER NOT NULL DEFAULT 0,
        last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_by UUID REFERENCES users(id),
        
        -- Ensure only one row exists
        CONSTRAINT single_counter_row CHECK (id = 1)
    );
    
    -- Insert initial record
    INSERT INTO license_sequence_counter (id, current_sequence, last_updated)
    VALUES (1, 0, NOW())
    ON CONFLICT (id) DO NOTHING;
    
    -- Add comments
    COMMENT ON TABLE license_sequence_counter IS 'Global sequence counter for license number generation';
    COMMENT ON COLUMN license_sequence_counter.current_sequence IS 'Current sequence number for license generation';
    COMMENT ON COLUMN license_sequence_counter.last_updated IS 'Timestamp of last sequence increment';
    """
    
    try:
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        
        logger.info("✅ license_sequence_counter table created successfully")
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to create license_sequence_counter table: {e}")
        return False


def create_licenses_table(engine):
    """Create the main licenses table"""
    logger.info("Creating licenses table...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS licenses (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        license_number VARCHAR(15) NOT NULL UNIQUE,
        
        -- Person and application links
        person_id UUID NOT NULL REFERENCES persons(id),
        created_from_application_id UUID REFERENCES applications(id),
        
        -- License details
        category licensecategory NOT NULL,
        status licensestatus NOT NULL DEFAULT 'ACTIVE',
        
        -- Issue information
        issue_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        issuing_location_id UUID NOT NULL REFERENCES locations(id),
        issued_by_user_id UUID NOT NULL REFERENCES users(id),
        
        -- Restrictions and conditions
        restrictions JSONB,
        medical_restrictions JSONB,
        
        -- Professional driving permit information
        has_professional_permit BOOLEAN NOT NULL DEFAULT FALSE,
        professional_permit_categories JSONB,
        professional_permit_expiry TIMESTAMP WITH TIME ZONE,
        
        -- Status management
        status_changed_date TIMESTAMP WITH TIME ZONE,
        status_changed_by UUID REFERENCES users(id),
        suspension_reason TEXT,
        suspension_start_date TIMESTAMP WITH TIME ZONE,
        suspension_end_date TIMESTAMP WITH TIME ZONE,
        cancellation_reason TEXT,
        cancellation_date TIMESTAMP WITH TIME ZONE,
        
        -- ISO 18013 compliance
        iso_compliance_data JSONB,
        barcode_data TEXT,
        security_features JSONB,
        
        -- SADC compliance
        sadc_compliance_verified BOOLEAN NOT NULL DEFAULT FALSE,
        international_validity BOOLEAN NOT NULL DEFAULT TRUE,
        vienna_convention_compliant BOOLEAN NOT NULL DEFAULT TRUE,
        
        -- Biometric links
        photo_file_path VARCHAR(500),
        signature_file_path VARCHAR(500),
        biometric_template_id VARCHAR(100),
        
        -- License history
        previous_license_id UUID REFERENCES licenses(id),
        is_upgrade BOOLEAN NOT NULL DEFAULT FALSE,
        upgrade_from_category licensecategory,
        
        -- External references
        legacy_license_number VARCHAR(20),
        captured_from_license_number VARCHAR(20),
        
        -- Audit fields
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    
    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_licenses_license_number ON licenses(license_number);
    CREATE INDEX IF NOT EXISTS idx_licenses_person_id ON licenses(person_id);
    CREATE INDEX IF NOT EXISTS idx_licenses_status ON licenses(status);
    CREATE INDEX IF NOT EXISTS idx_licenses_category ON licenses(category);
    CREATE INDEX IF NOT EXISTS idx_licenses_issue_date ON licenses(issue_date);
    CREATE INDEX IF NOT EXISTS idx_licenses_issuing_location ON licenses(issuing_location_id);
    
    -- Add comments
    COMMENT ON TABLE licenses IS 'Madagascar driver licenses with lifetime validity';
    COMMENT ON COLUMN licenses.license_number IS 'Generated license number with check digit';
    COMMENT ON COLUMN licenses.status IS 'License status: ACTIVE, SUSPENDED, CANCELLED';
    COMMENT ON COLUMN licenses.restrictions IS 'License restrictions (corrective lenses, etc.)';
    COMMENT ON COLUMN licenses.iso_compliance_data IS 'ISO 18013-1:2018 compliance data';
    COMMENT ON COLUMN licenses.barcode_data IS 'PDF417 barcode data for card';
    """
    
    try:
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        
        logger.info("✅ licenses table created successfully")
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to create licenses table: {e}")
        return False


def create_license_cards_table(engine):
    """Create the license cards table"""
    logger.info("Creating license_cards table...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS license_cards (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        card_number VARCHAR(20) NOT NULL UNIQUE,
        
        -- License relationship
        license_id UUID NOT NULL REFERENCES licenses(id) ON DELETE CASCADE,
        
        -- Card details
        status cardstatus NOT NULL DEFAULT 'PENDING_PRODUCTION',
        card_type VARCHAR(20) NOT NULL DEFAULT 'STANDARD',
        
        -- Validity dates
        issue_date TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        expiry_date TIMESTAMP WITH TIME ZONE NOT NULL,
        valid_from TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        
        -- Card production
        ordered_date TIMESTAMP WITH TIME ZONE,
        production_started TIMESTAMP WITH TIME ZONE,
        production_completed TIMESTAMP WITH TIME ZONE,
        ready_for_collection_date TIMESTAMP WITH TIME ZONE,
        collected_date TIMESTAMP WITH TIME ZONE,
        collected_by_user_id UUID REFERENCES users(id),
        
        -- Card specifications (ISO 18013 compliance)
        card_template VARCHAR(50) NOT NULL DEFAULT 'MADAGASCAR_STANDARD',
        iso_compliance_version VARCHAR(20) NOT NULL DEFAULT '18013-1:2018',
        security_level VARCHAR(20) NOT NULL DEFAULT 'STANDARD',
        
        -- Physical card data
        front_image_path VARCHAR(500),
        back_image_path VARCHAR(500),
        barcode_image_path VARCHAR(500),
        
        -- Production tracking
        production_batch_id VARCHAR(50),
        production_location_id UUID REFERENCES locations(id),
        quality_check_passed BOOLEAN,
        quality_check_date TIMESTAMP WITH TIME ZONE,
        quality_check_notes TEXT,
        
        -- Collection information
        collection_location_id UUID REFERENCES locations(id),
        collection_notice_sent BOOLEAN NOT NULL DEFAULT FALSE,
        collection_notice_date TIMESTAMP WITH TIME ZONE,
        collection_reference VARCHAR(50),
        
        -- Card status flags
        is_current BOOLEAN NOT NULL DEFAULT TRUE,
        is_expired BOOLEAN NOT NULL DEFAULT FALSE,
        replacement_requested BOOLEAN NOT NULL DEFAULT FALSE,
        replacement_reason VARCHAR(100),
        
        -- Audit fields
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    
    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_license_cards_card_number ON license_cards(card_number);
    CREATE INDEX IF NOT EXISTS idx_license_cards_license_id ON license_cards(license_id);
    CREATE INDEX IF NOT EXISTS idx_license_cards_status ON license_cards(status);
    CREATE INDEX IF NOT EXISTS idx_license_cards_is_current ON license_cards(is_current);
    CREATE INDEX IF NOT EXISTS idx_license_cards_expiry_date ON license_cards(expiry_date);
    CREATE INDEX IF NOT EXISTS idx_license_cards_collection_status ON license_cards(status) WHERE status = 'READY_FOR_COLLECTION';
    
    -- Add comments
    COMMENT ON TABLE license_cards IS 'Physical license cards with expiry dates';
    COMMENT ON COLUMN license_cards.card_number IS 'Physical card number';
    COMMENT ON COLUMN license_cards.expiry_date IS 'Card expiry date (5 years from issue)';
    COMMENT ON COLUMN license_cards.is_current IS 'Is this the current card for the license';
    """
    
    try:
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        
        logger.info("✅ license_cards table created successfully")
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to create license_cards table: {e}")
        return False


def create_license_status_history_table(engine):
    """Create the license status history table"""
    logger.info("Creating license_status_history table...")
    
    sql = """
    CREATE TABLE IF NOT EXISTS license_status_history (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        license_id UUID NOT NULL REFERENCES licenses(id) ON DELETE CASCADE,
        
        -- Status change details
        from_status licensestatus,
        to_status licensestatus NOT NULL,
        changed_by UUID NOT NULL REFERENCES users(id),
        changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        
        -- Change context
        reason VARCHAR(200),
        notes TEXT,
        system_initiated BOOLEAN NOT NULL DEFAULT FALSE,
        
        -- Suspension specific fields
        suspension_start_date TIMESTAMP WITH TIME ZONE,
        suspension_end_date TIMESTAMP WITH TIME ZONE
    );
    
    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_license_status_history_license_id ON license_status_history(license_id);
    CREATE INDEX IF NOT EXISTS idx_license_status_history_changed_at ON license_status_history(changed_at);
    CREATE INDEX IF NOT EXISTS idx_license_status_history_to_status ON license_status_history(to_status);
    
    -- Add comments
    COMMENT ON TABLE license_status_history IS 'Audit trail for license status changes';
    COMMENT ON COLUMN license_status_history.system_initiated IS 'Whether change was system-initiated';
    """
    
    try:
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        
        logger.info("✅ license_status_history table created successfully")
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to create license_status_history table: {e}")
        return False


def create_license_functions(engine):
    """Create utility functions for license management"""
    logger.info("Creating license utility functions...")
    
    sql = """
    -- Function to validate license number check digit
    CREATE OR REPLACE FUNCTION validate_license_number_check_digit(license_number TEXT)
    RETURNS BOOLEAN AS $$
    DECLARE
        base_number TEXT;
        check_digit INTEGER;
        calculated_check_digit INTEGER;
        digit_sum INTEGER := 0;
        digit_char CHAR;
        digit_value INTEGER;
        position_from_right INTEGER;
    BEGIN
        -- Check length
        IF LENGTH(license_number) != 12 THEN
            RETURN FALSE;
        END IF;
        
        -- Extract base number and check digit
        base_number := SUBSTRING(license_number FROM 1 FOR 11);
        check_digit := CAST(SUBSTRING(license_number FROM 12 FOR 1) AS INTEGER);
        
        -- Calculate using Luhn algorithm
        FOR i IN 1..LENGTH(base_number) LOOP
            digit_char := SUBSTRING(base_number FROM i FOR 1);
            digit_value := CAST(digit_char AS INTEGER);
            position_from_right := LENGTH(base_number) - i + 1;
            
            -- Double every second digit from right to left
            IF position_from_right % 2 = 0 THEN
                digit_value := digit_value * 2;
                IF digit_value > 9 THEN
                    digit_value := (digit_value / 10) + (digit_value % 10);
                END IF;
            END IF;
            
            digit_sum := digit_sum + digit_value;
        END LOOP;
        
        -- Calculate check digit
        calculated_check_digit := (10 - (digit_sum % 10)) % 10;
        
        RETURN check_digit = calculated_check_digit;
    END;
    $$ LANGUAGE plpgsql;
    
    -- Function to get next license sequence atomically
    CREATE OR REPLACE FUNCTION get_next_license_sequence(user_id_param UUID DEFAULT NULL)
    RETURNS INTEGER AS $$
    DECLARE
        next_sequence INTEGER;
    BEGIN
        UPDATE license_sequence_counter 
        SET current_sequence = current_sequence + 1,
            last_updated = NOW(),
            updated_by = user_id_param
        WHERE id = 1
        RETURNING current_sequence INTO next_sequence;
        
        RETURN next_sequence;
    END;
    $$ LANGUAGE plpgsql;
    
    -- Function to generate license number with check digit
    CREATE OR REPLACE FUNCTION generate_license_number(location_code_param TEXT, sequence_number_param INTEGER)
    RETURNS TEXT AS $$
    DECLARE
        province_code CHAR(1);
        location_number TEXT;
        sequence_str TEXT;
        base_number TEXT;
        check_digit INTEGER;
        digit_sum INTEGER := 0;
        digit_value INTEGER;
        position_from_right INTEGER;
    BEGIN
        -- Extract province code and location number
        province_code := SUBSTRING(location_code_param FROM 1 FOR 1);
        location_number := SUBSTRING(location_code_param FROM 2);
        
        -- Format sequence as 8 digits
        sequence_str := LPAD(sequence_number_param::TEXT, 8, '0');
        
        -- Combine base number
        base_number := province_code || location_number || sequence_str;
        
        -- Calculate check digit using Luhn algorithm
        FOR i IN 1..LENGTH(base_number) LOOP
            digit_value := CAST(SUBSTRING(base_number FROM i FOR 1) AS INTEGER);
            position_from_right := LENGTH(base_number) - i + 1;
            
            -- Double every second digit from right to left
            IF position_from_right % 2 = 0 THEN
                digit_value := digit_value * 2;
                IF digit_value > 9 THEN
                    digit_value := (digit_value / 10) + (digit_value % 10);
                END IF;
            END IF;
            
            digit_sum := digit_sum + digit_value;
        END LOOP;
        
        check_digit := (10 - (digit_sum % 10)) % 10;
        
        RETURN base_number || check_digit::TEXT;
    END;
    $$ LANGUAGE plpgsql;
    
    COMMENT ON FUNCTION validate_license_number_check_digit(TEXT) IS 'Validate license number check digit using Luhn algorithm';
    COMMENT ON FUNCTION get_next_license_sequence(UUID) IS 'Get next license sequence number atomically';
    COMMENT ON FUNCTION generate_license_number(TEXT, INTEGER) IS 'Generate license number with check digit';
    """
    
    try:
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        
        logger.info("✅ License utility functions created successfully")
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to create license functions: {e}")
        return False


def create_sample_data(engine):
    """Create sample license data for testing"""
    logger.info("Creating sample license data...")
    
    sql = """
    -- Sample data will be created when first license is issued through the application
    -- This ensures proper integration with the application workflow
    """
    
    try:
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        
        logger.info("✅ Sample data preparation completed")
        return True
    
    except Exception as e:
        logger.error(f"❌ Failed to create sample data: {e}")
        return False


def verify_migration(engine):
    """Verify that the migration was successful"""
    logger.info("Verifying license module migration...")
    
    try:
        with engine.connect() as conn:
            # Check all tables exist
            tables_to_check = [
                'license_sequence_counter',
                'licenses',
                'license_cards', 
                'license_status_history'
            ]
            
            for table in tables_to_check:
                result = conn.execute(text(f"SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '{table}'"))
                if result.scalar() == 0:
                    raise Exception(f"Table {table} not found")
            
            # Check enums exist
            enums_to_check = ['licensestatus', 'cardstatus']
            for enum_name in enums_to_check:
                result = conn.execute(text(f"SELECT COUNT(*) FROM pg_type WHERE typname = '{enum_name}'"))
                if result.scalar() == 0:
                    raise Exception(f"Enum {enum_name} not found")
            
            # Check functions exist
            functions_to_check = [
                'validate_license_number_check_digit',
                'get_next_license_sequence',
                'generate_license_number'
            ]
            for func_name in functions_to_check:
                result = conn.execute(text(f"SELECT COUNT(*) FROM pg_proc WHERE proname = '{func_name}'"))
                if result.scalar() == 0:
                    raise Exception(f"Function {func_name} not found")
            
            # Check sequence counter is initialized
            result = conn.execute(text("SELECT current_sequence FROM license_sequence_counter WHERE id = 1"))
            sequence_value = result.scalar()
            if sequence_value is None:
                raise Exception("License sequence counter not initialized")
            
            # Test license number generation function
            test_result = conn.execute(text("SELECT generate_license_number('T01', 123)"))
            test_license_number = test_result.scalar()
            if not test_license_number or len(test_license_number) != 12:
                raise Exception("License number generation function not working properly")
            
            # Test validation function
            validation_result = conn.execute(text(f"SELECT validate_license_number_check_digit('{test_license_number}')"))
            if not validation_result.scalar():
                raise Exception("License number validation function not working properly")
        
        logger.info("✅ License module migration verification completed successfully")
        return True
    
    except Exception as e:
        logger.error(f"❌ Migration verification failed: {e}")
        return False


def main():
    """Main migration function"""
    logger.info("🚀 STARTING MADAGASCAR LICENSE MODULE MIGRATION")
    logger.info("=" * 80)
    
    try:
        # Create database engine
        engine = create_db_engine()
        logger.info("✅ Database connection established")
        
        # Check dependencies
        if not check_dependencies(engine):
            logger.error("❌ Dependencies check failed")
            return False
        
        # Migration steps
        migration_steps = [
            ("Create license enums", create_license_enums),
            ("Create license sequence counter table", create_license_sequence_counter_table),
            ("Create licenses table", create_licenses_table),
            ("Create license cards table", create_license_cards_table),
            ("Create license status history table", create_license_status_history_table),
            ("Create license utility functions", create_license_functions),
            ("Create sample data", create_sample_data),
            ("Verify migration", verify_migration)
        ]
        
        for step_name, step_function in migration_steps:
            logger.info(f"\n📋 {step_name}...")
            if not step_function(engine):
                logger.error(f"❌ Failed: {step_name}")
                return False
        
        logger.info("\n" + "=" * 80)
        logger.info("🎉 MADAGASCAR LICENSE MODULE MIGRATION COMPLETED SUCCESSFULLY!")
        logger.info("\n📊 Migration Summary:")
        logger.info("✅ License sequence counter initialized")
        logger.info("✅ License tables created with ISO/SADC compliance")
        logger.info("✅ Card management system implemented")
        logger.info("✅ License number generation with check digit validation")
        logger.info("✅ Professional driving permit support")
        logger.info("✅ Complete audit trail and history tracking")
        logger.info("\n🚀 License module is ready for use!")
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Migration failed with error: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 