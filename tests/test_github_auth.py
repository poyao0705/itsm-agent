"""Tests for app.integrations.github.auth.get_access_token."""

import pytest
from unittest.mock import patch

import httpx

from tests.conftest import make_httpx_response


# ---------------------------------------------------------------------------
# get_access_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_access_token_success(mock_http_client):
    mock_http_client.post.return_value = make_httpx_response(
        201, json_data={"token": "ghs_installationtoken"}
    )

    with patch(
        "app.integrations.github.auth.jwt.encode", return_value="fake.jwt.token"
    ):
        from app.integrations.github.auth import get_access_token

        token = await get_access_token(mock_http_client, installation_id=12345)

    assert token == "ghs_installationtoken"
    mock_http_client.post.assert_called_once()

    call_args = mock_http_client.post.call_args
    assert "12345" in call_args[0][0]
    headers = call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer fake.jwt.token"
    assert headers["Accept"] == "application/vnd.github+json"


@pytest.mark.asyncio
async def test_get_access_token_http_error_raises(mock_http_client):
    mock_http_client.post.return_value = make_httpx_response(401)

    with patch(
        "app.integrations.github.auth.jwt.encode", return_value="fake.jwt.token"
    ):
        from app.integrations.github.auth import get_access_token

        with pytest.raises(httpx.HTTPStatusError):
            await get_access_token(mock_http_client, installation_id=999)


@pytest.mark.asyncio
async def test_get_access_token_builds_correct_jwt_payload(mock_http_client):
    """JWT payload contains iat, exp, iss fields."""
    mock_http_client.post.return_value = make_httpx_response(
        201, json_data={"token": "tok"}
    )
    captured_payload = {}

    def fake_encode(payload, *_args, **_kwargs):
        captured_payload.update(payload)
        return "fake.jwt"

    with patch("app.integrations.github.auth.jwt.encode", side_effect=fake_encode):
        from app.integrations.github.auth import get_access_token

        await get_access_token(mock_http_client, 1)

    assert "iat" in captured_payload
    assert "exp" in captured_payload
    assert "iss" in captured_payload
    assert captured_payload["exp"] > captured_payload["iat"]
