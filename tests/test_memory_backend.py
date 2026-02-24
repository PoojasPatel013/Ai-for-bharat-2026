"""Tests for in-memory queue backend implementation."""

import sys
import time
import threading
import pytest
from unittest.mock import patch, MagicMock

# Mock the rq module before importing anything else
sys.modules['rq'] = MagicMock()
sys.modules['rq.job'] = MagicMock()

from doc_healing.queue.memory_backend import MemoryQueueBackend
from doc_healing.queue.base import Task


@pytest.fixture
def sync_backend():
    """Create a MemoryQueueBackend in synchronous mode."""
    with patch('doc_healing.queue.memory_backend.get_settings') as mock_settings:
        settings = MagicMock()
        settings.sync_processing = True
        settings.worker_threads = 2
        mock_settings.return_value = settings
        
        backend = MemoryQueueBackend()
        yield backend


@pytest.fixture
def async_backend():
    """Create a MemoryQueueBackend in asynchronous mode."""
    with patch('doc_healing.queue.memory_backend.get_settings') as mock_settings:
        settings = MagicMock()
        settings.sync_processing = False
        settings.worker_threads = 2
        mock_settings.return_value = settings
        
        backend = MemoryQueueBackend()
        yield backend
        # Cleanup
        backend.shutdown()


def test_memory_backend_initialization_sync():
    """Test that memory backend initializes correctly in sync mode."""
    with patch('doc_healing.queue.memory_backend.get_settings') as mock_settings:
        settings = MagicMock()
        settings.sync_processing = True
        settings.worker_threads = 2
        mock_settings.return_value = settings
        
        backend = MemoryQueueBackend()
        
        assert backend.sync_processing is True
        assert backend.worker_threads == 2
        assert backend.queues == {}
        assert backend.tasks == {}
        assert len(backend.workers) == 0  # No workers in sync mode


def test_memory_backend_initialization_async():
    """Test that memory backend initializes correctly in async mode."""
    with patch('doc_healing.queue.memory_backend.get_settings') as mock_settings:
        settings = MagicMock()
        settings.sync_processing = False
        settings.worker_threads = 3
        mock_settings.return_value = settings
        
        backend = MemoryQueueBackend()
        
        assert backend.sync_processing is False
        assert backend.worker_threads == 3
        assert backend.running is True
        assert len(backend.workers) == 3  # Workers started in async mode
        
        # Cleanup
        backend.shutdown()


def test_enqueue_sync_executes_immediately(sync_backend):
    """Test that enqueue executes tasks immediately in sync mode."""
    executed = []
    
    def test_func(value):
        executed.append(value)
    
    task = sync_backend.enqueue("test_queue", test_func, "test_value")
    
    # Task should execute immediately
    assert "test_value" in executed
    assert task.func_name == "test_func"
    assert task.args == ("test_value",)
    assert task.queue_name == "test_queue"
    # Task should be removed after completion
    assert task.id not in sync_backend.tasks


def test_enqueue_sync_raises_on_error(sync_backend):
    """Test that enqueue raises exception when task fails in sync mode."""
    def failing_func():
        raise ValueError("Test error")
    
    with pytest.raises(ValueError, match="Test error"):
        sync_backend.enqueue("test_queue", failing_func)


def test_enqueue_async_queues_task(async_backend):
    """Test that enqueue queues tasks in async mode."""
    executed = []
    
    def test_func(value):
        executed.append(value)
    
    task = async_backend.enqueue("test_queue", test_func, "async_value")
    
    # Task should be queued, not executed immediately
    assert task.func_name == "test_func"
    assert task.args == ("async_value",)
    assert task.queue_name == "test_queue"
    
    # Wait for worker to process
    time.sleep(0.5)
    
    # Task should be executed by worker
    assert "async_value" in executed
    # Task should be removed after completion
    assert task.id not in async_backend.tasks


def test_enqueue_async_handles_errors(async_backend):
    """Test that async mode handles task errors gracefully."""
    def failing_func():
        raise ValueError("Async error")
    
    # Should not raise immediately
    task = async_backend.enqueue("test_queue", failing_func)
    
    # Wait for worker to process
    time.sleep(0.5)
    
    # Task should be removed even after failure
    assert task.id not in async_backend.tasks


def test_get_queue_creates_queue_once(sync_backend):
    """Test that _get_queue creates a queue only once per queue name."""
    queue1 = sync_backend._get_queue("test_queue")
    queue2 = sync_backend._get_queue("test_queue")
    
    assert queue1 is queue2
    assert "test_queue" in sync_backend.queues


def test_get_queue_creates_different_queues(sync_backend):
    """Test that _get_queue creates separate queues for different names."""
    queue1 = sync_backend._get_queue("webhooks")
    queue2 = sync_backend._get_queue("validation")
    
    assert queue1 is not queue2
    assert "webhooks" in sync_backend.queues
    assert "validation" in sync_backend.queues


def test_get_task_returns_none_for_empty_queue(sync_backend):
    """Test that get_task returns None when queue is empty."""
    task = sync_backend.get_task("empty_queue", timeout=0)
    assert task is None


def test_get_task_returns_queued_task(async_backend):
    """Test that get_task returns a queued task without removing it."""
    def test_func(value):
        time.sleep(1)  # Slow task to keep it in queue
    
    # Enqueue a task
    original_task = async_backend.enqueue("test_queue", test_func, "value")
    
    # Get the task (should not remove it)
    retrieved_task = async_backend.get_task("test_queue", timeout=1)
    
    assert retrieved_task is not None
    assert retrieved_task.id == original_task.id
    assert retrieved_task.func_name == "test_func"
    
    # Cleanup
    time.sleep(1.5)


def test_get_task_with_timeout(async_backend):
    """Test that get_task respects timeout parameter."""
    # Try to get from empty queue with short timeout
    start_time = time.time()
    task = async_backend.get_task("empty_queue", timeout=0.2)
    elapsed = time.time() - start_time
    
    assert task is None
    assert elapsed < 0.5  # Should timeout quickly


def test_mark_complete_removes_task(sync_backend):
    """Test that mark_complete removes task from tracking."""
    task = Task(
        id="test-123",
        func_name="test_func",
        args=(),
        kwargs={},
        queue_name="test_queue"
    )
    
    # Add task to tracking
    sync_backend.tasks[task.id] = task
    
    # Mark complete
    sync_backend.mark_complete(task)
    
    # Task should be removed
    assert task.id not in sync_backend.tasks


def test_mark_failed_removes_task(sync_backend):
    """Test that mark_failed removes task from tracking."""
    task = Task(
        id="test-456",
        func_name="test_func",
        args=(),
        kwargs={},
        queue_name="test_queue"
    )
    
    # Add task to tracking
    sync_backend.tasks[task.id] = task
    
    # Mark failed
    error = Exception("Test error")
    sync_backend.mark_failed(task, error)
    
    # Task should be removed
    assert task.id not in sync_backend.tasks


def test_multiple_tasks_async(async_backend):
    """Test that multiple tasks are processed correctly in async mode."""
    results = []
    lock = threading.Lock()
    
    def test_func(value):
        with lock:
            results.append(value)
    
    # Enqueue multiple tasks
    tasks = []
    for i in range(5):
        task = async_backend.enqueue("test_queue", test_func, i)
        tasks.append(task)
    
    # Wait for all tasks to complete
    time.sleep(1.0)
    
    # All tasks should be executed
    assert len(results) == 5
    assert set(results) == {0, 1, 2, 3, 4}
    
    # All tasks should be removed from tracking
    for task in tasks:
        assert task.id not in async_backend.tasks


def test_multiple_queues_async(async_backend):
    """Test that tasks from multiple queues are processed."""
    results = {"webhooks": [], "validation": []}
    lock = threading.Lock()
    
    def webhook_func(value):
        with lock:
            results["webhooks"].append(value)
    
    def validation_func(value):
        with lock:
            results["validation"].append(value)
    
    # Enqueue to different queues
    async_backend.enqueue("webhooks", webhook_func, "webhook1")
    async_backend.enqueue("validation", validation_func, "validation1")
    async_backend.enqueue("webhooks", webhook_func, "webhook2")
    
    # Wait for processing
    time.sleep(1.0)
    
    # All tasks should be executed
    assert len(results["webhooks"]) == 2
    assert len(results["validation"]) == 1
    assert "webhook1" in results["webhooks"]
    assert "webhook2" in results["webhooks"]
    assert "validation1" in results["validation"]


def test_shutdown_stops_workers(async_backend):
    """Test that shutdown stops all worker threads."""
    assert async_backend.running is True
    assert len(async_backend.workers) > 0
    
    # Get initial worker threads
    workers = async_backend.workers.copy()
    
    # Shutdown
    async_backend.shutdown()
    
    # Running flag should be False
    assert async_backend.running is False
    
    # Wait a bit for threads to stop
    time.sleep(0.5)
    
    # Workers should be stopped
    for worker in workers:
        assert not worker.is_alive()


def test_task_with_kwargs(sync_backend):
    """Test that tasks with keyword arguments work correctly."""
    result = {}
    
    def test_func(arg1, arg2, kwarg1=None, kwarg2=None):
        result["arg1"] = arg1
        result["arg2"] = arg2
        result["kwarg1"] = kwarg1
        result["kwarg2"] = kwarg2
    
    task = sync_backend.enqueue(
        "test_queue",
        test_func,
        "value1",
        "value2",
        kwarg1="kw1",
        kwarg2="kw2"
    )
    
    assert result["arg1"] == "value1"
    assert result["arg2"] == "value2"
    assert result["kwarg1"] == "kw1"
    assert result["kwarg2"] == "kw2"
    assert task.kwargs == {"kwarg1": "kw1", "kwarg2": "kw2"}


def test_concurrent_enqueue(async_backend):
    """Test that concurrent enqueue operations are thread-safe."""
    results = []
    lock = threading.Lock()
    
    def test_func(value):
        with lock:
            results.append(value)
    
    # Enqueue from multiple threads
    threads = []
    for i in range(10):
        thread = threading.Thread(
            target=lambda v: async_backend.enqueue("test_queue", test_func, v),
            args=(i,)
        )
        threads.append(thread)
        thread.start()
    
    # Wait for all enqueue operations
    for thread in threads:
        thread.join()
    
    # Wait for processing
    time.sleep(1.0)
    
    # All tasks should be executed
    assert len(results) == 10
    assert set(results) == set(range(10))
