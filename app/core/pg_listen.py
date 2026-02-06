"""
PostgreSQL LISTEN/NOTIFY Listener

Provides an async generator for subscribing to PostgreSQL notifications.
Uses asyncpg for real-time database event streaming.
"""

import asyncio
from typing import AsyncGenerator
from contextlib import asynccontextmanager

import asyncpg

from app.core.config import settings


def _get_asyncpg_dsn() -> str:
    """Convert SQLAlchemy DATABASE_URL to asyncpg format."""
    url = settings.DATABASE_URL
    # asyncpg uses 'postgresql://' not 'postgresql+asyncpg://'
    if "+asyncpg" in url:
        url = url.replace("+asyncpg", "")
    return url


@asynccontextmanager
async def get_listener_connection():
    """Create a dedicated asyncpg connection for LISTEN."""
    conn = await asyncpg.connect(_get_asyncpg_dsn())
    try:
        yield conn
    finally:
        await conn.close()


async def pg_listen(channel: str, timeout: float = 30.0) -> AsyncGenerator[str, None]:
    """
    Async generator that yields whenever a PostgreSQL notification arrives.

    Args:
        channel: The PostgreSQL channel name to LISTEN on.
        timeout: Seconds to wait before yielding a keep-alive signal.

    Yields:
        The notification payload (or empty string for keep-alive).
    """
    async with get_listener_connection() as conn:
        queue: asyncio.Queue[str] = asyncio.Queue()

        def callback(
            _connection: asyncpg.Connection,
            _pid: int,
            _channel: str,
            payload: str,
        ):
            queue.put_nowait(payload)

        await conn.add_listener(channel, callback)

        try:
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=timeout)
                    yield payload
                except asyncio.TimeoutError:
                    # Keep-alive: yield empty to let caller send a comment
                    yield ""
        finally:
            await conn.remove_listener(channel, callback)
