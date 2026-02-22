"""
Background task that refreshes the in-memory evaluation cache.

Wakes on an in-process asyncio.Event (set by the evaluation service after
DB writes) **or** every 30 s as a self-healing fallback.  Only ONE DB
query is executed per wake-up, and all SSE clients share the result.
"""

import asyncio

from fastapi.templating import Jinja2Templates

from app.core.evaluation_cache import get_evaluation_cache
from app.core.logging import get_logger
from app.core.notifier import wait_for_notification
from app.db.session import AsyncSessionLocal
from app.services.change_management.evaluations import EvaluationService

logger = get_logger(__name__)
templates = Jinja2Templates(directory="app/templates")


async def _fetch_and_render(limit: int = 5) -> str:
    """Fetch latest evaluations (per PR) from DB and render to HTML."""
    async with AsyncSessionLocal() as session:
        service = EvaluationService(session)
        evals = await service.get_latest_per_pr(limit=limit)

    return (
        templates.get_template("partials/evaluations_latest.html")
        .render({"request": None, "evaluations": evals})
        .replace("\n", "")
    )


async def cache_updater_task():
    """
    Background task that:
    1. Waits for an in-process notification (or 30 s timeout)
    2. Fetches fresh data from DB (once per update)
    3. Renders HTML template (once per update)
    4. Updates in-memory cache (all SSE clients read from here)
    """
    cache = get_evaluation_cache()
    logger.info("Cache updater task started")

    # Initial population
    try:
        html = await _fetch_and_render()
        await cache.update(html)
        logger.info("Cache initialized with initial data")
    except Exception as e:
        logger.error("Failed to initialize cache: %s", e)

    # Event-driven loop with periodic fallback
    while True:
        try:
            notified = await wait_for_notification(timeout=30.0)

            if notified:
                logger.debug("Cache updater received notification")
            else:
                logger.debug("Cache updater periodic refresh")

            # Fetch fresh data from DB (ONE query for ALL clients)
            try:
                async with asyncio.timeout(5.0):
                    html = await _fetch_and_render()

                await cache.update(html)
                logger.info("Cache updated successfully")

            except asyncio.TimeoutError:
                logger.error("DB query timeout in cache updater")
            except Exception as e:
                logger.error("Error updating cache: %s", e, exc_info=True)

        except asyncio.CancelledError:
            logger.info("Cache updater task cancelled")
            break
        except Exception as e:
            logger.error("Unexpected error in cache updater: %s", e, exc_info=True)
            await asyncio.sleep(5.0)

    logger.info("Cache updater task stopped")
