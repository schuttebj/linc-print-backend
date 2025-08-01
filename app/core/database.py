"""
Database Configuration for Madagascar License System
Compatible with SQLAlchemy 1.4 for Render.com deployment
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os

from app.core.config import get_settings

settings = get_settings()

# Create database engine with Render-optimized settings
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=5,  # Reduced for Render free tier
    max_overflow=10,  # Reduced for Render free tier  
    pool_timeout=30,
    pool_pre_ping=True,  # Verify connections before use
    echo=settings.DEBUG,  # Log SQL queries in debug mode
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Metadata for schema creation
metadata = MetaData()


def get_db():
    """
    Database dependency for FastAPI
    Provides a database session that automatically closes after request
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_database_connection():
    """Test database connection and return status (useful for health checks)"""
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return True, "Database connection successful"
    except Exception as e:
        return False, f"Database connection failed: {str(e)}"


def create_tables():
    """Create all database tables with proper enum creation"""
    from app.models.base import Base
    from app.models.enums import LicenseCategory
    from app.models.transaction import FeeType
    from app.models.printing import PrintJobStatus, PrintJobPriority, QualityCheckResult
    from sqlalchemy import text
    
    # Import all models to ensure they're registered with Base.metadata
    from app.models import user, person, application, transaction, license, card, printing
    
    print("🔧 Creating database enums before tables...")
    
    with engine.connect() as conn:
        # Create LicenseCategory enum
        print("📋 Creating LicenseCategory enum...")
        try:
            conn.execute(text("DROP TYPE IF EXISTS licensecategory CASCADE"))
        except Exception:
            pass
        
        license_values = [category.value for category in LicenseCategory]
        license_values_str = "', '".join(license_values)
        conn.execute(text(f"CREATE TYPE licensecategory AS ENUM ('{license_values_str}')"))
        print(f"✅ Created licensecategory enum with {len(license_values)} values")
        
        # Create FeeType enum
        print("📋 Creating FeeType enum...")
        try:
            conn.execute(text("DROP TYPE IF EXISTS feetype CASCADE"))
        except Exception:
            pass
        
        fee_type_values = [fee_type.value for fee_type in FeeType]
        fee_values_str = "', '".join(fee_type_values)
        conn.execute(text(f"CREATE TYPE feetype AS ENUM ('{fee_values_str}')"))
        print(f"✅ Created feetype enum with {len(fee_type_values)} values")
        
        # Create PrintJobStatus enum
        print("📋 Creating PrintJobStatus enum...")
        try:
            conn.execute(text("DROP TYPE IF EXISTS printjobstatus CASCADE"))
        except Exception:
            pass
        
        print_status_values = [status.value for status in PrintJobStatus]
        status_values_str = "', '".join(print_status_values)
        conn.execute(text(f"CREATE TYPE printjobstatus AS ENUM ('{status_values_str}')"))
        print(f"✅ Created printjobstatus enum with {len(print_status_values)} values")
        
        # Create PrintJobPriority enum
        print("📋 Creating PrintJobPriority enum...")
        try:
            conn.execute(text("DROP TYPE IF EXISTS printjobpriority CASCADE"))
        except Exception:
            pass
        
        priority_values = [priority.value for priority in PrintJobPriority]
        priority_values_str = "', '".join(priority_values)
        conn.execute(text(f"CREATE TYPE printjobpriority AS ENUM ('{priority_values_str}')"))
        print(f"✅ Created printjobpriority enum with {len(priority_values)} values")
        
        # Create QualityCheckResult enum
        print("📋 Creating QualityCheckResult enum...")
        try:
            conn.execute(text("DROP TYPE IF EXISTS qualitycheckresult CASCADE"))
        except Exception:
            pass
        
        qa_values = [result.value for result in QualityCheckResult]
        qa_values_str = "', '".join(qa_values)
        conn.execute(text(f"CREATE TYPE qualitycheckresult AS ENUM ('{qa_values_str}')"))
        print(f"✅ Created qualitycheckresult enum with {len(qa_values)} values")
        
        conn.commit()
    
    print("🔧 Creating all database tables...")
    print(f"📊 Found {len(Base.metadata.tables)} tables to create")
    Base.metadata.create_all(bind=engine)
    print("✅ All tables created successfully")


def drop_tables():
    """Drop all database tables (use with caution!)"""
    from app.models.base import Base
    from sqlalchemy import text
    
    # Import all models to ensure they're registered with Base.metadata
    from app.models import user, person, application, transaction, license, card, printing
    
    # First try the normal approach
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception as e:
        # If it fails due to foreign key constraints, use CASCADE
        print(f"Normal drop failed: {e}")
        print("Using CASCADE drop to handle foreign key constraints...")
        
        with engine.connect() as conn:
            # Get all table names
            result = conn.execute(text("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public'
                AND tablename NOT LIKE 'pg_%'
                AND tablename NOT LIKE 'information_schema%'
            """))
            
            tables = [row[0] for row in result.fetchall()]
            
            if tables:
                # Drop all tables with CASCADE
                tables_str = ", ".join(tables)
                conn.execute(text(f"DROP TABLE IF EXISTS {tables_str} CASCADE"))
                
                # Also drop any remaining sequences and types
                conn.execute(text("DROP TYPE IF EXISTS licensecategory CASCADE"))
                conn.execute(text("DROP TYPE IF EXISTS applicationstatus CASCADE"))
                conn.execute(text("DROP TYPE IF EXISTS userstatus CASCADE"))
                conn.execute(text("DROP TYPE IF EXISTS madagascaridtype CASCADE"))
                conn.execute(text("DROP TYPE IF EXISTS printjobstatus CASCADE"))
                conn.execute(text("DROP TYPE IF EXISTS printjobpriority CASCADE"))
                conn.execute(text("DROP TYPE IF EXISTS qualitycheckresult CASCADE"))
                
                conn.commit()
                print(f"Successfully dropped {len(tables)} tables with CASCADE") 