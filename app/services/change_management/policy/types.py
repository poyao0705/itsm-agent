"""
Change type rule model for policy configuration.

Pure data model — no service imports.
"""

from sqlmodel import SQLModel, Field
from typing import Optional, Dict, Any, Tuple


class ChangeTypeRule(SQLModel):
    """
    Rule for a specific change type.

    Parsed from policy YAML, not a database table.
    """

    id: str = Field(description="The id of the change type.")
    risk_level: str = Field(
        default="LOW", description="The risk level of the change type."
    )
    description: str = Field(description="The description of the change type.")
    path_patterns: Tuple[str, ...] = Field(
        default_factory=tuple, description="The path patterns of the change type."
    )
    services: Dict[str, Any] = Field(
        default_factory=dict, description="The services of the change type."
    )
    analysis: Optional[Dict[str, Any]] = Field(
        default=None, description="The analysis of the change type."
    )
