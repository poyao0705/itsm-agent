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
