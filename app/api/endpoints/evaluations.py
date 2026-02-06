from typing import Annotated, List
from fastapi import APIRouter, Query, Depends
from sqlmodel.ext.asyncio.session import AsyncSession
from app.dependencies.database import get_db
from app.services.change_management.evaluations import EvaluationService
from app.db.models.evaluation_run import EvaluationRunPublic

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_db)]


def get_evaluation_service(session: SessionDep) -> EvaluationService:
    """Get evaluation service (Dependency Injection)."""
    return EvaluationService(session)


@router.get("/", response_model=List[EvaluationRunPublic])
async def get_evaluations(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    service: Annotated[EvaluationService, Depends(get_evaluation_service)] = None,
):
    """Get evaluations with pagination."""
    return await service.get_evaluations(skip=skip, limit=limit)
