"""Analysis nodes for the Change Management Agent."""

import re
import fnmatch
import os
import yaml
import httpx

from app.core.logging import get_logger
from app.services.change_management.state import AgentState
from app.db.models.analysis_result import AnalysisResultCreate
from app.services.change_management.policy.loader import (
    load_policy,
    get_change_rules,
    get_risk_priority,
)
from app.services.change_management.nodes.utils import make_result
import app.services.jira.jira_client as jira_client
from app.core.config import settings

logger = get_logger(__name__)

_NODE_JIRA_TICKET = "analyze_jira_ticket_number"
_NODE_POLICY = "policy_rule_analysis"


async def analyze_jira_ticket_number(state: AgentState) -> dict:
    """Analyze the JIRA ticket number in the PR title and validate via JIRA API."""
    if not state.pr_info:
        logger.warning("Missing pr_info, skipping JIRA analysis.")
        return {}

    pr_title = (state.pr_info or {}).get("pr_title", "")
    details = {"pr_title": pr_title}

    # Extract JIRA ticket number from PR title (e.g. ABCD-1234)
    match = re.search(r"([A-Z]+-\d+)", pr_title)
    if not match:
        return make_result(
            node_name=_NODE_JIRA_TICKET,
            reason_code="JIRA_TICKET_NUMBER_NOT_FOUND",
            summary="[HIGH RISK] JIRA ticket number not found in PR title.",
            risk_level="HIGH",
            details=details,
        )

    jira_ticket_number = match.group(1)
    details["jira_ticket_number"] = jira_ticket_number
    results: list[AnalysisResultCreate] = []

    # Record that JIRA ticket number was found in PR title
    results.append(
        AnalysisResultCreate(
            node_name=_NODE_JIRA_TICKET,
            reason_code="JIRA_TICKET_NUMBER_FOUND",
            summary=f"[LOW RISK] JIRA ticket {jira_ticket_number} found in PR title.",
            risk_level="LOW",
            details=details,
        )
    )

    # Validate ticket via JIRA API
    jira_client_instance = jira_client.JiraClient(
        base_url=settings.JIRA_BASE_URL,
        email=settings.JIRA_EMAIL,
        api_token=settings.JIRA_API_TOKEN,
    )
    try:
        jira_ticket_metadata = await jira_client_instance.get_issue(jira_ticket_number)
    except httpx.HTTPError as e:
        logger.error("Failed to fetch JIRA ticket metadata: %s", e)
        results.append(
            AnalysisResultCreate(
                node_name=_NODE_JIRA_TICKET,
                reason_code="JIRA_API_ERROR",
                summary="[HIGH RISK] Failed to fetch JIRA ticket from JIRA API.",
                risk_level="HIGH",
                details=details,
            )
        )
        return {"risk_level": "HIGH", "analysis_results": results}

    # Record successful JIRA ticket validation
    results.append(
        AnalysisResultCreate(
            node_name=_NODE_JIRA_TICKET,
            reason_code="JIRA_TICKET_FOUND_IN_JIRA",
            summary=f"[LOW RISK] JIRA ticket {jira_ticket_number} fetched via JIRA API.",
            risk_level="LOW",
            details=details,
        )
    )

    return {
        "risk_level": "LOW",
        "analysis_results": results,
        "jira_ticket_number": jira_ticket_number,
        "jira_ticket_metadata": jira_ticket_metadata,
    }


def policy_rule_analysis(state: AgentState) -> dict:
    """Analyze code diff and assign risk level based on policy rules."""
    changed_files = (state.pr_info or {}).get("changed_files", [])
    if not changed_files:
        logger.debug("No changed files to analyze.")
        return {}

    # Load policy
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

    # Match files against rules (single pass, deduplicated)
    unique_matches = []
    seen: set[tuple[str, str]] = set()

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
        return {"risk_level": "LOW"}

    results = [
        AnalysisResultCreate(
            node_name=_NODE_POLICY,
            reason_code=f"{m['risk_level']}_RISK_RULES_MATCHED",
            summary=f"[{m['risk_level']} RISK] {m['file']}: {m['rule_desc']}",
            risk_level=m["risk_level"],
            details={"matched_file": m},
        )
        for m in unique_matches
    ]

    overall_risk = max(
        (m["risk_level"] for m in unique_matches),
        key=lambda r: risk_priority.get(r, -1),
    )

    return {"risk_level": overall_risk, "analysis_results": results}
