"""
Main API Router for Madagascar License System v1
Includes all endpoint routers
"""

from fastapi import APIRouter

# Import endpoints individually to avoid any import issues
from app.api.v1.endpoints import auth
from app.api.v1.endpoints import users  
from app.api.v1.endpoints import roles
from app.api.v1.endpoints import permissions
from app.api.v1.endpoints import persons
from app.api.v1.endpoints import applications
from app.api.v1.endpoints import licenses
from app.api.v1.endpoints import cards
from app.api.v1.endpoints import locations
from app.api.v1.endpoints import lookups
from app.api.v1.endpoints import audit
from app.api.v1.endpoints import printing
from app.api.v1.endpoints import transactions
from app.api.v1.endpoints import test_card_design

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(roles.router, prefix="/roles", tags=["Roles"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["Permissions"])
api_router.include_router(persons.router, prefix="/persons", tags=["Persons"])
api_router.include_router(applications.router, prefix="/applications", tags=["Applications"])
api_router.include_router(licenses.router, prefix="/licenses", tags=["Licenses"])
api_router.include_router(cards.router, prefix="/cards", tags=["Cards"])
api_router.include_router(locations.router, prefix="/locations", tags=["Locations"])
api_router.include_router(lookups.router, prefix="/lookups", tags=["Lookups"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_router.include_router(printing.router, prefix="/printing", tags=["Printing"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])
api_router.include_router(test_card_design.router, prefix="/test-card", tags=["Test Card Design"]) 