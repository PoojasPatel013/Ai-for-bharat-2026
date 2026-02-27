"""Base data models for common entities."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RepositoryInfo:
    """Information about a repository."""

    platform: str  # 'github' or 'gitlab'
    owner: str
    name: str
    full_name: str
    installation_id: Optional[int] = None


@dataclass
class PullRequestInfo:
    """Information about a pull request."""

    pr_number: int
    pr_id: int
    title: str
    branch: str
    base_branch: str
    author: str
    repository: RepositoryInfo


@dataclass
class CommitInfo:
    """Information about a commit."""

    sha: str
    message: str
    author: str
    timestamp: str


@dataclass
class DocumentationFile:
    """Represents a documentation file."""

    path: str
    content: str
    language: str = "markdown"
