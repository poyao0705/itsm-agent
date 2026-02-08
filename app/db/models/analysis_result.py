"""
Analysis result models and DTOs for the Change Management Agent.

All analysis result types in one place:
- AnalysisResultBase: shared fields
- AnalysisResultCreate: DTO for creating (used in AgentState)
- AnalysisResult: ORM model (database table)
- AnalysisResultPublic: response DTO
"""

import uuid
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime, timezone
from sqlmodel import SQLModel, Relationship, Field
from sqlalchemy import Column, DateTime
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

    # Override details to use JSONB column type
    details: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True),
        description="Detailed information about the analysis result.",
    )

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
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="The time when the analysis result was updated.",
    )

    evaluation_run: Optional["EvaluationRun"] = Relationship(
        back_populates="analysis_results"
    )

    def to_public(self) -> "AnalysisResultPublic":
        """Convert to render-safe public DTO."""
        return AnalysisResultPublic(
            id=self.id,
            node_name=self.node_name,
            reason_code=self.reason_code,
            summary=self.summary,
            risk_level=self.risk_level,
            details=self.details,
            updated_at=self.updated_at,
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
