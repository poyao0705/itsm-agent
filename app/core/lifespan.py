import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
import httpx

from app.db.session import engine
from app.services.change_management.cache_updater import cache_updater_task


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan function for the FastAPI application.
    Handles startup and shutdown events for application services.
    """
    # 1. Create shared HTTP client (connection pool reused across all requests)
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=5.0,  # Fail fast if target is unreachable
            read=30.0,  # Large diffs may take time
            write=10.0,
            pool=10.0,  # Don't wait too long for a free connection
        ),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )

    # 2. Start cache updater background task
    cache_task = asyncio.create_task(cache_updater_task())

    yield

    # 3. Stop cache updater
    cache_task.cancel()
    try:
        await cache_task
    except asyncio.CancelledError:
        pass

    # 4. Close shared HTTP client
    await app.state.http_client.aclose()

    # 5. Dispose Database Engine
    await engine.dispose()
