"""
PR Snapshot Model

Immutable snapshot of PR inputs being evaluated.
Key: (pr_id, head_sha, pr_body_sha256, policy_version)
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint, Column, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from app.models.pull_request import PullRequest
    from app.models.evaluation_run import EvaluationRun


class PRSnapshot(SQLModel, table=True):
    """
    PR Snapshot table (immutable).

    Stores immutable capture of PR inputs at evaluation time.
    Composite unique key: (pr_id, head_sha, pr_body_sha256, policy_version)
    """

    __tablename__ = "pr_snapshot"

    id: Optional[int] = Field(default=None, primary_key=True)
    pr_id: int = Field(
        foreign_key="pull_request.id",
        index=True,
        description="Foreign key to pull_request",
    )
    head_sha: str = Field(index=True, description="Git commit SHA of the PR head")
    pr_body_sha256: str = Field(
        index=True, description="SHA256 hash of PR body for idempotency"
    )
    policy_version: str = Field(index=True, description="Version of policy.yaml used")

    # Snapshot data
    pr_title: str = Field(description="PR title at snapshot time")
    changed_files: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False),
        description="Changed files summary (paths + stats) as JSON",
    )

    user_risk: Optional[str] = Field(
        default=None, description="User-declared risk level: LOW, HIGH, or UNKNOWN"
    )
    backout_text_hash: Optional[str] = Field(
        default=None, description="Hash of backout plan text"
    )
    backout_text: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True),
        description="Backout plan text (only if small enough)",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # Relationships
    pr: "PullRequest" = Relationship(back_populates="snapshots")
    evaluation_runs: List["EvaluationRun"] = Relationship(back_populates="snapshot")

    __table_args__ = (
        UniqueConstraint(
            "pr_id",
            "head_sha",
            "pr_body_sha256",
            "policy_version",
            name="uq_pr_snapshot",
        ),
    )
