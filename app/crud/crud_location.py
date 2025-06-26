"""
Location CRUD Operations for Madagascar License System
Handles location creation, updates, queries, and user code generation
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from uuid import UUID

from app.crud.base import CRUDBase
from app.models.user import Location, User
from app.schemas.location import LocationCreate, LocationUpdate


class CRUDLocation(CRUDBase[Location, LocationCreate, LocationUpdate]):
    """CRUD operations for Location"""

    def create_with_codes(
        self, 
        db: Session, 
        *, 
        obj_in: LocationCreate,
        created_by: Optional[str] = None
    ) -> Location:
        """Create location with auto-generated codes"""
        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"CRUD received province_code: {obj_in.province_code} (type: {type(obj_in.province_code)})")
        logger.info(f"CRUD received office_type: {obj_in.office_type} (type: {type(obj_in.office_type)})")
        
        # Generate location codes
        code = f"{obj_in.province_code.value}{obj_in.office_number}"
        full_code = f"MG-{code}"
        
        logger.info(f"Generated code: {code}")
        logger.info(f"Generated full_code: {full_code}")
        
        # Get province name mapping
        province_names = {
            "T": "ANTANANARIVO",
            "D": "ANTSIRANANA", 
            "F": "FIANARANTSOA",
            "M": "MAHAJANGA",
            "A": "TOAMASINA",
            "U": "TOLIARA"
        }
        
        province_name = province_names.get(obj_in.province_code.value, "UNKNOWN")
        
        # Create location object
        location_data = obj_in.dict()
        location_data.update({
            "code": code,
            "full_code": full_code,
            "province_code": obj_in.province_code.value,
            "office_type": obj_in.office_type.value,
            "province_name": province_name,
            "next_user_number": 1,
            "current_staff_count": 0,
            "is_active": True
        })
        
        if created_by:
            location_data["created_by"] = created_by
            location_data["updated_by"] = created_by
        
        db_obj = Location(**location_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        
        return db_obj

    def get_by_code(self, db: Session, *, code: str) -> Optional[Location]:
        """Get location by short code (e.g., T01)"""
        return db.query(Location).filter(
            Location.code == code.upper(),
            Location.is_active == True
        ).first()

    def get_by_full_code(self, db: Session, *, full_code: str) -> Optional[Location]:
        """Get location by full code (e.g., MG-T01)"""
        return db.query(Location).filter(
            Location.full_code == full_code.upper(),
            Location.is_active == True
        ).first()

    def get_by_province(
        self, 
        db: Session, 
        *, 
        province_code: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Location]:
        """Get locations by province code"""
        return db.query(Location).filter(
            Location.province_code == province_code.upper(),
            Location.is_active == True
        ).offset(skip).limit(limit).all()

    def get_operational_locations(self, db: Session) -> List[Location]:
        """Get all operational locations"""
        return db.query(Location).filter(
            Location.is_active == True,
            Location.is_operational == True
        ).order_by(Location.province_code, Location.office_number).all()

    def search_locations(
        self,
        db: Session,
        *,
        search: Optional[str] = None,
        province_code: Optional[str] = None,
        office_type: Optional[str] = None,
        is_operational: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[Location], int]:
        """Search locations with filters"""
        query = db.query(Location).filter(Location.is_active == True)
        
        # Text search
        if search:
            search_term = f"%{search.upper()}%"
            query = query.filter(
                or_(
                    Location.name.ilike(search_term),
                    Location.locality.ilike(search_term),
                    Location.code.ilike(search_term),
                    Location.full_code.ilike(search_term)
                )
            )
        
        # Province filter
        if province_code:
            query = query.filter(Location.province_code == province_code.upper())
        
        # Office type filter
        if office_type:
            query = query.filter(Location.office_type == office_type.upper())
        
        # Operational status filter
        if is_operational is not None:
            query = query.filter(Location.is_operational == is_operational)
        
        # Get total count
        total = query.count()
        
        # Apply pagination and ordering
        locations = query.order_by(
            Location.province_code, 
            Location.office_number
        ).offset(skip).limit(limit).all()
        
        return locations, total

    def get_location_statistics(self, db: Session) -> Dict[str, Any]:
        """Get location statistics"""
        # Total locations
        total_locations = db.query(Location).filter(Location.is_active == True).count()
        
        # Operational locations
        operational_locations = db.query(Location).filter(
            Location.is_active == True,
            Location.is_operational == True
        ).count()
        
        # Locations by province
        province_stats = db.query(
            Location.province_code,
            func.count(Location.id).label('count')
        ).filter(Location.is_active == True).group_by(Location.province_code).all()
        
        locations_by_province = {stat.province_code: stat.count for stat in province_stats}
        
        # Locations by type
        type_stats = db.query(
            Location.office_type,
            func.count(Location.id).label('count')
        ).filter(Location.is_active == True).group_by(Location.office_type).all()
        
        locations_by_type = {stat.office_type: stat.count for stat in type_stats}
        
        # Staff capacity
        capacity_stats = db.query(
            func.sum(Location.max_staff_capacity).label('total_capacity'),
            func.sum(Location.current_staff_count).label('current_staff')
        ).filter(Location.is_active == True).first()
        
        total_staff_capacity = capacity_stats.total_capacity or 0
        total_current_staff = capacity_stats.current_staff or 0
        
        capacity_utilization = 0.0
        if total_staff_capacity > 0:
            capacity_utilization = (total_current_staff / total_staff_capacity) * 100
        
        return {
            "total_locations": total_locations,
            "operational_locations": operational_locations,
            "locations_by_province": locations_by_province,
            "locations_by_type": locations_by_type,
            "total_staff_capacity": total_staff_capacity,
            "total_current_staff": total_current_staff,
            "capacity_utilization": round(capacity_utilization, 2)
        }

    def generate_next_user_code(self, db: Session, *, location_id: UUID) -> Dict[str, Any]:
        """Generate next user code for location"""
        location = db.query(Location).filter(
            Location.id == location_id,
            Location.is_active == True
        ).first()
        
        if not location:
            raise ValueError("Location not found")
        
        # Check capacity
        if location.next_user_number > 9999:
            raise ValueError("Location has reached maximum user capacity (9999)")
        
        # Generate user code
        user_code = f"{location.code}{location.next_user_number:04d}"
        
        # Update next user number
        location.next_user_number += 1
        db.commit()
        db.refresh(location)
        
        remaining_capacity = 9999 - location.next_user_number + 1
        
        return {
            "location_id": location_id,
            "location_code": location.code,
            "next_user_code": user_code,
            "user_number": location.next_user_number - 1,
            "remaining_capacity": remaining_capacity
        }

    def get_by_location_id(self, db: Session, *, location_id: UUID) -> Optional[Location]:
        """Get location by ID"""
        return db.query(Location).filter(
            Location.id == location_id,
            Location.is_active == True
        ).first()

    def update_staff_count(self, db: Session, *, location_id: UUID, staff_count: int) -> Location:
        """Update current staff count for location"""
        location = self.get_by_location_id(db=db, location_id=location_id)
        if not location:
            raise ValueError("Location not found")
        
        location.current_staff_count = staff_count
        db.commit()
        db.refresh(location)
        
        return location

    def get_province_offices(self, db: Session, *, province_code: str) -> List[Location]:
        """Get all offices in a province"""
        return db.query(Location).filter(
            Location.province_code == province_code.upper(),
            Location.is_active == True
        ).order_by(Location.office_number).all()

    def check_office_number_available(
        self, 
        db: Session, 
        *, 
        province_code: str, 
        office_number: str
    ) -> bool:
        """Check if office number is available in province"""
        existing = db.query(Location).filter(
            Location.province_code == province_code.upper(),
            Location.office_number == office_number,
            Location.is_active == True
        ).first()
        
        return existing is None


# Create instance
location = CRUDLocation(Location) 