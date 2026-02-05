"""
Persistence nodes for the Change Management Agent.

These nodes handle database operations for EvaluationRun and AnalysisResult.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import select
from langchain_core.runnables import RunnableConfig

from app.db.models.evaluation_run import EvaluationRun, EvaluationStatus
from app.schemas.agent_state import AgentState


def build_evaluation_key(state: AgentState) -> Optional[str]:
    """
    Build evaluation key from state.

    Format: owner/repo:pr_number:head_sha:body_hash
    """
    pr_info = state.pr_info or {}
    head_sha = pr_info.get("head_sha")
    body_hash = pr_info.get("pr_body_sha256", "")[:8]

    if not all([state.owner, state.repo, state.pr_number, head_sha]):
        return None

    return f"{state.owner}/{state.repo}:{state.pr_number}:{head_sha}:{body_hash}"


async def create_evaluation_run(state: AgentState, config: RunnableConfig) -> dict:
    """
    Create an EvaluationRun record at the start of the workflow.

    Must be called AFTER node_fetch_pr_info since we need head_sha and body_hash.
    """
    evaluation_key = build_evaluation_key(state)

    if not evaluation_key:
        print("Cannot create evaluation run: missing required state fields")
        return {}

    session = config["configurable"]["session"]

    # Check if evaluation already exists (idempotency)
    existing = await session.exec(
        select(EvaluationRun).where(EvaluationRun.evaluation_key == evaluation_key)
    )
    existing_run = existing.first()

    if existing_run:
        print(f"Evaluation run already exists: {evaluation_key}")
        return {"evaluation_run_id": existing_run.id}

    # Create new evaluation run
    run = EvaluationRun(
        evaluation_key=evaluation_key,
        status=EvaluationStatus.PROCESSING,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)

    print(f"Created evaluation run: {run.id} ({evaluation_key})")
    return {"evaluation_run_id": run.id}


async def finalize_evaluation_run(state: AgentState, config: RunnableConfig) -> dict:
    """
    Finalize the EvaluationRun and persist all AnalysisResults.

    - Batch inserts all analysis_results to DB
    - Updates EvaluationRun status to DONE or ERROR
    - Sets end_ts
    """
    if not state.evaluation_run_id:
        print("No evaluation_run_id in state, skipping finalization")
        return {}

    session = config["configurable"]["session"]

    # Fetch the evaluation run
    result = await session.exec(
        select(EvaluationRun).where(EvaluationRun.id == state.evaluation_run_id)
    )
    run = result.first()

    if not run:
        print(f"Evaluation run not found: {state.evaluation_run_id}")
        return {}

    # Batch insert analysis results - set run_id and add to session
    analysis_results = state.analysis_results or []
    for ar in analysis_results:
        ar.run_id = run.id
        session.add(ar)

    # Update evaluation run
    run.status = EvaluationStatus.DONE
    run.risk_level = state.risk_level
    run.end_ts = datetime.now(timezone.utc)

    await session.commit()

    print(f"Finalized evaluation run: {run.id} with {len(analysis_results)} results")
    return {}
