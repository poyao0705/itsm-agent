"""
Valkey Pub/Sub Module

Provides async pub/sub functionality using the redis-py library
connected to a Valkey server. Valkey is Redis-compatible.
"""

import asyncio
from typing import AsyncGenerator, Optional

import redis.asyncio as redis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Global client instance (lazily initialized)
_redis_client: Optional[redis.Redis] = None

EVAL_UPDATES_CHANNEL = "eval_updates"


async def get_valkey_client() -> redis.Redis:
    """
    Get or create the global async Redis client for Valkey.

    Returns a lazily-initialized singleton client.
    """
    global _redis_client
    if _redis_client is None:
        # Convert valkey:// scheme to redis:// for redis-py library
        # Also handle TLS: valkeys:// -> rediss://
        url = settings.VALKEY_URL
        url = url.replace("valkeys://", "rediss://").replace("valkey://", "redis://")
        _redis_client = redis.from_url(url, decode_responses=True)
        logger.info("Valkey client initialized: %s", url)
    return _redis_client


async def close_valkey() -> None:
    """Close the global Valkey client connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Valkey client closed.")


async def publish_eval_update(payload: str) -> None:
    """
    Publish an evaluation update notification.

    Args:
        payload: The message payload (typically the evaluation run ID)
    """
    client = await get_valkey_client()
    await client.publish(EVAL_UPDATES_CHANNEL, payload)
    logger.debug("Published to %s: %s", EVAL_UPDATES_CHANNEL, payload)


async def valkey_listen(
    channel: str, timeout: float = 30.0
) -> AsyncGenerator[str, None]:
    """
    Async generator that yields whenever a Valkey pub/sub message arrives.

    This mirrors the pg_listen API for drop-in replacement.

    Args:
        channel: The Valkey channel name to subscribe to.
        timeout: Seconds to wait before yielding a keep-alive signal.

    Yields:
        The message payload (or empty string for keep-alive).
    """
    client = await get_valkey_client()
    pubsub = client.pubsub()

    await pubsub.subscribe(channel)
    logger.info("Subscribed to Valkey channel: %s", channel)

    try:
        while True:
            try:
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=None),
                    timeout=timeout,
                )
                if message is not None:
                    # message format: {'type': 'message', 'channel': '...', 'data': '...'}
                    yield message.get("data", "")
                else:
                    # No message within timeout - yield keep-alive
                    yield ""
            except asyncio.TimeoutError:
                # Keep-alive: yield empty to let caller send a comment
                yield ""
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        logger.info("Unsubscribed from Valkey channel: %s", channel)
