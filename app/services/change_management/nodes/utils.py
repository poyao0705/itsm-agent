"""Shared utilities for change management analysis nodes."""

from app.db.models.analysis_result import AnalysisResultCreate


def make_result(
    node_name: str,
    reason_code: str,
    summary: str,
    risk_level: str,
    details: dict,
    **extra,
) -> dict:
    """Build a standard node return dict with a single AnalysisResultCreate.

    Extra keyword arguments are merged into the returned dict,
    useful for passing additional state keys (e.g. jira_ticket_number).
    """
    return {
        "risk_level": risk_level,
        "analysis_results": [
            AnalysisResultCreate(
                node_name=node_name,
                reason_code=reason_code,
                summary=summary,
                risk_level=risk_level,
                details=details,
            )
        ],
        **extra,
    }
