# app/services/agents/iso_auditor/state.py

from pydantic import BaseModel, Field
from typing import List, Optional, Annotated
import operator
from .schemas import RiskAnalysisResult

class ComplianceState(BaseModel):
    # --- 1. CONTEXT (Inputs) ---
    ticket_id: Optional[str] = Field(default=None, description="Jira Ticket Key (e.g., TRD-101)")
    ticket_owner: Optional[str] = Field(default="unknown_user@example.com", description="Email of the Jira Assignee")
    git_diff: str = Field(description="Raw text of the code changes")
    
    # --- 2. LOGIC OUTPUTS (AI Decisions) ---
    # Optional because they start as None
    risk_data: Optional[RiskAnalysisResult] = Field(default=None) # Agent 1
    # TODO: to be implemented
    # ci_data: Optional[CIResult] = None          # Agent 2
    # qa_data: Optional[QAResult] = None          # Agent 3
    # security_data: Optional[SecurityResult] = None # Agent 4
    
    # --- 3. THE AUDIT TRAIL (The Merge Target) ---
    # CRITICAL: 'operator.add' ensures that if Node A and Node B 
    # both write a log at the same time, BOTH logs are kept.
    audit_log: Annotated[List[str], operator.add] = Field(default_factory=list)

    # --- 🆕 RETRY MECHANISM ---
    # This holds the Pydantic error message if validation fails.
    # We default to None because usually there is no error.
    error_msg: Optional[str] = Field(default=None, description="Current validation error to fix")
    
    # Optional: Track retries to prevent infinite loops
    retry_count: int = Field(default=0)