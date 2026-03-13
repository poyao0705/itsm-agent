"""Runtime context for the Change Management graph."""

from dataclasses import dataclass

import httpx


@dataclass
class ChangeManagementContext:
    """Run-scoped dependencies injected into LangGraph nodes."""

    http_client: httpx.AsyncClient
