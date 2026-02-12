"""
Background task that listens to Valkey Streams and updates the in-memory cache.
This ensures only ONE DB query per update, shared by ALL SSE clients.
"""

import asyncio
import logging

from fastapi.templating import Jinja2Templates

from app.core import broadcast
from app.core.evaluation_cache import get_evaluation_cache
from app.db.session import AsyncSessionLocal
from app.services.change_management.evaluations import EvaluationService

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/templates")


async def _fetch_and_render(limit: int = 5) -> str:
    """Fetch latest evaluations from DB and render to HTML."""
    async with AsyncSessionLocal() as session:
        service = EvaluationService(session)
        evals = await service.get_evaluations(limit=limit)

    return (
        templates.get_template("partials/evaluations_latest.html")
        .render({"request": None, "evaluations": evals})
        .replace("\n", "")
    )


async def cache_updater_task():
    """
    Background task that:
    1. Listens to Valkey Stream updates
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

    # Listen for updates
    async with broadcast.subscribe(broadcast.STREAM_KEY) as queue:
        while True:
            try:
                # Wait for update signal from Valkey Stream
                await asyncio.wait_for(queue.get(), timeout=30.0)

                # Drain queue to coalesce rapid updates
                drained = 0
                while not queue.empty():
                    try:
                        queue.get_nowait()
                        drained += 1
                    except asyncio.QueueEmpty:
                        break

                if drained > 0:
                    logger.debug("Coalesced %d rapid updates", drained)

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

            except asyncio.TimeoutError:
                # Periodic refresh (every 30s even without updates)
                logger.debug("Cache updater keep-alive")
            except asyncio.CancelledError:
                logger.info("Cache updater task cancelled")
                break
            except Exception as e:
                logger.error("Unexpected error in cache updater: %s", e, exc_info=True)
                await asyncio.sleep(5.0)

    logger.info("Cache updater task stopped")
