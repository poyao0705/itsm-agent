"""Tests for app.integrations.github.client.GitHubClient."""

import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import make_httpx_response
from app.integrations.github.client import GitHubClient


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_without_token():
    client = GitHubClient()
    assert "Authorization" not in client.headers
    assert client.base_url == "https://api.github.com"


def test_init_with_token():
    client = GitHubClient(token="ghp_test")
    assert client.headers["Authorization"] == "token ghp_test"


# ---------------------------------------------------------------------------
# get_pr
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pr_success(mock_http_client):
    pr_data = {"title": "Fix bug", "number": 42}
    mock_http_client.get.return_value = make_httpx_response(200, json_data=pr_data)

    client = GitHubClient(token="tok")
    result = await client.get_pr("octocat", "Hello-World", 42)

    assert result == pr_data
    mock_http_client.get.assert_called_once()
    call_url = mock_http_client.get.call_args[0][0]
    assert "pulls/42" in call_url


@pytest.mark.asyncio
async def test_get_pr_raises_on_http_error(mock_http_client):
    import httpx

    mock_http_client.get.return_value = make_httpx_response(404)

    client = GitHubClient()
    with pytest.raises(httpx.HTTPStatusError):
        await client.get_pr("octocat", "repo", 99)


# ---------------------------------------------------------------------------
# get_pr_files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pr_files_success(mock_http_client):
    files_data = [{"filename": "README.md", "additions": 2, "deletions": 0}]
    mock_http_client.get.return_value = make_httpx_response(200, json_data=files_data)

    client = GitHubClient()
    result = await client.get_pr_files("owner", "repo", 1)

    assert result == files_data
    call_url = mock_http_client.get.call_args[0][0]
    assert "files" in call_url


# ---------------------------------------------------------------------------
# get_pr_diff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pr_diff_success(mock_http_client):
    diff_text = "diff --git a/foo.py b/foo.py\n+++ b/foo.py\n+new line"
    mock_http_client.get.return_value = make_httpx_response(200, text=diff_text)

    client = GitHubClient()
    result = await client.get_pr_diff("owner", "repo", 5)

    assert result == diff_text
    # Should request diff format
    call_headers = mock_http_client.get.call_args[1]["headers"]
    assert call_headers["Accept"] == "application/vnd.github.v3.diff"


# ---------------------------------------------------------------------------
# fetch_pr_info
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_pr_info_success(mock_http_client):
    pr_data = {
        "title": "Add feature",
        "body": "Closes JIRA-123",
        "head": {"sha": "abc123"},
        "base": {"sha": "def456"},
        "additions": 10,
        "deletions": 2,
    }
    files_data = [
        {
            "filename": "app/main.py",
            "additions": 10,
            "deletions": 2,
            "changes": 12,
            "status": "modified",
            "patch": "@@ -1 +1 @@",
        }
    ]

    mock_http_client.get.side_effect = [
        make_httpx_response(200, json_data=pr_data),
        make_httpx_response(200, json_data=files_data),
    ]

    client = GitHubClient(token="tok")
    result = await client.fetch_pr_info("owner", "repo", 7)

    assert result["pr_title"] == "Add feature"
    assert result["head_sha"] == "abc123"
    assert result["base_sha"] == "def456"
    assert len(result["changed_files"]) == 1
    assert result["changed_files"][0]["path"] == "app/main.py"
    assert "pr_body_sha256" in result
    assert mock_http_client.get.call_count == 2


@pytest.mark.asyncio
async def test_fetch_pr_info_with_diff(mock_http_client):
    pr_data = {
        "title": "PR",
        "body": "",
        "head": {"sha": "sha1"},
        "base": {"sha": "sha2"},
        "additions": 1,
        "deletions": 0,
    }
    diff_pr_data = {**pr_data}
    files_data = []
    diff_text = "diff --git a/x b/x"

    mock_http_client.get.side_effect = [
        make_httpx_response(200, json_data=pr_data),  # fetch_pr_info parallel call 1
        make_httpx_response(200, json_data=files_data),  # fetch_pr_info parallel call 2
        make_httpx_response(200, text=diff_text),  # get_pr_diff
    ]

    client = GitHubClient()
    result = await client.fetch_pr_info("owner", "repo", 1, include_diff=True)

    assert result.get("diff") == diff_text


# ---------------------------------------------------------------------------
# post_pr_comment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_pr_comment_success(mock_http_client):
    mock_http_client.post.return_value = make_httpx_response(201)

    client = GitHubClient(token="tok")
    await client.post_pr_comment("owner", "repo", 3, "LGTM!")

    mock_http_client.post.assert_called_once()
    call_kwargs = mock_http_client.post.call_args[1]
    assert call_kwargs["json"] == {"body": "LGTM!"}
    assert "issues/3/comments" in mock_http_client.post.call_args[0][0]
