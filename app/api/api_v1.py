from fastapi import APIRouter
from app.api.endpoints import github_router
from app.api.endpoints import health_router

router = APIRouter()

router.include_router(github_router, prefix="/github", tags=["github"])
router.include_router(health_router, prefix="/health", tags=["health"])
