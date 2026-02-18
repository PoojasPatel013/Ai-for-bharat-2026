"""Validation engine models."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, List


class ErrorType(Enum):
    """Types of execution errors."""

    SYNTAX = "syntax"
    RUNTIME = "runtime"
    TIMEOUT = "timeout"
    DEPENDENCY = "dependency"


@dataclass
class ExecutionError:
    """Details about an execution error."""

    type: ErrorType
    message: str
    line: Optional[int] = None
    stack_trace: Optional[str] = None


@dataclass
class CodeSnippet:
    """Represents a code snippet extracted from documentation."""

    id: str
    language: str
    code: str
    file: str
    line_start: int
    line_end: int
    dependencies: Optional[List[str]] = None


@dataclass
class ValidationResult:
    """Result of validating a code snippet."""

    snippet_id: str
    success: bool
    output: Optional[str] = None
    error: Optional[ExecutionError] = None
    execution_time: float = 0.0


@dataclass
class CodeContext:
    """Context information for code execution."""

    repository_path: str
    branch: str
    commit_sha: str
    available_modules: List[str]
