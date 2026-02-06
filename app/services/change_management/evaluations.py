from typing import List
from sqlmodel import select, func
from sqlalchemy import desc
from sqlalchemy.orm import selectinload
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.models.evaluation_run import EvaluationRun


class EvaluationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_evaluations(
        self, skip: int = 0, limit: int = 10
    ) -> List[EvaluationRun]:
        """
        Fetch evaluation runs with pagination.
        """
        statement = (
            select(EvaluationRun)
            .options(selectinload(EvaluationRun.analysis_results))
            .order_by(desc(EvaluationRun.start_ts))
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def count_evaluations(self) -> int:
        """
        Get total number of evaluation runs.
        """
        # pylint: disable-next=not-callable
        statement = select(func.count()).select_from(EvaluationRun)
        result = await self.session.execute(statement)
        return result.scalar() or 0
