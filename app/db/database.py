"""
ITSM Agent Database Configuration.

This module handles the setup and configuration of the database connection
using SQLModel (which wraps SQLAlchemy). It initializes the database engine
based on the application settings.

Attributes:
    engine: The global SQLModel engine instance used for database operations.
"""

from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from fastapi import FastAPI
from app.core.config import settings


engine_kwargs = {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30,
    "pool_recycle": 1800,
    "pool_pre_ping": True,
}

database_url = settings.DATABASE_URL

engine = create_async_engine(database_url, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    autoflush=False,
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan function for FastAPI application."""
    yield
    await engine.dispose()
