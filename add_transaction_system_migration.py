"""
Database Migration: Add Transaction System
Adds transaction, transaction_items, card_orders, and fee_structures tables
Removes application_fees table and related fee logic from applications
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import get_settings
from app.models.transaction import DEFAULT_FEE_STRUCTURE, FeeType
from app.models.user import User
import uuid

def run_migration():
    """Run the transaction system migration"""
    settings = get_settings()
    
    # Create database engine
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    with SessionLocal() as db:
        print("🔄 Starting transaction system migration...")
        
        try:
            # 1. Create new transaction tables
            print("📋 Creating transaction system tables...")
            
            # Drop tables if they exist (for clean migration)
            db.execute(text("""
                DROP TABLE IF EXISTS transaction_items CASCADE;
                DROP TABLE IF EXISTS transactions CASCADE;
                DROP TABLE IF EXISTS card_orders CASCADE;
                DROP TABLE IF EXISTS fee_structures CASCADE;
            """))
            
            # Create FeeType enum first
            print("📋 Creating FeeType enum...")
            
            # Drop existing enum if it exists
            db.execute(text("DROP TYPE IF EXISTS feetype CASCADE"))
            
            # Create FeeType enum with all values
            fee_type_values = [
                'THEORY_TEST_LIGHT', 'THEORY_TEST_HEAVY',
                'PRACTICAL_TEST_LIGHT', 'PRACTICAL_TEST_HEAVY', 
                'APPLICATION_PROCESSING',
                'CARD_PRODUCTION', 'CARD_URGENT', 'CARD_EMERGENCY',
                'TEMPORARY_LICENSE_NORMAL', 'TEMPORARY_LICENSE_URGENT', 'TEMPORARY_LICENSE_EMERGENCY',
                'INTERNATIONAL_PERMIT', 'PROFESSIONAL_PERMIT', 'MEDICAL_CERTIFICATE'
            ]
            values_str = "', '".join(fee_type_values)
            create_enum_sql = f"CREATE TYPE feetype AS ENUM ('{values_str}')"
            db.execute(text(create_enum_sql))
            print(f"✅ Created FeeType enum with {len(fee_type_values)} values")
            
            # Create fee_structures table
            db.execute(text("""
                CREATE TABLE fee_structures (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    fee_type feetype NOT NULL UNIQUE,
                    display_name VARCHAR(100) NOT NULL,
                    description TEXT,
                    amount NUMERIC(10, 2) NOT NULL,
                    currency VARCHAR(3) NOT NULL DEFAULT 'MGA',
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    effective_from TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    effective_until TIMESTAMP,
                    created_by UUID NOT NULL REFERENCES users(id),
                    last_updated_by UUID REFERENCES users(id),
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                );
                
                COMMENT ON TABLE fee_structures IS 'Configurable fee structure for all transaction types';
                COMMENT ON COLUMN fee_structures.fee_type IS 'Type of fee';
                COMMENT ON COLUMN fee_structures.display_name IS 'Human-readable fee name';
                COMMENT ON COLUMN fee_structures.description IS 'Fee description';
                COMMENT ON COLUMN fee_structures.amount IS 'Fee amount in Ariary (Ar)';
                COMMENT ON COLUMN fee_structures.currency IS 'Currency code';
                COMMENT ON COLUMN fee_structures.is_active IS 'Whether fee is currently active';
                COMMENT ON COLUMN fee_structures.effective_from IS 'When fee becomes effective';
                COMMENT ON COLUMN fee_structures.effective_until IS 'When fee expires (null = indefinite)';
                COMMENT ON COLUMN fee_structures.created_by IS 'User who created this fee structure';
                COMMENT ON COLUMN fee_structures.last_updated_by IS 'User who last updated this fee';
            """))
            
            # Create transactions table
            db.execute(text("""
                CREATE TABLE transactions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    transaction_number VARCHAR(20) NOT NULL UNIQUE,
                    transaction_type VARCHAR(20) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                    person_id UUID NOT NULL REFERENCES persons(id),
                    location_id UUID NOT NULL REFERENCES locations(id),
                    total_amount NUMERIC(10, 2) NOT NULL,
                    payment_method VARCHAR(20),
                    payment_reference VARCHAR(100),
                    processed_by UUID NOT NULL REFERENCES users(id),
                    processed_at TIMESTAMP,
                    receipt_number VARCHAR(50),
                    receipt_printed BOOLEAN NOT NULL DEFAULT FALSE,
                    receipt_printed_at TIMESTAMP,
                    notes TEXT,
                    transaction_metadata JSONB,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                );
                
                COMMENT ON TABLE transactions IS 'Main transaction record for payment processing';
                COMMENT ON COLUMN transactions.transaction_number IS 'Unique transaction number';
                COMMENT ON COLUMN transactions.transaction_type IS 'Type of transaction';
                COMMENT ON COLUMN transactions.status IS 'Transaction status';
                COMMENT ON COLUMN transactions.person_id IS 'Person making payment';
                COMMENT ON COLUMN transactions.location_id IS 'Location where payment is made';
                COMMENT ON COLUMN transactions.total_amount IS 'Total transaction amount';
                COMMENT ON COLUMN transactions.payment_method IS 'Payment method used';
                COMMENT ON COLUMN transactions.payment_reference IS 'Payment reference number';
                COMMENT ON COLUMN transactions.processed_by IS 'User who processed payment';
                COMMENT ON COLUMN transactions.processed_at IS 'When payment was processed';
                COMMENT ON COLUMN transactions.receipt_number IS 'Official receipt number';
                COMMENT ON COLUMN transactions.receipt_printed IS 'Whether receipt was printed';
                COMMENT ON COLUMN transactions.receipt_printed_at IS 'When receipt was printed';
                COMMENT ON COLUMN transactions.notes IS 'Transaction notes';
                COMMENT ON COLUMN transactions.transaction_metadata IS 'Additional transaction metadata';
                
                CREATE INDEX idx_transactions_person_id ON transactions(person_id);
                CREATE INDEX idx_transactions_location_id ON transactions(location_id);
                CREATE INDEX idx_transactions_status ON transactions(status);
                CREATE INDEX idx_transactions_created_at ON transactions(created_at);
            """))
            
            # Create card_orders table
            db.execute(text("""
                CREATE TABLE card_orders (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    order_number VARCHAR(20) NOT NULL UNIQUE,
                    status VARCHAR(30) NOT NULL DEFAULT 'PENDING_PAYMENT',
                    application_id UUID NOT NULL REFERENCES applications(id),
                    person_id UUID NOT NULL REFERENCES persons(id),
                    card_type VARCHAR(50) NOT NULL,
                    urgency_level INTEGER NOT NULL DEFAULT 1,
                    fee_amount NUMERIC(10, 2) NOT NULL,
                    payment_required BOOLEAN NOT NULL DEFAULT TRUE,
                    ordered_by UUID NOT NULL REFERENCES users(id),
                    ordered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    payment_deadline TIMESTAMP,
                    production_started_at TIMESTAMP,
                    production_completed_at TIMESTAMP,
                    ready_for_collection_at TIMESTAMP,
                    collected_at TIMESTAMP,
                    collected_by UUID REFERENCES users(id),
                    card_data JSONB,
                    production_metadata JSONB,
                    order_notes TEXT,
                    collection_notes TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                );
                
                COMMENT ON TABLE card_orders IS 'Card order management with payment tracking';
                COMMENT ON COLUMN card_orders.order_number IS 'Unique card order number';
                COMMENT ON COLUMN card_orders.status IS 'Order status';
                COMMENT ON COLUMN card_orders.application_id IS 'Application for card';
                COMMENT ON COLUMN card_orders.person_id IS 'Person ordering card';
                COMMENT ON COLUMN card_orders.card_type IS 'Type of card (license, permit, etc.)';
                COMMENT ON COLUMN card_orders.urgency_level IS 'Urgency level (1=normal, 2=urgent, 3=emergency)';
                COMMENT ON COLUMN card_orders.fee_amount IS 'Card production fee';
                COMMENT ON COLUMN card_orders.payment_required IS 'Whether payment is required';
                COMMENT ON COLUMN card_orders.ordered_by IS 'User who created order';
                COMMENT ON COLUMN card_orders.ordered_at IS 'When order was created';
                
                CREATE INDEX idx_card_orders_application_id ON card_orders(application_id);
                CREATE INDEX idx_card_orders_person_id ON card_orders(person_id);
                CREATE INDEX idx_card_orders_status ON card_orders(status);
            """))
            
            # Create transaction_items table
            db.execute(text("""
                CREATE TABLE transaction_items (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    transaction_id UUID NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
                    item_type VARCHAR(50) NOT NULL,
                    description VARCHAR(200) NOT NULL,
                    amount NUMERIC(10, 2) NOT NULL,
                    application_id UUID REFERENCES applications(id),
                    card_order_id UUID REFERENCES card_orders(id),
                    fee_structure_id UUID REFERENCES fee_structures(id),
                    item_metadata JSONB,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                
                COMMENT ON TABLE transaction_items IS 'Individual items within a transaction';
                COMMENT ON COLUMN transaction_items.transaction_id IS 'Parent transaction';
                COMMENT ON COLUMN transaction_items.item_type IS 'Type of item (application_fee, card_order, etc.)';
                COMMENT ON COLUMN transaction_items.description IS 'Human-readable description';
                COMMENT ON COLUMN transaction_items.amount IS 'Item amount';
                COMMENT ON COLUMN transaction_items.application_id IS 'Related application (if applicable)';
                COMMENT ON COLUMN transaction_items.card_order_id IS 'Related card order (if applicable)';
                COMMENT ON COLUMN transaction_items.fee_structure_id IS 'Fee structure used';
                
                CREATE INDEX idx_transaction_items_transaction_id ON transaction_items(transaction_id);
                CREATE INDEX idx_transaction_items_application_id ON transaction_items(application_id);
                CREATE INDEX idx_transaction_items_card_order_id ON transaction_items(card_order_id);
            """))
            
            print("✅ Transaction system tables created successfully")
            
            # 2. Remove old application_fees table
            print("🗑️ Removing old application_fees table...")
            db.execute(text("DROP TABLE IF EXISTS application_fees CASCADE;"))
            print("✅ Old application_fees table removed")
            
            # 3. Initialize default fee structures
            print("💰 Initializing default fee structures...")
            
            # Get a system user for created_by
            system_user = db.execute(text("SELECT id FROM users WHERE user_type = 'NATIONAL_ADMIN' LIMIT 1")).fetchone()
            if not system_user:
                print("❌ No NATIONAL_ADMIN user found. Creating system user...")
                system_user_id = str(uuid.uuid4())
                db.execute(text("""
                    INSERT INTO users (id, username, email, first_name, last_name, user_type, is_active, created_at)
                    VALUES (:id, 'system', 'system@linc.mg', 'System', 'User', 'NATIONAL_ADMIN', TRUE, CURRENT_TIMESTAMP)
                """), {"id": system_user_id})
            else:
                system_user_id = str(system_user[0])
            
            # Insert default fee structures
            for fee_type, data in DEFAULT_FEE_STRUCTURE.items():
                db.execute(text("""
                    INSERT INTO fee_structures (
                        fee_type, display_name, description, amount, created_by
                    ) VALUES (
                        :fee_type, :display_name, :description, :amount, :created_by
                    )
                """), {
                    "fee_type": fee_type.value,
                    "display_name": data["display_name"],
                    "description": data["description"],
                    "amount": float(data["amount"]),
                    "created_by": system_user_id
                })
            
            print(f"✅ Initialized {len(DEFAULT_FEE_STRUCTURE)} fee structures")
            
            # 4. Update user permissions
            print("🔐 Updating user permissions...")
            
            # Add transaction permissions to NATIONAL_ADMIN users
            db.execute(text("""
                UPDATE users 
                SET permissions = array_cat(
                    COALESCE(permissions, ARRAY[]::varchar[]),
                    ARRAY[
                        'transactions.create', 'transactions.read', 'transactions.update', 'transactions.delete',
                        'card_orders.create', 'card_orders.read', 'card_orders.update', 'card_orders.delete',
                        'fee_structures.create', 'fee_structures.read', 'fee_structures.update', 'fee_structures.delete'
                    ]
                )
                WHERE user_type = 'NATIONAL_ADMIN';
            """))
            
            # Add transaction permissions to PROVINCIAL_ADMIN users  
            db.execute(text("""
                UPDATE users 
                SET permissions = array_cat(
                    COALESCE(permissions, ARRAY[]::varchar[]),
                    ARRAY[
                        'transactions.create', 'transactions.read', 'transactions.update',
                        'card_orders.create', 'card_orders.read', 'card_orders.update',
                        'fee_structures.read'
                    ]
                )
                WHERE user_type = 'PROVINCIAL_ADMIN';
            """))
            
            print("✅ User permissions updated successfully")
            
            # Commit all changes
            db.commit()
            
            print("🎉 Transaction system migration completed successfully!")
            print("\n📊 Summary:")
            print("  ✅ Created fee_structures table")
            print("  ✅ Created transactions table") 
            print("  ✅ Created card_orders table")
            print("  ✅ Created transaction_items table")
            print("  ✅ Removed application_fees table")
            print(f"  ✅ Initialized {len(DEFAULT_FEE_STRUCTURE)} default fee structures")
            print("  ✅ Updated user permissions")
            print("\n🔄 Next steps:")
            print("  1. Deploy backend with transaction API endpoints")
            print("  2. Build frontend POS system")
            print("  3. Test payment processing workflow")
            
        except Exception as e:
            print(f"❌ Migration failed: {str(e)}")
            db.rollback()
            raise
            
if __name__ == "__main__":
    run_migration() 