"""Property-based tests for API endpoints."""

import sys
import importlib
import pytest
from hypothesis import given, strategies as st
from fastapi.testclient import TestClient

@pytest.fixture
def client(monkeypatch, tmp_path):
    """Create a test client with lightweight mode configuration."""
    monkeypatch.setenv("DOC_HEALING_DEPLOYMENT_MODE", "lightweight")
    monkeypatch.setenv("DOC_HEALING_DATABASE_BACKEND", "sqlite")
    sqlite_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DOC_HEALING_SQLITE_PATH", sqlite_path)
    monkeypatch.setenv("DOC_HEALING_QUEUE_BACKEND", "memory")
    monkeypatch.setenv("DOC_HEALING_SYNC_PROCESSING", "true")
    
    # Need to mock get_settings to return these values since the module is already loaded
    import doc_healing.config as config
    from doc_healing.config import Settings
    
    # Create lightweight settings directly
    test_settings = Settings(
        deployment_mode="lightweight",
        database_backend="sqlite",
        sqlite_path=sqlite_path,
        queue_backend="memory",
        sync_processing=True
    )
    
    # Patch the get_settings function
    mock_get_settings = lambda: test_settings
    monkeypatch.setattr(config, "get_settings", mock_get_settings)
    
    from doc_healing.api.main import app
    return TestClient(app)

# Use standard pytest parametrization instead of Hypothesis to avoid INTERNALERROR
# during async/TestClient initialization

WEBHOOK_PAYLOADS = [
    {"event_type": "push", "repository": "test/repo1", "data": {"key": "value"}},
    {"event_type": "pull_request", "repository": "test/repo2", "data": {}},
    {"event_type": "issue", "repository": "repo-only", "data": {"id": "123"}},
]

VALIDATION_PAYLOADS = [
    {"file_path": "docs/example.md", "snippet_id": "snip1", "code": "print(1)", "language": "python"},
    {"file_path": "README.md", "snippet_id": "snip2", "code": "console.log()", "language": "javascript"},
    {"file_path": "test.md", "snippet_id": "snip3", "code": "echo test", "language": "bash"},
]

HEALING_PAYLOADS = [
    {"file_path": "docs/example.md", "snippet_id": "snip1", "code": "print(1", "language": "python", "errors": ["SyntaxError"]},
    {"file_path": "README.md", "snippet_id": "snip2", "code": "console.log(", "language": "javascript", "errors": ["Missing delimiter"]},
]


@pytest.mark.parametrize("payload", WEBHOOK_PAYLOADS)
def test_property_webhook_endpoint_availability(client, payload):
    """Property 8: Webhook Endpoint Availability. Test that webhook endpoints correctly enqueue payload tasks."""
    response = client.post("/webhooks/github", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert data["queue_name"] == "webhooks"


@pytest.mark.parametrize("payload", VALIDATION_PAYLOADS)
def test_property_validation_functionality(client, payload):
    """Property 9: Validation Functionality. Test that validation endpoints enqueue valid tasks."""
    response = client.post("/validate/snippet", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert data["queue_name"] == "validation"


@pytest.mark.parametrize("payload", HEALING_PAYLOADS)
def test_property_healing_functionality(client, payload):
    """Property 10: Healing Functionality. Test that healing endpoints enqueue healing tasks."""
    response = client.post("/heal/snippet", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert data["queue_name"] == "healing"
