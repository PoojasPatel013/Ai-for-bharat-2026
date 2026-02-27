# Design Document: Lightweight Deployment

## Overview

This design transforms the Self-Healing Documentation Engine from a 5-container microservices architecture into a flexible deployment system that supports both full production mode and a lightweight development mode optimized for 8GB RAM laptops. The lightweight mode reduces the container count from 5 to 0-2 containers while maintaining core functionality through architectural simplifications: SQLite replaces PostgreSQL, an in-memory queue replaces Redis, and worker processes are consolidated into a single unified worker or run synchronously.

The design introduces a configuration-driven approach where deployment mode is controlled via environment variables, allowing developers to seamlessly switch between lightweight and full modes. This enables rapid local development without sacrificing the ability to test production-like configurations.

## Architecture

### Current Architecture (Full Mode)

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│  API (8000) │────▶│  PostgreSQL  │
└──────┬──────┘     │   (5432)     │
       │            └──────────────┘
       │
       ▼
┌─────────────┐
│    Redis    │
│   (6379)    │
└──────┬──────┘
       │
       ├──────────┬──────────┬──────────┐
       ▼          ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Worker:  │ │ Worker:  │ │ Worker:  │
│ Webhooks │ │Validation│ │ Healing  │
└──────────┘ └──────────┘ └──────────┘
```

**Resource Usage:**
- PostgreSQL: ~200-300MB
- Redis: ~50-100MB
- API: ~150-200MB
- 3 Workers: ~150-200MB each (450-600MB total)
- **Total: ~850MB-1.2GB**

### Lightweight Architecture (Development Mode)

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────┐
│      API Process            │
│  ┌──────────────────────┐   │
│  │   SQLite (file)      │   │
│  └──────────────────────┘   │
│  ┌──────────────────────┐   │
│  │  In-Memory Queue     │   │
│  └──────────────────────┘   │
│  ┌──────────────────────┐   │
│  │  Unified Worker      │   │
│  │  (threaded)          │   │
│  └──────────────────────┘   │
└─────────────────────────────┘
```

**Resource Usage:**
- Single Python process: ~200-400MB
- **Total: ~200-400MB** (75% reduction)

### Hybrid Architecture (Lightweight + Docker)

For developers who want some isolation but still need low resource usage:

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│  API        │────▶│  PostgreSQL  │
│  Container  │     │  (Alpine)    │
└─────────────┘     └──────────────┘
     │
     └─ Unified Worker (in-process)
     └─ SQLite option available
```

**Resource Usage:**
- PostgreSQL Alpine: ~50-100MB
- API Container: ~150-200MB
- **Total: ~200-300MB** (70% reduction)

## Components and Interfaces

### 1. Configuration System

**Purpose:** Centralize deployment mode configuration and feature toggles.

**Implementation:**

```python
# src/doc_healing/config.py

from enum import Enum
from pydantic_settings import BaseSettings

class DeploymentMode(str, Enum):
    FULL = "full"
    LIGHTWEIGHT = "lightweight"
    HYBRID = "hybrid"

class DatabaseBackend(str, Enum):
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"

class QueueBackend(str, Enum):
    REDIS = "redis"
    MEMORY = "memory"

class Settings(BaseSettings):
    # Deployment configuration
    deployment_mode: DeploymentMode = DeploymentMode.FULL
    
    # Database configuration
    database_backend: DatabaseBackend = DatabaseBackend.POSTGRESQL
    database_url: str = "postgresql://postgres:postgres@localhost:5432/doc_healing"
    sqlite_path: str = "./data/doc_healing.db"
    
    # Queue configuration
    queue_backend: QueueBackend = QueueBackend.REDIS
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    
    # Worker configuration
    unified_worker: bool = False
    worker_threads: int = 4
    sync_processing: bool = False
    
    # API configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    class Config:
        env_file = ".env"
        env_prefix = "DOC_HEALING_"

def get_settings() -> Settings:
    return Settings()
```

### 2. Database Abstraction Layer

**Purpose:** Provide a unified interface that works with both PostgreSQL and SQLite.

**Implementation:**

```python
# src/doc_healing/db/connection.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from doc_healing.config import get_settings, DatabaseBackend

def get_database_url() -> str:
    settings = get_settings()
    
    if settings.database_backend == DatabaseBackend.SQLITE:
        return f"sqlite:///{settings.sqlite_path}"
    else:
        return settings.database_url

def create_db_engine():
    url = get_database_url()
    settings = get_settings()
    
    if settings.database_backend == DatabaseBackend.SQLITE:
        # SQLite-specific configuration
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True
        )
    else:
        # PostgreSQL configuration
        engine = create_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True
        )
    
    return engine

engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 3. Queue Abstraction Layer

**Purpose:** Provide a unified interface for task queuing that works with both Redis and in-memory implementations.

**Implementation:**

```python
# src/doc_healing/queue/base.py

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional
from dataclasses import dataclass

@dataclass
class Task:
    id: str
    func_name: str
    args: tuple
    kwargs: dict
    queue_name: str

class QueueBackend(ABC):
    @abstractmethod
    def enqueue(self, queue_name: str, func: Callable, *args, **kwargs) -> Task:
        """Enqueue a task for processing"""
        pass
    
    @abstractmethod
    def get_task(self, queue_name: str, timeout: Optional[int] = None) -> Optional[Task]:
        """Get next task from queue"""
        pass
    
    @abstractmethod
    def mark_complete(self, task: Task) -> None:
        """Mark task as completed"""
        pass
    
    @abstractmethod
    def mark_failed(self, task: Task, error: Exception) -> None:
        """Mark task as failed"""
        pass

# src/doc_healing/queue/redis_backend.py

import redis
from rq import Queue
from doc_healing.queue.base import QueueBackend, Task
from doc_healing.config import get_settings

class RedisQueueBackend(QueueBackend):
    def __init__(self):
        settings = get_settings()
        self.redis_conn = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db
        )
        self.queues = {}
    
    def _get_queue(self, queue_name: str) -> Queue:
        if queue_name not in self.queues:
            self.queues[queue_name] = Queue(queue_name, connection=self.redis_conn)
        return self.queues[queue_name]
    
    def enqueue(self, queue_name: str, func: Callable, *args, **kwargs) -> Task:
        queue = self._get_queue(queue_name)
        job = queue.enqueue(func, *args, **kwargs)
        return Task(
            id=job.id,
            func_name=func.__name__,
            args=args,
            kwargs=kwargs,
            queue_name=queue_name
        )
    
    # ... other methods

# src/doc_healing/queue/memory_backend.py

import queue
import threading
import uuid
from typing import Dict
from doc_healing.queue.base import QueueBackend, Task
from doc_healing.config import get_settings

class MemoryQueueBackend(QueueBackend):
    def __init__(self):
        self.queues: Dict[str, queue.Queue] = {}
        self.tasks: Dict[str, Task] = {}
        self.lock = threading.Lock()
        settings = get_settings()
        
        # Start worker threads if not in sync mode
        if not settings.sync_processing:
            self._start_workers()
    
    def _get_queue(self, queue_name: str) -> queue.Queue:
        if queue_name not in self.queues:
            self.queues[queue_name] = queue.Queue()
        return self.queues[queue_name]
    
    def enqueue(self, queue_name: str, func: Callable, *args, **kwargs) -> Task:
        task = Task(
            id=str(uuid.uuid4()),
            func_name=func.__name__,
            args=args,
            kwargs=kwargs,
            queue_name=queue_name
        )
        
        settings = get_settings()
        if settings.sync_processing:
            # Execute immediately in sync mode
            try:
                func(*args, **kwargs)
                self.mark_complete(task)
            except Exception as e:
                self.mark_failed(task, e)
        else:
            # Queue for async processing
            q = self._get_queue(queue_name)
            with self.lock:
                self.tasks[task.id] = task
            q.put((func, args, kwargs, task))
        
        return task
    
    def _start_workers(self):
        settings = get_settings()
        for i in range(settings.worker_threads):
            thread = threading.Thread(target=self._worker_loop, daemon=True)
            thread.start()
    
    def _worker_loop(self):
        while True:
            # Process tasks from all queues
            for queue_name, q in self.queues.items():
                try:
                    func, args, kwargs, task = q.get(timeout=1)
                    try:
                        func(*args, **kwargs)
                        self.mark_complete(task)
                    except Exception as e:
                        self.mark_failed(task, e)
                except queue.Empty:
                    continue
    
    # ... other methods

# src/doc_healing/queue/factory.py

from doc_healing.queue.base import QueueBackend
from doc_healing.queue.redis_backend import RedisQueueBackend
from doc_healing.queue.memory_backend import MemoryQueueBackend
from doc_healing.config import get_settings, QueueBackend as QueueBackendEnum

_queue_backend: Optional[QueueBackend] = None

def get_queue_backend() -> QueueBackend:
    global _queue_backend
    if _queue_backend is None:
        settings = get_settings()
        if settings.queue_backend == QueueBackendEnum.REDIS:
            _queue_backend = RedisQueueBackend()
        else:
            _queue_backend = MemoryQueueBackend()
    return _queue_backend
```

### 4. Unified Worker Process

**Purpose:** Consolidate webhook, validation, and healing workers into a single process.

**Implementation:**

```python
# src/doc_healing/workers/unified.py

import logging
from doc_healing.queue.factory import get_queue_backend
from doc_healing.config import get_settings

logger = logging.getLogger(__name__)

class UnifiedWorker:
    def __init__(self):
        self.queue_backend = get_queue_backend()
        self.settings = get_settings()
        self.running = False
    
    def start(self):
        """Start the unified worker"""
        self.running = True
        logger.info("Starting unified worker")
        
        if self.settings.sync_processing:
            logger.info("Running in synchronous mode - tasks execute immediately")
            # In sync mode, tasks are executed when enqueued
            # This method just keeps the process alive
            import time
            while self.running:
                time.sleep(1)
        else:
            logger.info(f"Running with {self.settings.worker_threads} worker threads")
            # Worker threads are already started by MemoryQueueBackend
            # This method just keeps the process alive
            import time
            while self.running:
                time.sleep(1)
    
    def stop(self):
        """Stop the unified worker"""
        self.running = False
        logger.info("Stopping unified worker")

def main():
    worker = UnifiedWorker()
    try:
        worker.start()
    except KeyboardInterrupt:
        worker.stop()

if __name__ == "__main__":
    main()
```

### 5. API Integration

**Purpose:** Update API to use the abstraction layers and support lightweight mode.

**Implementation:**

```python
# src/doc_healing/api/main.py

from fastapi import FastAPI, Depends
from doc_healing.config import get_settings, DeploymentMode
from doc_healing.db.connection import get_db
from doc_healing.queue.factory import get_queue_backend

app = FastAPI(title="Doc Healing API")

@app.on_event("startup")
async def startup_event():
    settings = get_settings()
    logger.info(f"Starting API in {settings.deployment_mode} mode")
    logger.info(f"Database: {settings.database_backend}")
    logger.info(f"Queue: {settings.queue_backend}")
    
    # Initialize database
    from doc_healing.db.models import Base
    from doc_healing.db.connection import engine
    Base.metadata.create_all(bind=engine)

@app.post("/webhooks/github")
async def handle_github_webhook(payload: dict):
    queue = get_queue_backend()
    from doc_healing.workers.tasks import process_github_webhook
    task = queue.enqueue("webhooks", process_github_webhook, payload)
    return {"task_id": task.id, "status": "queued"}

# ... other endpoints
```

## Data Models

### Configuration Models

No changes to existing SQLAlchemy models are required. The models are already compatible with both PostgreSQL and SQLite with minor considerations:

**Compatibility Notes:**
- Avoid PostgreSQL-specific types (JSONB → JSON)
- Use SQLAlchemy's generic types (String, Integer, DateTime)
- Avoid database-specific features in migrations

### Environment Configuration

```bash
# .env.lightweight

# Deployment mode
DOC_HEALING_DEPLOYMENT_MODE=lightweight

# Database
DOC_HEALING_DATABASE_BACKEND=sqlite
DOC_HEALING_SQLITE_PATH=./data/doc_healing.db

# Queue
DOC_HEALING_QUEUE_BACKEND=memory
DOC_HEALING_SYNC_PROCESSING=false
DOC_HEALING_WORKER_THREADS=2

# API
DOC_HEALING_API_HOST=0.0.0.0
DOC_HEALING_API_PORT=8000
```

```bash
# .env.full

# Deployment mode
DOC_HEALING_DEPLOYMENT_MODE=full

# Database
DOC_HEALING_DATABASE_BACKEND=postgresql
DOC_HEALING_DATABASE_URL=postgresql://postgres:postgres@postgres:5432/doc_healing

# Queue
DOC_HEALING_QUEUE_BACKEND=redis
DOC_HEALING_REDIS_HOST=redis
DOC_HEALING_REDIS_PORT=6379

# API
DOC_HEALING_API_HOST=0.0.0.0
DOC_HEALING_API_PORT=8000
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Task Processing Across All Types

*For any* set of tasks containing webhook, validation, and healing task types, when processed by the unified worker, all tasks should complete successfully regardless of their type.

**Validates: Requirements 1.2**

### Property 2: Database File Location Configuration

*For any* valid file system path configured as the SQLite database location, when the system starts with SQLite backend, the database file should be created at exactly that configured path.

**Validates: Requirements 2.2**

### Property 3: Migration Compatibility Across Databases

*For any* Alembic migration in the migration history, when applied to both PostgreSQL and SQLite databases, both databases should reach functionally equivalent schema states that support the same operations.

**Validates: Requirements 2.3, 2.4**

### Property 4: Task Execution Mode Consistency

*For any* task enqueued in the in-memory queue, when sync_processing is enabled, the task should execute immediately before enqueue returns; when sync_processing is disabled, the task should execute asynchronously via worker threads.

**Validates: Requirements 3.2**

### Property 5: Queue Interface Consistency

*For any* task function and arguments, when enqueued using either Redis or memory queue backend, the task should execute with the same behavior and produce the same results.

**Validates: Requirements 3.3**

### Property 6: Queue Persistence Behavior

*For any* task enqueued before application restart, when using Redis backend, the task should persist and be available after restart; when using memory backend, the task should not persist after restart.

**Validates: Requirements 3.4**

### Property 7: Environment Variable Configuration

*For any* valid deployment mode setting (full, lightweight, hybrid) configured via environment variable, when the system starts, it should initialize with the corresponding database backend, queue backend, and worker configuration.

**Validates: Requirements 4.2, 8.1**

### Property 8: Webhook Endpoint Availability

*For any* valid webhook payload, when sent to the webhook endpoint in lightweight mode, the system should accept the request, enqueue it for processing, and return a success response.

**Validates: Requirements 5.1**

### Property 9: Validation Functionality

*For any* valid code validation request, when submitted in lightweight mode, the system should validate the code and return validation results equivalent to full mode.

**Validates: Requirements 5.2**

### Property 10: Healing Functionality

*For any* valid healing request, when submitted in lightweight mode, the system should process the healing task and generate corrections equivalent to full mode.

**Validates: Requirements 5.3**

### Property 11: Memory Metrics Logging

*For any* operation performed by the system, when memory monitoring is enabled, memory consumption metrics should appear in the application logs at regular intervals.

**Validates: Requirements 6.4**

## Error Handling

### Database Connection Errors

**SQLite-specific errors:**
- File permission errors when creating database file
- Disk space errors when writing to database
- Concurrent access errors (mitigated by check_same_thread=False)

**Handling:**
```python
try:
    engine = create_db_engine()
except OperationalError as e:
    if "unable to open database file" in str(e):
        logger.error(f"Cannot create SQLite database at {settings.sqlite_path}")
        logger.error("Check directory permissions and disk space")
        raise
    raise
```

### Queue Backend Errors

**Memory queue errors:**
- Thread exhaustion when too many concurrent tasks
- Memory exhaustion when queue grows too large

**Handling:**
```python
class MemoryQueueBackend:
    def enqueue(self, queue_name: str, func: Callable, *args, **kwargs) -> Task:
        q = self._get_queue(queue_name)
        if q.qsize() > MAX_QUEUE_SIZE:
            raise QueueFullError(f"Queue {queue_name} is full")
        # ... rest of implementation
```

### Configuration Errors

**Invalid configuration combinations:**
- Lightweight mode with Redis backend (warning, not error)
- Full mode with SQLite backend (warning, not error)

**Handling:**
```python
def validate_configuration(settings: Settings):
    if settings.deployment_mode == DeploymentMode.LIGHTWEIGHT:
        if settings.queue_backend == QueueBackend.REDIS:
            logger.warning("Lightweight mode typically uses memory queue, but Redis is configured")
        if settings.database_backend == DatabaseBackend.POSTGRESQL:
            logger.warning("Lightweight mode typically uses SQLite, but PostgreSQL is configured")
```

### Migration Errors

**Database-specific migration issues:**
- PostgreSQL-specific syntax in migrations
- SQLite limitations (no DROP COLUMN in older versions)

**Handling:**
- Use SQLAlchemy's batch operations for SQLite
- Test migrations against both databases in CI
- Provide rollback procedures

## Testing Strategy

### Dual Testing Approach

This feature requires both unit tests and property-based tests:

**Unit Tests** focus on:
- Specific configuration examples (lightweight mode with SQLite + memory queue)
- Edge cases (empty queue, missing database file)
- Error conditions (invalid configuration, connection failures)
- Integration points (API startup with different backends)

**Property Tests** focus on:
- Universal properties across all configurations
- Task processing consistency across queue backends
- Database operation equivalence across PostgreSQL and SQLite
- Configuration behavior across all valid environment variable combinations

### Property-Based Testing Configuration

**Library:** Hypothesis (Python)

**Configuration:**
- Minimum 100 iterations per property test
- Each test tagged with: `# Feature: lightweight-deployment, Property N: [property text]`
- Custom generators for:
  - Valid configuration combinations
  - Task payloads (webhook, validation, healing)
  - Database operations (CRUD operations)
  - File system paths

**Example Property Test:**

```python
from hypothesis import given, strategies as st
import pytest

@given(
    task_type=st.sampled_from(['webhook', 'validation', 'healing']),
    payload=st.dictionaries(st.text(), st.text())
)
@pytest.mark.property
def test_task_processing_across_types(task_type, payload):
    """
    Feature: lightweight-deployment, Property 1: Task Processing Across All Types
    
    For any set of tasks containing webhook, validation, and healing task types,
    when processed by the unified worker, all tasks should complete successfully.
    """
    # Test implementation
    pass
```

### Unit Test Examples

```python
def test_lightweight_mode_uses_sqlite():
    """Test that lightweight mode configuration uses SQLite"""
    os.environ['DOC_HEALING_DEPLOYMENT_MODE'] = 'lightweight'
    os.environ['DOC_HEALING_DATABASE_BACKEND'] = 'sqlite'
    
    settings = get_settings()
    assert settings.database_backend == DatabaseBackend.SQLITE
    
    url = get_database_url()
    assert url.startswith('sqlite:///')

def test_memory_queue_sync_execution():
    """Test that sync mode executes tasks immediately"""
    os.environ['DOC_HEALING_SYNC_PROCESSING'] = 'true'
    
    executed = []
    def test_task(value):
        executed.append(value)
    
    queue = MemoryQueueBackend()
    queue.enqueue('test', test_task, 'test_value')
    
    # In sync mode, task should execute immediately
    assert 'test_value' in executed

def test_api_starts_without_docker():
    """Test that API can start in lightweight mode without Docker"""
    os.environ['DOC_HEALING_DEPLOYMENT_MODE'] = 'lightweight'
    
    # Start API
    # Verify it responds to health check
    # Verify no Docker containers are running
    pass
```

### Integration Testing

**Test Scenarios:**
1. Full workflow in lightweight mode (webhook → validation → healing)
2. Mode switching (full → lightweight → full)
3. Data migration (SQLite → PostgreSQL)
4. Concurrent task processing with memory queue
5. API endpoint functionality across both modes

### Performance Testing

**Memory Usage Validation:**
- Measure baseline memory usage in full mode
- Measure memory usage in lightweight mode
- Verify lightweight mode uses < 50% of full mode memory
- Monitor memory over time to detect leaks

**Load Testing:**
- Test memory queue with varying task loads
- Verify graceful degradation under high load
- Test thread pool exhaustion scenarios

### Deployment Testing

**Docker Compose Validation:**
- Test docker-compose.lightweight.yml starts successfully
- Verify container count in lightweight mode
- Test docker-compose.full.yml for comparison

**Environment Configuration:**
- Test all environment variable combinations
- Verify configuration validation and warnings
- Test .env file loading
