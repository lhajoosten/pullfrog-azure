from fastapi import APIRouter
from pullfrog_azure_api.api.routes.authentication import router as authentication_router
from pullfrog_azure_api.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(authentication_router)
