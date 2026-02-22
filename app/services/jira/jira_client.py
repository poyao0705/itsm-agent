"""A client for interacting with the JIRA API."""

from typing import Any
import httpx


class JiraClient:
    """A reusable utility class for interacting with the JIRA API."""

    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.auth = (email, api_token)

    async def get_issue(self, issue_key: str) -> dict[str, Any]:
        """Fetch a JIRA issue by its key.

        Args:
            issue_key (str): The key of the JIRA issue to fetch.

        Returns:
            dict[str, Any]: The JIRA issue data.
        """

        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                auth=self.auth,
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return response.json()
