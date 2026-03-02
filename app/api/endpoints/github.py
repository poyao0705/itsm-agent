"""GitHub webhook endpoint: signature verification, payload parsing, and event routing."""

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import verify_signature
from app.db.session import AsyncSessionLocal
from app.dependencies.database import get_db
from app.services.change_management.evaluations import EvaluationService

logger = get_logger(__name__)

router = APIRouter()


@router.post("/webhook")
async def handle_github_webhook(
    request: Request,
    x_github_event: str = Header(...),
    x_hub_signature_256: str = Header(None),
    session: AsyncSession = Depends(get_db),
):
    """
    Handle GitHub webhook requests.

    - Verifies HMAC SHA-256 signature.
    - pull_request: runs the Change Management agent and returns its result.
    - Other events: logged and ignored.
    """
    raw_body = await request.body()

    # 1. Verify signature
    if not verify_signature(
        raw_body, settings.GITHUB_WEBHOOK_SECRET, x_hub_signature_256
    ):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # 2. Parse payload
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON body"}

    # 3. Route by event type
    if x_github_event == "pull_request":
        logger.info("Processing pull_request event: %s", payload.get("action"))
        action = payload.get("action")

        # Exclude PR merge actions
        is_merged = payload.get("pull_request", {}).get("merged", False)
        if action == "closed" and is_merged:
            return {"message": "PR merged, ignored"}

        # Run evaluation workflow with injected session
        service = EvaluationService(session)
        try:
            result = await service.run_evaluation_workflow(
                webhook_payload=payload,
                session_factory=AsyncSessionLocal,
            )
            return {"message": "PR processed", "state": result}
        except Exception as e:
            logger.error("Evaluation workflow failed: %s", str(e), exc_info=True)
            raise HTTPException(
                status_code=500, detail=f"Evaluation workflow failed: {str(e)}"
            ) from e

    logger.info("GitHub webhook received: %s", x_github_event)
    return {"message": "Event ignored", "event": x_github_event}
