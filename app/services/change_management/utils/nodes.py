import re
from app.services.change_management.utils.schemas import AnalysisResult
from app.services.change_management.utils.schemas import AgentState
from app.services.change_management.utils.github_client import GitHubClient
from app.core.config import settings


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

    if not pr_number:
        return {}

    return {
        "owner": owner,
        "repo": repo,
        "pr_number": pr_number,
        "pr_url": pr_url,
    }


async def node_fetch_pr_info(state: AgentState) -> AgentState:
    """
    Fetch PR info via GitHub API and store in pr_evidence.
    """
    pr_info = await GitHubClient(settings.GITHUB_TOKEN).fetch_pr_info(
        state.owner, state.repo, state.pr_number, include_diff=True
    )
    return {"pr_info": pr_info}


def node_analyze_jira_ticket_number(state: AgentState) -> AgentState:
    """
    Node to analyze the JIRA ticket number in the PR.
    """
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
        summary="JIRA ticket number not found in PR title.",
        details={"pr_title": pr_title},
    )

    return {"analysis_results": [analysis_result]}
