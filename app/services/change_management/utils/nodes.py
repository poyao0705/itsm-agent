"""
Node implementations for the Change Management Agent.
"""

import re
import fnmatch
import os
from app.services.change_management.utils.schemas import AnalysisResult
from app.services.change_management.utils.schemas import AgentState
from app.services.change_management.utils.github_client import (
    GitHubClient,
    get_access_token,
)

from app.services.change_management.utils.yaml_utils import (
    load_policy,
    get_change_rules,
    get_risk_priority,
)


async def node_read_pr_from_webhook(state: AgentState) -> AgentState:
    """
    Extract PR identifiers from webhook payload into state.

    If state contains 'webhook_payload' (pull_request event), populates
    owner, repo, pr_number, pr_id, pr_url. Otherwise no-op.
    """
    payload = state.webhook_payload or {}
    repo_data = payload.get("repository") or {}
    pr_data = payload.get("pull_request") or {}

    if not pr_data or not repo_data:
        return {}

    owner = (repo_data.get("owner") or {}).get("login") or repo_data.get(
        "full_name", ""
    ).split("/")[0]
    repo = repo_data.get("name", "")
    pr_number = int(pr_data.get("number", 0))
    pr_url = pr_data.get("html_url", "")
    installation_id = payload.get("installation", {}).get("id")

    if not pr_number:
        return {}

    return {
        "owner": owner,
        "repo": repo,
        "pr_number": pr_number,
        "pr_url": pr_url,
        "installation_id": installation_id,
    }


async def node_fetch_pr_info(state: AgentState) -> AgentState:
    """
    Fetch PR info via GitHub API and store in pr_evidence.
    """
    if not state.owner or not state.repo or not state.pr_number:
        print("Missing required PR identifiers, skipping fetch.")
        return {}

    # Use the installation token if available
    token = None
    if state.installation_id:
        try:
            token = await get_access_token(state.installation_id)
        except Exception as e:
            print(f"Failed to get installation token: {e}")

    pr_info = await GitHubClient(token).fetch_pr_info(
        state.owner, state.repo, state.pr_number, include_diff=True
    )
    return {"pr_info": pr_info}


def node_analyze_jira_ticket_number(state: AgentState) -> AgentState:
    """
    Node to analyze the JIRA ticket number in the PR.
    """
    if not state.pr_info:
        print("Missing pr_info, skipping JIRA analysis.")
        return {}

    pr_info = state.pr_info or {}
    pr_title = pr_info.get("pr_title", "")

    # Regex to extract PR title JIRA ticket number -- Pattern: ABCD-1234
    # Multiple characters + hyphen + multiple digits
    match = re.search(r"([A-Z]+-\d+)", pr_title)

    if match:
        return {"jira_ticket_number": match.group(1)}

    analysis_result = AnalysisResult(
        run_id=state.run_id,
        node_name="node_analyze_jira_ticket_number",
        reason_code="JIRA_TICKET_NUMBER_NOT_FOUND",
        summary="[BLOCKER] JIRA ticket number not found in PR title.",
        details={"pr_title": pr_title},
    )

    return {"analysis_results": [analysis_result]}


async def node_post_pr_comment(state: AgentState) -> AgentState:
    """
    Node to post a comment on the PR.
    """
    pr_info = state.pr_info or {}
    pr_url = pr_info.get("pr_url", "")
    analysis_results = state.analysis_results or []

    comment = "\n".join([res.summary for res in analysis_results])

    # We want to post a comment.
    if state.installation_id:
        try:
            token = await get_access_token(state.installation_id)

            client = GitHubClient(token)
            await client.post_pr_comment(
                state.owner,
                state.repo,
                state.pr_number,
                comment,
            )
            return {"pr_url": pr_url, "comment": "Commented on PR"}
        except Exception as e:
            return {"pr_url": pr_url, "comment": f"Failed to comment: {e}"}

    return {"pr_url": pr_url, "comment": "No installation ID, skipped comment"}


def node_policy_rule_analysis(state: AgentState) -> AgentState:
    """
    Analyze code diff and give a risk level based on policy rules.
    """
    pr_info = state.pr_info or {}
    changed_files = pr_info.get("changed_files", [])

    if not changed_files:
        print("No changed files to analyze.")
        return {}

    # Load Policy
    try:
        policy_path = os.path.join(os.getcwd(), "docs/policy.yaml")
        policy = load_policy(policy_path)
        rules = get_change_rules(policy, excluded_risk_levels=["LOW"])
        risk_priority = get_risk_priority(policy)
    except Exception as e:
        print(f"Failed to load policy: {e}")
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

    # Create one AnalysisResult per match
    results = [
        AnalysisResult(
            run_id=state.run_id,
            node_name="node_policy_rule_analysis",
            reason_code=f"{m['risk_level']}_RISK_RULES_MATCHED",
            summary=f"[{m['risk_level']} RISK] {m['file']}: {m['rule_desc']}",
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
