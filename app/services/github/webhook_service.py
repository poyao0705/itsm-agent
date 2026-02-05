"""GitHub webhook handling: payload parsing and event processing."""

import json
import logging

from starlette.requests import Request
from fastapi import HTTPException

from app.services.change_management.graph import change_management_graph
from app.services.github.security import verify_signature
from app.core.config import settings
from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


async def parse_webhook_payload(request: Request) -> dict:
    """
    Extract and parse the webhook payload from a GitHub webhook request.

    Tries:
    1. JSON body (default for application/json)
    2. Form data with "payload" field (application/x-www-form-urlencoded)
    3. Raw form data

    Returns:
        Parsed payload dict.
    """
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            return await request.json()
        except json.JSONDecodeError:
            return {"error": "Invalid JSON body"}


async def handle_github_webhook(
    request: Request, event_type: str, raw_body: bytes, signature_header: str
) -> dict:
    """
    Process a GitHub webhook: parse payload and route by event type.

    - Verifies HMAC SHA-256 signature.
    - pull_request: runs the Change Management agent and returns its result.
    - Other events: logged and ignored.

    Args:
        request: The incoming HTTP request.
        event_type: The X-GitHub-Event header value (e.g. "push", "pull_request").
        raw_body: The raw body bytes for signature verification.
        signature_header: The X-Hub-Signature-256 header.

    Returns:
        A dict to be returned as the JSON response (e.g. {"message": "...", ...}).
    """
    # 1. Verify Signature
    if not verify_signature(raw_body, settings.GITHUB_WEBHOOK_SECRET, signature_header):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # 2. Parse Payload (we can re-parse from raw_body or use request.json which is cached)
    # Since we have raw_body, we can just json.loads it if content-type is json
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON body"}

    if event_type == "pull_request":
        logger.info("Processing pull_request event: %s", payload.get("action"))
        action = payload.get("action")

        # Exclude pr merge actions
        is_merged = payload.get("pull_request", {}).get("merged", False)
        if action == "closed" and is_merged:
            return {"message": "PR merged, ignored"}

        async with AsyncSessionLocal() as session:
            result = await change_management_graph.ainvoke(
                {"webhook_payload": payload},
                config={"configurable": {"session": session}},
            )
        # print the final state
        # pprint.pprint(result)
        return {"message": "PR processed", "state": result}

    logger.info("GitHub webhook received: %s", event_type)
    return {"message": "Event ignored", "event": event_type}
