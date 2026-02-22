"""
Lightweight in-process notification for cache invalidation.

Replaces the Valkey Streams → broadcast multiplexer → RingQueue pipeline
with a single asyncio.Event.  The event naturally coalesces rapid signals
(multiple `.set()` calls before a single `.wait()` returns are free).
"""

import asyncio

_update_event = asyncio.Event()


def notify_cache_update() -> None:
    """Signal that evaluation data has changed (fire-and-forget, sync-safe)."""
    _update_event.set()


async def wait_for_notification(timeout: float = 30.0) -> bool:
    """
    Wait until notified or *timeout* seconds elapse.

    Returns True if a notification arrived, False on timeout.
    Clears the event so the next call blocks again.
    """
    try:
        await asyncio.wait_for(_update_event.wait(), timeout=timeout)
        _update_event.clear()
        return True
    except asyncio.TimeoutError:
        _update_event.clear()
        return False
