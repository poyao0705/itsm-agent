"""
Evaluation Run Model and Enums

Stores evaluation results for a snapshot.
Key: evaluation_key (unique)
"""

from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from enum import Enum
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, DateTime, Text, String
from sqlalchemy.dialects.postgresql import JSONB

if TYPE_CHECKING:
    from app.models.pr_snapshot import PRSnapshot


class EvaluationStatus(str, Enum):
    """Evaluation status enum."""

    PROCESSING = "PROCESSING"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    COMPLIANT = "COMPLIANT"
    ERROR = "ERROR"
    STALE = "STALE"  # From Section 7.2 of spec


class RiskLevel(str, Enum):
    """Risk level enum."""

    LOW = "LOW"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class EvaluationRun(SQLModel, table=True):
    """
    Evaluation Run table.

    Stores computed risks, status, reason codes, and timestamps for an evaluation.
    Unique key: evaluation_key
    """

    __tablename__ = "evaluation_run"

    id: Optional[int] = Field(default=None, primary_key=True)
    evaluation_key: str = Field(
        unique=True,
        index=True,
        description="Stable identifier: repo:pr_number:head_sha:pr_body_sha256:policy_version",
    )
    snapshot_id: int = Field(
        foreign_key="pr_snapshot.id",
        index=True,
        description="Foreign key to pr_snapshot",
    )

    # Timestamps
    start_ts: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    end_ts: Optional[datetime] = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )

    # Computed risks
    policy_risk: Optional[RiskLevel] = Field(
        default=None,
        sa_column=Column(String, nullable=True),
        description="Risk computed from policy.yaml file paths",
    )
    llm_risk: Optional[RiskLevel] = Field(
        default=None,
        sa_column=Column(String, nullable=True),
        description="Risk computed by LLM from diff content",
    )
    system_risk: Optional[RiskLevel] = Field(
        default=None,
        sa_column=Column(String, nullable=True),
        description="system_risk = max(policy_risk, llm_risk)",
    )

    # Results
    status: EvaluationStatus = Field(
        default=EvaluationStatus.PROCESSING, sa_column=Column(String, nullable=False)
    )
    reason_codes: List[str] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False),
        description="List of reason codes (e.g., MISSING_TICKET_NUMBER)",
    )

    # LLM metadata (optional)
    llm_model: Optional[str] = Field(
        default=None, description="LLM model identifier used (if LLM was called)"
    )
    llm_prompt_version: Optional[str] = Field(
        default=None, description="Prompt version identifier (if LLM was called)"
    )

    # Checkpointing (optional per spec Section 6.3)
    state_json: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
        description="Lightweight checkpoint for replay/resume",
    )

    # Relationships
    snapshot: "PRSnapshot" = Relationship(back_populates="evaluation_runs")
