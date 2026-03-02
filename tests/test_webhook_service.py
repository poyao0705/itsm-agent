"""Tests for the GitHub webhook endpoint (app.api.endpoints.github)."""

import json
import hmac
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.endpoints.github import handle_github_webhook


SECRET = "test-webhook-secret"


def _sign(body: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode(), msg=body, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _make_request(body: bytes) -> MagicMock:
    """Create a mock Request whose .body() returns the given bytes."""
    request = MagicMock()
    request.body = AsyncMock(return_value=body)
    return request


def _pr_body(action: str = "opened", merged: bool = False) -> bytes:
    return json.dumps(
        {
            "action": action,
            "pull_request": {"merged": merged, "number": 1},
            "repository": {"name": "repo", "owner": {"login": "owner"}},
            "installation": {"id": 999},
        }
    ).encode()


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_webhook_invalid_signature_raises_403():
    body = b'{"action": "opened"}'
    bad_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    with pytest.raises(HTTPException) as exc_info:
        await handle_github_webhook(
            request=_make_request(body),
            x_github_event="pull_request",
            x_hub_signature_256=bad_sig,
            session=AsyncMock(),
        )

    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Event routing
# Patch verify_signature to True so these tests are independent of the real
# GITHUB_WEBHOOK_SECRET loaded from .env.
# ---------------------------------------------------------------------------

_PATCH_SIG_OK = patch("app.api.endpoints.github.verify_signature", return_value=True)


@pytest.mark.asyncio
async def test_handle_webhook_merged_pr_is_ignored():
    body = _pr_body(action="closed", merged=True)

    with _PATCH_SIG_OK:
        result = await handle_github_webhook(
            request=_make_request(body),
            x_github_event="pull_request",
            x_hub_signature_256="any-sig",
            session=AsyncMock(),
        )
    assert result == {"message": "PR merged, ignored"}


@pytest.mark.asyncio
async def test_handle_webhook_non_pr_event_is_ignored():
    body = json.dumps({"ref": "refs/heads/main"}).encode()

    with _PATCH_SIG_OK:
        result = await handle_github_webhook(
            request=_make_request(body),
            x_github_event="push",
            x_hub_signature_256="any-sig",
            session=AsyncMock(),
        )
    assert result["message"] == "Event ignored"
    assert result["event"] == "push"


@pytest.mark.asyncio
async def test_handle_webhook_pull_request_returns_state():
    body = _pr_body(action="opened")
    fake_state = {"risk_level": "LOW", "analysis_results": []}

    mock_service = AsyncMock()
    mock_service.run_evaluation_workflow = AsyncMock(return_value=fake_state)

    with (
        _PATCH_SIG_OK,
        patch(
            "app.api.endpoints.github.EvaluationService",
            return_value=mock_service,
        ),
    ):
        result = await handle_github_webhook(
            request=_make_request(body),
            x_github_event="pull_request",
            x_hub_signature_256="any-sig",
            session=AsyncMock(),
        )

    assert result["message"] == "PR processed"
    assert result["state"] == fake_state


@pytest.mark.asyncio
async def test_handle_webhook_pull_request_workflow_error_raises_500():
    body = _pr_body(action="opened")

    mock_service = AsyncMock()
    mock_service.run_evaluation_workflow = AsyncMock(
        side_effect=RuntimeError("graph failed")
    )

    with (
        _PATCH_SIG_OK,
        patch(
            "app.api.endpoints.github.EvaluationService",
            return_value=mock_service,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await handle_github_webhook(
                request=_make_request(body),
                x_github_event="pull_request",
                x_hub_signature_256="any-sig",
                session=AsyncMock(),
            )

    assert exc_info.value.status_code == 500
    assert "graph failed" in exc_info.value.detail


@pytest.mark.asyncio
async def test_handle_webhook_invalid_json_body():
    body = b"not-valid-json"

    with _PATCH_SIG_OK:
        result = await handle_github_webhook(
            request=_make_request(body),
            x_github_event="push",
            x_hub_signature_256="any-sig",
            session=AsyncMock(),
        )
    assert "error" in result
