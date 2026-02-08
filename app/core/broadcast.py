"""
Broadcast Service - Singleton for SSE (per process)

NOTE: If running multiple workers (uvicorn --workers N), each worker
will have its own broadcaster. For true global singleton, use Redis/NATS.
"""

import asyncio
from typing import Set, Optional, List

from app.core.logging import get_logger
from app.core.pg_listen import pg_listen
from app.db.session import AsyncSessionLocal
from app.services.change_management.evaluations import EvaluationService

logger = get_logger(__name__)

# Global instance (Singleton per process)
_broadcaster: Optional["BroadcastEvaluationService"] = None


class BroadcastEvaluationService:
    """
    Singleton service that holds ONE connection to Postgres LISTEN
    and broadcasts updates to MANY in-memory queues (connected clients).

    Production hardening:
    - Bounded queues (maxsize=1) to prevent slow-client OOM
    - discard() instead of remove() to avoid KeyError on disconnect race
    - Skip DB fetch if no subscribers
    - Convert to render-safe DTOs before session closes
    - Optional snapshot-on-connect
    """

    def __init__(self):
        self.subscribers: Set[asyncio.Queue] = set()
        self.listen_task: Optional[asyncio.Task] = None
        self.latest_payload: Optional[List[dict]] = None  # Cache render-safe DTOs

    async def connect(self, queue: asyncio.Queue):
        """Add a client to the broadcast list and send initial snapshot."""
        self.subscribers.add(queue)
        await self.start()

        # Push snapshot immediately so new clients don't wait for next NOTIFY
        if self.latest_payload is not None:
            self._put_latest(queue, self.latest_payload)

    async def disconnect(self, queue: asyncio.Queue):
        """Remove a client. Uses discard() to avoid KeyError on race conditions."""
        self.subscribers.discard(queue)

    def _put_latest(self, queue: asyncio.Queue, payload: List[dict]):
        """
        Put payload into queue, dropping old data if queue is full.
        This prevents slow clients from causing OOM.
        """
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            # Drop the old item and put the new one
            try:
                _ = queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass  # Should never happen with maxsize=1

    async def start(self):
        """Start the background listener task."""
        if self.listen_task and not self.listen_task.done():
            return  # Already running

        self.listen_task = asyncio.create_task(self._listener_loop())
        logger.info("BroadcastService: Started background listener.")

    async def stop(self):
        """Stop the background listener."""
        if self.listen_task:
            self.listen_task.cancel()
            try:
                await self.listen_task
            except asyncio.CancelledError:
                pass
            self.listen_task = None
            logger.info("BroadcastService: Stopped.")

    async def _listener_loop(self):
        """
        Listen to PostgreSQL notifications and broadcast to all clients.
        """
        logger.info("BroadcastService: Listening to 'eval_updates'...")
        try:
            async for payload in pg_listen("eval_updates", timeout=30.0):
                if payload == "":
                    # Keep-alive tick
                    continue

                logger.debug("BroadcastService: Received payload: %s", payload)

                # Skip DB fetch if nobody is listening (saves resources)
                if not self.subscribers:
                    logger.debug("BroadcastService: No subscribers, skipping fetch.")
                    continue

                # Fetch ONCE
                try:
                    async with AsyncSessionLocal() as session:
                        service = EvaluationService(session)
                        evals = await service.get_evaluations(limit=5)

                        # Convert to render-safe DTOs BEFORE closing session
                        # This avoids DetachedInstanceError if template accesses lazy attrs
                        evals_payload = self._to_dto(evals)

                    # Cache for new subscribers
                    self.latest_payload = evals_payload

                    # Broadcast without blocking on slow clients
                    current_subs = list(self.subscribers)
                    logger.debug(
                        "BroadcastService: Broadcasting to %d clients.",
                        len(current_subs),
                    )

                    for q in current_subs:
                        self._put_latest(q, evals_payload)

                except Exception as e:
                    logger.error("BroadcastService error processing update: %s", e)

        except asyncio.CancelledError:
            # Normal shutdown
            raise
        except Exception as e:
            logger.error("BroadcastService listener loop crashed: %s", e, exc_info=True)
        finally:
            logger.info("BroadcastService listener loop ended.")

    def _to_dto(self, evals: list) -> List[dict]:
        """
        Convert SQLModel objects to render-safe dictionaries.
        Ensures no lazy-loading issues after session closes.

        Note: Keep datetime objects (not strings) so template can call .strftime()
        """
        result = []
        for e in evals:
            dto = {
                "id": str(e.id),
                "evaluation_key": e.evaluation_key,
                "owner": e.owner,
                "repo": e.repo,
                "pr_number": e.pr_number,
                "status": e.status.value if hasattr(e.status, "value") else e.status,
                "risk_level": e.risk_level,
                "start_ts": e.start_ts,  # Keep as datetime for template .strftime()
                "end_ts": e.end_ts,
                "display_name": e.display_name,  # Computed property
                # Include analysis results if needed by template
                "analysis_results": [
                    {
                        "id": str(ar.id),
                        "node_name": ar.node_name,
                        "reason_code": ar.reason_code,
                        "summary": ar.summary,
                        "risk_level": ar.risk_level,
                        "details": ar.details,
                    }
                    for ar in (e.analysis_results or [])
                ],
            }
            result.append(dto)
        return result


def get_broadcast_service() -> BroadcastEvaluationService:
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = BroadcastEvaluationService()
    return _broadcaster
