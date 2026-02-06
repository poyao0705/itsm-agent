"""
Evaluation Run Model and Enums

Stores evaluation results for a snapshot.
Key: evaluation_key (unique)
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime
from enum import Enum


class EvaluationStatus(str, Enum):
    """Evaluation status enum."""

    PROCESSING = "PROCESSING"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    DONE = "DONE"
    ERROR = "ERROR"


if TYPE_CHECKING:
    from app.db.models.analysis_result import AnalysisResult


class EvaluationRun(SQLModel, table=True):
    """
    Evaluation Run table.

    Stores computed risks, status, reason codes, and timestamps for an evaluation.
    Unique key: evaluation_key
    """

    __tablename__ = "evaluation_run"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    evaluation_key: str = Field(
        unique=True,
        index=True,
        description="Stable identifier: owner/repo:pr_number:head_sha:body_hash",
    )

    # Timestamps
    start_ts: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    end_ts: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # Status
    status: EvaluationStatus = Field(
        default=EvaluationStatus.PROCESSING,
        description="Current status of the evaluation run.",
    )
    risk_level: str = Field(
        default="LOW",
        description="The overall calculated risk level for this run.",
    )

    # Relationships
    analysis_results: List["AnalysisResult"] = Relationship(
        back_populates="evaluation_run"
    )
