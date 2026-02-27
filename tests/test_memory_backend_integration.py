"""Integration tests for memory backend with different configurations."""

import sys
import time
import pytest
from unittest.mock import patch, MagicMock

# Mock the rq module before importing anything else
sys.modules['rq'] = MagicMock()
sys.modules['rq.job'] = MagicMock()

from doc_healing.queue.memory_backend import MemoryQueueBackend


def test_sync_mode_immediate_execution():
    """Test that sync mode executes tasks immediately (Requirement 3.2)."""
    with patch('doc_healing.queue.memory_backend.get_settings') as mock_settings:
        settings = MagicMock()
        settings.sync_processing = True
        settings.worker_threads = 2
        mock_settings.return_value = settings
        
        backend = MemoryQueueBackend()
        
        # Track execution
        results = []
        
        def task_func(value):
            results.append(value)
        
        # Enqueue task
        task = backend.enqueue("test_queue", task_func, "immediate")
        
        # Should execute immediately without waiting
        assert "immediate" in results
        assert task.id not in backend.tasks


def test_async_mode_worker_threads():
    """Test that async mode uses worker threads (Requirement 3.2)."""
    with patch('doc_healing.queue.memory_backend.get_settings') as mock_settings:
        settings = MagicMock()
        settings.sync_processing = False
        settings.worker_threads = 3
        mock_settings.return_value = settings
        
        backend = MemoryQueueBackend()
        
        # Verify workers are started
        assert backend.running is True
        assert len(backend.workers) == 3
        
        # Track execution
        results = []
        
        def task_func(value):
            results.append(value)
        
        # Enqueue task
        task = backend.enqueue("test_queue", task_func, "async")
        
        # Should not execute immediately
        # Wait for worker to process
        time.sleep(0.5)
        
        # Should be executed by worker
        assert "async" in results
        
        # Cleanup
        backend.shutdown()


def test_multiple_queue_types():
    """Test that different queue types work correctly (Requirement 1.2)."""
    with patch('doc_healing.queue.memory_backend.get_settings') as mock_settings:
        settings = MagicMock()
        settings.sync_processing = False
        settings.worker_threads = 2
        mock_settings.return_value = settings
        
        backend = MemoryQueueBackend()
        
        # Track execution by queue
        results = {
            "webhooks": [],
            "validation": [],
            "healing": []
        }
        
        def webhook_task(value):
            results["webhooks"].append(value)
        
        def validation_task(value):
            results["validation"].append(value)
        
        def healing_task(value):
            results["healing"].append(value)
        
        # Enqueue to different queues
        backend.enqueue("webhooks", webhook_task, "webhook1")
        backend.enqueue("validation", validation_task, "validation1")
        backend.enqueue("healing", healing_task, "healing1")
        backend.enqueue("webhooks", webhook_task, "webhook2")
        
        # Wait for processing
        time.sleep(1.0)
        
        # All tasks should be processed
        assert len(results["webhooks"]) == 2
        assert len(results["validation"]) == 1
        assert len(results["healing"]) == 1
        
        # Cleanup
        backend.shutdown()


def test_task_interface_consistency():
    """Test that task interface is consistent (Requirement 3.3)."""
    with patch('doc_healing.queue.memory_backend.get_settings') as mock_settings:
        settings = MagicMock()
        settings.sync_processing = True
        settings.worker_threads = 2
        mock_settings.return_value = settings
        
        backend = MemoryQueueBackend()
        
        def test_func(arg1, arg2, kwarg1=None):
            return f"{arg1}-{arg2}-{kwarg1}"
        
        # Enqueue with args and kwargs
        task = backend.enqueue(
            "test_queue",
            test_func,
            "value1",
            "value2",
            kwarg1="kwvalue"
        )
        
        # Verify task structure matches interface
        assert task.id is not None
        assert task.func_name == "test_func"
        assert task.args == ("value1", "value2")
        assert task.kwargs == {"kwarg1": "kwvalue"}
        assert task.queue_name == "test_queue"


def test_no_persistence_across_restarts():
    """Test that tasks don't persist across restarts (Requirement 3.4)."""
    with patch('doc_healing.queue.memory_backend.get_settings') as mock_settings:
        settings = MagicMock()
        settings.sync_processing = False
        settings.worker_threads = 2
        mock_settings.return_value = settings
        
        # Create first backend instance
        backend1 = MemoryQueueBackend()
        
        def slow_task():
            time.sleep(2)
        
        # Enqueue task
        task = backend1.enqueue("test_queue", slow_task)
        
        # Shutdown (simulating restart)
        backend1.shutdown()
        
        # Create new backend instance (simulating restart)
        backend2 = MemoryQueueBackend()
        
        # Task should not exist in new instance
        assert task.id not in backend2.tasks
        assert "test_queue" not in backend2.queues or backend2.queues["test_queue"].empty()
        
        # Cleanup
        backend2.shutdown()


def test_error_handling_in_async_mode():
    """Test that errors are handled gracefully in async mode."""
    with patch('doc_healing.queue.memory_backend.get_settings') as mock_settings:
        settings = MagicMock()
        settings.sync_processing = False
        settings.worker_threads = 2
        mock_settings.return_value = settings
        
        backend = MemoryQueueBackend()
        
        # Track successful tasks
        results = []
        
        def failing_task():
            raise ValueError("Task failed")
        
        def successful_task(value):
            results.append(value)
        
        # Enqueue failing task
        task1 = backend.enqueue("test_queue", failing_task)
        
        # Enqueue successful task after failing one
        task2 = backend.enqueue("test_queue", successful_task, "success")
        
        # Wait for processing
        time.sleep(1.0)
        
        # Successful task should still execute
        assert "success" in results
        
        # Both tasks should be removed from tracking
        assert task1.id not in backend.tasks
        assert task2.id not in backend.tasks
        
        # Cleanup
        backend.shutdown()


def test_graceful_shutdown():
    """Test that shutdown stops workers gracefully."""
    with patch('doc_healing.queue.memory_backend.get_settings') as mock_settings:
        settings = MagicMock()
        settings.sync_processing = False
        settings.worker_threads = 2
        mock_settings.return_value = settings
        
        backend = MemoryQueueBackend()
        
        # Verify workers are running
        assert backend.running is True
        workers = backend.workers.copy()
        assert all(w.is_alive() for w in workers)
        
        # Shutdown
        backend.shutdown()
        
        # Verify shutdown
        assert backend.running is False
        
        # Wait for threads to stop
        time.sleep(0.5)
        
        # Workers should be stopped
        for worker in workers:
            assert not worker.is_alive()
