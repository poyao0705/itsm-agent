from fastapi import APIRouter, Header, Request

from app.services.github import handle_github_webhook as process_webhook

router = APIRouter()


@router.post("/webhook")
async def handle_github_webhook(request: Request, x_github_event: str = Header(...)):
    """
    Handle GitHub webhook requests.

    Delegates to the GitHub webhook service for payload parsing and
    event-specific processing (e.g. pull_request -> Change Management agent).
    """
    return await process_webhook(request, x_github_event)
