"""Tests for Redis queue backend implementation."""

import sys
import pytest
from unittest.mock import Mock, MagicMock, patch

# Mock the rq module before importing redis_backend
sys.modules['rq'] = MagicMock()
sys.modules['rq.job'] = MagicMock()

from doc_healing.queue.redis_backend import RedisQueueBackend
from doc_healing.queue.base import Task


@pytest.fixture
def mock_redis():
    """Create a mock Redis connection."""
    with patch('doc_healing.queue.redis_backend.Redis') as mock_redis_class:
        mock_conn = MagicMock()
        mock_redis_class.return_value = mock_conn
        yield mock_conn


@pytest.fixture
def mock_queue():
    """Create a mock RQ Queue."""
    with patch('doc_healing.queue.redis_backend.Queue') as mock_queue_class:
        mock_q = MagicMock()
        mock_queue_class.return_value = mock_q
        yield mock_q


@pytest.fixture
def redis_backend(mock_redis):
    """Create a RedisQueueBackend instance with mocked Redis."""
    return RedisQueueBackend()


def test_redis_backend_initialization(mock_redis):
    """Test that Redis backend initializes with correct settings."""
    backend = RedisQueueBackend()
    
    assert backend.redis_conn is not None
    assert backend.queues == {}


def test_enqueue_creates_task(redis_backend, mock_queue):
    """Test that enqueue creates a task with correct attributes."""
    # Setup mock job
    mock_job = MagicMock()
    mock_job.id = "test-job-123"
    mock_queue.enqueue.return_value = mock_job
    
    # Create a test function
    def test_func(arg1, arg2, kwarg1=None):
        pass
    
    # Enqueue the task
    task = redis_backend.enqueue("test_queue", test_func, "value1", "value2", kwarg1="kwvalue")
    
    # Verify task attributes
    assert task.id == "test-job-123"
    assert task.func_name == "test_func"
    assert task.args == ("value1", "value2")
    assert task.kwargs == {"kwarg1": "kwvalue"}
    assert task.queue_name == "test_queue"


def test_enqueue_calls_rq_enqueue(redis_backend, mock_queue):
    """Test that enqueue properly calls RQ's enqueue method."""
    mock_job = MagicMock()
    mock_job.id = "job-456"
    mock_queue.enqueue.return_value = mock_job
    
    def test_func():
        pass
    
    redis_backend.enqueue("webhooks", test_func)
    
    # Verify RQ enqueue was called
    mock_queue.enqueue.assert_called_once_with(test_func)


def test_get_queue_creates_queue_once(redis_backend):
    """Test that _get_queue creates a queue only once per queue name."""
    with patch('doc_healing.queue.redis_backend.Queue') as mock_queue_class:
        mock_q1 = MagicMock()
        mock_queue_class.return_value = mock_q1
        
        # Get the same queue twice
        queue1 = redis_backend._get_queue("test_queue")
        queue2 = redis_backend._get_queue("test_queue")
        
        # Should only create once
        assert mock_queue_class.call_count == 1
        assert queue1 is queue2
        assert "test_queue" in redis_backend.queues


def test_get_queue_creates_different_queues(redis_backend):
    """Test that _get_queue creates separate queues for different names."""
    with patch('doc_healing.queue.redis_backend.Queue') as mock_queue_class:
        mock_q1 = MagicMock()
        mock_q2 = MagicMock()
        mock_queue_class.side_effect = [mock_q1, mock_q2]
        
        # Get two different queues
        queue1 = redis_backend._get_queue("webhooks")
        queue2 = redis_backend._get_queue("validation")
        
        # Should create both
        assert mock_queue_class.call_count == 2
        assert queue1 is not queue2
        assert "webhooks" in redis_backend.queues
        assert "validation" in redis_backend.queues


def test_get_task_returns_none_for_empty_queue(redis_backend, mock_queue):
    """Test that get_task returns None when queue is empty."""
    mock_queue.job_ids = []
    
    task = redis_backend.get_task("empty_queue")
    
    assert task is None


def test_get_task_returns_first_task(redis_backend, mock_queue):
    """Test that get_task returns the first task in the queue."""
    with patch('doc_healing.queue.redis_backend.Job') as mock_job_class:
        # Setup mock queue with job IDs
        mock_queue.job_ids = ["job-1", "job-2", "job-3"]
        
        # Setup mock job
        mock_job = MagicMock()
        mock_job.id = "job-1"
        mock_job.func_name = "test_function"
        mock_job.args = ("arg1",)
        mock_job.kwargs = {"key": "value"}
        mock_job_class.fetch.return_value = mock_job
        
        task = redis_backend.get_task("test_queue")
        
        # Verify correct job was fetched
        mock_job_class.fetch.assert_called_once_with("job-1", connection=redis_backend.redis_conn)
        
        # Verify task attributes
        assert task.id == "job-1"
        assert task.func_name == "test_function"
        assert task.args == ("arg1",)
        assert task.kwargs == {"key": "value"}
        assert task.queue_name == "test_queue"


def test_mark_complete_logs_completion(redis_backend):
    """Test that mark_complete properly handles job completion."""
    with patch('doc_healing.queue.redis_backend.Job') as mock_job_class:
        mock_job = MagicMock()
        mock_job_class.fetch.return_value = mock_job
        
        task = Task(
            id="job-123",
            func_name="test_func",
            args=(),
            kwargs={},
            queue_name="test_queue"
        )
        
        # Should not raise an exception
        redis_backend.mark_complete(task)
        
        # Verify job was fetched
        mock_job_class.fetch.assert_called_once_with("job-123", connection=redis_backend.redis_conn)


def test_mark_failed_logs_error(redis_backend):
    """Test that mark_failed properly handles job failure."""
    with patch('doc_healing.queue.redis_backend.Job') as mock_job_class:
        mock_job = MagicMock()
        mock_job_class.fetch.return_value = mock_job
        
        task = Task(
            id="job-456",
            func_name="failing_func",
            args=(),
            kwargs={},
            queue_name="test_queue"
        )
        
        error = Exception("Test error")
        
        # Should not raise an exception
        redis_backend.mark_failed(task, error)
        
        # Verify job was fetched
        mock_job_class.fetch.assert_called_once_with("job-456", connection=redis_backend.redis_conn)


def test_mark_complete_raises_on_missing_job(redis_backend):
    """Test that mark_complete raises exception for non-existent job."""
    with patch('doc_healing.queue.redis_backend.Job') as mock_job_class:
        mock_job_class.fetch.side_effect = Exception("Job not found")
        
        task = Task(
            id="nonexistent",
            func_name="test_func",
            args=(),
            kwargs={},
            queue_name="test_queue"
        )
        
        with pytest.raises(Exception, match="Job not found"):
            redis_backend.mark_complete(task)


def test_mark_failed_raises_on_missing_job(redis_backend):
    """Test that mark_failed raises exception for non-existent job."""
    with patch('doc_healing.queue.redis_backend.Job') as mock_job_class:
        mock_job_class.fetch.side_effect = Exception("Job not found")
        
        task = Task(
            id="nonexistent",
            func_name="test_func",
            args=(),
            kwargs={},
            queue_name="test_queue"
        )
        
        error = Exception("Test error")
        
        with pytest.raises(Exception, match="Job not found"):
            redis_backend.mark_failed(task, error)
