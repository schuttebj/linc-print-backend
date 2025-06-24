"""
Main API Router for Madagascar License System v1
Includes all endpoint routers
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, roles, permissions, persons, locations

# Create main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(roles.router, prefix="/roles", tags=["Roles"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["Permissions"])
api_router.include_router(persons.router, prefix="/persons", tags=["Persons"])
api_router.include_router(locations.router, prefix="/locations", tags=["Locations"]) 