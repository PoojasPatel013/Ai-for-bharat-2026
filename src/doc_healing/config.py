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
    redis_url: Optional[str] = None

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
        
        import os
        import logging
        
        secret_name = os.environ.get("DOC_HEALING_AWS_SECRET_NAME")
        if secret_name:
            # We are likely running in an AWS Environment if this is set
            try:
                from doc_healing.aws.secrets import get_secret
                aws_secrets = get_secret(secret_name)
                
                # Apply overrides from AWS Secrets
                if "DATABASE_URL" in aws_secrets:
                    _settings.database_url = aws_secrets["DATABASE_URL"]
                
                # Check for explicit REDIS_URL first
                if "REDIS_URL" in aws_secrets:
                    _settings.redis_url = aws_secrets["REDIS_URL"]
                else:
                    if "REDIS_HOST" in aws_secrets:
                        _settings.redis_host = aws_secrets["REDIS_HOST"]
                    if "REDIS_PORT" in aws_secrets:
                        _settings.redis_port = int(aws_secrets["REDIS_PORT"])
                        
                if "BEDROCK_MODEL_ID" in aws_secrets:
                    _settings.bedrock_model_id = aws_secrets["BEDROCK_MODEL_ID"]
                    
                logging.getLogger(__name__).info(f"Loaded credentials securely from AWS Secrets Manager: {secret_name}")
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to load AWS Secrets '{secret_name}', falling back to local env variables: {e}")

    return _settings
