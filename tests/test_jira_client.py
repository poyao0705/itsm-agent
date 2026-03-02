"""Tests for app.services.jira.jira_client.JiraClient."""

import pytest
import httpx
from unittest.mock import MagicMock

from tests.conftest import make_httpx_response
from app.integrations.jira.client import JiraClient


BASE_URL = "https://mycompany.atlassian.net"
EMAIL = "sre@example.com"
TOKEN = "my-api-token"


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_strips_trailing_slash():
    client = JiraClient(BASE_URL + "/", EMAIL, TOKEN)
    assert not client.base_url.endswith("/")
    assert client.base_url == BASE_URL


def test_init_stores_auth_tuple():
    client = JiraClient(BASE_URL, EMAIL, TOKEN)
    assert client.auth == (EMAIL, TOKEN)


# ---------------------------------------------------------------------------
# get_issue — success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_issue_success(mock_http_client):
    issue_data = {
        "id": "10001",
        "key": "PROJ-42",
        "fields": {"summary": "Fix login bug", "status": {"name": "In Progress"}},
    }
    mock_http_client.get.return_value = make_httpx_response(200, json_data=issue_data)

    client = JiraClient(BASE_URL, EMAIL, TOKEN)
    result = await client.get_issue("PROJ-42")

    assert result == issue_data
    mock_http_client.get.assert_called_once()

    call_args = mock_http_client.get.call_args
    assert "PROJ-42" in call_args[0][0]
    assert call_args[1]["auth"] == (EMAIL, TOKEN)
    assert call_args[1]["headers"] == {"Accept": "application/json"}


@pytest.mark.asyncio
async def test_get_issue_url_format(mock_http_client):
    mock_http_client.get.return_value = make_httpx_response(200, json_data={})

    client = JiraClient(BASE_URL, EMAIL, TOKEN)
    await client.get_issue("XYZ-999")

    expected_url = f"{BASE_URL}/rest/api/3/issue/XYZ-999"
    actual_url = mock_http_client.get.call_args[0][0]
    assert actual_url == expected_url


# ---------------------------------------------------------------------------
# get_issue — HTTP errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_issue_404_raises(mock_http_client):
    mock_http_client.get.return_value = make_httpx_response(404)

    client = JiraClient(BASE_URL, EMAIL, TOKEN)
    with pytest.raises(httpx.HTTPStatusError):
        await client.get_issue("NOTFOUND-1")


@pytest.mark.asyncio
async def test_get_issue_401_raises(mock_http_client):
    mock_http_client.get.return_value = make_httpx_response(401)

    client = JiraClient(BASE_URL, EMAIL, TOKEN)
    with pytest.raises(httpx.HTTPStatusError):
        await client.get_issue("PROJ-1")


@pytest.mark.asyncio
async def test_get_issue_500_raises(mock_http_client):
    mock_http_client.get.return_value = make_httpx_response(500)

    client = JiraClient(BASE_URL, EMAIL, TOKEN)
    with pytest.raises(httpx.HTTPStatusError):
        await client.get_issue("PROJ-1")
