import sys
import os
import traceback
from fastapi.testclient import TestClient

# Set env vars BEFORE any doc_healing modules are imported
os.environ["DOC_HEALING_DEPLOYMENT_MODE"] = "lightweight"
os.environ["DOC_HEALING_DATABASE_BACKEND"] = "sqlite"
os.environ["DOC_HEALING_SQLITE_PATH"] = "test.db"
os.environ["DOC_HEALING_QUEUE_BACKEND"] = "memory"
os.environ["DOC_HEALING_SYNC_PROCESSING"] = "true"

print("Starting debug script...")
try:
    from doc_healing.api.main import app
    from doc_healing.config import get_settings
    
    print(f"Deployment mode: {get_settings().deployment_mode}")
    print(f"Queue backend: {get_settings().queue_backend}")
    print(f"Sync processing: {get_settings().sync_processing}")

    client = TestClient(app)
    
    print("Hitting webhook endpoint...")
    payload = {
        "event_type": "push",
        "repository": "test",
        "data": {}
    }
    response = client.post("/webhooks/github", json=payload)
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.json()}")
    
except Exception as e:
    traceback.print_exc()

print("Debug script finished")
