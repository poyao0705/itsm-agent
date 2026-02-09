"""
Generic Broadcast Service for SSE Pub/Sub

Provides a channel-based broadcast system that bridges Valkey pub/sub
to in-memory SSE client queues. Each worker maintains its own connected
clients; Valkey ensures cross-worker message delivery.

Usage:
    # Subscribe a client queue to a channel
    queue = await broadcast_service.subscribe("eval_updates")

    # In your event generator
    async for payload in queue:
        yield {"event": "update", "data": payload}

    # Unsubscribe when done
    await broadcast_service.unsubscribe("eval_updates", queue)
"""

import asyncio
from typing import Dict, Set, Optional, Callable, Awaitable, Any

from app.core.logging import get_logger
from app.core.valkey_pubsub import valkey_listen

logger = get_logger(__name__)

# Type alias for message handlers
MessageHandler = Callable[[str], Awaitable[Any]]


class BroadcastService:
    """
    Generic pub/sub to SSE bridge.

    Manages per-channel subscriptions and Valkey listener tasks.
    Each channel can have multiple client queues and an optional
    message handler for transforming payloads before broadcast.

    Production hardening:
    - Bounded queues (maxsize=1) to prevent slow-client OOM
    - Reconnect with exponential backoff on connection failures
    - Channel-based isolation
    """

    def __init__(self):
        # channel -> set of subscriber queues
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        # channel -> listener task
        self._listener_tasks: Dict[str, asyncio.Task] = {}
        # channel -> message handler (transforms raw payload to broadcast data)
        self._handlers: Dict[str, MessageHandler] = {}
        # channel -> latest payload cache (for snapshot on connect)
        self._cache: Dict[str, Any] = {}

    def register_handler(self, channel: str, handler: MessageHandler) -> None:
        """
        Register a message handler for a channel.

        The handler transforms the raw Valkey payload into the data
        that will be broadcast to subscribers.
        """
        self._handlers[channel] = handler
        logger.info("Registered handler for channel: %s", channel)

    async def subscribe(self, channel: str, queue: asyncio.Queue) -> None:
        """
        Subscribe a client queue to a channel.
        Starts the listener task if this is the first subscriber.
        Fetches fresh data via handler to avoid stale cache issues.
        """
        if channel not in self._subscribers:
            self._subscribers[channel] = set()

        self._subscribers[channel].add(queue)
        logger.debug(
            "Client subscribed to %s (total: %d)",
            channel,
            len(self._subscribers[channel]),
        )

        # Start listener if not running
        await self._ensure_listener(channel)

        # Fetch fresh data via handler on subscribe (not stale cache)
        # This ensures new clients always get current DB state
        handler = self._handlers.get(channel)
        if handler:
            try:
                fresh_data = await handler("")  # Empty payload, handler fetches from DB
                self._put_nowait(queue, fresh_data)
            except Exception as e:
                logger.warning("Failed to fetch fresh data on subscribe: %s", e)
                # Fall back to cache if handler fails
                if channel in self._cache:
                    self._put_nowait(queue, self._cache[channel])
        elif channel in self._cache:
            # No handler, use cache as fallback
            self._put_nowait(queue, self._cache[channel])

    async def unsubscribe(self, channel: str, queue: asyncio.Queue) -> None:
        """
        Unsubscribe a client queue from a channel.
        Uses discard() to avoid KeyError on race conditions.
        """
        if channel in self._subscribers:
            self._subscribers[channel].discard(queue)
            logger.debug("Client unsubscribed from %s", channel)

    async def _ensure_listener(self, channel: str) -> None:
        """Start the listener task for a channel if not already running."""
        if channel in self._listener_tasks and not self._listener_tasks[channel].done():
            return  # Already running

        self._listener_tasks[channel] = asyncio.create_task(
            self._listener_loop(channel)
        )
        logger.info("Started listener for channel: %s", channel)

    async def _listener_loop(self, channel: str) -> None:
        """
        Listen to Valkey pub/sub and broadcast to all subscribers.
        Resilient: retries with exponential backoff on connection failures.
        """
        backoff = 0.5

        while True:
            try:
                async for payload in valkey_listen(channel, timeout=30.0):
                    backoff = 0.5  # Reset after successful receive

                    if not payload:
                        continue  # Keep-alive tick

                    logger.debug("Received on %s: %s", channel, payload)

                    subscribers = self._subscribers.get(channel, set())
                    if not subscribers:
                        logger.debug("No subscribers for %s, skipping", channel)
                        continue

                    # Transform payload if handler registered
                    handler = self._handlers.get(channel)
                    if handler:
                        try:
                            data = await handler(payload)
                        except Exception as e:
                            logger.error("Handler error for %s: %s", channel, e)
                            continue
                    else:
                        data = payload

                    # Cache for new subscribers
                    self._cache[channel] = data

                    # Broadcast to all subscribers
                    for q in list(subscribers):
                        self._put_nowait(q, data)

            except asyncio.CancelledError:
                logger.info("Listener cancelled for channel: %s", channel)
                raise
            except Exception:
                logger.exception("Listener crashed for %s, retrying...", channel)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 10.0)

    def _put_nowait(self, queue: asyncio.Queue, data: Any) -> None:
        """
        Put data into queue, dropping old data if queue is full.
        Prevents slow clients from causing OOM.
        """
        try:
            queue.put_nowait(data)
        except asyncio.QueueFull:
            try:
                _ = queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                queue.put_nowait(data)
            except asyncio.QueueFull:
                pass  # Should never happen with maxsize=1

    async def start_all(self) -> None:
        """Start listeners for all registered handlers."""
        for channel in self._handlers:
            await self._ensure_listener(channel)

    async def stop_all(self) -> None:
        """Stop all listener tasks."""
        for channel, task in self._listener_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped listener for channel: %s", channel)
        self._listener_tasks.clear()


# -----------------------------------------------------------------------------
# Singleton instance
# -----------------------------------------------------------------------------
_broadcast_service: Optional[BroadcastService] = None


def get_broadcast_service() -> BroadcastService:
    """Get the global BroadcastService singleton."""
    global _broadcast_service
    if _broadcast_service is None:
        _broadcast_service = BroadcastService()
    return _broadcast_service
