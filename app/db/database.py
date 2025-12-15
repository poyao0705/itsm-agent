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

engine_kwargs = {}

database_url = settings.DATABASE_URL
if "sqlite" in database_url:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
    # Ensure usage of aiosqlite driver for async operation
    if "sqlite+aiosqlite" not in database_url:
        database_url = database_url.replace("sqlite://", "sqlite+aiosqlite://")
else:
    engine_kwargs.update(
        {
            "pool_size": 10,
            "max_overflow": 20,
            "pool_timeout": 30,
            "pool_recycle": 1800,
        }
    )

engine = create_async_engine(database_url, **engine_kwargs)
