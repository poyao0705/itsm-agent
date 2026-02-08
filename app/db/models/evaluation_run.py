"""
Evaluation Run Model and Enums

Stores evaluation results for a snapshot.
Key: evaluation_key (unique)
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, String
from enum import Enum

from app.db.models.analysis_result import AnalysisResultPublic

if TYPE_CHECKING:
    from app.db.models.analysis_result import AnalysisResult


class EvaluationStatus(str, Enum):
    """Evaluation status enum."""

    PROCESSING = "PROCESSING"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    DONE = "DONE"
    ERROR = "ERROR"


# -----------------------------------------------------------------------------
# Base
# -----------------------------------------------------------------------------
class EvaluationRunBase(SQLModel):
    """Shared fields for EvaluationRun."""

    evaluation_key: str = Field(
        unique=True,
        index=True,
        description="Stable identifier: owner/repo:pr_number:head_sha:body_hash",
    )
    status: str = Field(
        default=EvaluationStatus.PROCESSING,
        sa_column=Column(String, nullable=False, default=EvaluationStatus.PROCESSING),
        description="Current status of the evaluation run.",
    )
    risk_level: str = Field(
        default="LOW",
        description="The overall calculated risk level for this run.",
    )
    owner: Optional[str] = Field(
        default=None, index=True, description="Repository owner"
    )
    repo: Optional[str] = Field(default=None, index=True, description="Repository name")
    pr_number: Optional[int] = Field(
        default=None, index=True, description="Pull request number"
    )

    @property
    def display_name(self) -> str:
        """Returns human-readable name, using stored fields if available."""
        if self.owner and self.repo and self.pr_number:
            return f"{self.owner}/{self.repo} #{self.pr_number}"

        # Fallback: parse from key (legacy records)
        key = str(self.evaluation_key)
        parts = key.split(":")
        if len(parts) >= 2:
            return f"{parts[0]} #{parts[1]}"
        return key


# -----------------------------------------------------------------------------
# ORM Model (Database layer)
# -----------------------------------------------------------------------------
class EvaluationRun(EvaluationRunBase, table=True):
    """
    Evaluation Run table.
    """

    __tablename__ = "evaluation_run"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    start_ts: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    end_ts: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # Relationships
    analysis_results: List["AnalysisResult"] = Relationship(
        back_populates="evaluation_run"
    )

    def to_public(self) -> "EvaluationRunPublic":
        """Convert to render-safe public DTO."""
        return EvaluationRunPublic(
            id=self.id,
            evaluation_key=self.evaluation_key,
            status=self.status,
            risk_level=self.risk_level,
            owner=self.owner,
            repo=self.repo,
            pr_number=self.pr_number,
            start_ts=self.start_ts,
            end_ts=self.end_ts,
            analysis_results=[ar.to_public() for ar in (self.analysis_results or [])],
        )


# -----------------------------------------------------------------------------
# Public (Response/Read layer)
# -----------------------------------------------------------------------------
class EvaluationRunPublic(EvaluationRunBase):
    """
    Public DTO for EvaluationRun responses.
    """

    id: uuid.UUID
    start_ts: datetime
    end_ts: Optional[datetime] = None
    analysis_results: List[AnalysisResultPublic] = []
