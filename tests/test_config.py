"""Tests for configuration system."""

import os
import pytest
from doc_healing.config import (
    Settings,
    DeploymentMode,
    DatabaseBackend,
    QueueBackend,
    get_settings,
)


def test_default_settings():
    """Test that default settings are correctly initialized."""
    settings = Settings()
    
    assert settings.deployment_mode == DeploymentMode.FULL
    assert settings.database_backend == DatabaseBackend.POSTGRESQL
    assert settings.queue_backend == QueueBackend.REDIS
    assert settings.api_host == "0.0.0.0"
    assert settings.api_port == 8000
    assert settings.worker_threads == 4
    assert settings.sync_processing is False


def test_lightweight_mode_configuration(monkeypatch):
    """Test lightweight mode configuration via environment variables."""
    monkeypatch.setenv("DOC_HEALING_DEPLOYMENT_MODE", "lightweight")
    monkeypatch.setenv("DOC_HEALING_DATABASE_BACKEND", "sqlite")
    monkeypatch.setenv("DOC_HEALING_QUEUE_BACKEND", "memory")
    monkeypatch.setenv("DOC_HEALING_SQLITE_PATH", "./test_data/test.db")
    
    settings = Settings()
    
    assert settings.deployment_mode == DeploymentMode.LIGHTWEIGHT
    assert settings.database_backend == DatabaseBackend.SQLITE
    assert settings.queue_backend == QueueBackend.MEMORY
    assert settings.sqlite_path == "./test_data/test.db"


def test_full_mode_configuration(monkeypatch):
    """Test full mode configuration via environment variables."""
    monkeypatch.setenv("DOC_HEALING_DEPLOYMENT_MODE", "full")
    monkeypatch.setenv("DOC_HEALING_DATABASE_BACKEND", "postgresql")
    monkeypatch.setenv("DOC_HEALING_QUEUE_BACKEND", "redis")
    monkeypatch.setenv("DOC_HEALING_DATABASE_URL", "postgresql://user:pass@db:5432/test")
    
    settings = Settings()
    
    assert settings.deployment_mode == DeploymentMode.FULL
    assert settings.database_backend == DatabaseBackend.POSTGRESQL
    assert settings.queue_backend == QueueBackend.REDIS
    assert settings.database_url == "postgresql://user:pass@db:5432/test"


def test_hybrid_mode_configuration(monkeypatch):
    """Test hybrid mode configuration."""
    monkeypatch.setenv("DOC_HEALING_DEPLOYMENT_MODE", "hybrid")
    
    settings = Settings()
    
    assert settings.deployment_mode == DeploymentMode.HYBRID


def test_worker_configuration(monkeypatch):
    """Test worker-specific configuration."""
    monkeypatch.setenv("DOC_HEALING_UNIFIED_WORKER", "true")
    monkeypatch.setenv("DOC_HEALING_WORKER_THREADS", "8")
    monkeypatch.setenv("DOC_HEALING_SYNC_PROCESSING", "true")
    
    settings = Settings()
    
    assert settings.unified_worker is True
    assert settings.worker_threads == 8
    assert settings.sync_processing is True


def test_redis_configuration(monkeypatch):
    """Test Redis-specific configuration."""
    monkeypatch.setenv("DOC_HEALING_REDIS_HOST", "redis-server")
    monkeypatch.setenv("DOC_HEALING_REDIS_PORT", "6380")
    monkeypatch.setenv("DOC_HEALING_REDIS_DB", "2")
    
    settings = Settings()
    
    assert settings.redis_host == "redis-server"
    assert settings.redis_port == 6380
    assert settings.redis_db == 2


def test_api_configuration(monkeypatch):
    """Test API-specific configuration."""
    monkeypatch.setenv("DOC_HEALING_API_HOST", "127.0.0.1")
    monkeypatch.setenv("DOC_HEALING_API_PORT", "9000")
    
    settings = Settings()
    
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 9000


def test_get_settings_singleton():
    """Test that get_settings returns a singleton instance."""
    # Clear the global settings
    import doc_healing.config
    doc_healing.config._settings = None
    
    settings1 = get_settings()
    settings2 = get_settings()
    
    assert settings1 is settings2
