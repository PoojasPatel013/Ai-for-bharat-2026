"""Unit tests for deployment configurations and migrations."""

import os
import pytest
from pathlib import Path
import yaml

def test_docker_compose_lightweight_valid(tmp_path):
    """Test docker-compose.lightweight.yml is valid YAML."""
    compose_path = Path(__file__).parent.parent / "docker-compose.lightweight.yml"
    assert compose_path.exists(), "docker-compose.lightweight.yml should exist"
    
    with open(compose_path, 'r') as f:
        data = yaml.safe_load(f)
        
    assert "services" in data
    assert "api" in data["services"]
    assert "worker" in data["services"]
    
    api_env = data["services"]["api"].get("environment", {})
    if isinstance(api_env, dict):
        assert api_env.get("DOC_HEALING_DEPLOYMENT_MODE") == "lightweight"
        assert api_env.get("DOC_HEALING_DATABASE_BACKEND") == "sqlite"
        assert api_env.get("DOC_HEALING_QUEUE_BACKEND") == "memory"
        
    worker_env = data["services"]["worker"].get("environment", {})
    if isinstance(worker_env, dict):
        assert worker_env.get("DOC_HEALING_UNIFIED_WORKER") == "true"
        

def test_environment_templates_complete():
    """Test environment templates contain all required configuration options."""
    # Check that .env.example exists and contains required keys
    env_path = Path(__file__).parent.parent / ".env.example"
    assert env_path.exists(), ".env.example should exist"
    
    expected_keys = [
        "DOC_HEALING_DEPLOYMENT_MODE",
        "DOC_HEALING_DATABASE_BACKEND",
        "DOC_HEALING_QUEUE_BACKEND"
    ]
    
    with open(env_path, 'r') as f:
        content = f.read()
        for key in expected_keys:
            assert key in content, f"{key} missing from .env.example"

def test_makefile_commands_present():
    """Test Makefile commands include required deployment targets."""
    makefile_path = Path(__file__).parent.parent / "Makefile"
    if not makefile_path.exists():
        pytest.skip("Makefile not found")
        
    with open(makefile_path, 'r') as f:
        content = f.read()
        assert "dev-lightweight:" in content or "dev:" in content
        
