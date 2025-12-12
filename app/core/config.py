from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os

class Settings(BaseSettings):
    # Core
    PROJECT_NAME: str = "ITSM Agent"
    DATABASE_URL: str
    
    # AI / Model Providers
    OPENAI_API_KEY: str

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_ignore_empty=True,
        extra="ignore"
    )

settings = Settings()