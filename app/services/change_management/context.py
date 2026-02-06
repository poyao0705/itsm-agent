"""
LangGraph Runtime Context for Change Management.

Defines the context schema for dependency injection into LangGraph nodes.
"""

from dataclasses import dataclass
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession


@dataclass
class Ctx:
    """Runtime context for LangGraph nodes.

    Attributes:
        db: Async session factory for database operations.
    """

    db: async_sessionmaker[AsyncSession]
