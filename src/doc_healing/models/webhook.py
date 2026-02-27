"""Webhook event models."""

from dataclasses import dataclass
from typing import List, Literal

from doc_healing.models.base import RepositoryInfo, PullRequestInfo, CommitInfo


@dataclass
class WebhookEvent:
    """Represents a webhook event from GitHub or GitLab."""

    source: Literal["github", "gitlab"]
    type: Literal["pull_request", "push", "merge_request"]
    repository: RepositoryInfo
    pull_request: PullRequestInfo
    commits: List[CommitInfo]
    signature: str
