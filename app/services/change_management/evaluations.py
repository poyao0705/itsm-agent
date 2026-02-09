from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlmodel import select, func
from sqlalchemy import desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.core.logging import get_logger
from app.core.logging import get_logger
from app.core.valkey_pubsub import publish_to_stream
from app.core import broadcast
from app.db.models.evaluation_run import EvaluationRun, EvaluationStatus
from app.db.models.analysis_result import AnalysisResult
from app.services.change_management.graph import change_management_graph
from app.services.change_management.context import Ctx

logger = get_logger(__name__)


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

    async def run_evaluation_workflow(
        self,
        webhook_payload: dict,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> dict:
        """
        Run the complete evaluation workflow with persistence.

        This method orchestrates the entire evaluation process:
        1. Create EvaluationRun record (status=PROCESSING)
        2. Invoke graph (pure logic, no persistence)
        3. Persist analysis results
        4. Update status to DONE

        On error: Update status to ERROR and re-raise (fail-fast).

        Args:
            webhook_payload: GitHub webhook payload
            session_factory: Async session factory for graph context

        Returns:
            Final graph state dict

        Raises:
            Exception: Re-raises any exception after updating status to ERROR
        """
        # Extract eval context (key + metadata)
        context = self._extract_evaluation_context(webhook_payload)
        if not context:
            raise ValueError("Cannot extract evaluation context from webhook payload")

        run_id: Optional[str] = None
        evaluation_key = context[
            "evaluation_key"
        ]  # keys still need this for error logging/checks

        try:
            # 1. Create EvaluationRun record with context
            run_id = await self._create_evaluation_run(context)

            # 2. Invoke graph (pure logic, no DB operations in nodes)
            result = await change_management_graph.ainvoke(
                {"webhook_payload": webhook_payload},
                context=Ctx(db=session_factory),
            )

            # 3. Persist analysis results from final state
            await self._persist_analysis_results(run_id, result)

            # 4. Update status to DONE
            await self._finalize_evaluation_run(run_id, result)

            return result

        except Exception as e:
            # Best-effort: Update status to ERROR before re-raising
            if run_id:
                await self._mark_evaluation_error(run_id, str(e))
            raise

    def _extract_evaluation_context(self, payload: dict) -> Optional[dict]:
        """
        Extract evaluation key and PR metadata from webhook payload.
        """
        repo_data = payload.get("repository") or {}
        pr_data = payload.get("pull_request") or {}

        owner = (repo_data.get("owner") or {}).get("login") or repo_data.get(
            "full_name", ""
        ).split("/")[0]
        repo = repo_data.get("name", "")
        pr_number = pr_data.get("number")
        head_sha = (pr_data.get("head") or {}).get("sha", "")

        # Body hash
        body = pr_data.get("body") or ""
        import hashlib

        body_hash = hashlib.sha256(body.encode()).hexdigest()[:8]

        if not all([owner, repo, pr_number, head_sha]):
            return None

        key = f"{owner}/{repo}:{pr_number}:{head_sha}:{body_hash}"

        return {
            "evaluation_key": key,
            "owner": owner,
            "repo": repo,
            "pr_number": pr_number,
        }

    async def _create_evaluation_run(self, context: dict) -> str:
        """
        Create an EvaluationRun record with status=PROCESSING.

        Uses ON CONFLICT DO NOTHING for idempotency.

        Returns:
            The run ID (UUID as string)
        """
        evaluation_key = context["evaluation_key"]
        stmt = (
            insert(EvaluationRun)
            .values(
                evaluation_key=evaluation_key,
                owner=context["owner"],
                repo=context["repo"],
                pr_number=context["pr_number"],
                status=EvaluationStatus.PROCESSING,
                start_ts=datetime.now(timezone.utc),
            )
            .on_conflict_do_nothing(index_elements=[EvaluationRun.evaluation_key])
            .returning(EvaluationRun.id)
        )

        res = await self.session.execute(stmt)
        run_id = res.scalar_one_or_none()

        if run_id is None:
            # Row already exists, fetch existing ID
            existing = await self.session.execute(
                select(EvaluationRun.id).where(
                    EvaluationRun.evaluation_key == evaluation_key
                )
            )
            run_id = existing.scalar_one()
            logger.info("Evaluation run already exists: %s", evaluation_key)
        else:
            logger.info("Created evaluation run: %s (%s)", run_id, evaluation_key)

        await self.session.commit()
        await self.session.commit()
        await publish_to_stream(
            broadcast.STREAM_KEY, {"type": "update", "run_id": str(run_id)}
        )
        return str(run_id)

    async def _persist_analysis_results(self, run_id: str, state: dict) -> None:
        """
        Batch insert analysis results from graph state.

        Args:
            run_id: Evaluation run UUID
            state: Final graph state containing analysis_results
        """
        analysis_findings = state.get("analysis_results") or []

        for finding in analysis_findings:
            ar = AnalysisResult(
                run_id=run_id,
                node_name=finding.node_name,
                reason_code=finding.reason_code,
                summary=finding.summary,
                risk_level=finding.risk_level,
                details=finding.details,
            )
            self.session.add(ar)

        await self.session.commit()
        logger.info(
            "Persisted %d analysis results for run %s", len(analysis_findings), run_id
        )

    async def _finalize_evaluation_run(self, run_id: str, state: dict) -> None:
        """
        Update EvaluationRun status to DONE and set risk_level, end_ts.

        Args:
            run_id: Evaluation run UUID
            state: Final graph state containing risk_level
        """
        result = await self.session.execute(
            select(EvaluationRun).where(EvaluationRun.id == run_id)
        )
        run = result.scalar_one()

        run.status = EvaluationStatus.DONE
        run.risk_level = state.get("risk_level", "LOW")
        run.end_ts = datetime.now(timezone.utc)

        await self.session.commit()
        await self.session.commit()
        await publish_to_stream(
            broadcast.STREAM_KEY, {"type": "update", "run_id": str(run_id)}
        )
        logger.info("Finalized evaluation run: %s with status DONE", run_id)

    async def _mark_evaluation_error(self, run_id: str, error_message: str) -> None:
        """
        Best-effort: Update evaluation run status to ERROR.

        Args:
            run_id: Evaluation run UUID
            error_message: Error description
        """
        try:
            result = await self.session.execute(
                select(EvaluationRun).where(EvaluationRun.id == run_id)
            )
            run = result.scalar_one_or_none()

            if run:
                run.status = EvaluationStatus.ERROR
                run.end_ts = datetime.now(timezone.utc)
                run.end_ts = datetime.now(timezone.utc)
                await self.session.commit()
                await publish_to_stream(
                    broadcast.STREAM_KEY, {"type": "update", "run_id": str(run_id)}
                )
                logger.warning(
                    "Marked evaluation run %s as ERROR: %s", run_id, error_message
                )
        except Exception as e:
            # Best-effort - don't fail if we can't update
            logger.error("Failed to mark evaluation as ERROR: %s", e)
