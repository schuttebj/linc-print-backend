"""
Person Management API Endpoints - Madagascar Implementation
RESTful API endpoints for natural persons, aliases, and addresses
Includes search functionality and duplicate detection
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.database import get_db
from app.api.v1.endpoints.auth import get_current_user
from app.api.v1.endpoints.users import require_permission
from app.crud import crud_person
from app.models.user import User
from app.schemas.person import (
    PersonCreate, PersonUpdate, PersonResponse, PersonSummary,
    PersonSearchRequest, PersonDuplicateCheckResponse,
    PersonAliasCreate, PersonAliasUpdate, PersonAliasResponse,
    PersonAddressCreate, PersonAddressUpdate, PersonAddressResponse
)

router = APIRouter()


def check_permission(user: User, permission: str) -> bool:
    """Check if user has specific permission"""
    if user.is_superuser:
        return True
    return user.has_permission(permission)


def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(current_user: User = Depends(get_current_user)):
        if not check_permission(current_user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}"
            )
        return current_user
    return decorator


# Person CRUD endpoints
@router.post("/", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
def create_person(
    *,
    db: Session = Depends(get_db),
    person_in: PersonCreate,
    current_user: User = Depends(require_permission("persons.create"))
) -> PersonResponse:
    """
    Create new person with optional aliases and addresses
    Requires persons.create permission
    """
    try:
        person = crud_person.person.create_with_details(
            db=db, 
            obj_in=person_in, 
            created_by=str(current_user.id)
        )
        
        # TODO: Check for duplicates after creation and flag if needed
        # duplicates = crud_person.person.find_potential_duplicates(
        #     db=db, person=person, threshold=70.0
        # )
        # if duplicates:
        #     # Log duplicate warning or create review task
        #     pass
        
        return person
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error creating person: {str(e)}"
        )


@router.get("/search")
def search_persons(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("persons.search")),
    surname: Optional[str] = Query(None, description="Search by surname (partial match)"),
    first_name: Optional[str] = Query(None, description="Search by first name (partial match)"),
    document_number: Optional[str] = Query(None, description="Search by document number"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    birth_date: Optional[str] = Query(None, description="Search by birth date (YYYY-MM-DD)"),
    nationality_code: Optional[str] = Query(None, description="Filter by nationality"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    locality: Optional[str] = Query(None, description="Search by address locality"),
    phone_number: Optional[str] = Query(None, description="Search by phone number"),
    include_details: bool = Query(False, description="Include full person details (aliases, addresses) instead of summary"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of records to return")
):
    """
    Search persons with multiple criteria
    Returns summary information for list views by default, or full details if include_details=true
    Requires persons.search permission
    """
    # Parse birth_date if provided
    parsed_birth_date = None
    if birth_date:
        try:
            from datetime import datetime
            parsed_birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid birth_date format. Use YYYY-MM-DD"
            )
    
    search_params = PersonSearchRequest(
        surname=surname,
        first_name=first_name,
        document_number=document_number,
        document_type=document_type,
        birth_date=parsed_birth_date,
        nationality_code=nationality_code,
        is_active=is_active,
        locality=locality,
        phone_number=phone_number,
        skip=skip,
        limit=limit
    )
    
    persons, total_count = crud_person.person.search_persons(db=db, search_params=search_params)
    
    if include_details:
        # Return full person details with aliases and addresses
        detailed_persons = []
        for person in persons:
            detailed_person = crud_person.person.get_with_details(db=db, id=person.id)
            if detailed_person:
                detailed_persons.append(detailed_person)
        return detailed_persons
    else:
        # Convert to summary format for backwards compatibility
        summaries = []
        for person in persons:
            # Get primary document info
            primary_alias = next((a for a in person.aliases if a.is_primary), None)
            
            summary = PersonSummary(
                id=person.id,
                surname=person.surname,
                first_name=person.first_name,
                middle_name=person.middle_name,
                person_nature=person.person_nature,
                birth_date=person.birth_date,
                nationality_code=person.nationality_code,
                is_active=person.is_active,
                primary_document=primary_alias.document_number if primary_alias else None,
                primary_document_type=primary_alias.document_type if primary_alias else None
            )
            summaries.append(summary)
        
        # TODO: Add total_count to response headers
        # response.headers["X-Total-Count"] = str(total_count)
        
        return summaries


@router.get("/{person_id}", response_model=PersonResponse)
def get_person(
    *,
    db: Session = Depends(get_db),
    person_id: UUID,
    current_user: User = Depends(require_permission("persons.read"))
) -> PersonResponse:
    """
    Get person by ID with all details (aliases and addresses)
    Requires persons.read permission
    """
    person = crud_person.person.get_with_details(db=db, id=person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found"
        )
    
    return person


@router.put("/{person_id}", response_model=PersonResponse)
def update_person(
    *,
    db: Session = Depends(get_db),
    person_id: UUID,
    person_update: PersonUpdate,
    current_user: User = Depends(require_permission("persons.update"))
) -> PersonResponse:
    """
    Update person information
    Requires persons.update permission
    """
    person = crud_person.person.get(db=db, id=person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found"
        )
    
    updated_person = crud_person.person.update(
        db=db, 
        db_obj=person, 
        obj_in=person_update,
        updated_by=current_user.username
    )
    
    return crud_person.person.get_with_details(db=db, id=updated_person.id)


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(
    *,
    db: Session = Depends(get_db),
    person_id: UUID,
    current_user: User = Depends(require_permission("persons.delete"))
) -> None:
    """
    Soft delete person (set is_active=False)
    Requires persons.delete permission (Supervisor+ only)
    """
    person = crud_person.person.get(db=db, id=person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found"
        )
    
    # Always soft delete to maintain data integrity
    crud_person.person.update(
        db=db, 
        db_obj=person, 
        obj_in=PersonUpdate(is_active=False),
        updated_by=current_user.username
    )


# Duplicate detection endpoints
@router.get("/{person_id}/duplicates", response_model=PersonDuplicateCheckResponse)
def check_person_duplicates(
    *,
    db: Session = Depends(get_db),
    person_id: UUID,
    current_user: User = Depends(require_permission("persons.check_duplicates")),
    threshold: float = Query(70.0, ge=0.0, le=100.0, description="Similarity threshold percentage")
) -> PersonDuplicateCheckResponse:
    """
    Check for potential duplicate persons
    Returns persons with similarity score above threshold
    Requires persons.check_duplicates permission
    """
    person = crud_person.person.get_with_details(db=db, id=person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found"
        )
    
    duplicates = crud_person.person.find_potential_duplicates(
        db=db, 
        person=person, 
        threshold=threshold
    )
    
    # Convert to response format
    duplicate_summaries = []
    for dup in duplicates:
        dup_person = dup['person']
        primary_alias = next((a for a in dup_person.aliases if a.is_primary), None)
        
        duplicate_summaries.append({
            'id': str(dup_person.id),
            'surname': dup_person.surname,
            'first_name': dup_person.first_name,
            'birth_date': dup_person.birth_date.isoformat() if dup_person.birth_date else None,
            'primary_document': primary_alias.document_number if primary_alias else None,
            'similarity_score': dup['similarity_score'],
            'match_criteria': dup['match_criteria']
        })
    
    return PersonDuplicateCheckResponse(
        person_id=person_id,
        potential_duplicates=duplicate_summaries,
        similarity_threshold=threshold
    )


# Person Alias (Document) endpoints
@router.post("/{person_id}/aliases", response_model=PersonAliasResponse, status_code=status.HTTP_201_CREATED)
def create_person_alias(
    *,
    db: Session = Depends(get_db),
    person_id: UUID,
    alias_in: PersonAliasCreate,
    current_user: User = Depends(require_permission("person_aliases.create"))
) -> PersonAliasResponse:
    """
    Add identification document to person
    Requires person_aliases.create permission
    """
    person = crud_person.person.get(db=db, id=person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found"
        )
    
    # Check if document number already exists
    existing_alias = crud_person.person_alias.get_by_document_number(
        db=db, 
        document_number=alias_in.document_number,
        document_type=alias_in.document_type
    )
    if existing_alias:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document number already exists"
        )
    
    alias = crud_person.person_alias.create_for_person(
        db=db, 
        obj_in=alias_in, 
        person_id=person_id,
        created_by=str(current_user.id)
    )
    
    return alias


@router.get("/{person_id}/aliases", response_model=List[PersonAliasResponse])
def get_person_aliases(
    *,
    db: Session = Depends(get_db),
    person_id: UUID,
    current_user: User = Depends(require_permission("person_aliases.read"))
) -> List[PersonAliasResponse]:
    """
    Get all identification documents for person
    Requires person_aliases.read permission
    """
    person = crud_person.person.get(db=db, id=person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found"
        )
    
    aliases = crud_person.person_alias.get_person_aliases(db=db, person_id=person_id)
    return aliases


@router.put("/{person_id}/aliases/{alias_id}", response_model=PersonAliasResponse)
def update_person_alias(
    *,
    db: Session = Depends(get_db),
    person_id: UUID,
    alias_id: UUID,
    alias_update: PersonAliasUpdate,
    current_user: User = Depends(require_permission("person_aliases.update"))
) -> PersonAliasResponse:
    """
    Update person identification document
    Requires person_aliases.update permission
    """
    alias = crud_person.person_alias.get(db=db, id=alias_id)
    if not alias or alias.person_id != person_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alias not found"
        )
    
    updated_alias = crud_person.person_alias.update(
        db=db, 
        db_obj=alias, 
        obj_in=alias_update,
        updated_by=current_user.username
    )
    
    return updated_alias


@router.put("/{person_id}/aliases/{alias_id}/set-primary", response_model=PersonAliasResponse)
def set_primary_alias(
    *,
    db: Session = Depends(get_db),
    person_id: UUID,
    alias_id: UUID,
    current_user: User = Depends(require_permission("person_aliases.set_primary"))
) -> PersonAliasResponse:
    """
    Set identification document as primary for person
    Requires person_aliases.set_primary permission
    """
    alias = crud_person.person_alias.get(db=db, id=alias_id)
    if not alias or alias.person_id != person_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alias not found"
        )
    
    updated_alias = crud_person.person_alias.set_primary(
        db=db, 
        alias_id=alias_id,
        updated_by=current_user.username
    )
    
    return updated_alias


@router.delete("/{person_id}/aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person_alias(
    *,
    db: Session = Depends(get_db),
    person_id: UUID,
    alias_id: UUID,
    current_user: User = Depends(require_permission("person_aliases.delete"))
) -> None:
    """
    Delete person identification document
    Requires person_aliases.delete permission (Supervisor+ only)
    """
    alias = crud_person.person_alias.get(db=db, id=alias_id)
    if not alias or alias.person_id != person_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alias not found"
        )
    
    # TODO: Prevent deletion of primary document if it's the only one
    # person_aliases = crud_person.person_alias.get_person_aliases(db=db, person_id=person_id)
    # if len(person_aliases) == 1:
    #     raise HTTPException(
    #         status_code=status.HTTP_400_BAD_REQUEST,
    #         detail="Cannot delete the only identification document"
    #     )
    
    crud_person.person_alias.remove(db=db, id=alias_id)


# Person Address endpoints
@router.post("/{person_id}/addresses", response_model=PersonAddressResponse, status_code=status.HTTP_201_CREATED)
def create_person_address(
    *,
    db: Session = Depends(get_db),
    person_id: UUID,
    address_in: PersonAddressCreate,
    current_user: User = Depends(require_permission("person_addresses.create"))
) -> PersonAddressResponse:
    """
    Add address to person
    Requires person_addresses.create permission
    """
    person = crud_person.person.get(db=db, id=person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found"
        )
    
    address = crud_person.person_address.create_for_person(
        db=db, 
        obj_in=address_in, 
        person_id=person_id,
        created_by=str(current_user.id)
    )
    
    return address


@router.get("/{person_id}/addresses", response_model=List[PersonAddressResponse])
def get_person_addresses(
    *,
    db: Session = Depends(get_db),
    person_id: UUID,
    current_user: User = Depends(require_permission("person_addresses.read")),
    address_type: Optional[str] = Query(None, description="Filter by address type")
) -> List[PersonAddressResponse]:
    """
    Get all addresses for person, optionally filtered by type
    Requires person_addresses.read permission
    """
    person = crud_person.person.get(db=db, id=person_id)
    if not person:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Person not found"
        )
    
    addresses = crud_person.person_address.get_person_addresses(
        db=db, 
        person_id=person_id,
        address_type=address_type
    )
    return addresses


@router.put("/{person_id}/addresses/{address_id}", response_model=PersonAddressResponse)
def update_person_address(
    *,
    db: Session = Depends(get_db),
    person_id: UUID,
    address_id: UUID,
    address_update: PersonAddressUpdate,
    current_user: User = Depends(require_permission("person_addresses.update"))
) -> PersonAddressResponse:
    """
    Update person address
    Requires person_addresses.update permission
    """
    address = crud_person.person_address.get(db=db, id=address_id)
    if not address or address.person_id != person_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    updated_address = crud_person.person_address.update(
        db=db, 
        db_obj=address, 
        obj_in=address_update,
        updated_by=current_user.username
    )
    
    return updated_address


@router.put("/{person_id}/addresses/{address_id}/set-primary", response_model=PersonAddressResponse)
def set_primary_address(
    *,
    db: Session = Depends(get_db),
    person_id: UUID,
    address_id: UUID,
    current_user: User = Depends(require_permission("person_addresses.set_primary"))
) -> PersonAddressResponse:
    """
    Set address as primary for its type
    Requires person_addresses.set_primary permission
    """
    address = crud_person.person_address.get(db=db, id=address_id)
    if not address or address.person_id != person_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    updated_address = crud_person.person_address.set_primary(
        db=db, 
        address_id=address_id,
        updated_by=current_user.username
    )
    
    return updated_address


@router.delete("/{person_id}/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person_address(
    *,
    db: Session = Depends(get_db),
    person_id: UUID,
    address_id: UUID,
    current_user: User = Depends(require_permission("person_addresses.delete"))
) -> None:
    """
    Delete person address
    Requires person_addresses.delete permission (Supervisor+ only)
    """
    address = crud_person.person_address.get(db=db, id=address_id)
    if not address or address.person_id != person_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    crud_person.person_address.remove(db=db, id=address_id)


# TODO: Add bulk operations when needed
# @router.post("/bulk-import", response_model=PersonBulkImportResponse)
# def bulk_import_persons(
#     *,
#     db: Session = Depends(get_db),
#     import_data: PersonBulkImportRequest,
#     current_user: User = Depends(require_permission("persons.bulk_import"))
# ) -> PersonBulkImportResponse:
#     """
#     Bulk import persons from data migration
#     Admin only operation
#     """
#     pass

# TODO: Add advanced search with fuzzy matching
# @router.post("/advanced-search", response_model=List[PersonSummary])
# def advanced_search_persons(
#     *,
#     db: Session = Depends(get_db),
#     search_criteria: AdvancedSearchRequest,
#     current_user: User = Depends(require_permission("persons.advanced_search"))
# ) -> List[PersonSummary]:
#     """
#     Advanced search with fuzzy matching and similarity scoring
#     """
#     pass 