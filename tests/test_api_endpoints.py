"""Tests for API endpoints using queue factory."""

import pytest
from fastapi.testclient import TestClient
import os
import sys
import importlib


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Create a test client with lightweight mode configuration."""
    # Set up lightweight mode configuration
    monkeypatch.setenv("DOC_HEALING_DEPLOYMENT_MODE", "lightweight")
    monkeypatch.setenv("DOC_HEALING_DATABASE_BACKEND", "sqlite")
    sqlite_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DOC_HEALING_SQLITE_PATH", sqlite_path)
    monkeypatch.setenv("DOC_HEALING_QUEUE_BACKEND", "memory")
    monkeypatch.setenv("DOC_HEALING_SYNC_PROCESSING", "true")
    
    # Clear and reload modules
    for module in ['doc_healing.config', 'doc_healing.db.connection', 'doc_healing.api.main']:
        if module in sys.modules:
            importlib.reload(sys.modules[module])
    
    # Import after setting environment variables
    from doc_healing.api.main import app
    
    return TestClient(app)


def test_github_webhook_endpoint(client):
    """Test GitHub webhook endpoint enqueues task."""
    payload = {
        "event_type": "push",
        "repository": "test/repo",
        "data": {"test": "data"}
    }
    
    response = client.post("/webhooks/github", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert data["queue_name"] == "webhooks"


def test_gitlab_webhook_endpoint(client):
    """Test GitLab webhook endpoint enqueues task."""
    payload = {
        "object_kind": "push",
        "project": {"name": "test-project"},
        "data": {"test": "data"}
    }
    
    response = client.post("/webhooks/gitlab", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert data["queue_name"] == "webhooks"


def test_validate_snippet_endpoint(client):
    """Test code snippet validation endpoint enqueues task."""
    request_data = {
        "file_path": "docs/example.md",
        "snippet_id": "snippet-1",
        "code": "print('hello')",
        "language": "python"
    }
    
    response = client.post("/validate/snippet", json=request_data)
    
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert data["queue_name"] == "validation"


def test_validate_file_endpoint(client):
    """Test file validation endpoint enqueues task."""
    request_data = {
        "file_path": "docs/example.md",
        "content": "# Example\n```python\nprint('hello')\n```"
    }
    
    response = client.post("/validate/file", json=request_data)
    
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert data["queue_name"] == "validation"


def test_heal_snippet_endpoint(client):
    """Test code snippet healing endpoint enqueues task."""
    request_data = {
        "file_path": "docs/example.md",
        "snippet_id": "snippet-1",
        "code": "print('hello'",
        "language": "python",
        "errors": ["SyntaxError: unexpected EOF while parsing"]
    }
    
    response = client.post("/heal/snippet", json=request_data)
    
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert data["queue_name"] == "healing"


def test_heal_file_endpoint(client):
    """Test file healing endpoint enqueues task."""
    request_data = {
        "file_path": "docs/example.md",
        "validation_results": {
            "snippets_found": 1,
            "snippets_valid": 0,
            "snippets_invalid": 1,
            "errors": ["SyntaxError in snippet-1"]
        }
    }
    
    response = client.post("/heal/file", json=request_data)
    
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert data["queue_name"] == "healing"


def test_webhook_endpoint_with_invalid_payload(client):
    """Test webhook endpoint handles errors gracefully."""
    # This test verifies error handling, but the endpoint should still accept
    # the payload and enqueue it - the task itself will handle validation
    payload = {"invalid": "payload"}
    
    response = client.post("/webhooks/github", json=payload)
    
    # Should still enqueue successfully - validation happens in the task
    assert response.status_code == 200


def test_validation_endpoint_with_missing_fields(client):
    """Test validation endpoint rejects requests with missing required fields."""
    request_data = {
        "file_path": "docs/example.md",
        # Missing snippet_id, code, and language
    }
    
    response = client.post("/validate/snippet", json=request_data)
    
    # Should return 422 Unprocessable Entity for validation error
    assert response.status_code == 422
