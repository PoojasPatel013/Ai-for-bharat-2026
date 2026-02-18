#!/usr/bin/env python3
"""Initialize the database with tables and seed data."""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from doc_healing.db.base import engine, Base
from doc_healing.db.models import (
    Repository,
    PullRequest,
    ValidationWorkflowDB,
    CodeSnippetDB,
    CodeSymbolDB,
    DocumentationReferenceDB,
    WebhookEventDB,
    ValidationMetricsDB,
    CorrectionMetricsDB,
    SystemMetricsDB,
)


def init_db() -> None:
    """Initialize the database."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")


if __name__ == "__main__":
    init_db()
