# app/core/runtime.py
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from app.core.config import settings


def build_llm() -> ChatOpenAI:
    """
    Build the LLM instance.
    """
    return ChatOpenAI(
        api_key=SecretStr(settings.OPENAI_API_KEY),
        model="gpt-5-mini",
        temperature=0,
        max_completion_tokens=1000,
        max_retries=3,
    )
