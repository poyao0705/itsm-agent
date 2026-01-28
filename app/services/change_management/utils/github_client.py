"""
GitHub REST API client for fetching PR information.

This module provides functions to fetch PR data using the GitHub REST API.
REST is chosen over GraphQL because:
1. REST provides full diff content (GraphQL cannot)
2. Simpler API with better documentation
3. All required data available in 1-2 calls
"""

import asyncio
import hashlib
from typing import Dict, List, Optional, Any
import httpx


class GitHubClient:
    """Client for interacting with GitHub REST API."""

    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub client.

        Args:
            token: GitHub Personal Access Token or GitHub App token
        """
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ITSM-Agent/1.0",
        }
        if token:
            self.headers["Authorization"] = f"token {token}"

    async def get_pr(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """
        Get pull request details.

        Args:
            owner: Repository owner (e.g., "octocat")
            repo: Repository name (e.g., "Hello-World")
            pr_number: Pull request number

        Returns:
            PR data including title, body, head SHA, etc.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def get_pr_files(
        self, owner: str, repo: str, pr_number: int
    ) -> List[Dict[str, Any]]:
        """
        Get list of files changed in a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            List of file change objects with path, additions, deletions, etc.
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """
        Get full diff content for a pull request.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number

        Returns:
            Full diff content as text (unified diff format)
        """
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"

        headers = {
            **self.headers,
            "Accept": "application/vnd.github.v3.diff",  # Request diff format
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.text

    async def fetch_pr_info(
        self, owner: str, repo: str, pr_number: int, include_diff: bool = False
    ) -> Dict[str, Any]:
        """
        Fetch all PR evidence needed for evaluation.

        This is the main function to use - it fetches everything in parallel.

        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            include_diff: Whether to include full diff content (can be large)

        Returns:
            Dictionary containing:
            - pr_title: PR title
            - pr_body: PR body
            - head_sha: Commit SHA of PR head
            - changed_files: List of changed files with paths and stats
            - diff: Full diff content (if include_diff=True)
            - pr_body_sha256: SHA256 hash of PR body for idempotency
        """
        # Fetch PR details and files in parallel
        async with httpx.AsyncClient() as client:
            pr_url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
            files_url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/files"

            # Fetch both in parallel
            pr_response, files_response = await asyncio.gather(
                client.get(pr_url, headers=self.headers),
                client.get(files_url, headers=self.headers),
            )

            pr_response.raise_for_status()
            files_response.raise_for_status()

            pr_data = pr_response.json()
            files_data = files_response.json()

        # Extract changed files info
        changed_files = [
            {
                "path": file["filename"],
                "additions": file.get("additions", 0),
                "deletions": file.get("deletions", 0),
                "changes": file.get("changes", 0),
                "status": file.get("status"),  # added, modified, removed, renamed
                "patch": file.get("patch"),  # Small patch snippet (if available)
            }
            for file in files_data
        ]

        # Compute PR body hash for idempotency
        pr_body = pr_data.get("body", "") or ""
        pr_body_sha256 = hashlib.sha256(pr_body.encode()).hexdigest()

        result = {
            "pr_title": pr_data.get("title", ""),
            "pr_body": pr_body,
            "pr_body_sha256": pr_body_sha256,
            "head_sha": pr_data.get("head", {}).get("sha"),
            "base_sha": pr_data.get("base", {}).get("sha"),
            "changed_files": changed_files,
            "changed_files_count": len(changed_files),
            "total_additions": pr_data.get("additions", 0),
            "total_deletions": pr_data.get("deletions", 0),
        }

        # Optionally fetch full diff (can be large, so make it optional)
        if include_diff:
            result["diff"] = await self.get_pr_diff(owner, repo, pr_number)

        return result
