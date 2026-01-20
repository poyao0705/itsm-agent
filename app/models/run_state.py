"""
Run State Model

Mutable projection of latest status for dashboard display.
Key: (repo_full_name, pr_number)
"""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint, Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB

from app.models.evaluation_run import EvaluationStatus, RiskLevel

if TYPE_CHECKING:
    from app.models.pull_request import PullRequest


class RunState(SQLModel, table=True):
    """
    Run State table (mutable projection).

    Stores the latest known status for dashboard display.
    Composite unique key: (repo_full_name, pr_number)
    """

    __tablename__ = "run_state"

    id: Optional[int] = Field(default=None, primary_key=True)
    repo_full_name: str = Field(index=True, description="Repository full name")
    pr_number: int = Field(index=True, description="GitHub PR number")

    # Latest evaluation reference
    latest_evaluation_key: Optional[str] = Field(
        default=None,
        description="Reference to the latest evaluation_run.evaluation_key",
    )

    # Current status
    status: EvaluationStatus = Field(
        default=EvaluationStatus.PROCESSING, sa_column=Column(String, nullable=False)
    )
    reason_codes: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False),
        description="List of reason codes",
    )
    system_risk: Optional[RiskLevel] = Field(
        default=None, sa_column=Column(String, nullable=True)
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationship
    pr_id: Optional[int] = Field(
        default=None, foreign_key="pull_request.id", index=True
    )
    pr: Optional["PullRequest"] = Relationship(back_populates="run_state")

    __table_args__ = (
        UniqueConstraint("repo_full_name", "pr_number", name="uq_run_state"),
    )
