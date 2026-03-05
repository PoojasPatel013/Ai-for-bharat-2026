"""Main FastAPI application."""

import logging
import os
from pathlib import Path
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
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

description = """
🏜️ **OASIS — Self-Healing Documentation Engine**

A GitHub/GitLab bot that automatically validates and heals broken code snippets in your documentation using hybrid analysis (static + AI).

---

## How It Works

1. **Webhook** — GitHub sends a PR event to OASIS
2. **Analysis** — OASIS extracts code from docs, runs static analysis (AST, compile, heuristics)
3. **AI Healing** — Amazon Bedrock (Nova Pro + Claude 4 Sonnet) generates intelligent fix suggestions
4. **PR Comment** — OASIS posts a detailed report with errors and fixes

## Supported Languages

Python, JavaScript, TypeScript, Java, Go, Ruby, Rust, C/C++, PHP, Bash, and more.

## Getting Started

1. Add a `.doc-healing.yml` to your repo root
2. Create a GitHub webhook pointing to `/webhooks/github`
3. Open a PR — OASIS analyzes it automatically

## Links

- **[Landing Page](/)** — Full documentation with guide, architecture, and live demo
"""

tags_metadata = [
    {"name": "Webhooks", "description": "Receive and process GitHub/GitLab webhook events"},
    {"name": "Validation", "description": "Validate code snippets and documentation files"},
    {"name": "Healing", "description": "Auto-fix broken code using static analysis + Bedrock AI"},
    {"name": "Health", "description": "Service health and status endpoints"},
]

app = FastAPI(
    title="🏜️ OASIS — Self-Healing Documentation Engine",
    description=description,
    version="0.1.0",
    openapi_tags=tags_metadata,
)

# Mount static files (CSS, JS)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


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


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the OASIS landing page."""
    index_path = Path(__file__).parent / "static" / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"), status_code=200)
    return HTMLResponse(content="<h1>OASIS — Self-Healing Documentation Engine</h1><p>Static files not found.</p>", status_code=200)


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(content={"status": "healthy"}, status_code=200)


# Webhook Endpoints

@app.post("/webhooks/github", response_model=TaskResponse)
async def handle_github_webhook(request: Request) -> TaskResponse:
    """Handle GitHub webhook events with signature verification.
    
    Verifies the X-Hub-Signature-256 header, then enqueues a task
    to process the GitHub webhook payload.
    """
    import hashlib
    import hmac
    
    settings = get_settings()
    body = await request.body()
    
    # Verify webhook signature if secret is configured
    webhook_secret = settings.github_webhook_secret
    if webhook_secret:
        signature = request.headers.get("X-Hub-Signature-256", "")
        expected = "sha256=" + hmac.new(
            webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning("Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    import json as json_mod
    payload = json_mod.loads(body)
    
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


# Live Analysis Endpoint (synchronous — used by the landing page demo)

class AnalyzeRequest(BaseModel):
    """Request model for real-time code analysis."""
    code: str
    language: str = "unknown"

class AnalyzeResponse(BaseModel):
    """Response model for real-time code analysis."""
    language: str
    has_issues: bool
    errors: list

@app.post("/api/analyze", response_model=AnalyzeResponse, tags=["Validation"])
async def analyze_code_endpoint(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a code snippet in real-time using OASIS static analyzers.
    
    This endpoint runs the same static analysis pipeline used during
    PR processing, but returns results synchronously. Used by the 
    landing page live demo.
    """
    from doc_healing.llm.static_analyzer import analyze_code, detect_language
    
    code = request.code.strip()
    language = request.language.strip().lower()
    
    if not code:
        return AnalyzeResponse(language="unknown", has_issues=False, errors=[])
    
    # Auto-detect language if needed
    if language in ("unknown", "auto", ""):
        language = detect_language(code)
    
    # Run the real static analyzer
    result = analyze_code(code, language)
    
    errors = result.get("errors", [])
    
    return AnalyzeResponse(
        language=language,
        has_issues=len(errors) > 0,
        errors=errors
    )
