"""Tests for worker task implementations."""

import pytest
from unittest.mock import MagicMock, patch

from doc_healing.workers.tasks import (
    process_github_webhook,
    process_gitlab_webhook,
    validate_code_snippet,
    validate_documentation_file,
    heal_code_snippet,
    heal_documentation_file,
)


@pytest.fixture
def mock_queue_backend():
    """Mock queue backend for testing."""
    with patch('doc_healing.workers.tasks.get_queue_backend') as mock:
        queue = MagicMock()
        mock.return_value = queue
        yield queue


class TestWebhookTasks:
    """Tests for webhook processing tasks."""

    def test_process_github_webhook_success(self, mock_queue_backend):
        """Test successful GitHub webhook processing."""
        payload = {
            "event_type": "push",
            "repository": {"name": "test-repo"},
        }
        
        # Should not raise any exceptions
        process_github_webhook(payload)

    def test_process_github_webhook_invalid_payload(self, mock_queue_backend):
        """Test GitHub webhook with invalid payload."""
        with pytest.raises(ValueError, match="must be a dictionary"):
            process_github_webhook("not a dict")

    def test_process_github_webhook_missing_event_type(self, mock_queue_backend):
        """Test GitHub webhook with missing event type."""
        payload = {"repository": {"name": "test-repo"}}
        
        # Should log warning but not raise exception
        process_github_webhook(payload)

    def test_process_gitlab_webhook_success(self, mock_queue_backend):
        """Test successful GitLab webhook processing."""
        payload = {
            "object_kind": "push",
            "project": {"name": "test-repo"},
        }
        
        # Should not raise any exceptions
        process_gitlab_webhook(payload)

    def test_process_gitlab_webhook_invalid_payload(self, mock_queue_backend):
        """Test GitLab webhook with invalid payload."""
        with pytest.raises(ValueError, match="must be a dictionary"):
            process_gitlab_webhook("not a dict")


class TestValidationTasks:
    """Tests for validation tasks."""

    def test_validate_code_snippet_success(self, mock_queue_backend):
        """Test successful code snippet validation."""
        result = validate_code_snippet(
            file_path="docs/example.md",
            snippet_id="snippet-1",
            code="print('hello')",
            language="python"
        )
        
        assert result["valid"] is True
        assert result["snippet_id"] == "snippet-1"
        assert result["file_path"] == "docs/example.md"
        assert result["language"] == "python"
        assert isinstance(result["errors"], list)
        assert isinstance(result["warnings"], list)

    def test_validate_code_snippet_missing_parameters(self, mock_queue_backend):
        """Test validation with missing parameters."""
        with pytest.raises(ValueError, match="are required"):
            validate_code_snippet(
                file_path="",
                snippet_id="snippet-1",
                code="print('hello')",
                language="python"
            )

    def test_validate_documentation_file_success(self, mock_queue_backend):
        """Test successful documentation file validation."""
        result = validate_documentation_file(
            file_path="docs/example.md",
            content="# Example\n\n```python\nprint('hello')\n```"
        )
        
        assert result["file_path"] == "docs/example.md"
        assert "snippets_found" in result
        assert "snippets_valid" in result
        assert "snippets_invalid" in result
        assert isinstance(result["errors"], list)

    def test_validate_documentation_file_missing_parameters(self, mock_queue_backend):
        """Test validation with missing parameters."""
        with pytest.raises(ValueError, match="are required"):
            validate_documentation_file(file_path="", content="")


class TestHealingTasks:
    """Tests for healing tasks."""

    def test_heal_code_snippet_success(self, mock_queue_backend):
        """Test code snippet healing."""
        result = heal_code_snippet(
            file_path="docs/example.md",
            snippet_id="snippet-1",
            code="print('hello'",  # Missing closing parenthesis
            language="python",
            errors=["SyntaxError: unexpected EOF"]
        )
        
        assert result["snippet_id"] == "snippet-1"
        assert result["file_path"] == "docs/example.md"
        assert "healed" in result
        assert "healed_code" in result
        assert "changes" in result
        assert "confidence" in result

    def test_heal_code_snippet_missing_parameters(self, mock_queue_backend):
        """Test healing with missing parameters."""
        with pytest.raises(ValueError, match="are required"):
            heal_code_snippet(
                file_path="",
                snippet_id="snippet-1",
                code="print('hello')",
                language="python",
                errors=[]
            )

    def test_heal_code_snippet_no_errors(self, mock_queue_backend):
        """Test healing with no errors provided."""
        # Should log warning but not raise exception
        result = heal_code_snippet(
            file_path="docs/example.md",
            snippet_id="snippet-1",
            code="print('hello')",
            language="python",
            errors=[]
        )
        
        assert result["snippet_id"] == "snippet-1"

    def test_heal_documentation_file_success(self, mock_queue_backend):
        """Test documentation file healing."""
        validation_results = {
            "file_path": "docs/example.md",
            "snippets_found": 2,
            "snippets_valid": 1,
            "snippets_invalid": 1,
        }
        
        result = heal_documentation_file(
            file_path="docs/example.md",
            validation_results=validation_results
        )
        
        assert result["file_path"] == "docs/example.md"
        assert "snippets_healed" in result
        assert "snippets_failed" in result
        assert "pull_request_url" in result

    def test_heal_documentation_file_missing_parameters(self, mock_queue_backend):
        """Test healing with missing parameters."""
        with pytest.raises(ValueError, match="are required"):
            heal_documentation_file(file_path="", validation_results=None)
