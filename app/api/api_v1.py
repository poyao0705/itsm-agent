from fastapi import APIRouter
from app.api.endpoints import github_router

router = APIRouter()

router.include_router(github_router, prefix="/github", tags=["github"])
