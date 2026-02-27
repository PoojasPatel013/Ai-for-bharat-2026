"""Orchestration service models."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List

from doc_healing.models.validation import ValidationResult
from doc_healing.models.healing import CorrectionResult


class WorkflowStatus(Enum):
    """Status of a validation workflow."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ValidationWorkflow:
    """Represents a validation workflow for a pull request."""

    pull_request_id: str
    status: WorkflowStatus
    results: List[ValidationResult]
    corrections: List[CorrectionResult]
    start_time: datetime
    end_time: Optional[datetime] = None


class StatusCheckStatus(Enum):
    """Status of a PR status check."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass
class PRStatusCheck:
    """Represents a PR status check."""

    name: str
    status: StatusCheckStatus
    conclusion: Optional[str]
    summary: str
    details_url: Optional[str] = None


@dataclass
class FileChange:
    """Represents a file change in a commit."""

    path: str
    content: str


@dataclass
class BotCommit:
    """Represents a commit made by the bot."""

    message: str
    files: List[FileChange]
    branch: str
    marker: str  # '[bot:doc-healing]' prefix for recursion detection
