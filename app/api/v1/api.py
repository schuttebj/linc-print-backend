"""
Main API Router for Madagascar License System v1
Includes all endpoint routers
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, roles, permissions, persons, locations, lookups, audit, applications, licenses, cards

# Create main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(roles.router, prefix="/roles", tags=["Roles"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["Permissions"])
api_router.include_router(persons.router, prefix="/persons", tags=["Persons"])
api_router.include_router(locations.router, prefix="/locations", tags=["Locations"])
api_router.include_router(applications.router, prefix="/applications", tags=["Applications"])
api_router.include_router(licenses.router, prefix="/licenses", tags=["Licenses"])
api_router.include_router(cards.router, prefix="/cards", tags=["Cards"])
api_router.include_router(lookups.router, prefix="/lookups", tags=["Lookups"])
api_router.include_router(audit.router, prefix="/audit", tags=["Audit Logs"]) 