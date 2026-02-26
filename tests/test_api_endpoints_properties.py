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
    
    # Clear and reload modules
    for module in ['doc_healing.config', 'doc_healing.db.connection', 'doc_healing.api.main']:
        if module in sys.modules:
            importlib.reload(sys.modules[module])
            
    from doc_healing.api.main import app
    
    return TestClient(app)

# Strategies for Payload Generation
github_payload_st = st.fixed_dictionaries({
    "event_type": st.text(min_size=1),
    "repository": st.text(min_size=1),
    "data": st.dictionaries(st.text(min_size=1), st.text())
})

validation_snippet_st = st.fixed_dictionaries({
    "file_path": st.text(min_size=1),
    "snippet_id": st.text(min_size=1),
    "code": st.text(min_size=1),
    "language": st.sampled_from(["python", "javascript", "bash"])
})

healing_snippet_st = st.fixed_dictionaries({
    "file_path": st.text(min_size=1),
    "snippet_id": st.text(min_size=1),
    "code": st.text(min_size=1),
    "language": st.sampled_from(["python", "javascript", "bash"]),
    "errors": st.lists(st.text(min_size=1), min_size=1)
})

@given(payload=github_payload_st)
def test_property_webhook_endpoint_availability(client, payload):
    """Property 8: Webhook Endpoint Availability. Test that webhook endpoints correctly enqueue payload tasks."""
    response = client.post("/webhooks/github", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert data["queue_name"] == "webhooks"

@given(payload=validation_snippet_st)
def test_property_validation_functionality(client, payload):
    """Property 9: Validation Functionality. Test that validation endpoints enqueue valid tasks."""
    response = client.post("/validate/snippet", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert data["queue_name"] == "validation"

@given(payload=healing_snippet_st)
def test_property_healing_functionality(client, payload):
    """Property 10: Healing Functionality. Test that healing endpoints enqueue healing tasks."""
    response = client.post("/heal/snippet", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert data["queue_name"] == "healing"
