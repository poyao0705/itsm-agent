"""
Analysis Finding DTO for the Change Management Agent state.
"""

from typing import Dict, Any, Optional
from sqlmodel import SQLModel


class AnalysisFinding(SQLModel):
    """
    DTO for a single analysis finding.
    Used in AgentState to ensure serializability.
    """

    node_name: str
    reason_code: str
    summary: str
    details: Dict[str, Any] = {}
