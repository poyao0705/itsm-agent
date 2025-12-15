"""
ITSM Agent Compliance Schemas
"""

from typing import Literal
from pydantic import BaseModel, Field


# The Strict Schema for the AI
class RiskAnalysisResult(BaseModel):
    """
    Risk Analysis Result
    """

    risk_score: Literal["HIGH", "MEDIUM", "LOW"] = Field(
        description="The risk level based on ISO 20000 Clause 8.7"
    )
    risk_reason: str = Field(
        description="A concise explanation (max 1 sentence) citing the specific file or line."
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0"
    )


# class ComplianceResult(BaseModel):
#     status: Literal["APPROVED", "REJECTED", "NEEDS_MANUAL_REVIEW"]
#     summary: str
#     required_approvals: list[str] = Field(default_factory=list)
