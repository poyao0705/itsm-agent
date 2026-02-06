"""
Persistence nodes for the Change Management Agent.

These nodes handle database operations for EvaluationRun and AnalysisResult.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import select
from sqlalchemy.dialects.postgresql import insert
from langgraph.runtime import Runtime

from app.db.models.evaluation_run import EvaluationRun, EvaluationStatus
from app.db.models.analysis_result import AnalysisResult
from app.schemas.agent_state import AgentState
from app.services.change_management.context import Ctx


def build_evaluation_key(state: AgentState) -> Optional[str]:
    """
    Build evaluation key from state.

    Format: owner/repo:pr_number:head_sha:body_hash
    """
    pr_info = state.pr_info or {}
    head_sha = pr_info.get("head_sha")
    body_hash = pr_info.get("pr_body_sha256", "")

    if not all([state.owner, state.repo, state.pr_number, head_sha]):
        return None

    return f"{state.owner}/{state.repo}:{state.pr_number}:{head_sha}:{body_hash}"


async def create_evaluation_run(state: AgentState, runtime: Runtime[Ctx]) -> dict:
    """
    Create an EvaluationRun record at the start of the workflow.

    Uses ON CONFLICT DO NOTHING to handle race conditions/idempotency.
    """
    evaluation_key = build_evaluation_key(state)

    if not evaluation_key:
        print("Cannot create evaluation run: missing required state fields")
        return {}

    async with runtime.context.db() as session:
        async with session.begin():
            # Atomically insert or ignore
            stmt = (
                insert(EvaluationRun)
                .values(
                    evaluation_key=evaluation_key,
                    status=EvaluationStatus.PROCESSING,
                    start_ts=datetime.now(timezone.utc),
                )
                .on_conflict_do_nothing(index_elements=[EvaluationRun.evaluation_key])
                .returning(EvaluationRun.id)
            )

            res = await session.execute(stmt)
            run_id = res.scalar_one_or_none()

            if run_id is None:
                # If interaction failed (row exists), fetch existing ID
                existing = await session.exec(
                    select(EvaluationRun.id).where(
                        EvaluationRun.evaluation_key == evaluation_key
                    )
                )
                run_id = existing.first()
                print(f"Evaluation run already exists: {evaluation_key}")
            else:
                print(f"Created evaluation run: {run_id} ({evaluation_key})")

            return {"evaluation_run_id": run_id}


async def finalize_evaluation_run(state: AgentState, runtime: Runtime[Ctx]) -> dict:
    """
    Finalize the EvaluationRun and persist all AnalysisResults.

    - Batch inserts all analysis_results to DB
    - Updates EvaluationRun status to DONE or ERROR
    - Sets end_ts
    """
    if not state.evaluation_run_id:
        print("No evaluation_run_id in state, skipping finalization")
        return {}

    async with runtime.context.db() as session:
        async with session.begin():
            # Fetch the evaluation run
            result = await session.exec(
                select(EvaluationRun).where(EvaluationRun.id == state.evaluation_run_id)
            )
            run = result.first()

            if not run:
                print(f"Evaluation run not found: {state.evaluation_run_id}")
                return {}

            # Batch insert analysis results - convert DTO to ORM and add to session
            analysis_findings = state.analysis_results or []
            for finding in analysis_findings:
                ar = AnalysisResult(
                    run_id=run.id,
                    node_name=finding.node_name,
                    reason_code=finding.reason_code,
                    summary=finding.summary,
                    risk_level=finding.risk_level,
                    details=finding.details,
                )
                session.add(ar)

            # Update evaluation run
            run.status = EvaluationStatus.DONE
            run.risk_level = state.risk_level
            run.end_ts = datetime.now(timezone.utc)

            await session.commit()

            print(
                f"Finalized evaluation run: {run.id} with {len(analysis_findings)} results"
            )
            return {}
