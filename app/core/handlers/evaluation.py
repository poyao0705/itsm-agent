"""
Evaluation Broadcast Handler

Domain-specific handler for the 'eval_updates' channel.
Fetches latest evaluations from DB and converts to public DTOs.
"""

from typing import List

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.db.models.evaluation_run import EvaluationRunPublic
from app.services.change_management.evaluations import EvaluationService

logger = get_logger(__name__)

EVAL_UPDATES_CHANNEL = "eval_updates"


async def handle_eval_update(payload: str) -> List[EvaluationRunPublic]:
    """
    Handler for evaluation update messages.

    Fetches latest evaluations from DB and converts to public DTOs.
    The payload (run_id) is currently ignored since we fetch the latest N.

    Args:
        payload: The Valkey message payload (typically run_id)

    Returns:
        List of EvaluationRunPublic DTOs for SSE broadcast
    """
    logger.debug("Processing eval update: %s", payload)

    async with AsyncSessionLocal() as session:
        service = EvaluationService(session)
        evals = await service.get_evaluations(limit=5)
        return [e.to_public() for e in evals]


def register_evaluation_handler(broadcast_service) -> None:
    """Register the evaluation handler with the broadcast service."""
    broadcast_service.register_handler(EVAL_UPDATES_CHANNEL, handle_eval_update)
    logger.info("Registered evaluation broadcast handler")
