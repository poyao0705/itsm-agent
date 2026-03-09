"""FastAPI dependency for the shared HTTP client."""

from fastapi import Request
import httpx


def get_http_client(request: Request) -> httpx.AsyncClient:
    """Return the shared httpx.AsyncClient stored on application state."""
    return request.app.state.http_client