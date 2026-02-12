"""
In-memory cache for evaluation data.
Single source of truth updated by background worker, read by all SSE clients.
"""

from typing import Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class CachedEvaluations:
    """Cached evaluation data with version tracking."""

    html: str
    updated_at: datetime
    version: int


class EvaluationCache:
    """Thread-safe in-memory cache for evaluation HTML."""

    def __init__(self):
        self._data: Optional[CachedEvaluations] = None
        self._lock = asyncio.Lock()
        self._version = 0
        self._condition = asyncio.Condition()

    async def get(self) -> Optional[CachedEvaluations]:
        """Get cached data (no lock needed for read)."""
        return self._data

    async def update(self, html: str):
        """Update cache with new data and notify all waiting SSE clients."""
        async with self._lock:
            self._version += 1
            self._data = CachedEvaluations(
                html=html,
                updated_at=datetime.now(),
                version=self._version,
            )
            logger.debug("Cache updated to version %d", self._version)
        # Wake all SSE clients waiting for a new version
        async with self._condition:
            self._condition.notify_all()

    async def wait_for_update(self, current_version: int, timeout: float) -> bool:
        """
        Block until the cache version exceeds *current_version*, or *timeout*.
        Returns True if an update arrived, False on timeout.
        """
        async with self._condition:
            try:
                await asyncio.wait_for(
                    self._condition.wait_for(lambda: self._version > current_version),
                    timeout=timeout,
                )
                return True
            except asyncio.TimeoutError:
                return False

    def get_version(self) -> int:
        """Quick version check without locking."""
        return self._version

    async def is_empty(self) -> bool:
        """Check if cache has been initialized."""
        return self._data is None


# Global singleton
_cache = EvaluationCache()


def get_evaluation_cache() -> EvaluationCache:
    """Get the global evaluation cache instance."""
    return _cache
