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
    print("node_fetch_pr_info pr_info:", pr_info)
    return {"pr_info": pr_info}


def node_analyze_jira_ticket_number(state: AgentState) -> AgentState:
    """
    Node to analyze the JIRA ticket number in the PR.
    """

    return state
