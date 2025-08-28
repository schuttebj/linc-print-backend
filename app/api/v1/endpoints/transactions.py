"""
Transaction Management API Endpoints
Handles payment processing, POS system, and transaction management
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session, joinedload
from decimal import Decimal
import uuid
from datetime import datetime, date

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.core.audit_decorators import audit_create, audit_update, audit_delete, get_transaction_by_id
from app.models.user import User
from app.models.person import Person
from app.models.application import Application
from app.models.enums import ApplicationStatus
from app.models.transaction import Transaction as TransactionModel
from app.crud import crud_transaction, crud_card_order, crud_fee_structure, transaction_calculator, person as crud_person, person_alias
from app.schemas.transaction import (
    Transaction, TransactionCreate, TransactionUpdate,
    CardOrder, CardOrderCreate, CardOrderUpdate,
    FeeStructure, FeeStructureCreate, FeeStructureUpdate,
    PersonPaymentSummary, PaymentRequest, PaymentResponse,
    TransactionSummary, ReceiptData,
    PayableApplicationItem, PayableCardOrderItem
)

router = APIRouter()


# POS System Endpoints
@router.get("/pos/search/{id_number}", response_model=PersonPaymentSummary)
def search_person_for_payment(
    id_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PersonPaymentSummary:
    """
    Search for person by ID number and get their payable items
    Used by POS system for payment processing
    """
    if not current_user.has_permission("transactions.create"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access POS system"
        )
    
    # Find person by ID number through their alias (document)
    # First try to find the alias by document number
    found_person_alias = person_alias.get_by_document_number(
        db=db, 
        document_number=id_number,
        document_type="MADAGASCAR_ID"  # National ID document type
    )
    
    # If not found as MADAGASCAR_ID, try without document type filter
    if not found_person_alias:
        found_person_alias = person_alias.get_by_document_number(
            db=db, 
            document_number=id_number
        )
    
    if not found_person_alias:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found with this ID number"
        )
    
    # Get the person from the alias
    person = crud_person.get(db=db, id=found_person_alias.person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person record not found"
        )
    
    # Get payable applications
    payable_applications = crud_transaction.get_payable_applications(db=db, person_id=person.id)
    application_items = []
    total_applications_amount = Decimal('0.00')
    
    for application in payable_applications:
        # Calculate fees for this application
        fees = transaction_calculator.calculate_application_fees(
            db=db, application=application, fee_crud=crud_fee_structure
        )
        
        application_total = sum(Decimal(str(fee['amount'])) for fee in fees)
        total_applications_amount += application_total
        
        application_items.append(PayableApplicationItem(
            id=application.id,
            application_number=application.application_number,
            application_type=application.application_type.value,
            license_category=application.license_category.value,
            status=application.status.value,
            fees=fees,
            total_amount=round(float(application_total), 2)
        ))
    
    # Get payable card orders
    payable_card_orders = crud_transaction.get_orderable_cards(db=db, person_id=person.id)
    card_order_items = []
    total_card_orders_amount = Decimal('0.00')
    
    for card_order in payable_card_orders:
        total_card_orders_amount += card_order.fee_amount
        
        card_order_items.append(PayableCardOrderItem(
            id=card_order.id,
            order_number=card_order.order_number,
            card_type=card_order.card_type,
            urgency_level=card_order.urgency_level,
            fee_amount=card_order.fee_amount,
            application_number=card_order.application.application_number,
            application_type=card_order.application.application_type.value
        ))
    
    grand_total = total_applications_amount + total_card_orders_amount
    
    return PersonPaymentSummary(
        person_id=person.id,
        person_name=f"{person.first_name} {person.surname}",
        person_id_number=found_person_alias.document_number,
        payable_applications=application_items,
        payable_card_orders=card_order_items,
        total_applications_amount=round(float(total_applications_amount), 2),
        total_card_orders_amount=round(float(total_card_orders_amount), 2),
        grand_total_amount=round(float(grand_total), 2)
    )


@router.post("/pos/process-payment", response_model=PaymentResponse)
@audit_create(resource_type="TRANSACTION", screen_reference="PaymentProcessing")
def process_payment(
    payment_request: PaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> PaymentResponse:
    """
    Process payment for selected applications and card orders
    Main POS system payment endpoint
    """
    if not current_user.has_permission("transactions.create"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to process payments"
        )
    
    # Check location access
    if not current_user.can_access_location(payment_request.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to process payments at this location"
        )
    
    # Verify person exists
    person = crud_person.get(db=db, id=payment_request.person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found"
        )
    
    transaction_items = []
    updated_applications = []
    updated_card_orders = []
    
    # Process application payments
    for application_id in payment_request.application_ids:
        application = db.query(Application).filter(Application.id == application_id).first()
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Application {application_id} not found"
            )
        
        # Check if application is in a payable status
        if application.status not in [ApplicationStatus.SUBMITTED, ApplicationStatus.CARD_PAYMENT_PENDING]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Application {application.application_number} is not in a payable status (currently {application.status})"
            )
        
        # Calculate fees for this application
        fees = transaction_calculator.calculate_application_fees(
            db=db, application=application, fee_crud=crud_fee_structure
        )
        
        transaction_items.extend(fees)
        updated_applications.append(application_id)
    
    # Process card order payments
    for card_order_id in payment_request.card_order_ids:
        card_order = crud_card_order.get(db=db, id=card_order_id)
        if not card_order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Card order {card_order_id} not found"
            )
        
        if card_order.status != "PENDING_PAYMENT":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Card order {card_order.order_number} is not pending payment"
            )
        
        # Calculate fees for this card order
        fees = transaction_calculator.calculate_card_fees(
            db=db, card_order=card_order, fee_crud=crud_fee_structure
        )
        
        transaction_items.extend(fees)
        updated_card_orders.append(card_order_id)
    
    # Create transaction with payment
    transaction = crud_transaction.create_with_items(
        db=db,
        person_id=payment_request.person_id,
        location_id=payment_request.location_id,
        processed_by=current_user.id,
        items=transaction_items,
        payment_method=payment_request.payment_method,
        payment_reference=payment_request.payment_reference,
        notes=payment_request.notes
    )
    
    # Generate receipt URL (for future implementation)
    receipt_url = f"/api/v1/transactions/{transaction.id}/receipt"
    
    success_message = f"Payment processed successfully. Receipt: {transaction.receipt_number}"
    
    return PaymentResponse(
        transaction=transaction,
        receipt_url=receipt_url,
        updated_applications=updated_applications,
        updated_card_orders=updated_card_orders,
        success_message=success_message
    )


# Transaction CRUD Endpoints
@router.get("/", response_model=List[Transaction])
def get_transactions(
    skip: int = 0,
    limit: int = 100,
    person_id: Optional[uuid.UUID] = None,
    location_id: Optional[uuid.UUID] = None,
    transaction_status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[Transaction]:
    """
    Get transactions with optional filtering
    """
    if not current_user.has_permission("transactions.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to read transactions"
        )
    
    query = db.query(crud_transaction.model).options(
        joinedload(crud_transaction.model.items),
        joinedload(crud_transaction.model.person)
    )
    
    # Apply filters
    if person_id:
        query = query.filter(crud_transaction.model.person_id == person_id)
    
    if location_id:
        # Check location access
        if not current_user.can_access_location(location_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access transactions from this location"
            )
        query = query.filter(crud_transaction.model.location_id == location_id)
    else:
        # If no location specified, filter by user's accessible locations
        accessible_locations = current_user.get_accessible_locations()
        if accessible_locations:
            query = query.filter(crud_transaction.model.location_id.in_(accessible_locations))
    
    if transaction_status:
        query = query.filter(crud_transaction.model.status == transaction_status)
    
    transactions = query.order_by(crud_transaction.model.created_at.desc()).offset(skip).limit(limit).all()
    return transactions


# Fee Structure Management
@router.get("/fee-structures", response_model=List[FeeStructure])
async def get_fee_structures(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all fee structures for fee management"""
    # Check permissions
    if not current_user.has_permission("transactions.read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return crud_fee_structure.get_all(db)

@router.put("/fee-structures/{fee_structure_id}", response_model=FeeStructure)
@audit_update(
    resource_type="FEE_STRUCTURE", 
    screen_reference="FeeStructureForm",
    get_old_data=lambda db, fee_id: db.query(crud_fee_structure.model).filter(crud_fee_structure.model.id == fee_id).first()
)
async def update_fee_structure(
    fee_structure_id: uuid.UUID,
    fee_update: FeeStructureUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a specific fee structure amount"""
    # Check permissions - only admins can update fees
    if not current_user.has_permission("transactions.manage_fees"):
        raise HTTPException(status_code=403, detail="Insufficient permissions to manage fees")
    
    fee_structure = crud_fee_structure.get(db, id=fee_structure_id)
    if not fee_structure:
        raise HTTPException(status_code=404, detail="Fee structure not found")
    
    # Update the fee structure
    updated_fee = crud_fee_structure.update(db=db, db_obj=fee_structure, obj_in=fee_update)
    
    return updated_fee

@router.get("/fee-structures/by-application-type")
async def get_fees_by_application_type(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get fees organized by application type for easy management"""
    # Check permissions
    if not current_user.has_permission("transactions.read"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    from app.models.enums import ApplicationType, MADAGASCAR_FEE_DISPLAY
    
    # Get all fee structures
    all_fees = crud_fee_structure.get_all(db)
    
    # Organize by application type
    fee_mapping = {
        ApplicationType.NEW_LICENSE: {
            "name": "New License",
            "fees": {
                "test_fees": [],
                "application_fee": None,
                "total_light": 0,
                "total_heavy": 0
            }
        },
        ApplicationType.LEARNERS_PERMIT: {
            "name": "Learner's Permit",
            "fees": {
                "test_fees": [],
                "application_fee": None,
                "total_light": 0,
                "total_heavy": 0
            }
        },
        ApplicationType.RENEWAL: {
            "name": "License Renewal",
            "fees": {
                "application_fee": None,
                "total": 0
            }
        },
        ApplicationType.REPLACEMENT: {
            "name": "License Replacement",
            "fees": {
                "application_fee": None,
                "total": 0
            }
        },
        ApplicationType.TEMPORARY_LICENSE: {
            "name": "Temporary License",
            "fees": {
                "application_fee": None,
                "total": 0
            }
        },
        ApplicationType.INTERNATIONAL_PERMIT: {
            "name": "International Permit",
            "fees": {
                "application_fee": None,
                "total": 0
            }
        },
        ApplicationType.PROFESSIONAL_LICENSE: {
            "name": "Professional License",
            "fees": {
                "application_fee": None,
                "total": 0
            }
        },
        ApplicationType.FOREIGN_CONVERSION: {
            "name": "Foreign Conversion",
            "fees": {
                "application_fee": None,
                "total": 0
            }
        }
    }
    
    # Map fees to application types
    for fee in all_fees:
        fee_type = fee.fee_type.value
        
        # Test fees (apply to multiple application types)
        if fee_type in ["THEORY_TEST_LIGHT", "THEORY_TEST_HEAVY", "PRACTICAL_TEST_LIGHT", "PRACTICAL_TEST_HEAVY"]:
            for app_type in [ApplicationType.NEW_LICENSE, ApplicationType.LEARNERS_PERMIT]:
                if app_type in fee_mapping:
                    fee_mapping[app_type]["fees"]["test_fees"].append({
                        "id": fee.id,
                        "type": fee_type,
                        "display_name": fee.display_name,
                        "amount": float(fee.amount),
                        "description": fee.description
                    })
        
        # Application-specific fees
        elif fee_type == "NEW_LICENSE_FEE":
            fee_mapping[ApplicationType.NEW_LICENSE]["fees"]["application_fee"] = {
                "id": fee.id,
                "type": fee_type,
                "display_name": fee.display_name,
                "amount": float(fee.amount),
                "description": fee.description
            }
        elif fee_type == "RENEWAL_FEE":
            fee_mapping[ApplicationType.RENEWAL]["fees"]["application_fee"] = {
                "id": fee.id,
                "type": fee_type,
                "display_name": fee.display_name,
                "amount": float(fee.amount),
                "description": fee.description
            }
        elif fee_type == "REPLACEMENT_FEE":
            fee_mapping[ApplicationType.REPLACEMENT]["fees"]["application_fee"] = {
                "id": fee.id,
                "type": fee_type,
                "display_name": fee.display_name,
                "amount": float(fee.amount),
                "description": fee.description
            }
        elif fee_type == "TEMPORARY_LICENSE_FEE":
            fee_mapping[ApplicationType.TEMPORARY_LICENSE]["fees"]["application_fee"] = {
                "id": fee.id,
                "type": fee_type,
                "display_name": fee.display_name,
                "amount": float(fee.amount),
                "description": fee.description
            }
        elif fee_type == "INTERNATIONAL_PERMIT_FEE":
            fee_mapping[ApplicationType.INTERNATIONAL_PERMIT]["fees"]["application_fee"] = {
                "id": fee.id,
                "type": fee_type,
                "display_name": fee.display_name,
                "amount": float(fee.amount),
                "description": fee.description
            }
        elif fee_type == "PROFESSIONAL_LICENSE_FEE":
            fee_mapping[ApplicationType.PROFESSIONAL_LICENSE]["fees"]["application_fee"] = {
                "id": fee.id,
                "type": fee_type,
                "display_name": fee.display_name,
                "amount": float(fee.amount),
                "description": fee.description
            }
        elif fee_type == "FOREIGN_CONVERSION_FEE":
            fee_mapping[ApplicationType.FOREIGN_CONVERSION]["fees"]["application_fee"] = {
                "id": fee.id,
                "type": fee_type,
                "display_name": fee.display_name,
                "amount": float(fee.amount),
                "description": fee.description
            }
    
    # Calculate totals
    for app_type, data in fee_mapping.items():
        if "total_light" in data["fees"]:
            # Applications with tests
            theory_light = next((f["amount"] for f in data["fees"]["test_fees"] if f["type"] == "THEORY_TEST_LIGHT"), 0)
            practical_light = next((f["amount"] for f in data["fees"]["test_fees"] if f["type"] == "PRACTICAL_TEST_LIGHT"), 0)
            theory_heavy = next((f["amount"] for f in data["fees"]["test_fees"] if f["type"] == "THEORY_TEST_HEAVY"), 0)
            practical_heavy = next((f["amount"] for f in data["fees"]["test_fees"] if f["type"] == "PRACTICAL_TEST_HEAVY"), 0)
            application_fee = data["fees"]["application_fee"]["amount"] if data["fees"]["application_fee"] else 0
            
            if app_type == ApplicationType.NEW_LICENSE:
                data["fees"]["total_light"] = theory_light + practical_light + application_fee
                data["fees"]["total_heavy"] = theory_heavy + practical_heavy + application_fee
            else:  # LEARNERS_PERMIT
                data["fees"]["total_light"] = theory_light
                data["fees"]["total_heavy"] = theory_heavy
        else:
            # Single payment applications
            application_fee = data["fees"]["application_fee"]["amount"] if data["fees"]["application_fee"] else 0
            data["fees"]["total"] = application_fee
    
    return fee_mapping


# Card Order Management
@router.post("/card-orders", response_model=CardOrder)
@audit_create(resource_type="CARD_ORDER", screen_reference="CardOrderForm")
def create_card_order(
    card_order_in: CardOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> CardOrder:
    """
    Create new card order
    """
    if not current_user.has_permission("card_orders.create"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to create card orders"
        )
    
    # Get the application to verify it exists and is in correct status
    application = db.query(Application).filter(Application.id == card_order_in.application_id).first()
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Calculate card fee
    fees = transaction_calculator.calculate_card_fees(
        db=db, card_order=card_order, fee_crud=crud_fee_structure
    )
    total_fee = sum(Decimal(str(fee['amount'])) for fee in fees)
    
    # Create card order
    card_order_data = card_order_in.dict()
    card_order_data['fee_amount'] = total_fee
    card_order_data['ordered_by'] = current_user.id
    
    card_order = crud_card_order.create(db=db, obj_in=card_order_data)
    
    return card_order


@router.get("/card-orders", response_model=List[CardOrder])
def get_card_orders(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> List[CardOrder]:
    """
    Get card orders with pagination and filtering
    """
    if not current_user.has_permission("card_orders.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to read card orders"
        )
    
    # Apply location-based filtering based on user permissions
    query = db.query(CardOrder)
    
    if current_user.user_type in ["LOCATION_USER", "PROVINCIAL_ADMIN"]:
        # Filter by user's accessible locations
        accessible_locations = current_user.get_accessible_locations()
        if accessible_locations:
            query = query.join(Application).filter(Application.location_id.in_(accessible_locations))
    
    if status:
        query = query.filter(CardOrder.status == status)
    
    card_orders = query.order_by(CardOrder.created_at.desc()).offset(skip).limit(limit).all()
    return card_orders


# Reporting
@router.get("/reports/daily-summary", response_model=TransactionSummary)
def get_daily_transaction_summary(
    date: Optional[date] = None,
    location_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> TransactionSummary:
    """
    Get daily transaction summary report
    """
    if not current_user.has_permission("transactions.read"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to read transaction reports"
        )
    
    if location_id and not current_user.can_access_location(location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access reports for this location"
        )
    
    if date is None:
        date = datetime.utcnow().date()
    
    summary = crud_transaction.get_daily_summary(
        db=db,
        date=date,
        location_id=location_id
    )
    
    return summary


@router.get("/{transaction_id}", response_model=Transaction)
def get_transaction(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Transaction:
    """
    Get transaction by ID
    """
    transaction = crud_transaction.get(db=db, id=transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    # Check location access
    if not current_user.can_access_location(transaction.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this transaction"
        )
    
    return transaction


@router.get("/{transaction_id}/receipt")
def get_transaction_receipt(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate and return transaction receipt (A4 format)
    """
    # Get transaction with person and aliases loaded
    transaction = db.query(TransactionModel).options(
        joinedload(TransactionModel.person).joinedload(Person.aliases),
        joinedload(TransactionModel.location)
    ).filter(TransactionModel.id == transaction_id).first()
    
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    
    # Check location access
    if not current_user.can_access_location(transaction.location_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this transaction"
        )
    
    # Mark receipt as printed
    if not transaction.receipt_printed:
        transaction.receipt_printed = True
        transaction.receipt_printed_at = datetime.utcnow()
        db.commit()
    
    # Get the person's primary ID number from their aliases
    primary_alias = None
    if transaction.person.aliases:
        # Try to find a Madagascar ID first, then any alias
        for alias in transaction.person.aliases:
            if alias.document_type == "MADAGASCAR_ID" and alias.is_primary:
                primary_alias = alias
                break
        if not primary_alias:
            # Fallback to first alias if no primary Madagascar ID found
            primary_alias = transaction.person.aliases[0] if transaction.person.aliases else None

    # Generate comprehensive A4 receipt data for frontend printing
    receipt_data = {
        # Transaction details
        "receipt_number": transaction.receipt_number,
        "transaction_number": transaction.transaction_number,
        "date": transaction.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        
        # Government headers
        "government_header": "REPUBLIC OF MADAGASCAR",
        "department_header": "MINISTRY OF TRANSPORT",
        "office_header": "DRIVER'S LICENSE SERVICES",
        "receipt_title": "OFFICIAL PAYMENT RECEIPT",
        
        # Person details
        "person_name": f"{transaction.person.first_name} {transaction.person.surname}",
        "person_id": primary_alias.document_number if primary_alias else "N/A",
        
        # Location details
        "location": transaction.location.name if transaction.location else "Unknown",
        "location_address": f"{transaction.location.street_address}, {transaction.location.locality}" if transaction.location and transaction.location.street_address else "",
        "location_code": transaction.location.full_code if transaction.location else "",
        
        # Payment details
        "items": [
            {
                "description": item.description,
                "amount": float(item.amount),
                "currency": "MGA"
            }
            for item in transaction.items
        ],
        "total_amount": float(transaction.total_amount),
        "payment_method": transaction.payment_method.value if transaction.payment_method else "Unknown",
        "payment_reference": transaction.payment_reference,
        
        # Processing details
        "processed_by": f"{current_user.first_name} {current_user.last_name}",
        "processed_by_id": current_user.username,
        "processing_date": transaction.processed_at.strftime("%Y-%m-%d %H:%M:%S") if transaction.processed_at else transaction.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        
        # Additional information
        "footer": "Please keep this receipt as proof of payment. Present this receipt when collecting your license or card.",
        "validity_note": "This receipt is valid for 90 days from the date of payment.",
        "contact_info": "For inquiries, contact your local license office.",
        "currency": "MGA",
        "currency_name": "Malagasy Ariary"
    }
    
    return receipt_data 