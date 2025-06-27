"""
Database Migration: Add operational_schedule column to locations table
This migration adds structured operational schedule support while maintaining backward compatibility
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def get_database_url():
    """Get database URL from environment variables"""
    # Try to get from environment or use default for development
    return os.getenv('DATABASE_URL', 'postgresql://user:password@localhost/database')

def run_migration():
    """Run the migration to add operational_schedule column"""
    
    database_url = get_database_url()
    engine = create_engine(database_url)
    
    try:
        with engine.connect() as connection:
            # Check if column already exists
            result = connection.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'locations' 
                AND column_name = 'operational_schedule'
            """))
            
            if result.fetchone():
                print("✅ Column 'operational_schedule' already exists in 'locations' table")
                return True
            
            # Add the new column
            connection.execute(text("""
                ALTER TABLE locations 
                ADD COLUMN operational_schedule TEXT
            """))
            
            # Update the comment
            connection.execute(text("""
                COMMENT ON COLUMN locations.operational_schedule IS 'Structured operational schedule (JSON array of day schedules)'
            """))
            
            # Commit the transaction
            connection.commit()
            
            print("✅ Successfully added 'operational_schedule' column to 'locations' table")
            return True
            
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔄 Running database migration: Add operational_schedule column...")
    success = run_migration()
    sys.exit(0 if success else 1) 