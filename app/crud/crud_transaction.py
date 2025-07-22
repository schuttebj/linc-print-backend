"""
CRUD operations for Transaction Management
Handles payment processing, POS system logic, and fee calculations
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func
from decimal import Decimal
import uuid
from datetime import datetime, timedelta

from app.crud.base import CRUDBase
from app.models.transaction import (
    Transaction, TransactionItem, CardOrder, FeeStructure,
    TransactionType, TransactionStatus, PaymentMethod, FeeType, CardOrderStatus,
    DEFAULT_FEE_STRUCTURE
)
from app.models.application import Application, ApplicationStatus
from app.models.enums import ApplicationType, LicenseCategory
from app.schemas.transaction import (
    TransactionCreate, TransactionUpdate, TransactionItemCreate,
    CardOrderCreate, CardOrderUpdate, FeeStructureCreate, FeeStructureUpdate
)


class CRUDTransaction(CRUDBase[Transaction, TransactionCreate, TransactionUpdate]):
    """CRUD operations for Transactions"""
    
    def generate_transaction_number(self, db: Session) -> str:
        """Generate unique transaction number"""
        today = datetime.now()
        prefix = f"TXN{today.strftime('%Y%m%d')}"
        
        # Find highest number for today
        last_transaction = db.query(Transaction).filter(
            Transaction.transaction_number.like(f"{prefix}%")
        ).order_by(desc(Transaction.transaction_number)).first()
        
        if last_transaction:
            last_num = int(last_transaction.transaction_number[-4:])
            new_num = last_num + 1
        else:
            new_num = 1
            
        return f"{prefix}{new_num:04d}"
    
    def create_with_items(
        self,
        db: Session,
        *,
        person_id: uuid.UUID,
        location_id: uuid.UUID,
        processed_by: uuid.UUID,
        items: List[Dict[str, Any]],
        payment_method: Optional[PaymentMethod] = None,
        payment_reference: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Transaction:
        """Create transaction with items and process payment"""
        
        # Calculate total amount
        total_amount = sum(Decimal(str(item['amount'])) for item in items)
        
        # Determine transaction type
        has_applications = any(item.get('application_id') for item in items)
        has_cards = any(item.get('card_order_id') for item in items)
        
        if has_applications and has_cards:
            transaction_type = TransactionType.MIXED_PAYMENT
        elif has_applications:
            transaction_type = TransactionType.APPLICATION_PAYMENT
        else:
            transaction_type = TransactionType.CARD_ORDER_PAYMENT
        
        # Create transaction
        transaction = Transaction(
            transaction_number=self.generate_transaction_number(db),
            transaction_type=transaction_type,
            status=TransactionStatus.PENDING,
            person_id=person_id,
            location_id=location_id,
            total_amount=total_amount,
            processed_by=processed_by,
            notes=notes
        )
        
        db.add(transaction)
        db.flush()  # Get transaction ID
        
        # Create transaction items
        for item_data in items:
            item = TransactionItem(
                transaction_id=transaction.id,
                item_type=item_data['item_type'],
                description=item_data['description'],
                amount=Decimal(str(item_data['amount'])),
                application_id=item_data.get('application_id'),
                card_order_id=item_data.get('card_order_id'),
                fee_structure_id=item_data.get('fee_structure_id'),
                metadata=item_data.get('metadata')
            )
            db.add(item)
        
        # If payment method provided, complete the payment
        if payment_method:
            self.complete_payment(
                db=db,
                transaction=transaction,
                payment_method=payment_method,
                payment_reference=payment_reference
            )
        
        db.commit()
        db.refresh(transaction)
        return transaction
    
    def complete_payment(
        self,
        db: Session,
        transaction: Transaction,
        payment_method: PaymentMethod,
        payment_reference: Optional[str] = None
    ) -> Transaction:
        """Complete payment for a transaction"""
        
        transaction.status = TransactionStatus.PAID
        transaction.payment_method = payment_method
        transaction.payment_reference = payment_reference
        transaction.processed_at = datetime.utcnow()
        
        # Generate receipt number
        if not transaction.receipt_number:
            transaction.receipt_number = self.generate_receipt_number(db)
        
        # Update related application statuses
        for item in transaction.items:
            if item.application_id:
                application = db.query(Application).filter(
                    Application.id == item.application_id
                ).first()
                if application and application.status == ApplicationStatus.SUBMITTED:
                    application.status = ApplicationStatus.PAID
                    application.updated_at = datetime.utcnow()
            
            if item.card_order_id:
                card_order = db.query(CardOrder).filter(
                    CardOrder.id == item.card_order_id
                ).first()
                if card_order and card_order.status == CardOrderStatus.PENDING_PAYMENT:
                    card_order.status = CardOrderStatus.PAID
        
        db.commit()
        return transaction
    
    def generate_receipt_number(self, db: Session) -> str:
        """Generate unique receipt number"""
        today = datetime.now()
        prefix = f"RCP{today.strftime('%Y%m%d')}"
        
        last_receipt = db.query(Transaction).filter(
            Transaction.receipt_number.like(f"{prefix}%")
        ).order_by(desc(Transaction.receipt_number)).first()
        
        if last_receipt:
            last_num = int(last_receipt.receipt_number[-4:])
            new_num = last_num + 1
        else:
            new_num = 1
            
        return f"{prefix}{new_num:04d}"
    
    def get_payable_applications(self, db: Session, person_id: uuid.UUID) -> List[Application]:
        """Get applications that can be paid for (SUBMITTED status)"""
        return db.query(Application).filter(
            and_(
                Application.person_id == person_id,
                Application.status == ApplicationStatus.SUBMITTED
            )
        ).options(joinedload(Application.person)).all()
    
    def get_orderable_cards(self, db: Session, person_id: uuid.UUID) -> List[CardOrder]:
        """Get card orders that can be paid for"""
        return db.query(CardOrder).filter(
            and_(
                CardOrder.person_id == person_id,
                CardOrder.status == CardOrderStatus.PENDING_PAYMENT
            )
        ).options(
            joinedload(CardOrder.application),
            joinedload(CardOrder.person)
        ).all()
    
    def get_by_person(self, db: Session, person_id: uuid.UUID) -> List[Transaction]:
        """Get all transactions for a person"""
        return db.query(Transaction).filter(
            Transaction.person_id == person_id
        ).options(
            joinedload(Transaction.items),
            joinedload(Transaction.person)
        ).order_by(desc(Transaction.created_at)).all()
    
    def get_by_location(self, db: Session, location_id: uuid.UUID) -> List[Transaction]:
        """Get all transactions for a location"""
        return db.query(Transaction).filter(
            Transaction.location_id == location_id
        ).options(
            joinedload(Transaction.items),
            joinedload(Transaction.person)
        ).order_by(desc(Transaction.created_at)).all()
    
    def get_daily_summary(self, db: Session, location_id: uuid.UUID, date: datetime) -> Dict[str, Any]:
        """Get daily transaction summary for a location"""
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        transactions = db.query(Transaction).filter(
            and_(
                Transaction.location_id == location_id,
                Transaction.created_at >= start_date,
                Transaction.created_at < end_date,
                Transaction.status == TransactionStatus.PAID
            )
        ).all()
        
        total_amount = sum(t.total_amount for t in transactions)
        total_count = len(transactions)
        
        # Group by payment method
        payment_methods = {}
        for transaction in transactions:
            method = transaction.payment_method.value if transaction.payment_method else 'UNKNOWN'
            if method not in payment_methods:
                payment_methods[method] = {'count': 0, 'amount': Decimal('0.00')}
            payment_methods[method]['count'] += 1
            payment_methods[method]['amount'] += transaction.total_amount
        
        return {
            'date': date.date(),
            'location_id': location_id,
            'total_transactions': total_count,
            'total_amount': total_amount,
            'payment_methods': payment_methods,
            'transactions': transactions
        }


class CRUDCardOrder(CRUDBase[CardOrder, CardOrderCreate, CardOrderUpdate]):
    """CRUD operations for Card Orders"""
    
    def generate_order_number(self, db: Session) -> str:
        """Generate unique card order number"""
        today = datetime.now()
        prefix = f"CO{today.strftime('%Y%m%d')}"
        
        last_order = db.query(CardOrder).filter(
            CardOrder.order_number.like(f"{prefix}%")
        ).order_by(desc(CardOrder.order_number)).first()
        
        if last_order:
            last_num = int(last_order.order_number[-4:])
            new_num = last_num + 1
        else:
            new_num = 1
            
        return f"{prefix}{new_num:04d}"
    
    def create_for_application(
        self,
        db: Session,
        *,
        application_id: uuid.UUID,
        ordered_by: uuid.UUID,
        urgency_level: int = 1,
        card_type: str = "license"
    ) -> CardOrder:
        """Create card order for an application"""
        
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            raise ValueError("Application not found")
        
        # Check if application is eligible for card order
        if application.application_type == ApplicationType.NEW_LICENSE and application.status != ApplicationStatus.PASSED:
            raise ValueError("New license applications must pass tests before card ordering")
        
        # Calculate fee based on urgency
        fee_amount = self.calculate_card_fee(urgency_level)
        
        card_order = CardOrder(
            order_number=self.generate_order_number(db),
            status=CardOrderStatus.PENDING_PAYMENT,
            application_id=application_id,
            person_id=application.person_id,
            card_type=card_type,
            urgency_level=urgency_level,
            fee_amount=fee_amount,
            ordered_by=ordered_by
        )
        
        db.add(card_order)
        db.commit()
        db.refresh(card_order)
        return card_order
    
    def calculate_card_fee(self, urgency_level: int) -> Decimal:
        """Calculate card production fee based on urgency"""
        fee_mapping = {
            1: Decimal("38000.00"),   # Normal
            2: Decimal("100000.00"),  # Urgent  
            3: Decimal("400000.00"),  # Emergency
        }
        return fee_mapping.get(urgency_level, Decimal("38000.00"))
    
    def get_by_application(self, db: Session, application_id: uuid.UUID) -> Optional[CardOrder]:
        """Get card order for an application"""
        return db.query(CardOrder).filter(CardOrder.application_id == application_id).first()
    
    def get_ready_for_production(self, db: Session) -> List[CardOrder]:
        """Get card orders ready for production (paid status)"""
        return db.query(CardOrder).filter(
            CardOrder.status == CardOrderStatus.PAID
        ).options(
            joinedload(CardOrder.application),
            joinedload(CardOrder.person)
        ).all()


class CRUDFeeStructure(CRUDBase[FeeStructure, FeeStructureCreate, FeeStructureUpdate]):
    """CRUD operations for Fee Structures"""
    
    def get_effective_fees(self, db: Session, date: datetime = None) -> List[FeeStructure]:
        """Get all effective fee structures for a given date"""
        if date is None:
            date = datetime.utcnow()
        
        return db.query(FeeStructure).filter(
            and_(
                FeeStructure.is_active == True,
                FeeStructure.effective_from <= date,
                or_(
                    FeeStructure.effective_until.is_(None),
                    FeeStructure.effective_until > date
                )
            )
        ).all()
    
    def get_by_fee_type(self, db: Session, fee_type: FeeType) -> Optional[FeeStructure]:
        """Get current fee structure for a specific fee type"""
        return db.query(FeeStructure).filter(
            and_(
                FeeStructure.fee_type == fee_type,
                FeeStructure.is_active == True
            )
        ).order_by(desc(FeeStructure.effective_from)).first()
    
    def initialize_default_fees(self, db: Session, created_by: uuid.UUID) -> List[FeeStructure]:
        """Initialize default fee structures"""
        fee_structures = []
        
        for fee_type, data in DEFAULT_FEE_STRUCTURE.items():
            existing = self.get_by_fee_type(db, fee_type)
            if not existing:
                fee_structure = FeeStructure(
                    fee_type=fee_type,
                    display_name=data['display_name'],
                    description=data['description'],
                    amount=data['amount'],
                    created_by=created_by
                )
                db.add(fee_structure)
                fee_structures.append(fee_structure)
        
        db.commit()
        return fee_structures


class TransactionCalculator:
    """Helper class for calculating transaction fees"""
    
    @staticmethod
    def calculate_application_fees(
        db: Session,
        application: Application,
        fee_crud: CRUDFeeStructure
    ) -> List[Dict[str, Any]]:
        """Calculate fees for an application"""
        fees = []
        
        # Application processing fee
        processing_fee = fee_crud.get_by_fee_type(db, FeeType.APPLICATION_PROCESSING)
        if processing_fee:
            fees.append({
                'item_type': 'application_processing',
                'description': f"Application Processing - {application.application_type.value}",
                'amount': processing_fee.amount,
                'application_id': application.id,
                'fee_structure_id': processing_fee.id
            })
        
        # Theory test fee (for new licenses and learner's permits)
        if application.application_type in [ApplicationType.NEW_LICENSE, ApplicationType.LEARNERS_PERMIT]:
            is_heavy = application.license_category in [
                LicenseCategory.C1, LicenseCategory.C, LicenseCategory.C1E, LicenseCategory.CE,
                LicenseCategory.D1, LicenseCategory.D, LicenseCategory.D2
            ]
            
            theory_fee_type = FeeType.THEORY_TEST_HEAVY if is_heavy else FeeType.THEORY_TEST_LIGHT
            theory_fee = fee_crud.get_by_fee_type(db, theory_fee_type)
            if theory_fee:
                fees.append({
                    'item_type': 'theory_test',
                    'description': f"Theory Test - {application.license_category.value}",
                    'amount': theory_fee.amount,
                    'application_id': application.id,
                    'fee_structure_id': theory_fee.id
                })
        
        # Practical test fee (for new licenses)
        if application.application_type == ApplicationType.NEW_LICENSE:
            is_heavy = application.license_category in [
                LicenseCategory.C1, LicenseCategory.C, LicenseCategory.C1E, LicenseCategory.CE,
                LicenseCategory.D1, LicenseCategory.D, LicenseCategory.D2
            ]
            
            practical_fee_type = FeeType.PRACTICAL_TEST_HEAVY if is_heavy else FeeType.PRACTICAL_TEST_LIGHT
            practical_fee = fee_crud.get_by_fee_type(db, practical_fee_type)
            if practical_fee:
                fees.append({
                    'item_type': 'practical_test',
                    'description': f"Practical Test - {application.license_category.value}",
                    'amount': practical_fee.amount,
                    'application_id': application.id,
                    'fee_structure_id': practical_fee.id
                })
        
        # Temporary license fee
        if application.application_type == ApplicationType.TEMPORARY_LICENSE:
            urgency = getattr(application, 'priority', 1)
            if urgency == 3:
                temp_fee_type = FeeType.TEMPORARY_LICENSE_EMERGENCY
            elif urgency == 2:
                temp_fee_type = FeeType.TEMPORARY_LICENSE_URGENT
            else:
                temp_fee_type = FeeType.TEMPORARY_LICENSE_NORMAL
            
            temp_fee = fee_crud.get_by_fee_type(db, temp_fee_type)
            if temp_fee:
                fees.append({
                    'item_type': 'temporary_license',
                    'description': f"Temporary License - {temp_fee.display_name}",
                    'amount': temp_fee.amount,
                    'application_id': application.id,
                    'fee_structure_id': temp_fee.id
                })
        
        # International permit fee
        if application.application_type == ApplicationType.INTERNATIONAL_PERMIT:
            intl_fee = fee_crud.get_by_fee_type(db, FeeType.INTERNATIONAL_PERMIT)
            if intl_fee:
                fees.append({
                    'item_type': 'international_permit',
                    'description': "International Driving Permit",
                    'amount': intl_fee.amount,
                    'application_id': application.id,
                    'fee_structure_id': intl_fee.id
                })
        
        # Professional permit fee
        if application.application_type == ApplicationType.PROFESSIONAL_LICENSE:
            prof_fee = fee_crud.get_by_fee_type(db, FeeType.PROFESSIONAL_PERMIT)
            if prof_fee:
                fees.append({
                    'item_type': 'professional_permit',
                    'description': "Professional Driving Permit",
                    'amount': prof_fee.amount,
                    'application_id': application.id,
                    'fee_structure_id': prof_fee.id
                })
        
        return fees
    
    @staticmethod
    def calculate_card_fees(
        db: Session,
        card_order: CardOrder,
        fee_crud: CRUDFeeStructure
    ) -> List[Dict[str, Any]]:
        """Calculate fees for a card order"""
        fees = []
        
        # Determine fee type based on urgency
        if card_order.urgency_level == 3:
            fee_type = FeeType.CARD_EMERGENCY
        elif card_order.urgency_level == 2:
            fee_type = FeeType.CARD_URGENT
        else:
            fee_type = FeeType.CARD_PRODUCTION
        
        card_fee = fee_crud.get_by_fee_type(db, fee_type)
        if card_fee:
            fees.append({
                'item_type': 'card_production',
                'description': f"Card Production - {card_fee.display_name}",
                'amount': card_fee.amount,
                'card_order_id': card_order.id,
                'fee_structure_id': card_fee.id
            })
        
        return fees


# Create instances
crud_transaction = CRUDTransaction(Transaction)
crud_card_order = CRUDCardOrder(CardOrder)
crud_fee_structure = CRUDFeeStructure(FeeStructure)
transaction_calculator = TransactionCalculator() 