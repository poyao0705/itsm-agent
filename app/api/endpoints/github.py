from fastapi import APIRouter, Header, Request

from app.services.github import handle_github_webhook as process_webhook

router = APIRouter()


@router.post("/webhook")
async def handle_github_webhook(
    request: Request,
    x_github_event: str = Header(...),
    x_hub_signature_256: str = Header(None),
):
    """
    Handle GitHub webhook requests.

    Delegates to the GitHub webhook service for payload parsing and
    event-specific processing (e.g. pull_request -> Change Management agent).
    """
    raw_body = await request.body()
    return await process_webhook(request, x_github_event, raw_body, x_hub_signature_256)
