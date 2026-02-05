"""
ITSM Agent Database Dependencies
"""

from typing import AsyncGenerator
from sqlmodel.ext.asyncio.session import AsyncSession
from app.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session"""
    async with AsyncSessionLocal() as session:
        yield session
