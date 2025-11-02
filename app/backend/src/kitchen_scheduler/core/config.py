from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="KITCHEN_", case_sensitive=False)

    environment: Literal["development", "staging", "production"] = "development"
    project_name: str = "Kitchen Scheduling API"
    version: str = "0.1.0"

    database_url: str = "postgresql+asyncpg://scheduler:scheduler@localhost:5432/kitchen_scheduler"

    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires_minutes: int = 60
    jwt_refresh_token_expires_days: int = 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
