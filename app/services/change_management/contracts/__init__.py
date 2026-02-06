"""
Contracts for the Change Management Agent.

Pure data models and DTOs with no service-layer imports.
"""

from app.services.change_management.contracts.agent_state import AgentState
from app.db.models.analysis_result import AnalysisResultCreate

__all__ = ["AgentState", "AnalysisResultCreate"]
