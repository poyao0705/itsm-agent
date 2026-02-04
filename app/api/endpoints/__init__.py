from .github import router as github_router
from .health import router as health_router

__all__ = ["github_router", "health_router"]
