"""
Web Router - HTMX / Template responses

All routes that return HTML (full pages or partials) live here.
This keeps the API layer clean for pure JSON endpoints.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Query
from fastapi.templating import Jinja2Templates
from sqlmodel.ext.asyncio.session import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.dependencies.database import get_db
from app.services.change_management.evaluations import EvaluationService

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

SessionDep = Annotated[AsyncSession, Depends(get_db)]


def get_evaluation_service(session: SessionDep) -> EvaluationService:
    """Get evaluation service (Dependency Injection)."""
    return EvaluationService(session)


# -----------------------------------------------------------------------------
# Page Routes
# -----------------------------------------------------------------------------


@router.get("/")
async def root(request: Request, db: AsyncSession = Depends(get_db)):
    service = EvaluationService(db)
    evals = await service.get_evaluations(limit=5)

    # If HTMX request, return the dashboard partial
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/dashboard.html", {"request": request, "evaluations": evals}
        )

    # Full page load
    return templates.TemplateResponse(
        "index.html", {"request": request, "evaluations": evals}
    )


@router.get("/evaluations")
async def evaluations_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    service = EvaluationService(db)
    skip = (page - 1) * page_size
    evals = await service.get_evaluations(skip=skip, limit=page_size)
    total_count = await service.count_evaluations()
    total_pages = (total_count + page_size - 1) // page_size

    context = {
        "request": request,
        "evaluations": evals,
        "page": page,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }

    # If HTMX request, return the evaluations list partial
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/evaluations_list.html", context)

    # Full page load
    return templates.TemplateResponse("evaluations.html", context)


# -----------------------------------------------------------------------------
# SSE Streams (HTML fragment updates)
# -----------------------------------------------------------------------------


@router.get("/evaluations/sse-stream")
async def sse_stream(request: Request):
    """
    SSE stream that reads from in-memory cache.
    Zero DB load per client - all clients share cached data.
    SSE clients wait on an asyncio.Condition inside the cache,
    so they are only woken *after* the cache updater has written
    fresh data (no race with the notifier signal).
    """
    from app.core.evaluation_cache import get_evaluation_cache
    import asyncio

    async def event_generator():
        cache = get_evaluation_cache()
        last_version = 0

        # Send initial data from cache
        cached = await cache.get()
        if cached:
            yield {"event": "eval-update", "data": cached.html}
            last_version = cached.version
        else:
            # Cache not initialized yet, wait a bit
            await asyncio.sleep(0.5)
            cached = await cache.get()
            if cached:
                yield {"event": "eval-update", "data": cached.html}
                last_version = cached.version
            else:
                yield {"event": "error", "data": "Cache not ready"}

        # Wait for cache updates (condition is signalled by cache_updater)
        while True:
            if await request.is_disconnected():
                break

            updated = await cache.wait_for_update(last_version, timeout=15.0)
            if updated:
                cached = await cache.get()
                if cached:
                    yield {"event": "eval-update", "data": cached.html}
                    last_version = cached.version
            else:
                # Timeout — send keep-alive
                yield {"comment": "keep-alive"}

    return EventSourceResponse(event_generator())
