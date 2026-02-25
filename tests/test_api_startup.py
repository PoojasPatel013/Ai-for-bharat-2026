"""Tests for API startup event."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os
import sys
import importlib


def test_api_startup_lightweight_mode(monkeypatch, tmp_path):
    """Test API startup in lightweight mode with SQLite."""
    # Set up lightweight mode configuration
    monkeypatch.setenv("DOC_HEALING_DEPLOYMENT_MODE", "lightweight")
    monkeypatch.setenv("DOC_HEALING_DATABASE_BACKEND", "sqlite")
    sqlite_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DOC_HEALING_SQLITE_PATH", sqlite_path)
    monkeypatch.setenv("DOC_HEALING_QUEUE_BACKEND", "memory")
    
    # Clear the global settings instance and reload modules
    if 'doc_healing.config' in sys.modules:
        importlib.reload(sys.modules['doc_healing.config'])
    if 'doc_healing.db.connection' in sys.modules:
        importlib.reload(sys.modules['doc_healing.db.connection'])
    if 'doc_healing.api.main' in sys.modules:
        importlib.reload(sys.modules['doc_healing.api.main'])
    
    # Import after setting environment variables
    from doc_healing.api.main import app
    
    # Create test client (this triggers startup event)
    with TestClient(app) as client:
        # Verify API is running
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
        
        # Verify database file was created
        assert os.path.exists(sqlite_path)


def test_api_startup_full_mode(monkeypatch):
    """Test API startup in full mode with PostgreSQL."""
    # Set up full mode configuration
    monkeypatch.setenv("DOC_HEALING_DEPLOYMENT_MODE", "full")
    monkeypatch.setenv("DOC_HEALING_DATABASE_BACKEND", "postgresql")
    monkeypatch.setenv("DOC_HEALING_DATABASE_URL", "postgresql://test:test@localhost:5432/test")
    monkeypatch.setenv("DOC_HEALING_QUEUE_BACKEND", "redis")
    
    # Clear and reload modules
    if 'doc_healing.config' in sys.modules:
        importlib.reload(sys.modules['doc_healing.config'])
    if 'doc_healing.db.connection' in sys.modules:
        importlib.reload(sys.modules['doc_healing.db.connection'])
    if 'doc_healing.api.main' in sys.modules:
        importlib.reload(sys.modules['doc_healing.api.main'])
    
    # Mock the database engine to avoid actual PostgreSQL connection
    with patch("doc_healing.api.main.engine") as mock_engine, \
         patch("doc_healing.api.main.Base") as mock_base:
        mock_engine.connect = MagicMock()
        mock_base.metadata.create_all = MagicMock()
        
        # Import after setting environment variables
        from doc_healing.api.main import app
        
        # Create test client (this triggers startup event)
        with TestClient(app) as client:
            # Verify API is running
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"


def test_api_startup_logging(monkeypatch, tmp_path, caplog):
    """Test that startup event logs deployment configuration."""
    import logging
    caplog.set_level(logging.INFO)
    
    # Set up lightweight mode configuration
    monkeypatch.setenv("DOC_HEALING_DEPLOYMENT_MODE", "lightweight")
    monkeypatch.setenv("DOC_HEALING_DATABASE_BACKEND", "sqlite")
    sqlite_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DOC_HEALING_SQLITE_PATH", sqlite_path)
    monkeypatch.setenv("DOC_HEALING_QUEUE_BACKEND", "memory")
    
    # Clear and reload modules
    if 'doc_healing.config' in sys.modules:
        importlib.reload(sys.modules['doc_healing.config'])
    if 'doc_healing.db.connection' in sys.modules:
        importlib.reload(sys.modules['doc_healing.db.connection'])
    if 'doc_healing.api.main' in sys.modules:
        importlib.reload(sys.modules['doc_healing.api.main'])
    
    # Import after setting environment variables
    from doc_healing.api.main import app
    
    # Create test client (this triggers startup event)
    with TestClient(app) as client:
        # Verify logging messages
        log_messages = [record.message for record in caplog.records]
        
        assert any("Starting API in lightweight mode" in msg for msg in log_messages)
        assert any("Database backend: sqlite" in msg for msg in log_messages)
        assert any("Queue backend: memory" in msg for msg in log_messages)
        assert any(f"SQLite database path: {sqlite_path}" in msg for msg in log_messages)
        assert any("Initializing database schema" in msg for msg in log_messages)
        assert any("Database schema initialized successfully" in msg for msg in log_messages)
