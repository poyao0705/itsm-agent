"""GitHub webhook handling: payload parsing and event processing."""

import json
import logging
from urllib.parse import unquote
import pprint

from starlette.requests import Request

from app.services.change_management.agent import change_management_graph

logger = logging.getLogger(__name__)


async def parse_webhook_payload(request: Request) -> dict:
    """
    Extract and parse the webhook payload from a GitHub webhook request.

    Tries form data with a "payload" field (URL-decoded JSON), then falls back
    to raw JSON body if form parsing fails.

    Returns:
        Parsed payload dict, or a dict with "raw_payload"/"error" on failure.
    """
    try:
        form_data = await request.form()
        if "payload" in form_data:
            payload_str = unquote(form_data["payload"])
            try:
                return json.loads(payload_str)
            except json.JSONDecodeError:
                return {"raw_payload": payload_str}
        return dict(form_data) if form_data else {}
    except Exception as e:
        try:
            body = await request.body()
            return json.loads(body) if body else {}
        except Exception:
            return {"error": f"Failed to parse request: {str(e)}"}


async def handle_github_webhook(request: Request, event_type: str) -> dict:
    """
    Process a GitHub webhook: parse payload and route by event type.

    - pull_request: runs the Change Management agent and returns its result.
    - Other events: logged and ignored.

    Args:
        request: The incoming HTTP request.
        event_type: The X-GitHub-Event header value (e.g. "push", "pull_request").

    Returns:
        A dict to be returned as the JSON response (e.g. {"message": "...", ...}).
    """
    payload = await parse_webhook_payload(request)

    if event_type == "pull_request":
        # Exclude pr merge actions
        action = payload.get("action")
        is_merged = payload.get("pull_request", {}).get("merged", False)
        if action == "closed" and is_merged:
            return {"message": "PR merged, ignored"}

        result = await change_management_graph.ainvoke({"webhook_payload": payload})
        # print the final state
        pprint.pprint(result)
        return {"message": "PR processed", "state": result}

    logger.info("GitHub webhook received: %s", event_type)
    return {"message": "Event ignored", "event": event_type}
