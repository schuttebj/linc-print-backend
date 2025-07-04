#!/usr/bin/env python3
"""
Migration to add new application types to the ApplicationType enum
Adds: CONVERSION, PROFESSIONAL_LICENSE, FOREIGN_CONVERSION
"""

import asyncio
import asyncpg
from app.core.config import get_settings

async def add_new_application_types():
    """Add new application types to the database enum"""
    settings = get_settings()
    
    # Connect to database
    conn = await asyncpg.connect(
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database=settings.POSTGRES_DB,
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT
    )
    
    try:
        print("🔄 Adding new application types to database...")
        
        # Add new enum values
        new_types = [
            'CONVERSION',
            'PROFESSIONAL_LICENSE', 
            'FOREIGN_CONVERSION'
        ]
        
        for app_type in new_types:
            try:
                # Check if the enum value already exists
                result = await conn.fetchval(
                    """
                    SELECT 1 FROM pg_enum 
                    WHERE enumlabel = $1 
                    AND enumtypid = (
                        SELECT oid FROM pg_type WHERE typname = 'applicationtype'
                    )
                    """,
                    app_type
                )
                
                if not result:
                    # Add the new enum value
                    await conn.execute(
                        f"ALTER TYPE applicationtype ADD VALUE '{app_type}'"
                    )
                    print(f"✅ Added application type: {app_type}")
                else:
                    print(f"⚠️ Application type already exists: {app_type}")
                    
            except Exception as e:
                print(f"❌ Error adding {app_type}: {e}")
                
        print("✅ Application types migration completed!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(add_new_application_types()) 