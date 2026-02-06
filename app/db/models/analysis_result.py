"""
Analysis result models and DTOs for the Change Management Agent.
"""

import uuid
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime, timezone
from sqlmodel import SQLModel, Relationship, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from app.db.models.evaluation_run import EvaluationRun


# -----------------------------------------------------------------------------
# Base
# -----------------------------------------------------------------------------
class AnalysisResultBase(SQLModel):
    """Shared fields for AnalysisResult."""

    node_name: str = Field(
        ..., description="The name of the node that produced this result."
    )
    reason_code: str = Field(
        ..., description="The reason code for the analysis result."
    )
    summary: str = Field(
        ..., description="A human-readable summary of the analysis result."
    )
    risk_level: str = Field(
        default="LOW", description="The risk level associated with this finding."
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True),
        description="Detailed information about the analysis result.",
    )


# -----------------------------------------------------------------------------
# Create (DTO layer)
# -----------------------------------------------------------------------------
class AnalysisResultCreate(AnalysisResultBase):
    """
    DTO for creating an analysis result (e.g., in AgentState).
    Does not have an ID or timestamps yet.
    """

    pass


# -----------------------------------------------------------------------------
# ORM Model (Database layer)
# -----------------------------------------------------------------------------
class AnalysisResult(AnalysisResultBase, table=True):
    """
    ORM Model for a single analysis result in the database.
    """

    __tablename__ = "analysis_result"

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    run_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="evaluation_run.id",
        description="The ID of the evaluation run.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="The time when the analysis result was updated.",
    )

    evaluation_run: Optional["EvaluationRun"] = Relationship(
        back_populates="analysis_results"
    )


# -----------------------------------------------------------------------------
# Public (Response/Read layer)
# -----------------------------------------------------------------------------
class AnalysisResultPublic(AnalysisResultBase):
    """
    Public DTO for AnalysisResult responses.
    """

    id: uuid.UUID
    updated_at: datetime
