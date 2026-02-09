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
from app.db.session import AsyncSessionLocal
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
    """SSE stream that pushes updated evaluation rows via BroadcastService."""
    from app.core import broadcast
    import asyncio

    async def event_generator():
        # We use the context manager for robust cleanup
        async with broadcast.subscribe(broadcast.STREAM_KEY) as queue:

            # 1. Send initial snapshot (State Synchronization)
            # Use short-lived session to avoid pinning connection for long stream
            async with AsyncSessionLocal() as session:
                service = EvaluationService(session)
                initial_evals = await service.get_evaluations(limit=5)

            html = (
                templates.get_template("partials/evaluations_latest.html")
                .render({"request": request, "evaluations": initial_evals})
                .replace("\n", "")
            )
            yield {"event": "eval-update", "data": html}

            # 2. Stream loop
            try:
                while True:
                    if await request.is_disconnected():
                        break

                    try:
                        # Wait for invalidation signal (coalesced)
                        await asyncio.wait_for(queue.get(), timeout=15.0)

                        # Fetch fresh data (Self-Healing / Invalidation Pattern)
                        # Use new short-lived session
                        async with AsyncSessionLocal() as session:
                            service = EvaluationService(session)
                            evals = await service.get_evaluations(limit=5)

                        html = (
                            templates.get_template("partials/evaluations_latest.html")
                            .render({"request": request, "evaluations": evals})
                            .replace("\n", "")
                        )

                        yield {"event": "eval-update", "data": html}

                    except asyncio.TimeoutError:
                        # Keep-alive
                        yield {"comment": "keep-alive"}

            except asyncio.CancelledError:
                # Context manager handles unsubscribe in finally block of `async with`
                raise

    return EventSourceResponse(event_generator())
