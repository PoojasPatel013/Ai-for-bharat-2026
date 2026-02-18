"""Shared data models and types."""

from doc_healing.models.base import (
    RepositoryInfo,
    PullRequestInfo,
    CommitInfo,
    DocumentationFile,
)
from doc_healing.models.webhook import WebhookEvent
from doc_healing.models.validation import (
    CodeSnippet,
    ErrorType,
    ExecutionError,
    ValidationResult,
    CodeContext,
)
from doc_healing.models.healing import CorrectionRequest, CorrectionResult
from doc_healing.models.mapping import (
    SymbolType,
    Visibility,
    CodeSymbol,
    ChangeType,
    SymbolChange,
    ReferenceType,
    DocumentationReference,
)
from doc_healing.models.orchestration import (
    WorkflowStatus,
    ValidationWorkflow,
    StatusCheckStatus,
    PRStatusCheck,
    FileChange,
    BotCommit,
)
from doc_healing.models.config import (
    DocumentationPaths,
    LanguageConfig,
    ValidationConfig,
    NotificationConfig,
    SnippetMarkers,
    RepositoryConfig,
)

__all__ = [
    # Base models
    "RepositoryInfo",
    "PullRequestInfo",
    "CommitInfo",
    "DocumentationFile",
    # Webhook models
    "WebhookEvent",
    # Validation models
    "CodeSnippet",
    "ErrorType",
    "ExecutionError",
    "ValidationResult",
    "CodeContext",
    # Healing models
    "CorrectionRequest",
    "CorrectionResult",
    # Mapping models
    "SymbolType",
    "Visibility",
    "CodeSymbol",
    "ChangeType",
    "SymbolChange",
    "ReferenceType",
    "DocumentationReference",
    # Orchestration models
    "WorkflowStatus",
    "ValidationWorkflow",
    "StatusCheckStatus",
    "PRStatusCheck",
    "FileChange",
    "BotCommit",
    # Config models
    "DocumentationPaths",
    "LanguageConfig",
    "ValidationConfig",
    "NotificationConfig",
    "SnippetMarkers",
    "RepositoryConfig",
]
