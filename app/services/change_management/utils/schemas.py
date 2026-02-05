from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Literal, Optional, List, Annotated, Dict, Any, Tuple
import operator
import uuid

# Should be a generic analysis result dataclass to be stored in an array in the AgentState. Starting with a reason code, summary, and updated_at/updated_by.


class AnalysisResult(BaseModel):
    """
    Result of analysis.
    """

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="The id of the analysis result.",
    )
    run_id: str = Field(description="The id of the run.")
    node_name: str = Field(
        description="The name of the node that performed the analysis."
    )
    reason_code: str = Field(description="The reason code of the analysis.")
    summary: str = Field(description="The summary of the analysis.")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured payload: outputs + evidence signals (safe to store/log)",
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_by: Optional[str] = Field(
        default=None, description="The user who updated the analysis."
    )


class AgentState(BaseModel):
    """
    State of the Change Management Agent.
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
    risk_level: Literal["LOW", "HIGH", "UNKNOWN"] = Field(
        default="UNKNOWN", description="The risk level of the PR."
    )
    installation_id: Optional[int] = Field(
        default=None, description="The GitHub App installation ID."
    )
    analysis_results: Annotated[List[AnalysisResult], operator.add] = Field(
        default_factory=list, description="The analysis results of the agent."
    )


class ChangeTypeRule(BaseModel):
    """
    Rule for a specific change type.
    """

    id: str = Field(description="The id of the change type.")
    risk_level: str = Field(
        default="LOW", description="The risk level of the change type."
    )
    description: str = Field(description="The description of the change type.")
    path_patterns: Tuple[str, ...] = Field(
        default_factory=tuple, description="The path patterns of the change type."
    )
    services: Dict[str, Any] = Field(
        default_factory=dict, description="The services of the change type."
    )
    analysis: Optional[Dict[str, Any]] = Field(
        default=None, description="The analysis of the change type."
    )
