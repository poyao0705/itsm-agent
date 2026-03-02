"""Tests for change management graph nodes: utils and pr_io."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.change_management.nodes.utils import make_result
from app.services.change_management.nodes.pr_io import (
    read_pr_from_webhook,
    fetch_pr_info,
)
from app.services.change_management.state import AgentState
from app.db.models.analysis_result import AnalysisResultCreate


# ===========================================================================
# make_result
# ===========================================================================


def test_make_result_basic():
    result = make_result(
        node_name="my_node",
        reason_code="NO_JIRA",
        summary="Missing JIRA ticket.",
        risk_level="HIGH",
        details={"pr_title": "chore: update deps"},
    )
    assert result["risk_level"] == "HIGH"
    assert len(result["analysis_results"]) == 1
    ar: AnalysisResultCreate = result["analysis_results"][0]
    assert ar.node_name == "my_node"
    assert ar.reason_code == "NO_JIRA"
    assert ar.summary == "Missing JIRA ticket."
    assert ar.risk_level == "HIGH"
    assert ar.details == {"pr_title": "chore: update deps"}


def test_make_result_extra_kwargs_are_merged():
    result = make_result(
        node_name="n",
        reason_code="R",
        summary="S",
        risk_level="LOW",
        details={},
        jira_ticket_number="PROJ-42",
    )
    assert result.get("jira_ticket_number") == "PROJ-42"


def test_make_result_empty_details():
    result = make_result(
        node_name="n", reason_code="R", summary="S", risk_level="MEDIUM", details={}
    )
    assert result["analysis_results"][0].details == {}


# ===========================================================================
# read_pr_from_webhook
# ===========================================================================


def _make_state(payload: dict | None = None) -> AgentState:
    return AgentState(webhook_payload=payload)


@pytest.mark.asyncio
async def test_read_pr_from_webhook_extracts_fields():
    payload = {
        "action": "opened",
        "repository": {"name": "my-repo", "owner": {"login": "my-org"}},
        "pull_request": {
            "number": 15,
            "html_url": "https://github.com/my-org/my-repo/pull/15",
        },
        "installation": {"id": 777},
    }
    state = _make_state(payload)
    result = await read_pr_from_webhook(state)

    assert result["owner"] == "my-org"
    assert result["repo"] == "my-repo"
    assert result["pr_number"] == 15
    assert result["pr_url"] == "https://github.com/my-org/my-repo/pull/15"
    assert result["installation_id"] == 777


@pytest.mark.asyncio
async def test_read_pr_from_webhook_no_payload_returns_empty():
    state = _make_state(payload=None)
    result = await read_pr_from_webhook(state)
    assert result == {}


@pytest.mark.asyncio
async def test_read_pr_from_webhook_missing_pr_data_returns_empty():
    state = _make_state(payload={"action": "push", "repository": {"name": "repo"}})
    result = await read_pr_from_webhook(state)
    assert result == {}


@pytest.mark.asyncio
async def test_read_pr_from_webhook_pr_number_zero_returns_empty():
    payload = {
        "repository": {"name": "r", "owner": {"login": "o"}},
        "pull_request": {"number": 0, "html_url": ""},
    }
    state = _make_state(payload)
    result = await read_pr_from_webhook(state)
    assert result == {}


@pytest.mark.asyncio
async def test_read_pr_from_webhook_uses_full_name_fallback():
    """owner should be extracted from repository.full_name when owner.login is absent."""
    payload = {
        "repository": {"name": "repo", "owner": {}, "full_name": "fallback-org/repo"},
        "pull_request": {"number": 3, "html_url": ""},
    }
    state = _make_state(payload)
    result = await read_pr_from_webhook(state)
    assert result.get("owner") == "fallback-org"


# ===========================================================================
# fetch_pr_info
# ===========================================================================


@pytest.mark.asyncio
async def test_fetch_pr_info_missing_identifiers_returns_empty():
    state = AgentState()  # no owner/repo/pr_number
    result = await fetch_pr_info(state)
    assert result == {}


def _pr_get_side_effects(
    pr_data: dict, files_data: list = None, diff_text: str = ""
) -> list:
    """Build the 3-response mock list needed for fetch_pr_info(include_diff=True):
    parallel GET for PR details, parallel GET for files, GET for diff.
    """
    from tests.conftest import make_httpx_response

    return [
        make_httpx_response(200, json_data=pr_data),
        make_httpx_response(200, json_data=files_data or []),
        make_httpx_response(200, text=diff_text),
    ]


@pytest.mark.asyncio
async def test_fetch_pr_info_calls_github_client(mock_http_client):
    pr_data = {
        "title": "My PR",
        "body": "body",
        "head": {"sha": "abc"},
        "base": {"sha": "def"},
        "additions": 5,
        "deletions": 1,
    }
    mock_http_client.get.side_effect = _pr_get_side_effects(pr_data)

    state = AgentState(owner="org", repo="repo", pr_number=1)

    # No installation_id → token is None, no auth call
    with patch(
        "app.services.change_management.nodes.pr_io.get_access_token"
    ) as mock_token:
        result = await fetch_pr_info(state)

    mock_token.assert_not_called()
    assert result["pr_info"]["pr_title"] == "My PR"


@pytest.mark.asyncio
async def test_fetch_pr_info_uses_installation_token(mock_http_client):
    pr_data = {
        "title": "Secure PR",
        "body": "",
        "head": {"sha": "sha1"},
        "base": {"sha": "sha2"},
        "additions": 0,
        "deletions": 0,
    }
    mock_http_client.get.side_effect = _pr_get_side_effects(pr_data)

    state = AgentState(owner="org", repo="repo", pr_number=2, installation_id=555)

    with patch(
        "app.services.change_management.nodes.pr_io.get_access_token",
        AsyncMock(return_value="inst-token"),
    ):
        result = await fetch_pr_info(state)

    assert result["pr_info"]["pr_title"] == "Secure PR"


@pytest.mark.asyncio
async def test_fetch_pr_info_continues_if_token_fetch_fails(mock_http_client):
    """A token fetch failure should log a warning but still attempt the PR fetch."""
    pr_data = {
        "title": "PR",
        "body": "",
        "head": {"sha": "s"},
        "base": {"sha": "b"},
        "additions": 0,
        "deletions": 0,
    }
    mock_http_client.get.side_effect = _pr_get_side_effects(pr_data)

    state = AgentState(owner="o", repo="r", pr_number=9, installation_id=123)

    with patch(
        "app.services.change_management.nodes.pr_io.get_access_token",
        AsyncMock(side_effect=Exception("token error")),
    ):
        result = await fetch_pr_info(state)

    # Should still have pr_info with token=None (no Authorization header set)
    assert "pr_info" in result
