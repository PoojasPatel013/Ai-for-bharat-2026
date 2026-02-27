"""Database models using SQLAlchemy."""

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    TIMESTAMP,
    ForeignKey,
    Index,
    BigInteger,
    Numeric,
    JSON,
)
from sqlalchemy.orm import relationship

from doc_healing.db.base import Base


class Repository(Base):
    """Repository table."""

    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    platform = Column(String(20), nullable=False)
    owner = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    full_name = Column(String(511), nullable=False)
    installation_id = Column(BigInteger, nullable=True)
    config = Column(JSON, default={})
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    pull_requests = relationship("PullRequest", back_populates="repository")
    code_symbols = relationship("CodeSymbolDB", back_populates="repository")
    webhook_events = relationship("WebhookEventDB", back_populates="repository")

    __table_args__ = (Index("idx_platform_fullname", "platform", "full_name", unique=True),)


class PullRequest(Base):
    """Pull request table."""

    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    pr_number = Column(Integer, nullable=False)
    pr_id = Column(BigInteger, nullable=False)
    title = Column(String(500))
    branch = Column(String(255))
    base_branch = Column(String(255))
    author = Column(String(255))
    status = Column(String(50), default="open")
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    repository = relationship("Repository", back_populates="pull_requests")
    validation_workflows = relationship("ValidationWorkflowDB", back_populates="pull_request")

    __table_args__ = (Index("idx_repo_pr_number", "repository_id", "pr_number", unique=True),)


class ValidationWorkflowDB(Base):
    """Validation workflow table."""

    __tablename__ = "validation_workflows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False)
    status = Column(String(50), default="pending")
    total_snippets = Column(Integer, default=0)
    passed_snippets = Column(Integer, default=0)
    failed_snippets = Column(Integer, default=0)
    corrected_snippets = Column(Integer, default=0)
    execution_time_ms = Column(Integer)
    started_at = Column(TIMESTAMP, default=datetime.utcnow)
    completed_at = Column(TIMESTAMP, nullable=True)
    error_message = Column(Text, nullable=True)

    # Relationships
    pull_request = relationship("PullRequest", back_populates="validation_workflows")
    code_snippets = relationship("CodeSnippetDB", back_populates="workflow")


class CodeSnippetDB(Base):
    """Code snippet table."""

    __tablename__ = "code_snippets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(Integer, ForeignKey("validation_workflows.id"), nullable=False)
    file_path = Column(String(1000), nullable=False)
    language = Column(String(50), nullable=False)
    line_start = Column(Integer, nullable=False)
    line_end = Column(Integer, nullable=False)
    original_code = Column(Text, nullable=False)
    corrected_code = Column(Text, nullable=True)
    validation_status = Column(String(50), default="pending")
    execution_output = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    execution_time_ms = Column(Integer)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    workflow = relationship("ValidationWorkflowDB", back_populates="code_snippets")
    documentation_references = relationship(
        "DocumentationReferenceDB", back_populates="snippet"
    )


class CodeSymbolDB(Base):
    """Code symbol table."""

    __tablename__ = "code_symbols"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    signature = Column(Text)
    file_path = Column(String(1000), nullable=False)
    line_number = Column(Integer)
    commit_sha = Column(String(40))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    repository = relationship("Repository", back_populates="code_symbols")
    documentation_references = relationship(
        "DocumentationReferenceDB", back_populates="symbol"
    )

    __table_args__ = (Index("idx_repo_name_type", "repository_id", "name", "type"),)


class DocumentationReferenceDB(Base):
    """Documentation reference table."""

    __tablename__ = "documentation_references"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snippet_id = Column(Integer, ForeignKey("code_snippets.id"), nullable=False)
    symbol_id = Column(Integer, ForeignKey("code_symbols.id"), nullable=False)
    confidence = Column(Numeric(3, 2), default=0.0)
    reference_type = Column(String(50))
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    snippet = relationship("CodeSnippetDB", back_populates="documentation_references")
    symbol = relationship("CodeSymbolDB", back_populates="documentation_references")


class WebhookEventDB(Base):
    """Webhook event table."""

    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    event_id = Column(String(255))
    payload = Column(JSON, nullable=False)
    processed_at = Column(TIMESTAMP, nullable=True)
    status = Column(String(50), default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    # Relationships
    repository = relationship("Repository", back_populates="webhook_events")

    __table_args__ = (Index("idx_repo_event_id", "repository_id", "event_id", unique=True),)


class ValidationMetricsDB(Base):
    """Validation metrics table."""

    __tablename__ = "validation_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    workflow_id = Column(Integer, ForeignKey("validation_workflows.id"), nullable=False)
    language = Column(String(50), nullable=False)
    total_snippets = Column(Integer, nullable=False)
    passed_snippets = Column(Integer, nullable=False)
    failed_snippets = Column(Integer, nullable=False)
    corrected_snippets = Column(Integer, nullable=False)
    average_execution_time_ms = Column(Integer)
    total_execution_time_ms = Column(Integer)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_repo_created", "repository_id", "created_at"),
        Index("idx_lang_created", "language", "created_at"),
    )


class CorrectionMetricsDB(Base):
    """Correction metrics table."""

    __tablename__ = "correction_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    snippet_id = Column(Integer, ForeignKey("code_snippets.id"), nullable=False)
    error_type = Column(String(50), nullable=False)
    correction_applied = Column(Boolean, default=False)
    confidence = Column(Numeric(3, 2))
    validated = Column(Boolean, default=False)
    manual_review_required = Column(Boolean, default=False)
    accepted = Column(Boolean, nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_repo_created_corr", "repository_id", "created_at"),
        Index("idx_error_created", "error_type", "created_at"),
    )


class SystemMetricsDB(Base):
    """System metrics table."""

    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    webhook_queue_depth = Column(Integer)
    active_containers = Column(Integer)
    container_pool_utilization = Column(Numeric(5, 2))
    database_connections = Column(Integer)
    api_rate_limit_remaining = Column(Integer)
    average_webhook_latency_ms = Column(Integer)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    __table_args__ = (Index("idx_sys_created", "created_at"),)
