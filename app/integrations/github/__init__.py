"""
GitHub integration package.
"""

from app.integrations.github.auth import get_access_token
from app.integrations.github.client import GitHubClient

__all__ = [
    "get_access_token",
    "GitHubClient",
]
