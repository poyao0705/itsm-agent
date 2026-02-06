"""
Analysis result models and DTOs for the Change Management Agent.
"""

import uuid
from typing import Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime
from sqlmodel import SQLModel, Relationship, Field
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from app.db.models.evaluation_run import EvaluationRun


class AnalysisResultPublic(SQLModel):
    """
    DTO for a single analysis finding/result.
    Used in AgentState to ensure serializability.
    """

    node_name: str
    reason_code: str
    summary: str
    risk_level: str
    details: Dict[str, Any] = {}


class AnalysisResult(SQLModel, table=True):
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
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="The time when the analysis result was updated.",
    )

    evaluation_run: Optional["EvaluationRun"] = Relationship(
        back_populates="analysis_results"
    )
