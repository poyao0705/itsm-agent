"""Tests for app.services.github.security.verify_signature."""

import hmac
import hashlib

import pytest

from app.services.github.security import verify_signature


SECRET = "my-webhook-secret"


def _make_signature(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), msg=body, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_valid_signature_returns_true():
    body = b'{"action": "opened"}'
    sig = _make_signature(body, SECRET)
    assert verify_signature(body, SECRET, sig) is True


def test_valid_signature_empty_body():
    body = b""
    sig = _make_signature(body, SECRET)
    assert verify_signature(body, SECRET, sig) is True


# ---------------------------------------------------------------------------
# Negative cases
# ---------------------------------------------------------------------------


def test_missing_signature_header_returns_false():
    body = b'{"action": "opened"}'
    assert verify_signature(body, SECRET, "") is False
    assert verify_signature(body, SECRET, None) is False  # type: ignore[arg-type]


def test_wrong_secret_returns_false():
    body = b'{"action": "opened"}'
    sig = _make_signature(body, "different-secret")
    assert verify_signature(body, SECRET, sig) is False


def test_tampered_body_returns_false():
    original_body = b'{"action": "opened"}'
    sig = _make_signature(original_body, SECRET)
    tampered_body = b'{"action": "closed"}'
    assert verify_signature(tampered_body, SECRET, sig) is False


def test_signature_without_prefix_returns_false():
    body = b'{"action": "opened"}'
    # Raw hex without "sha256=" prefix
    raw_hex = hmac.new(SECRET.encode(), msg=body, digestmod=hashlib.sha256).hexdigest()
    assert verify_signature(body, SECRET, raw_hex) is False


def test_malformed_signature_returns_false():
    body = b'{"action": "opened"}'
    assert verify_signature(body, SECRET, "sha256=not-a-real-hex") is False
