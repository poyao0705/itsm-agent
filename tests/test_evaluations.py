"""Tests for app.services.change_management.evaluations.EvaluationService."""

import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.change_management.evaluations import EvaluationService


def _make_service(http_client=None):
    """Return an EvaluationService with a stubbed AsyncSession."""
    session = AsyncMock()
    return EvaluationService(session, http_client=http_client)


def _make_pr_payload(
    owner="octocat",
    repo="hello-world",
    pr_number=7,
    head_sha="deadbeef1234",
    body="Closes JIRA-100",
    action="opened",
):
    return {
        "action": action,
        "repository": {"name": repo, "owner": {"login": owner}},
        "pull_request": {
            "number": pr_number,
            "body": body,
            "head": {"sha": head_sha},
        },
        "installation": {"id": 999},
    }


# ---------------------------------------------------------------------------
# _extract_evaluation_context
# ---------------------------------------------------------------------------


def test_extract_context_builds_key():
    svc = _make_service()
    payload = _make_pr_payload()
    ctx = svc._extract_evaluation_context(payload)

    assert ctx is not None
    assert ctx["owner"] == "octocat"
    assert ctx["repo"] == "hello-world"
    assert ctx["pr_number"] == 7

    # Key format: owner/repo:pr_number:head_sha:body_hash[:8]
    body_hash = hashlib.sha256(b"Closes JIRA-100").hexdigest()[:8]
    expected_key = f"octocat/hello-world:7:deadbeef1234:{body_hash}"
    assert ctx["evaluation_key"] == expected_key


def test_extract_context_missing_owner_returns_none():
    svc = _make_service()
    payload = _make_pr_payload()
    # Remove owner info
    payload["repository"] = {"name": "repo", "owner": {}, "full_name": ""}
    result = svc._extract_evaluation_context(payload)
    assert result is None


def test_extract_context_missing_pr_number_returns_none():
    svc = _make_service()
    payload = _make_pr_payload()
    payload["pull_request"]["number"] = None
    result = svc._extract_evaluation_context(payload)
    assert result is None


def test_extract_context_missing_head_sha_returns_none():
    svc = _make_service()
    payload = _make_pr_payload()
    payload["pull_request"]["head"] = {}
    result = svc._extract_evaluation_context(payload)
    assert result is None


def test_extract_context_empty_body_uses_empty_hash():
    svc = _make_service()
    payload = _make_pr_payload(body="")
    ctx = svc._extract_evaluation_context(payload)
    assert ctx is not None
    expected_hash = hashlib.sha256(b"").hexdigest()[:8]
    assert ctx["evaluation_key"].endswith(expected_hash)


def test_extract_context_none_body_treated_as_empty():
    svc = _make_service()
    payload = _make_pr_payload()
    payload["pull_request"]["body"] = None
    ctx = svc._extract_evaluation_context(payload)
    assert ctx is not None


# ---------------------------------------------------------------------------
# count_evaluations — pagination/counting (mocked session)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_evaluations_returns_scalar():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = 5
    session.execute = AsyncMock(return_value=mock_result)

    svc = EvaluationService(session)
    count = await svc.count_evaluations()
    assert count == 5


@pytest.mark.asyncio
async def test_count_evaluations_returns_zero_on_none():
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar.return_value = None
    session.execute = AsyncMock(return_value=mock_result)

    svc = EvaluationService(session)
    count = await svc.count_evaluations()
    assert count == 0


# ---------------------------------------------------------------------------
# run_evaluation_workflow — error path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_evaluation_workflow_reraises_on_graph_error(mock_http_client):
    svc = _make_service(mock_http_client)
    payload = _make_pr_payload()
    mark_error = AsyncMock()

    with (
        patch.object(
            svc,
            "_extract_evaluation_context",
            return_value={
                "evaluation_key": "k",
                "owner": "o",
                "repo": "r",
                "pr_number": 1,
            },
        ),
        patch.object(svc, "_create_evaluation_run", AsyncMock(return_value="uuid-123")),
        patch(
            "app.services.change_management.evaluations.change_management_graph"
        ) as mock_graph,
        patch.object(svc, "_mark_evaluation_error", mark_error),
    ):
        mock_graph.ainvoke = AsyncMock(side_effect=RuntimeError("graph boom"))

        with pytest.raises(RuntimeError, match="graph boom"):
            await svc.run_evaluation_workflow(payload)

        mock_graph.ainvoke.assert_awaited_once_with(
            {"webhook_payload": payload},
            context={"http_client": mock_http_client},
        )
        mark_error.assert_awaited_once_with("uuid-123", "graph boom")


@pytest.mark.asyncio
async def test_run_evaluation_workflow_success(mock_http_client):
    svc = _make_service(mock_http_client)
    payload = _make_pr_payload()
    fake_state = {"risk_level": "LOW", "analysis_results": []}

    mock_persist = AsyncMock()
    mock_finalize = AsyncMock()

    with (
        patch.object(
            svc,
            "_extract_evaluation_context",
            return_value={
                "evaluation_key": "k",
                "owner": "o",
                "repo": "r",
                "pr_number": 1,
            },
        ),
        patch.object(svc, "_create_evaluation_run", AsyncMock(return_value="uuid-456")),
        patch(
            "app.services.change_management.evaluations.change_management_graph"
        ) as mock_graph,
        patch.object(svc, "_persist_analysis_results", mock_persist),
        patch.object(svc, "_finalize_evaluation_run", mock_finalize),
    ):
        mock_graph.ainvoke = AsyncMock(return_value=fake_state)
        result = await svc.run_evaluation_workflow(payload)

        assert result == fake_state
        mock_graph.ainvoke.assert_awaited_once_with(
            {"webhook_payload": payload},
            context={"http_client": mock_http_client},
        )
        mock_persist.assert_called_once_with("uuid-456", fake_state)
        mock_finalize.assert_called_once_with("uuid-456", fake_state)
