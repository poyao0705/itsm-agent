"""
Analysis nodes for the Change Management Agent.

These nodes perform analysis logic like JIRA ticket parsing and policy rule matching.
"""

import re
import fnmatch
import os
import yaml

from app.core.logging import get_logger
from app.services.change_management.state import AgentState
from app.db.models.analysis_result import AnalysisResultCreate
from app.services.change_management.policy.loader import (
    load_policy,
    get_change_rules,
    get_risk_priority,
)

logger = get_logger(__name__)


def analyze_jira_ticket_number(state: AgentState) -> dict:
    """
    Node to analyze the JIRA ticket number in the PR.
    """
    if not state.pr_info:
        logger.warning("Missing pr_info, skipping JIRA analysis.")
        return {}

    pr_info = state.pr_info or {}
    pr_title = pr_info.get("pr_title", "")

    # Regex to extract PR title JIRA ticket number -- Pattern: ABCD-1234
    # Multiple characters + hyphen + multiple digits
    match = re.search(r"([A-Z]+-\d+)", pr_title)

    if match:
        return {"jira_ticket_number": match.group(1)}

    analysis_result = AnalysisResultCreate(
        node_name="analyze_jira_ticket_number",
        reason_code="JIRA_TICKET_NUMBER_NOT_FOUND",
        summary="[HIGH RISK] JIRA ticket number not found in PR title.",
        risk_level="HIGH",
        details={"pr_title": pr_title},
    )

    return {"risk_level": "HIGH", "analysis_results": [analysis_result]}


def policy_rule_analysis(state: AgentState) -> dict:
    """
    Analyze code diff and give a risk level based on policy rules.
    """
    pr_info = state.pr_info or {}
    changed_files = pr_info.get("changed_files", [])

    if not changed_files:
        logger.debug("No changed files to analyze.")
        return {}

    # Load Policy
    try:
        policy_path = os.path.join(
            os.path.dirname(__file__), "..", "policy", "policy.yaml"
        )
        policy = load_policy(policy_path)
        rules = get_change_rules(policy, excluded_risk_levels=["LOW"])
        risk_priority = get_risk_priority(policy)
    except (FileNotFoundError, yaml.YAMLError) as e:
        logger.error("Failed to load or parse policy: %s", e)
        return {}
    except Exception as e:
        logger.error("Unexpected error loading policy: %s", e, exc_info=True)
        return {}

    # Match files against rules (single pass with inline deduplication)
    unique_matches = []
    seen = set()

    for file_obj in changed_files:
        path = file_obj.get("path", "")
        for rule in rules:
            if any(fnmatch.fnmatch(path, p) for p in rule.path_patterns):
                key = (path, rule.id)
                if key not in seen:
                    seen.add(key)
                    unique_matches.append(
                        {
                            "file": path,
                            "rule_id": rule.id,
                            "rule_desc": rule.description,
                            "risk_level": rule.risk_level,
                        }
                    )

    if not unique_matches:
        return {"risk_level": "UNKNOWN"}

    # Create one AnalysisResultCreate per match
    results = [
        AnalysisResultCreate(
            node_name="policy_rule_analysis",
            reason_code=f"{m['risk_level']}_RISK_RULES_MATCHED",
            summary=f"[{m['risk_level']} RISK] {m['file']}: {m['rule_desc']}",
            risk_level=m["risk_level"],
            details={"matched_file": m},
        )
        for m in unique_matches
    ]

    # Determine overall risk (highest priority wins, based on YAML order)
    overall_risk = max(
        (m["risk_level"] for m in unique_matches),
        key=lambda r: risk_priority.get(r, -1),
    )

    return {"risk_level": overall_risk, "analysis_results": results}
