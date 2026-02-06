from typing import Annotated, List
from fastapi import APIRouter, Query, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from app.dependencies.database import get_db
from app.services.change_management.evaluations import EvaluationService
from app.db.models.evaluation_run import EvaluationRunPublic
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from sse_starlette.sse import EventSourceResponse
import asyncio

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

SessionDep = Annotated[AsyncSession, Depends(get_db)]


def get_evaluation_service(session: SessionDep) -> EvaluationService:
    """Get evaluation service (Dependency Injection)."""
    return EvaluationService(session)


@router.get("/", response_model=List[EvaluationRunPublic])
async def get_evaluations(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    service: Annotated[EvaluationService, Depends(get_evaluation_service)] = None,
):
    """Get evaluations with pagination."""
    res = await service.get_evaluations(skip=skip, limit=limit)

    # If it's an HTMX request, return the partial template
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/evaluations_latest.html",
            {"request": request, "evaluations": res},
        )

    # Otherwise, return the model objects (FastAPI will convert to JSON via response_model)
    return res


@router.get("/sse-stream")
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
