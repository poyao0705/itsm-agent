# Inside app/api/endpoints/github.py
import json
from urllib.parse import unquote
from fastapi import APIRouter, Header, Request

from app.services.change_management.agent import change_management_graph

router = APIRouter()


@router.post("/webhook")  # Standard path naming
async def handle_github_webhook(request: Request, x_github_event: str = Header(...)):
    """
    Handle GitHub webhook requests.

    Args:
        request: The incoming HTTP request.
        x_github_event: The GitHub event type (e.g., 'push', 'pull_request').

    Returns:
        A JSON response indicating the webhook was received.
    """
    try:
        form_data = await request.form()
        if "payload" in form_data:
            # Extract and URL-decode the payload field, then parse as JSON
            payload_str = unquote(form_data["payload"])
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                # JSON parsing failed, return raw payload string
                payload = {"raw_payload": payload_str}
        else:
            # No payload field, return form data as dict
            payload = dict(form_data) if form_data else {}
    except Exception as e:
        # If form parsing fails, try raw body as JSON
        try:
            body = await request.body()
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {"error": f"Failed to parse request: {str(e)}"}

    # Process pull_request events through the Change Management agent
    if x_github_event == "pull_request":
        result = await change_management_graph.ainvoke({"webhook_payload": payload})
        return {"message": "PR processed", "state": result}

    # Log and ignore other events
    print(f"GitHub webhook received: {x_github_event}")
    # print(f"Payload: {payload}")
    return {"message": "Event ignored", "event": x_github_event}
