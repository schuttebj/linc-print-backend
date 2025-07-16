#!/usr/bin/env python3
"""
Migration to add expiry_date column to licenses table
and update existing learner's permits with proper expiry dates (6 months from issue date)
"""

import os
import sys
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, DateTime, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import UUID

# Add the app directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import get_settings
from app.models.license import License
from app.models.enums import LicenseCategory

def run_migration():
    """Run the license expiry date migration"""
    settings = get_settings()
    
    # Create database connection
    engine = create_engine(settings.get_database_url())
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    print("Starting license expiry date migration...")
    
    with engine.connect() as connection:
        # 1. Add expiry_date column to licenses table
        print("Adding expiry_date column to licenses table...")
        try:
            connection.execute(text("""
                ALTER TABLE licenses 
                ADD COLUMN IF NOT EXISTS expiry_date TIMESTAMP WITH TIME ZONE;
            """))
            connection.commit()
            print("✅ Successfully added expiry_date column")
        except Exception as e:
            print(f"❌ Error adding expiry_date column: {e}")
            return False
    
    # 2. Update existing learner's permits with expiry dates
    print("Updating existing learner's permits with expiry dates...")
    
    db = SessionLocal()
    try:
        # Get all learner's permits (categories '1', '2', '3')
        learners_permits = db.query(License).filter(
            License.category.in_([
                LicenseCategory.LEARNERS_1,
                LicenseCategory.LEARNERS_2, 
                LicenseCategory.LEARNERS_3
            ])
        ).all()
        
        updated_count = 0
        for permit in learners_permits:
            if permit.expiry_date is None:  # Only update if not already set
                # Set expiry to 6 months (180 days) from issue date
                permit.expiry_date = permit.issue_date + timedelta(days=180)
                updated_count += 1
        
        db.commit()
        print(f"✅ Successfully updated {updated_count} learner's permits with expiry dates")
        
        # Show some statistics
        total_permits = len(learners_permits)
        print(f"📊 Total learner's permits found: {total_permits}")
        print(f"📊 Permits updated: {updated_count}")
        print(f"📊 Permits already had expiry dates: {total_permits - updated_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating learner's permits: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def verify_migration():
    """Verify the migration was successful"""
    settings = get_settings()
    engine = create_engine(settings.get_database_url())
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    print("\nVerifying migration...")
    
    db = SessionLocal()
    try:
        # Check if expiry_date column exists
        result = db.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'licenses' AND column_name = 'expiry_date';
        """))
        
        if result.fetchone():
            print("✅ expiry_date column exists")
        else:
            print("❌ expiry_date column missing")
            return False
        
        # Check learner's permits with expiry dates
        learners_with_expiry = db.query(License).filter(
            License.category.in_([
                LicenseCategory.LEARNERS_1,
                LicenseCategory.LEARNERS_2,
                LicenseCategory.LEARNERS_3
            ]),
            License.expiry_date.is_not(None)
        ).count()
        
        total_learners = db.query(License).filter(
            License.category.in_([
                LicenseCategory.LEARNERS_1,
                LicenseCategory.LEARNERS_2,
                LicenseCategory.LEARNERS_3
            ])
        ).count()
        
        print(f"📊 Learner's permits with expiry dates: {learners_with_expiry}/{total_learners}")
        
        # Show some examples
        examples = db.query(License).filter(
            License.category.in_([
                LicenseCategory.LEARNERS_1,
                LicenseCategory.LEARNERS_2,
                LicenseCategory.LEARNERS_3
            ]),
            License.expiry_date.is_not(None)
        ).limit(3).all()
        
        if examples:
            print("\n📝 Example learner's permits:")
            for permit in examples:
                print(f"   • Category {permit.category.value}: Issue {permit.issue_date.strftime('%Y-%m-%d')} → Expires {permit.expiry_date.strftime('%Y-%m-%d')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verifying migration: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 License Expiry Date Migration")
    print("=" * 50)
    
    # Run migration
    if run_migration():
        print("\n✅ Migration completed successfully!")
        
        # Verify migration
        if verify_migration():
            print("\n🎉 Migration verification passed!")
        else:
            print("\n⚠️ Migration verification failed!")
            sys.exit(1)
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)
    
    print("\n📋 Summary:")
    print("• Added expiry_date column to licenses table")
    print("• Updated existing learner's permits with 6-month expiry dates")
    print("• Learner's permits now properly expire 6 months after issue date")
    print("• Regular licenses remain valid indefinitely (no expiry date)") 