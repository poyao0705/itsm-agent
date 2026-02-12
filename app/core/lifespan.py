import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.db.session import engine
from app.core.broadcast import get_broadcast_service
from app.core.cache_updater import cache_updater_task
from app.core.valkey_pubsub import close_valkey


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Lifespan function for the FastAPI application.
    Handles startup and shutdown events for application services.
    """
    # 1. Get broadcast service
    broadcast_service = get_broadcast_service()

    # 2. Start all registered listeners
    await broadcast_service.start_all()

    # 3. Start cache updater background task
    cache_task = asyncio.create_task(cache_updater_task())

    yield

    # 4. Stop cache updater
    cache_task.cancel()
    try:
        await cache_task
    except asyncio.CancelledError:
        pass

    # 5. Shutdown Broadcast Service
    await broadcast_service.stop_all()

    # 6. Close Valkey/Redis Connection
    await close_valkey()

    # 7. Dispose Database Engine
    await engine.dispose()
