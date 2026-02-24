"""Tests for queue backend factory."""

import sys
import pytest
from unittest.mock import MagicMock, patch

# Mock the rq module before importing anything else
sys.modules['rq'] = MagicMock()
sys.modules['rq.job'] = MagicMock()

from doc_healing.queue.factory import get_queue_backend, reset_queue_backend
from doc_healing.queue.redis_backend import RedisQueueBackend
from doc_healing.queue.memory_backend import MemoryQueueBackend
from doc_healing.config import QueueBackend as QueueBackendEnum


@pytest.fixture(autouse=True)
def reset_factory():
    """Reset the factory singleton before each test."""
    reset_queue_backend()
    yield
    reset_queue_backend()


def test_get_queue_backend_returns_redis_backend():
    """Test that factory returns Redis backend when configured."""
    with patch('doc_healing.queue.factory.get_settings') as mock_settings:
        settings = MagicMock()
        settings.queue_backend = QueueBackendEnum.REDIS
        settings.deployment_mode = MagicMock(value="full")
        settings.redis_host = "localhost"
        settings.redis_port = 6379
        settings.redis_db = 0
        mock_settings.return_value = settings
        
        with patch('doc_healing.queue.redis_backend.Redis'):
            backend = get_queue_backend()
            
            assert isinstance(backend, RedisQueueBackend)


def test_get_queue_backend_returns_memory_backend():
    """Test that factory returns memory backend when configured."""
    with patch('doc_healing.queue.factory.get_settings') as mock_settings:
        settings = MagicMock()
        settings.queue_backend = QueueBackendEnum.MEMORY
        settings.deployment_mode = MagicMock(value="lightweight")
        settings.sync_processing = True
        settings.worker_threads = 2
        mock_settings.return_value = settings
        
        backend = get_queue_backend()
        
        assert isinstance(backend, MemoryQueueBackend)


def test_get_queue_backend_returns_singleton():
    """Test that factory returns the same instance on multiple calls."""
    with patch('doc_healing.queue.factory.get_settings') as mock_settings:
        settings = MagicMock()
        settings.queue_backend = QueueBackendEnum.MEMORY
        settings.deployment_mode = MagicMock(value="lightweight")
        settings.sync_processing = True
        settings.worker_threads = 2
        mock_settings.return_value = settings
        
        backend1 = get_queue_backend()
        backend2 = get_queue_backend()
        
        assert backend1 is backend2


def test_reset_queue_backend_clears_singleton():
    """Test that reset_queue_backend clears the singleton instance."""
    with patch('doc_healing.queue.factory.get_settings') as mock_settings:
        settings = MagicMock()
        settings.queue_backend = QueueBackendEnum.MEMORY
        settings.deployment_mode = MagicMock(value="lightweight")
        settings.sync_processing = True
        settings.worker_threads = 2
        mock_settings.return_value = settings
        
        backend1 = get_queue_backend()
        reset_queue_backend()
        backend2 = get_queue_backend()
        
        # Should be different instances after reset
        assert backend1 is not backend2


def test_reset_queue_backend_calls_shutdown_on_memory_backend():
    """Test that reset calls shutdown on memory backend."""
    with patch('doc_healing.queue.factory.get_settings') as mock_settings:
        settings = MagicMock()
        settings.queue_backend = QueueBackendEnum.MEMORY
        settings.deployment_mode = MagicMock(value="lightweight")
        settings.sync_processing = True
        settings.worker_threads = 2
        mock_settings.return_value = settings
        
        backend = get_queue_backend()
        
        with patch.object(backend, 'shutdown') as mock_shutdown:
            reset_queue_backend()
            mock_shutdown.assert_called_once()


def test_reset_queue_backend_does_not_call_shutdown_on_redis_backend():
    """Test that reset does not call shutdown on Redis backend."""
    with patch('doc_healing.queue.factory.get_settings') as mock_settings:
        settings = MagicMock()
        settings.queue_backend = QueueBackendEnum.REDIS
        settings.deployment_mode = MagicMock(value="full")
        settings.redis_host = "localhost"
        settings.redis_port = 6379
        settings.redis_db = 0
        mock_settings.return_value = settings
        
        with patch('doc_healing.queue.redis_backend.Redis'):
            backend = get_queue_backend()
            
            # Redis backend doesn't have shutdown method
            # This should not raise an error
            reset_queue_backend()


def test_factory_logs_backend_initialization():
    """Test that factory logs backend initialization."""
    with patch('doc_healing.queue.factory.get_settings') as mock_settings:
        settings = MagicMock()
        settings.queue_backend = QueueBackendEnum.MEMORY
        settings.deployment_mode = MagicMock(value="lightweight")
        settings.sync_processing = True
        settings.worker_threads = 2
        mock_settings.return_value = settings
        
        with patch('doc_healing.queue.factory.logger') as mock_logger:
            backend = get_queue_backend()
            
            # Should log initialization
            assert mock_logger.info.call_count >= 2
            # Check that it logged the backend type
            calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any('memory' in str(call).lower() for call in calls)


def test_factory_with_redis_backend_configuration():
    """Test factory with full Redis backend configuration."""
    with patch('doc_healing.queue.factory.get_settings') as mock_factory_settings:
        with patch('doc_healing.queue.redis_backend.get_settings') as mock_redis_settings:
            settings = MagicMock()
            settings.queue_backend = QueueBackendEnum.REDIS
            settings.deployment_mode = MagicMock(value="full")
            settings.redis_host = "redis.example.com"
            settings.redis_port = 6380
            settings.redis_db = 1
            mock_factory_settings.return_value = settings
            mock_redis_settings.return_value = settings
            
            with patch('doc_healing.queue.redis_backend.Redis') as mock_redis:
                backend = get_queue_backend()
                
                # Verify Redis was initialized with correct settings
                mock_redis.assert_called_once()
                call_kwargs = mock_redis.call_args[1]
                assert call_kwargs['host'] == "redis.example.com"
                assert call_kwargs['port'] == 6380
                assert call_kwargs['db'] == 1


def test_factory_with_memory_backend_configuration():
    """Test factory with full memory backend configuration."""
    with patch('doc_healing.queue.factory.get_settings') as mock_settings:
        settings = MagicMock()
        settings.queue_backend = QueueBackendEnum.MEMORY
        settings.deployment_mode = MagicMock(value="lightweight")
        settings.sync_processing = False
        settings.worker_threads = 4
        mock_settings.return_value = settings
        
        backend = get_queue_backend()
        
        # Verify memory backend was configured correctly
        assert backend.sync_processing is False
        assert backend.worker_threads == 4
        assert backend.running is True
        
        # Cleanup
        backend.shutdown()


def test_reset_queue_backend_when_none_exists():
    """Test that reset_queue_backend handles case when no backend exists."""
    # Should not raise an error
    reset_queue_backend()
    reset_queue_backend()  # Call twice to ensure idempotency
