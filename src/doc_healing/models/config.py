"""Configuration models."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class DocumentationPaths:
    """Configuration for documentation file paths."""

    include: List[str] = field(default_factory=lambda: ["docs/**/*.md", "README.md", "*.mdx"])
    exclude: List[str] = field(
        default_factory=lambda: ["docs/archive/**", "__pycache__/**", "venv/**"]
    )


@dataclass
class LanguageConfig:
    """Configuration for a specific language."""

    enabled: bool = True
    timeout: int = 30
    dependencies: List[str] = field(default_factory=list)
    custom_setup: Optional[str] = None


@dataclass
class ValidationConfig:
    """Configuration for validation behavior."""

    auto_correct: bool = True
    confidence_threshold: float = 0.8
    require_manual_review: bool = False
    block_on_failure: bool = True
    parallel_execution: bool = True
    max_concurrent_snippets: int = 10


@dataclass
class NotificationConfig:
    """Configuration for bot notifications."""

    pr_comments: bool = True
    status_checks: bool = True
    review_comments: bool = True
    email_alerts: bool = False


@dataclass
class SnippetMarkers:
    """Configuration for code snippet markers."""

    code_block_languages: List[str] = field(
        default_factory=lambda: ["python", "javascript", "typescript", "java", "go", "rust"]
    )
    ignore_marker: str = "<!-- doc-healing:ignore -->"


@dataclass
class RepositoryConfig:
    """Complete repository configuration."""

    enabled: bool = True
    documentation_paths: DocumentationPaths = field(default_factory=DocumentationPaths)
    languages: Dict[str, LanguageConfig] = field(
        default_factory=lambda: {
            "python": LanguageConfig(timeout=30, dependencies=["requests", "pytest"]),
            "javascript": LanguageConfig(timeout=20, dependencies=["axios"]),
            "typescript": LanguageConfig(timeout=25),
            "java": LanguageConfig(timeout=60),
            "go": LanguageConfig(timeout=45),
            "rust": LanguageConfig(timeout=90),
        }
    )
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    notifications: NotificationConfig = field(default_factory=NotificationConfig)
    snippet_markers: SnippetMarkers = field(default_factory=SnippetMarkers)
