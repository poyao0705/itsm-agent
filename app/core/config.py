"""
App Configuration.

This module defines the global application settings using Pydantic Settings.
It loads configuration variables from environment variables and/or a .env file,
ensuring typed and validated settings for the application.

Attributes:
    settings: The global instance of the Settings class, ready to be imported and used.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os


class Settings(BaseSettings):
    """
    Application Settings.

    This class defines the configuration for the application, validating
    environment variables against the specified types.

    Attributes:
        PROJECT_NAME: The name of the project (default: "ITSM Agent").
        DATABASE_URL: The connection string for the database.
        OPENAI_API_KEY: The API key for accessing OpenAI services.
    """

    # Core
    PROJECT_NAME: str = "ITSM Agent"
    DATABASE_URL: str

    # AI / Model Providers
    OPENAI_API_KEY: str

    model_config = SettingsConfigDict(
        env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()
