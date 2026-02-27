"""Healing engine models."""

from dataclasses import dataclass

from doc_healing.models.validation import CodeSnippet, ExecutionError, CodeContext


@dataclass
class CorrectionRequest:
    """Request to generate a correction for a broken snippet."""

    snippet: CodeSnippet
    error: ExecutionError
    code_context: CodeContext
    documentation_context: str


@dataclass
class CorrectionResult:
    """Result of generating a correction."""

    original_snippet: CodeSnippet
    corrected_code: str
    confidence: float
    explanation: str
    validated: bool
