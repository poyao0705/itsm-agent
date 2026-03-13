"""
PR I/O nodes for the Change Management Agent.

These nodes handle reading from webhooks, fetching PR info, and posting comments.
"""

import httpx

from app.core.logging import get_logger
from app.services.change_management.state import AgentState
from app.integrations.github import GitHubClient, get_access_token

logger = get_logger(__name__)


def is_retryable_github_error(exc: Exception) -> bool:
    """Return whether a GitHub API error is worth retrying."""
    if isinstance(exc, httpx.RequestError):
        return True

    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code if exc.response is not None else None
        return status_code == 429 or (status_code is not None and status_code >= 500)

    return False


def _get_http_client(state: AgentState) -> httpx.AsyncClient:
    """Return the HTTP client injected into graph state."""
    client = state.http_client
    if client is None:
        raise RuntimeError("http_client not provided in graph state")
    return client


async def read_pr_from_webhook(state: AgentState) -> dict:
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
    # GitHub App installation ID - used to generate scoped access tokens for this specific app installation
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


async def fetch_pr_info(state: AgentState) -> dict:
    """
    Fetch PR info via GitHub API and store in pr_evidence.
    """
    if not state.owner or not state.repo or not state.pr_number:
        logger.warning("Missing required PR identifiers, skipping fetch.")
        return {}

    client = _get_http_client(state)

    # Use the installation token if available
    token = None
    if state.installation_id:
        try:
            token = await get_access_token(client, state.installation_id)
        except httpx.HTTPError as exc:
            logger.warning("Failed to get installation token: %s", exc)
            raise

    try:
        pr_info = await GitHubClient(client, token).fetch_pr_info(
            state.owner, state.repo, state.pr_number, include_diff=True
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "Failed to fetch PR info for %s/%s#%s: %s",
            state.owner,
            state.repo,
            state.pr_number,
            exc,
        )
        raise

    return {"pr_info": pr_info}


async def post_pr_comment(state: AgentState) -> dict:
    """
    Node to post a comment on the PR.
    """
    pr_info = state.pr_info or {}
    pr_url = pr_info.get("pr_url", "")
    analysis_results = state.analysis_results or []

    comment = "\n".join([res.summary for res in analysis_results])

    client = _get_http_client(state)

    # We want to post a comment.
    if state.installation_id:
        try:
            token = await get_access_token(client, state.installation_id)

            github_client = GitHubClient(client, token)
            await github_client.post_pr_comment(
                state.owner,
                state.repo,
                state.pr_number,
                comment,
            )
            return {"pr_url": pr_url, "comment": "Commented on PR"}
        except httpx.HTTPError as exc:
            return {"pr_url": pr_url, "comment": f"Failed to comment: {exc}"}

    return {"pr_url": pr_url, "comment": "No installation ID, skipped comment"}
