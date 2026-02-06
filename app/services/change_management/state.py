"""
Agent state model for the Change Management Agent.

Pure graph state — no service-layer imports.
"""

from sqlmodel import SQLModel, Field
from typing import Optional, List, Annotated, Dict, Any
import operator
import uuid

from app.db.models.analysis_result import AnalysisResultCreate
from app.services.change_management.policy.priority import get_default_risk_priority


def merge_risk_level(left: str, right: str) -> str:
    """
    Reducer for risk_level. Returns the highest risk level.
    Priority is determined by the sequence in policy.yaml.
    """
    priorities = get_default_risk_priority()
    return left if priorities.get(left, 0) > priorities.get(right, 0) else right


class AgentState(SQLModel):
    """
    State of the Change Management Agent.

    This is used by LangGraph to manage workflow state, not a database table.
    """

    run_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="The id of the run."
    )
    webhook_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Raw webhook payload from GitHub (pull_request event).",
    )
    pr_number: int = Field(default=None, description="The number of the PR.")
    pr_url: str = Field(default=None, description="The URL of the PR.")
    owner: Optional[str] = Field(
        default=None, description="Repository owner (e.g. from webhook)."
    )
    repo: Optional[str] = Field(
        default=None, description="Repository name (e.g. from webhook)."
    )
    pr_info: Optional[Dict[str, Any]] = Field(
        default=None,
        description="PR info from GitHub API (title, body, changed_files, etc.).",
    )
    jira_ticket_number: Optional[str] = Field(
        default=None, description="The JIRA ticket number of the PR."
    )
    risk_level: Annotated[str, merge_risk_level] = Field(
        default="LOW", description="The risk level of the PR."
    )
    installation_id: Optional[int] = Field(
        default=None, description="The GitHub App installation ID."
    )
    analysis_results: Annotated[List[AnalysisResultCreate], operator.add] = Field(
        default_factory=list, description="The analysis results of the agent."
    )
    evaluation_run_id: Optional[uuid.UUID] = Field(
        default=None, description="Database ID of the EvaluationRun record."
    )
