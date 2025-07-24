"""
Main API Router for Madagascar License System v1
Includes all endpoint routers
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth, admin, persons, applications, licenses, cards, locations, 
    lookup, audit, printing, transactions, test_card_design
)

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(persons.router, prefix="/persons", tags=["Persons"])
api_router.include_router(applications.router, prefix="/applications", tags=["Applications"])
api_router.include_router(licenses.router, prefix="/licenses", tags=["Licenses"])
api_router.include_router(cards.router, prefix="/cards", tags=["Cards"])
api_router.include_router(locations.router, prefix="/locations", tags=["Locations"])
api_router.include_router(lookup.router, prefix="/lookups", tags=["Lookups"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit"])
api_router.include_router(printing.router, prefix="/printing", tags=["Printing"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["Transactions"])

# Test endpoints (only for development)
api_router.include_router(test_card_design.router, prefix="/test-card", tags=["Test Card Design"]) 