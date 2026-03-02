"""
Shared test configuration and fixtures.

Environment variables are set here before any app modules are imported,
because `settings = Settings()` runs eagerly at import time.
"""

import os

# ---------------------------------------------------------------------------
# Minimal environment variables required by Settings() at import time
# ---------------------------------------------------------------------------
os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test_db"
)
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("GITHUB_APP_ID", "12345")
os.environ.setdefault(
    "GITHUB_APP_PRIVATE_KEY",
    # Minimal fake PEM-like string (not a file path → no file read attempted)
    "FAKE_PRIVATE_KEY_FOR_TESTS",
)
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("JIRA_BASE_URL", "https://test.atlassian.net")
os.environ.setdefault("JIRA_EMAIL", "test@example.com")
os.environ.setdefault("JIRA_API_TOKEN", "test-jira-token")

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock

import app.core.http_client as http_client_module


@pytest.fixture(autouse=True)
def mock_http_client(monkeypatch):
    """
    Replace the global httpx.AsyncClient singleton with a MagicMock for every test.

    Individual tests can configure `.get.return_value` / `.post.return_value`
    on the returned mock as needed.
    """
    client = MagicMock(spec=httpx.AsyncClient)
    client.get = AsyncMock()
    client.post = AsyncMock()
    monkeypatch.setattr(http_client_module, "http_client", client)
    return client


def make_httpx_response(
    status_code: int = 200, json_data: dict | None = None, text: str = ""
) -> MagicMock:
    """Helper to build a fake httpx.Response-like mock."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data or {})
    resp.text = text
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"HTTP {status_code}",
            request=MagicMock(),
            response=resp,
        )
    return resp
