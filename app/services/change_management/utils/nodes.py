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


# Node to analyze code diff and give a risk level
def node_analyze_code_diff_hard(state: AgentState) -> AgentState:
    """
    Node to analyze code diff and give a risk level based on the hard gate.
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
    except Exception as e:
        print(f"Failed to load policy: {e}")
        return {}

    # Check for HIGH risk matches
    matched_rules = []

    for file_obj in changed_files:
        path = file_obj.get("path", "")
        for rule in rules:
            for pattern in rule.path_patterns:
                if fnmatch.fnmatch(path, pattern):
                    matched_rules.append((path, rule))

    if matched_rules:
        # Deduplicate, formatted for details
        unique_matches = []
        seen = set()
        for path, rule in matched_rules:
            key = (path, rule.id)
            if key not in seen:
                unique_matches.append(
                    {"file": path, "rule_id": rule.id, "rule_desc": rule.description}
                )
                seen.add(key)
        # New line for each file
        unique_file_paths = sorted(list(set(m["file"] for m in unique_matches)))
        files_str = "\n".join([f"- {f}" for f in unique_file_paths])
        summary = f"Detected HIGH risk changes based on policy. Matched {len(unique_file_paths)} files. \nFiles:\n{files_str}"

        result = AnalysisResult(
            run_id=state.run_id,
            node_name="node_analyze_code_diff_hard",
            reason_code="HARD_GATE_HIGH_RISK",
            summary="[HIGH RISK] " + summary,
            details={"matched_files": unique_matches},
        )

        return {"risk_level": "HIGH", "analysis_results": [result]}

    return {"risk_level": "UNKNOWN"}
