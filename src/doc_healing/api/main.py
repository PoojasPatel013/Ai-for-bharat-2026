"""Main FastAPI application."""

import logging
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from doc_healing.config import get_settings
from doc_healing.db.connection import engine
from doc_healing.db.base import Base
from doc_healing.monitoring.memory import log_memory_usage

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
    
    # Log memory metrics
    log_memory_usage(context="server_startup")


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": "Self-Healing Documentation Engine API", "version": "0.1.0"}


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(content={"status": "healthy"}, status_code=200)


# Webhook Endpoints

@app.post("/webhooks/github", response_model=TaskResponse)
async def handle_github_webhook(payload: Dict[str, Any]) -> TaskResponse:
    """Handle GitHub webhook events.
    
    Enqueues a task to process the GitHub webhook payload.
    
    Args:
        payload: The webhook payload from GitHub
        
    Returns:
        TaskResponse with task_id and status
        
    Raises:
        HTTPException: If enqueuing fails
    """
    try:
        # Lazy import to avoid Windows fork context issues
        from doc_healing.queue.factory import get_queue_backend
        from doc_healing.workers.tasks import process_github_webhook
        
        queue = get_queue_backend()
        task = queue.enqueue("webhooks", process_github_webhook, payload)
        logger.info(f"Enqueued GitHub webhook task: {task.id}")
        return TaskResponse(
            task_id=task.id,
            status="queued",
            queue_name="webhooks"
        )
    except Exception as e:
        logger.error(f"Failed to enqueue GitHub webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue webhook: {str(e)}")


@app.post("/webhooks/gitlab", response_model=TaskResponse)
async def handle_gitlab_webhook(payload: Dict[str, Any]) -> TaskResponse:
    """Handle GitLab webhook events.
    
    Enqueues a task to process the GitLab webhook payload.
    
    Args:
        payload: The webhook payload from GitLab
        
    Returns:
        TaskResponse with task_id and status
        
    Raises:
        HTTPException: If enqueuing fails
    """
    try:
        # Lazy import to avoid Windows fork context issues
        from doc_healing.queue.factory import get_queue_backend
        from doc_healing.workers.tasks import process_gitlab_webhook
        
        queue = get_queue_backend()
        task = queue.enqueue("webhooks", process_gitlab_webhook, payload)
        logger.info(f"Enqueued GitLab webhook task: {task.id}")
        return TaskResponse(
            task_id=task.id,
            status="queued",
            queue_name="webhooks"
        )
    except Exception as e:
        logger.error(f"Failed to enqueue GitLab webhook: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue webhook: {str(e)}")


# Validation Endpoints

@app.post("/validate/snippet", response_model=TaskResponse)
async def validate_snippet(request: ValidationRequest) -> TaskResponse:
    """Validate a code snippet.
    
    Enqueues a task to validate a code snippet from documentation.
    
    Args:
        request: ValidationRequest with file_path, snippet_id, code, and language
        
    Returns:
        TaskResponse with task_id and status
        
    Raises:
        HTTPException: If enqueuing fails
    """
    try:
        # Lazy import to avoid Windows fork context issues
        from doc_healing.queue.factory import get_queue_backend
        from doc_healing.workers.tasks import validate_code_snippet
        
        queue = get_queue_backend()
        task = queue.enqueue(
            "validation",
            validate_code_snippet,
            request.file_path,
            request.snippet_id,
            request.code,
            request.language
        )
        logger.info(f"Enqueued code snippet validation task: {task.id}")
        return TaskResponse(
            task_id=task.id,
            status="queued",
            queue_name="validation"
        )
    except Exception as e:
        logger.error(f"Failed to enqueue validation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue validation: {str(e)}")


@app.post("/validate/file", response_model=TaskResponse)
async def validate_file(request: FileValidationRequest) -> TaskResponse:
    """Validate all code snippets in a documentation file.
    
    Enqueues a task to validate all code snippets in a documentation file.
    
    Args:
        request: FileValidationRequest with file_path and content
        
    Returns:
        TaskResponse with task_id and status
        
    Raises:
        HTTPException: If enqueuing fails
    """
    try:
        # Lazy import to avoid Windows fork context issues
        from doc_healing.queue.factory import get_queue_backend
        from doc_healing.workers.tasks import validate_documentation_file
        
        queue = get_queue_backend()
        task = queue.enqueue(
            "validation",
            validate_documentation_file,
            request.file_path,
            request.content
        )
        logger.info(f"Enqueued file validation task: {task.id}")
        return TaskResponse(
            task_id=task.id,
            status="queued",
            queue_name="validation"
        )
    except Exception as e:
        logger.error(f"Failed to enqueue file validation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue validation: {str(e)}")


# Healing Endpoints

@app.post("/heal/snippet", response_model=TaskResponse)
async def heal_snippet(request: HealingRequest) -> TaskResponse:
    """Heal a code snippet that failed validation.
    
    Enqueues a task to automatically fix a code snippet.
    
    Args:
        request: HealingRequest with file_path, snippet_id, code, language, and errors
        
    Returns:
        TaskResponse with task_id and status
        
    Raises:
        HTTPException: If enqueuing fails
    """
    try:
        # Lazy import to avoid Windows fork context issues
        from doc_healing.queue.factory import get_queue_backend
        from doc_healing.workers.tasks import heal_code_snippet
        
        queue = get_queue_backend()
        task = queue.enqueue(
            "healing",
            heal_code_snippet,
            request.file_path,
            request.snippet_id,
            request.code,
            request.language,
            request.errors
        )
        logger.info(f"Enqueued code snippet healing task: {task.id}")
        return TaskResponse(
            task_id=task.id,
            status="queued",
            queue_name="healing"
        )
    except Exception as e:
        logger.error(f"Failed to enqueue healing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue healing: {str(e)}")


@app.post("/heal/file", response_model=TaskResponse)
async def heal_file(request: FileHealingRequest) -> TaskResponse:
    """Heal all invalid code snippets in a documentation file.
    
    Enqueues a task to automatically fix all invalid code snippets in a file.
    
    Args:
        request: FileHealingRequest with file_path and validation_results
        
    Returns:
        TaskResponse with task_id and status
        
    Raises:
        HTTPException: If enqueuing fails
    """
    try:
        # Lazy import to avoid Windows fork context issues
        from doc_healing.queue.factory import get_queue_backend
        from doc_healing.workers.tasks import heal_documentation_file
        
        queue = get_queue_backend()
        task = queue.enqueue(
            "healing",
            heal_documentation_file,
            request.file_path,
            request.validation_results
        )
        logger.info(f"Enqueued file healing task: {task.id}")
        return TaskResponse(
            task_id=task.id,
            status="queued",
            queue_name="healing"
        )
    except Exception as e:
        logger.error(f"Failed to enqueue file healing: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue healing: {str(e)}")

