"""
App Configuration.

This module defines the global application settings using Pydantic Settings.
It loads configuration variables from environment variables and/or a .env file,
ensuring typed and validated settings for the application.

Attributes:
    settings: The global instance of the Settings class, ready to be imported and used.
"""

import os
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    VALKEY_URL: str = "valkey://localhost:6379"  # Default for local dev

    # AI / Model Providers
    OPENAI_API_KEY: str

    # Github
    GITHUB_APP_ID: str
    GITHUB_APP_PRIVATE_KEY: str
    GITHUB_WEBHOOK_SECRET: str

    @field_validator("GITHUB_APP_PRIVATE_KEY", mode="after")
    @classmethod
    def load_private_key(cls, v: str) -> str:
        """
        Loads the private key content.
        If the value is a file path, reads the file.
        Also handles escaped newlines (\\n) in environment variables.
        """
        if os.path.isfile(v):
            with open(v, "r", encoding="utf-8") as f:
                return f.read()
        return v.replace("\\n", "\n")

    model_config = SettingsConfigDict(
        env_file=".env", env_ignore_empty=True, extra="ignore"
    )


settings = Settings()
