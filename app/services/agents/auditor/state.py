# app/services/agents/iso_auditor/state.py

from pydantic import BaseModel, Field
from typing import List, Optional, Annotated
import operator

class AuditorState(BaseModel):
    # --- 1. CONTEXT (Inputs) ---
    ticket_id: Optional[str] = Field(default=None, description="Jira Ticket Key (e.g., TRD-101)")
    ticket_owner: Optional[str] = Field(default="unknown_user@example.com", description="Email of the Jira Assignee")
    git_diff: str = Field(description="Raw text of the code changes")
    
    # --- 2. LOGIC OUTPUTS (AI Decisions) ---
    # Optional because they start as None
    risk_score: Optional[str] = Field(default=None, description="HIGH or LOW")
    risk_reason: Optional[str] = Field(default=None)
    ci_tag: Optional[str] = Field(default=None, description="Service Name")
    
    # --- 3. THE AUDIT TRAIL (The Merge Target) ---
    # CRITICAL: 'operator.add' ensures that if Node A and Node B 
    # both write a log at the same time, BOTH logs are kept.
    audit_log: Annotated[List[str], operator.add] = Field(default_factory=list)