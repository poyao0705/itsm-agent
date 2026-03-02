"""Tests for app.services.github.webhook_service."""

import json
import hmac
import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.github.webhook_service import (
    parse_webhook_payload,
    handle_github_webhook,
)


SECRET = "test-webhook-secret"


def _sign(body: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode(), msg=body, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ---------------------------------------------------------------------------
# parse_webhook_payload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_webhook_payload_json():
    payload_data = {"action": "opened", "number": 42}
    raw = json.dumps(payload_data).encode()

    request = MagicMock()
    request.headers = {"content-type": "application/json"}
    request.json = AsyncMock(return_value=payload_data)

    result = await parse_webhook_payload(request)
    assert result == payload_data


@pytest.mark.asyncio
async def test_parse_webhook_payload_invalid_json():
    request = MagicMock()
    request.headers = {"content-type": "application/json"}
    request.json = AsyncMock(side_effect=json.JSONDecodeError("err", "", 0))

    result = await parse_webhook_payload(request)
    assert result == {"error": "Invalid JSON body"}


# ---------------------------------------------------------------------------
# handle_github_webhook — signature checks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_webhook_invalid_signature_raises_403():
    body = b'{"action": "opened"}'
    bad_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    # Let the real verify_signature run — it will reject the bad sig
    with pytest.raises(HTTPException) as exc_info:
        await handle_github_webhook("pull_request", body, bad_sig)

    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# handle_github_webhook — pull_request events
# Patch verify_signature to True so these tests are independent of the real
# GITHUB_WEBHOOK_SECRET loaded from the project's .env file.
# ---------------------------------------------------------------------------

_PATCH_SIG_OK = patch(
    "app.services.github.webhook_service.verify_signature", return_value=True
)


def _pr_body(action: str = "opened", merged: bool = False) -> bytes:
    return json.dumps(
        {
            "action": action,
            "pull_request": {"merged": merged, "number": 1},
            "repository": {"name": "repo", "owner": {"login": "owner"}},
            "installation": {"id": 999},
        }
    ).encode()


@pytest.mark.asyncio
async def test_handle_webhook_merged_pr_is_ignored():
    body = _pr_body(action="closed", merged=True)

    with _PATCH_SIG_OK:
        result = await handle_github_webhook("pull_request", body, "any-sig")
    assert result == {"message": "PR merged, ignored"}


@pytest.mark.asyncio
async def test_handle_webhook_non_pr_event_is_ignored():
    body = json.dumps({"ref": "refs/heads/main"}).encode()

    with _PATCH_SIG_OK:
        result = await handle_github_webhook("push", body, "any-sig")
    assert result["message"] == "Event ignored"
    assert result["event"] == "push"


@pytest.mark.asyncio
async def test_handle_webhook_pull_request_returns_state():
    body = _pr_body(action="opened")
    fake_state = {"risk_level": "LOW", "analysis_results": []}

    mock_service = AsyncMock()
    mock_service.run_evaluation_workflow = AsyncMock(return_value=fake_state)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        _PATCH_SIG_OK,
        patch(
            "app.services.github.webhook_service.AsyncSessionLocal",
            return_value=mock_session,
        ),
        patch(
            "app.services.github.webhook_service.EvaluationService",
            return_value=mock_service,
        ),
    ):
        result = await handle_github_webhook("pull_request", body, "any-sig")

    assert result["message"] == "PR processed"
    assert result["state"] == fake_state


@pytest.mark.asyncio
async def test_handle_webhook_pull_request_workflow_error_raises_500():
    body = _pr_body(action="opened")

    mock_service = AsyncMock()
    mock_service.run_evaluation_workflow = AsyncMock(
        side_effect=RuntimeError("graph failed")
    )

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        _PATCH_SIG_OK,
        patch(
            "app.services.github.webhook_service.AsyncSessionLocal",
            return_value=mock_session,
        ),
        patch(
            "app.services.github.webhook_service.EvaluationService",
            return_value=mock_service,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await handle_github_webhook("pull_request", body, "any-sig")

    assert exc_info.value.status_code == 500
    assert "graph failed" in exc_info.value.detail


@pytest.mark.asyncio
async def test_handle_webhook_invalid_json_body():
    body = b"not-valid-json"

    with _PATCH_SIG_OK:
        result = await handle_github_webhook("push", body, "any-sig")
    # JSON parse error path returns an error dict
    assert "error" in result
