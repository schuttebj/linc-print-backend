"""
CRUD operations for Person Management - Madagascar Implementation
Database operations for natural persons, aliases, and addresses
Includes search functionality and duplicate detection preparation
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, case, desc
from uuid import UUID
import difflib
from datetime import date

from app.crud.base import CRUDBase
from app.models.person import Person, PersonAlias, PersonAddress
from app.schemas.person import (
    PersonCreate, PersonUpdate, PersonSearchRequest,
    PersonAliasCreate, PersonAliasUpdate,
    PersonAddressCreate, PersonAddressUpdate
)


def capitalize_person_data(person: Person) -> Person:
    """
    Ensure all text fields in person data are capitalized
    Applies to both the person and related aliases/addresses
    """
    if not person:
        return person
    
    # Capitalize person text fields
    if person.surname:
        person.surname = person.surname.upper()
    if person.first_name:
        person.first_name = person.first_name.upper()
    if person.middle_name:
        person.middle_name = person.middle_name.upper()
    if person.person_nature:
        person.person_nature = person.person_nature.upper()
    if person.nationality_code:
        person.nationality_code = person.nationality_code.upper()
    if person.preferred_language:
        person.preferred_language = person.preferred_language.lower()  # Language codes stay lowercase
    if person.email_address:
        person.email_address = person.email_address.upper()
    
    # Capitalize alias text fields
    for alias in person.aliases:
        if alias.document_type:
            alias.document_type = alias.document_type.upper()
        if alias.document_number:
            alias.document_number = alias.document_number.upper()
        if alias.country_of_issue:
            alias.country_of_issue = alias.country_of_issue.upper()
        if alias.name_in_document:
            alias.name_in_document = alias.name_in_document.upper()
    
    # Capitalize address text fields
    for address in person.addresses:
        if address.address_type:
            address.address_type = address.address_type.upper()
        if address.street_line1:
            address.street_line1 = address.street_line1.upper()
        if address.street_line2:
            address.street_line2 = address.street_line2.upper()
        if address.locality:
            address.locality = address.locality.upper()
        if address.town:
            address.town = address.town.upper()
        if address.country:
            address.country = address.country.upper()
        if address.province_code:
            address.province_code = address.province_code.upper()
    
    return person


class CRUDPerson(CRUDBase[Person, PersonCreate, PersonUpdate]):
    """CRUD operations for Person entities"""
    
    def create_with_details(
        self, 
        db: Session, 
        *, 
        obj_in: PersonCreate,
        created_by: Optional[str] = None
    ) -> Person:
        """
        Create person with aliases and addresses - ALL CAPITALIZED
        Handles primary document/address validation
        """
        # Create person record
        person_data = obj_in.dict(exclude={'aliases', 'addresses'})
        person_data['created_by'] = created_by
        person_data['updated_by'] = created_by
        
        db_person = Person(**person_data)
        db.add(db_person)
        db.flush()  # Get the person ID
        
        # Create aliases (identification documents)
        if obj_in.aliases:
            for alias_data in obj_in.aliases:
                alias_dict = alias_data.dict()
                alias_dict['person_id'] = db_person.id
                alias_dict['created_by'] = created_by
                alias_dict['updated_by'] = created_by
                
                db_alias = PersonAlias(**alias_dict)
                db.add(db_alias)
        
        # Create addresses
        if obj_in.addresses:
            for address_data in obj_in.addresses:
                address_dict = address_data.dict()
                address_dict['person_id'] = db_person.id
                address_dict['created_by'] = created_by
                address_dict['updated_by'] = created_by
                
                db_address = PersonAddress(**address_dict)
                db.add(db_address)
        
        db.commit()
        db.refresh(db_person)
        
        # Ensure returned data is capitalized
        db_person = capitalize_person_data(db_person)
        
        return db_person
    
    def get_with_details(self, db: Session, id: UUID) -> Optional[Person]:
        """Get person with all related data (aliases and addresses) - ALL CAPITALIZED"""
        person = db.query(Person).options(
            joinedload(Person.aliases),
            joinedload(Person.addresses)
        ).filter(Person.id == id).first()
        
        if person:
            person = capitalize_person_data(person)
        
        return person
    
    def search_persons(
        self, 
        db: Session, 
        *, 
        search_params: PersonSearchRequest
    ) -> Tuple[List[Person], int]:
        """
        Advanced person search with multiple criteria - ALL CAPITALIZED RESULTS
        Returns (results, total_count)
        """
        query = db.query(Person).options(
            joinedload(Person.aliases),
            joinedload(Person.addresses)
        )
        
        # Apply filters
        if search_params.surname:
            query = query.filter(Person.surname.ilike(f"%{search_params.surname.upper()}%"))
        
        if search_params.first_name:
            query = query.filter(Person.first_name.ilike(f"%{search_params.first_name.upper()}%"))
        
        if search_params.birth_date:
            query = query.filter(Person.birth_date == search_params.birth_date)
        
        if search_params.nationality_code:
            query = query.filter(Person.nationality_code == search_params.nationality_code.upper())
        
        if search_params.is_active is not None:
            query = query.filter(Person.is_active == search_params.is_active)
        
        # Search by document number and/or type (single join with aliases)
        alias_filters = []
        if search_params.document_number:
            alias_filters.append(
                PersonAlias.document_number.ilike(f"%{search_params.document_number.upper()}%")
            )
        if search_params.document_type:
            alias_filters.append(
                PersonAlias.document_type == search_params.document_type.upper()
            )
        
        if alias_filters:
            query = query.join(PersonAlias).filter(and_(*alias_filters))
        
        # Search by address locality
        if search_params.locality:
            query = query.join(PersonAddress).filter(
                PersonAddress.locality.ilike(f"%{search_params.locality.upper()}%")
            )
        
        # Search by phone number
        if search_params.phone_number:
            phone_filter = or_(
                Person.cell_phone.ilike(f"%{search_params.phone_number}%"),
                Person.work_phone.ilike(f"%{search_params.phone_number}%")
            )
            query = query.filter(phone_filter)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination and ordering
        query = query.order_by(Person.surname, Person.first_name)
        query = query.offset(search_params.skip).limit(search_params.limit)
        
        results = query.all()
        
        # Capitalize all results
        results = [capitalize_person_data(person) for person in results]
        
        return results, total_count
    
    def find_potential_duplicates(
        self, 
        db: Session, 
        *, 
        person: Person,
        threshold: float = 70.0
    ) -> List[Dict[str, Any]]:
        """
        Find potential duplicate persons using similarity scoring
        Based on birth_date, surname, first_name, address, and phone
        """
        # TODO: Implement comprehensive duplicate detection algorithm
        # For now, implement basic matching on key fields
        
        potential_duplicates = []
        
        # Get all other active persons
        other_persons = db.query(Person).options(
            joinedload(Person.aliases),
            joinedload(Person.addresses)
        ).filter(
            Person.id != person.id,
            Person.is_active == True
        ).all()
        
        for other_person in other_persons:
            similarity_score = self._calculate_similarity_score(person, other_person)
            
            if similarity_score >= threshold:
                potential_duplicates.append({
                    'person': other_person,
                    'similarity_score': similarity_score,
                    'match_criteria': self._get_match_criteria(person, other_person)
                })
        
        # Sort by similarity score (highest first)
        potential_duplicates.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        return potential_duplicates
    
    def _calculate_similarity_score(self, person1: Person, person2: Person) -> float:
        """
        Calculate similarity score between two persons
        TODO: Enhance with more sophisticated algorithms (fuzzy matching, phonetic similarity)
        """
        score = 0.0
        total_weight = 0.0
        
        # Birth date match (weight: 30%)
        birth_weight = 30.0
        if person1.birth_date and person2.birth_date:
            if person1.birth_date == person2.birth_date:
                score += birth_weight
            total_weight += birth_weight
        
        # Surname similarity (weight: 25%)
        surname_weight = 25.0
        if person1.surname and person2.surname:
            surname_similarity = difflib.SequenceMatcher(
                None, person1.surname.lower(), person2.surname.lower()
            ).ratio() * 100
            score += (surname_similarity * surname_weight / 100)
            total_weight += surname_weight
        
        # First name similarity (weight: 20%)
        fname_weight = 20.0
        if person1.first_name and person2.first_name:
            fname_similarity = difflib.SequenceMatcher(
                None, person1.first_name.lower(), person2.first_name.lower()
            ).ratio() * 100
            score += (fname_similarity * fname_weight / 100)
            total_weight += fname_weight
        
        # Phone number match (weight: 15%)
        phone_weight = 15.0
        if person1.cell_phone and person2.cell_phone:
            if person1.cell_phone == person2.cell_phone:
                score += phone_weight
            total_weight += phone_weight
        
        # Address similarity (weight: 10%)
        address_weight = 10.0
        if person1.addresses and person2.addresses:
            # Compare primary residential addresses
            addr1 = next((a for a in person1.addresses if a.address_type == 'residential' and a.is_primary), None)
            addr2 = next((a for a in person2.addresses if a.address_type == 'residential' and a.is_primary), None)
            
            if addr1 and addr2:
                if addr1.locality.lower() == addr2.locality.lower():
                    score += address_weight
                total_weight += address_weight
        
        # Return percentage score
        return (score / total_weight) * 100 if total_weight > 0 else 0.0
    
    def _get_match_criteria(self, person1: Person, person2: Person) -> Dict[str, bool]:
        """Get detailed match criteria for duplicate analysis"""
        criteria = {
            'birth_date_match': False,
            'surname_match': False,
            'first_name_similar': False,
            'phone_match': False,
            'address_similar': False
        }
        
        # Birth date
        if person1.birth_date and person2.birth_date:
            criteria['birth_date_match'] = person1.birth_date == person2.birth_date
        
        # Surname
        if person1.surname and person2.surname:
            criteria['surname_match'] = person1.surname.lower() == person2.surname.lower()
        
        # First name similarity (>80%)
        if person1.first_name and person2.first_name:
            similarity = difflib.SequenceMatcher(
                None, person1.first_name.lower(), person2.first_name.lower()
            ).ratio()
            criteria['first_name_similar'] = similarity > 0.8
        
        # Phone match
        if person1.cell_phone and person2.cell_phone:
            criteria['phone_match'] = person1.cell_phone == person2.cell_phone
        
        # Address similarity
        if person1.addresses and person2.addresses:
            addr1 = next((a for a in person1.addresses if a.address_type == 'residential' and a.is_primary), None)
            addr2 = next((a for a in person2.addresses if a.address_type == 'residential' and a.is_primary), None)
            
            if addr1 and addr2:
                criteria['address_similar'] = addr1.locality.lower() == addr2.locality.lower()
        
        return criteria


class CRUDPersonAlias(CRUDBase[PersonAlias, PersonAliasCreate, PersonAliasUpdate]):
    """CRUD operations for Person Aliases (identification documents)"""
    
    def create_for_person(
        self, 
        db: Session, 
        *, 
        obj_in: PersonAliasCreate, 
        person_id: UUID,
        created_by: Optional[str] = None
    ) -> PersonAlias:
        """Create alias for specific person"""
        alias_data = obj_in.dict()
        alias_data['person_id'] = person_id
        alias_data['created_by'] = created_by
        alias_data['updated_by'] = created_by
        
        # If this is marked as primary, unset other primary documents
        if alias_data.get('is_primary', False):
            db.query(PersonAlias).filter(
                PersonAlias.person_id == person_id,
                PersonAlias.is_primary == True
            ).update({'is_primary': False, 'updated_by': created_by})
        
        db_alias = PersonAlias(**alias_data)
        db.add(db_alias)
        db.commit()
        db.refresh(db_alias)
        return db_alias
    
    def get_by_document_number(
        self, 
        db: Session, 
        *, 
        document_number: str, 
        document_type: Optional[str] = None
    ) -> Optional[PersonAlias]:
        """Find alias by document number and optionally type"""
        query = db.query(PersonAlias).filter(PersonAlias.document_number == document_number)
        if document_type:
            query = query.filter(PersonAlias.document_type == document_type)
        return query.first()
    
    def get_person_aliases(self, db: Session, *, person_id: UUID) -> List[PersonAlias]:
        """Get all aliases for a person"""
        return db.query(PersonAlias).filter(PersonAlias.person_id == person_id).all()
    
    def set_primary(
        self, 
        db: Session, 
        *, 
        alias_id: UUID, 
        updated_by: Optional[str] = None
    ) -> PersonAlias:
        """Set an alias as primary (unsets others for same person)"""
        alias = db.query(PersonAlias).filter(PersonAlias.id == alias_id).first()
        if not alias:
            raise ValueError("Alias not found")
        
        # Unset other primary documents for this person
        db.query(PersonAlias).filter(
            PersonAlias.person_id == alias.person_id,
            PersonAlias.is_primary == True
        ).update({'is_primary': False, 'updated_by': updated_by})
        
        # Set this one as primary
        alias.is_primary = True
        alias.updated_by = updated_by
        db.commit()
        db.refresh(alias)
        return alias


class CRUDPersonAddress(CRUDBase[PersonAddress, PersonAddressCreate, PersonAddressUpdate]):
    """CRUD operations for Person Addresses"""
    
    def create_for_person(
        self, 
        db: Session, 
        *, 
        obj_in: PersonAddressCreate, 
        person_id: UUID,
        created_by: Optional[str] = None
    ) -> PersonAddress:
        """Create address for specific person"""
        address_data = obj_in.dict()
        address_data['person_id'] = person_id
        address_data['created_by'] = created_by
        address_data['updated_by'] = created_by
        
        # If this is marked as primary, unset other primary addresses of same type
        if address_data.get('is_primary', False):
            db.query(PersonAddress).filter(
                PersonAddress.person_id == person_id,
                PersonAddress.address_type == address_data['address_type'],
                PersonAddress.is_primary == True
            ).update({'is_primary': False, 'updated_by': created_by})
        
        db_address = PersonAddress(**address_data)
        db.add(db_address)
        db.commit()
        db.refresh(db_address)
        return db_address
    
    def get_person_addresses(
        self, 
        db: Session, 
        *, 
        person_id: UUID, 
        address_type: Optional[str] = None
    ) -> List[PersonAddress]:
        """Get addresses for a person, optionally filtered by type"""
        query = db.query(PersonAddress).filter(PersonAddress.person_id == person_id)
        if address_type:
            query = query.filter(PersonAddress.address_type == address_type)
        return query.all()
    
    def set_primary(
        self, 
        db: Session, 
        *, 
        address_id: UUID, 
        updated_by: Optional[str] = None
    ) -> PersonAddress:
        """Set an address as primary for its type (unsets others of same type)"""
        address = db.query(PersonAddress).filter(PersonAddress.id == address_id).first()
        if not address:
            raise ValueError("Address not found")
        
        # Unset other primary addresses of same type for this person
        db.query(PersonAddress).filter(
            PersonAddress.person_id == address.person_id,
            PersonAddress.address_type == address.address_type,
            PersonAddress.is_primary == True
        ).update({'is_primary': False, 'updated_by': updated_by})
        
        # Set this one as primary
        address.is_primary = True
        address.updated_by = updated_by
        db.commit()
        db.refresh(address)
        return address


# Create instances
person = CRUDPerson(Person)
person_alias = CRUDPersonAlias(PersonAlias)
person_address = CRUDPersonAddress(PersonAddress)


# TODO: Add duplicate detection service when ready
# class DuplicateDetectionService:
#     """
#     Advanced duplicate detection service
#     TODO: Implement when needed with:
#     - Fuzzy string matching (fuzzywuzzy)
#     - Phonetic similarity (soundex, metaphone)
#     - Address normalization
#     - Machine learning similarity scoring
#     """
#     
#     def __init__(self, threshold: float = 70.0):
#         self.threshold = threshold
#     
#     def find_duplicates(self, db: Session, person: Person) -> List[Dict]:
#         """Advanced duplicate detection with ML scoring"""
#         pass
#     
#     def auto_merge_duplicates(self, db: Session, person1_id: UUID, person2_id: UUID) -> Person:
#         """Automatically merge duplicate persons"""
#         pass 