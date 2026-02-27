"""Test data models."""

import pytest
from doc_healing.models import (
    RepositoryInfo,
    PullRequestInfo,
    CodeSnippet,
    ValidationResult,
    ErrorType,
    ExecutionError,
)


@pytest.mark.unit
def test_repository_info_creation():
    """Test creating a RepositoryInfo instance."""
    repo = RepositoryInfo(
        platform="github",
        owner="test-owner",
        name="test-repo",
        full_name="test-owner/test-repo",
        installation_id=12345,
    )
    assert repo.platform == "github"
    assert repo.owner == "test-owner"
    assert repo.name == "test-repo"
    assert repo.full_name == "test-owner/test-repo"
    assert repo.installation_id == 12345


@pytest.mark.unit
def test_code_snippet_creation():
    """Test creating a CodeSnippet instance."""
    snippet = CodeSnippet(
        id="snippet-1",
        language="python",
        code="print('hello')",
        file="README.md",
        line_start=10,
        line_end=12,
        dependencies=["requests"],
    )
    assert snippet.id == "snippet-1"
    assert snippet.language == "python"
    assert snippet.code == "print('hello')"
    assert snippet.file == "README.md"
    assert snippet.line_start == 10
    assert snippet.line_end == 12
    assert snippet.dependencies == ["requests"]


@pytest.mark.unit
def test_validation_result_success():
    """Test creating a successful ValidationResult."""
    result = ValidationResult(
        snippet_id="snippet-1", success=True, output="hello\n", execution_time=0.5
    )
    assert result.snippet_id == "snippet-1"
    assert result.success is True
    assert result.output == "hello\n"
    assert result.error is None
    assert result.execution_time == 0.5


@pytest.mark.unit
def test_validation_result_failure():
    """Test creating a failed ValidationResult."""
    error = ExecutionError(
        type=ErrorType.SYNTAX, message="SyntaxError: invalid syntax", line=1
    )
    result = ValidationResult(
        snippet_id="snippet-1", success=False, error=error, execution_time=0.1
    )
    assert result.snippet_id == "snippet-1"
    assert result.success is False
    assert result.error is not None
    assert result.error.type == ErrorType.SYNTAX
    assert result.error.message == "SyntaxError: invalid syntax"
    assert result.error.line == 1
