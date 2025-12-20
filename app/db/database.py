"""
ITSM Agent Database Configuration.

This module handles the setup and configuration of the database connection
using SQLModel (which wraps SQLAlchemy). It initializes the database engine
based on the application settings.

Attributes:
    engine: The global SQLModel engine instance used for database operations.
"""

from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

engine_kwargs = {
    "pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30,
    "pool_recycle": 1800,
}

database_url = settings.DATABASE_URL

# Ensure usage of asyncpg driver for async operation with PostgreSQL
if "postgresql" in database_url and "postgresql+asyncpg" not in database_url:
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(database_url, **engine_kwargs)
