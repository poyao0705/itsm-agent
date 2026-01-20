"""
Pull Request Model

Stores stable PR identity and basic metadata.
Key: (repo_full_name, pr_number)
"""

from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint, Column, DateTime

if TYPE_CHECKING:
    from app.models.pr_snapshot import PRSnapshot
    from app.models.run_state import RunState


class PullRequest(SQLModel, table=True):
    """
    Pull Request table.

    Stores stable identity for a GitHub Pull Request.
    Composite unique key: (repo_full_name, pr_number)
    """

    __tablename__ = "pull_request"

    id: Optional[int] = Field(default=None, primary_key=True)
    repo_full_name: str = Field(
        index=True, description="Repository full name, e.g., 'owner/repo'"
    )
    pr_number: int = Field(index=True, description="GitHub PR number")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # Relationships
    snapshots: List["PRSnapshot"] = Relationship(back_populates="pr")
    run_state: Optional["RunState"] = Relationship(back_populates="pr")

    __table_args__ = (
        UniqueConstraint("repo_full_name", "pr_number", name="uq_pr_identity"),
    )
