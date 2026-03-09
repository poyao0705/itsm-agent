"""Dependency providers for application services and integrations."""

from typing import Annotated

from fastapi import Depends
import httpx
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.dependencies.database import get_db
from app.dependencies.http import get_http_client
from app.integrations.github.client import GitHubClient
from app.integrations.jira.client import JiraClient
from app.services.change_management.evaluations import EvaluationService


def get_github_client(
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> GitHubClient:
    """Build a GitHub client with the shared HTTP transport."""
    return GitHubClient(client=client)


def get_jira_client(
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> JiraClient:
    """Build a JIRA client with configured credentials."""
    return JiraClient(
        client=client,
        base_url=settings.JIRA_BASE_URL,
        email=settings.JIRA_EMAIL,
        api_token=settings.JIRA_API_TOKEN,
    )


def get_evaluation_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> EvaluationService:
    """Build an evaluation service with DB and HTTP dependencies."""
    return EvaluationService(session=session, http_client=client)