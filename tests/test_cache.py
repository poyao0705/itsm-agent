"""Tests for app.services.change_management.cache.EvaluationCache."""

import asyncio
import pytest

from app.services.change_management.cache import EvaluationCache


# ---------------------------------------------------------------------------
# Basic state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_initially_empty():
    cache = EvaluationCache()
    assert await cache.is_empty() is True
    assert await cache.get() is None
    assert cache.get_version() == 0


@pytest.mark.asyncio
async def test_cache_update_stores_data():
    cache = EvaluationCache()
    await cache.update("<p>hello</p>")

    data = await cache.get()
    assert data is not None
    assert data.html == "<p>hello</p>"
    assert data.version == 1
    assert await cache.is_empty() is False


@pytest.mark.asyncio
async def test_cache_version_increments_on_each_update():
    cache = EvaluationCache()
    await cache.update("v1")
    await cache.update("v2")
    await cache.update("v3")

    assert cache.get_version() == 3
    data = await cache.get()
    assert data.html == "v3"
    assert data.version == 3


# ---------------------------------------------------------------------------
# wait_for_update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wait_for_update_returns_true_when_cache_updates():
    cache = EvaluationCache()
    await cache.update("initial")

    async def updater():
        await asyncio.sleep(0.05)
        await cache.update("new content")

    asyncio.create_task(updater())
    got_update = await cache.wait_for_update(current_version=1, timeout=1.0)
    assert got_update is True
    assert (await cache.get()).html == "new content"


@pytest.mark.asyncio
async def test_wait_for_update_returns_false_on_timeout():
    cache = EvaluationCache()
    await cache.update("unchanged")

    # Current version is 1; no further update will arrive → timeout
    got_update = await cache.wait_for_update(current_version=1, timeout=0.05)
    assert got_update is False


@pytest.mark.asyncio
async def test_wait_for_update_returns_immediately_if_already_newer():
    cache = EvaluationCache()
    await cache.update("v1")
    await cache.update("v2")  # version is now 2

    # Client is behind on version 0 → should return immediately
    got_update = await cache.wait_for_update(current_version=0, timeout=1.0)
    assert got_update is True


# ---------------------------------------------------------------------------
# Multiple waiters (fan-out)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multiple_waiters_all_notified():
    cache = EvaluationCache()

    results = []

    async def waiter():
        got = await cache.wait_for_update(current_version=0, timeout=1.0)
        results.append(got)

    tasks = [asyncio.create_task(waiter()) for _ in range(5)]
    await asyncio.sleep(0.02)
    await cache.update("broadcast")
    await asyncio.gather(*tasks)

    assert all(results), "All waiters should have received the update"
    assert len(results) == 5
