"""
LLM Client Initialization.

This module creates and exports the global LLM instance(s) used
throughout the application.  Keeping this separate from config.py
avoids mixing configuration parsing with external-client setup and
prevents circular imports as the project grows.
"""

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.core.config import settings

default_llm = ChatOpenAI(
    api_key=SecretStr(settings.OPENAI_API_KEY),
    model="gpt-5-mini",
    temperature=0,
    max_completion_tokens=1000,
    max_retries=3,
)
