"""
Web Router - HTMX / Template responses

All routes that return HTML (full pages or partials) live here.
This keeps the API layer clean for pure JSON endpoints.
"""

from typing import Annotated
import asyncio

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
async def sse_stream(
    request: Request,
    service: Annotated[EvaluationService, Depends(get_evaluation_service)] = None,
):
    """SSE stream that pushes updated evaluation rows to the frontend."""

    async def event_generator():
        last_id = None
        while True:
            # Check if client closed connection
            if await request.is_disconnected():
                break

            evals = await service.get_evaluations(limit=5)
            current_id = str(evals[0].id) if evals else None

            # Only send update if the latest evaluation has changed
            if current_id != last_id:
                last_id = current_id
                yield {
                    "event": "eval-update",
                    "data": templates.get_template("partials/evaluations_latest.html")
                    .render({"request": request, "evaluations": evals})
                    .replace("\n", ""),
                }

            await asyncio.sleep(5)

    return EventSourceResponse(event_generator())
