# app/core/runtime.py
from langchain_openai import ChatOpenAI
from langchain_core.runnables import Runnable
from app.core.config import settings
from app.services.change_management.utils.github_client import GitHubClient


def build_llm() -> Runnable:
    """
    Build the LLM Runnable.
    """
    return ChatOpenAI(
        api_key=settings.OPENAI_API_KEY,
        model="gpt-5-mini",
        temperature=0,
        max_tokens=800,
    )
