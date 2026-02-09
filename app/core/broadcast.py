"""
Stateless Broadcast System using Valkey Streams.

Replaces the legacy BroadcastService with a functional, generator-based
architecture. This module manages a single background listener task (multiplexer)
that fans out Stream events to local asyncio queues.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Set, Optional

from app.core.valkey_pubsub import stream_read

logger = logging.getLogger(__name__)

# Constants
STREAM_KEY = "eval_updates"

# Global Registry
_subscribers: Dict[str, Set[asyncio.Queue]] = {}
_listener_task: Optional[asyncio.Task] = None
_shutdown_event: asyncio.Event = asyncio.Event()


class RingQueue(asyncio.Queue):
    """
    A FIFO queue that drops the oldest item when full.
    Essential for preventing slow clients from blocking the multiplexer.
    """

    def put_nowait(self, item):
        if self.full():
            try:
                self.get_nowait()
                self.get_nowait()
            except asyncio.QueueEmpty:
                pass
        super().put_nowait(item)

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.get()


async def _multiplexer_loop():
    """
    Background task that reads from Valkey Streams and fans out to queues.
    """
    logger.info("Broadcast Multiplexer started listening to %s", STREAM_KEY)

    # Start listening for new messages ($)
    streams = {STREAM_KEY: "$"}

    while not _shutdown_event.is_set():
        try:
            # Check if we have any subscribers at all
            if not _subscribers:
                await asyncio.sleep(1.0)
                # Ensure we don't process backlog if re-subscribing later?
                # Actually, if we just sleep, then when someone subscribes,
                # we resume from last ID. That's good behavior (catch up slightly).
                # But if we were truly idle for hours, maybe we should jump to $?
                # For now, simplistic approach is fine.
                streams[STREAM_KEY] = "$"
                continue

            # Block for 1 second max
            # XREAD returns [[stream_name, [(msg_id, data)]], ...]
            # Note: redis-py usually returns byte keys/values unless decode_responses=True
            response = await stream_read(streams, count=100, block=1000)

            if response:
                for stream_name, messages in response:
                    last_id = messages[-1][0]
                    streams[stream_name] = last_id

                    # Fan-out to subscribers of this channel (or global stream)
                    # Mapping: STREAM_KEY -> subscribers["eval_updates"]?
                    # The user code currently uses channel names.
                    # We'll assume the channel name IS the stream key.
                    if stream_name in _subscribers:
                        # Coalesce: Send one signal per batch to each subscriber
                        # This prevents queue spamming during bursts.
                        queues = list(_subscribers[stream_name])
                        last_id = messages[-1][0]
                        # Create a signal object (data is ignored by SSW handler anyway)
                        signal = {"type": "invalidate", "last_id": last_id}

                        for q in queues:
                            try:
                                q.put_nowait(signal)
                            except Exception:
                                pass

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Multiplexer error: %s", e)
            await asyncio.sleep(1.0)

    logger.info("Broadcast Multiplexer stopped")


async def start_broadcaster():
    """Start the global background listener."""
    global _listener_task
    if _listener_task is None or _listener_task.done():
        _shutdown_event.clear()
        _listener_task = asyncio.create_task(_multiplexer_loop())


async def stop_broadcaster():
    """Stop the global background listener."""
    global _listener_task
    _shutdown_event.set()
    if _listener_task:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        _listener_task = None


@asynccontextmanager
async def subscribe(channel: str) -> AsyncGenerator[RingQueue, None]:
    """
    Context manager to subscribe to a channel.
    Yields an async-iterable RingQueue.
    """
    if channel not in _subscribers:
        _subscribers[channel] = set()

    # Create a bounded queue for this client
    queue = RingQueue(maxsize=100)
    _subscribers[channel].add(queue)

    try:
        yield queue
    finally:
        # Cleanup on disconnect (RAII)
        if channel in _subscribers:
            _subscribers[channel].discard(queue)
            if not _subscribers[channel]:
                del _subscribers[channel]


# -----------------------------------------------------------------------------
# Compatibility Layer for Lifespan
# -----------------------------------------------------------------------------


class BroadcastServiceFacade:
    """
    Compatibility facade for legacy lifespan integration.
    Allows lifespan.py to start/stop the global multiplexer.
    """

    async def start_all(self):
        await start_broadcaster()

    async def stop_all(self):
        await stop_broadcaster()

    async def subscribe(self, channel: str):
        """Deprecated: Use async with subscribe() instead."""
        raise NotImplementedError("Use 'async with broadcast.subscribe()' pattern")

    def register_handler(self, channel, handler):
        """Deprecated: Handlers are removed in stateless architecture."""
        pass


_facade = BroadcastServiceFacade()


def get_broadcast_service() -> BroadcastServiceFacade:
    return _facade
