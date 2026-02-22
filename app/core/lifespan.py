import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.db.session import engine
from app.services.change_management.cache_updater import cache_updater_task


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Lifespan function for the FastAPI application.
    Handles startup and shutdown events for application services.
    """
    # 1. Start cache updater background task
    cache_task = asyncio.create_task(cache_updater_task())

    yield

    # 2. Stop cache updater
    cache_task.cancel()
    try:
        await cache_task
    except asyncio.CancelledError:
        pass

    # 3. Dispose Database Engine
    await engine.dispose()
