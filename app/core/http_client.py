"""
Shared httpx.AsyncClient managed by the application lifespan.

Usage:
    from app.core.http_client import http_client

    response = await http_client.get("https://...")
"""

import httpx

# Will be initialized during app lifespan startup
http_client: httpx.AsyncClient = None  # type: ignore[assignment]
