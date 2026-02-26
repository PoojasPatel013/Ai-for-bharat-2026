"""Configuration system for deployment modes and settings management."""

from enum import Enum
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class DeploymentMode(str, Enum):
    """Deployment mode configuration."""

    FULL = "full"
    LIGHTWEIGHT = "lightweight"
    HYBRID = "hybrid"


class DatabaseBackend(str, Enum):
    """Database backend configuration."""

    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


class QueueBackend(str, Enum):
    """Queue backend configuration."""

    REDIS = "redis"
    MEMORY = "memory"


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Deployment configuration
    deployment_mode: DeploymentMode = DeploymentMode.FULL

    # Database configuration
    database_backend: DatabaseBackend = DatabaseBackend.POSTGRESQL
    database_url: str = "postgresql://postgres:postgres@localhost:5432/doc_healing"
    sqlite_path: str = "./data/doc_healing.db"

    # Queue configuration
    queue_backend: QueueBackend = QueueBackend.REDIS
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # Worker configuration
    unified_worker: bool = False
    worker_threads: int = 4
    sync_processing: bool = False

    # API configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # LLM Configuration
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    bedrock_fallback_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="DOC_HEALING_",
        case_sensitive=False,
    )


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
