"""Main FastAPI application."""

import logging
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from doc_healing.config import get_settings
from doc_healing.db.connection import engine
from doc_healing.db.base import Base
from doc_healing.queue.factory import get_queue_backend
from doc_healing.workers.tasks import (
    process_github_webhook,
    process_gitlab_webhook,
    validate_code_snippet,
    validate_documentation_file,
    heal_code_snippet,
    heal_documentation_file,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Self-Healing Documentation Engine",
    description="A GitHub/GitLab bot that validates and auto-corrects code snippets in documentation",
    version="0.1.0",
)


# Request/Response Models
class WebhookPayload(BaseModel):
    """Generic webhook payload model."""
    event_type: str | None = None
    object_kind: str | None = None
    data: Dict[str, Any] = {}


class ValidationRequest(BaseModel):
    """Request model for code snippet validation."""
    file_path: str
    snippet_id: str
    code: str
    language: str


class FileValidationRequest(BaseModel):
    """Request model for documentation file validation."""
    file_path: str
    content: str


class HealingRequest(BaseModel):
    """Request model for code snippet healing."""
    file_path: str
    snippet_id: str
    code: str
    language: str
    errors: list[str]


class FileHealingRequest(BaseModel):
    """Request model for documentation file healing."""
    file_path: str
    validation_results: Dict[str, Any]


class TaskResponse(BaseModel):
    """Response model for enqueued tasks."""
    task_id: str
    status: str
    queue_name: str


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    settings = get_settings()
    
    # Log deployment configuration
    logger.info(f"Starting API in {settings.deployment_mode.value} mode")
    logger.info(f"Database backend: {settings.database_backend.value}")
    logger.info(f"Queue backend: {settings.queue_backend.value}")
    
    # Log database connection details
    if settings.database_backend.value == "sqlite":
        logger.info(f"SQLite database path: {settings.sqlite_path}")
    else:
        logger.info(f"PostgreSQL database URL: {settings.database_url}")
    
    # Initialize database schema (create tables if they don't exist)
    # This is especially important for SQLite support
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized successfully")


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Self-Healing Documentation Engine API", "version": "0.1.0"}


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(content={"status": "healthy"}, status_code=200)
