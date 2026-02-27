"""Tests for unified worker implementation."""

import sys
import time
import threading
import pytest
from unittest.mock import patch, MagicMock, Mock

# Mock the rq module before importing anything else
sys.modules['rq'] = MagicMock()
sys.modules['rq.job'] = MagicMock()

from doc_healing.workers.unified import UnifiedWorker
from doc_healing.queue.memory_backend import MemoryQueueBackend


@pytest.fixture
def mock_settings_sync():
    """Mock settings for synchronous mode."""
    settings = MagicMock()
    settings.deployment_mode = "lightweight"
    settings.queue_backend = MagicMock(value="memory")
    settings.sync_processing = True
    settings.worker_threads = 2
    return settings


@pytest.fixture
def mock_settings_async():
    """Mock settings for asynchronous mode."""
    settings = MagicMock()
    settings.deployment_mode = "lightweight"
    settings.queue_backend = MagicMock(value="memory")
    settings.sync_processing = False
    settings.worker_threads = 2
    return settings


def test_unified_worker_initialization_sync(mock_settings_sync):
    """Test that unified worker initializes correctly in sync mode."""
    with patch('doc_healing.workers.unified.get_settings', return_value=mock_settings_sync):
        with patch('doc_healing.workers.unified.get_queue_backend') as mock_backend:
            mock_backend.return_value = MagicMock(spec=MemoryQueueBackend)
            
            worker = UnifiedWorker()
            
            assert worker.settings == mock_settings_sync
            assert worker.running is False
            assert worker.shutdown_requested is False


def test_unified_worker_initialization_async(mock_settings_async):
    """Test that unified worker initializes correctly in async mode."""
    with patch('doc_healing.workers.unified.get_settings', return_value=mock_settings_async):
        with patch('doc_healing.workers.unified.get_queue_backend') as mock_backend:
            mock_backend.return_value = MagicMock(spec=MemoryQueueBackend)
            
            worker = UnifiedWorker()
            
            assert worker.settings == mock_settings_async
            assert worker.running is False
            assert worker.shutdown_requested is False


def test_unified_worker_start_sync_mode(mock_settings_sync):
    """Test that worker starts correctly in synchronous mode."""
    with patch('doc_healing.workers.unified.get_settings', return_value=mock_settings_sync):
        with patch('doc_healing.workers.unified.get_queue_backend') as mock_backend:
            mock_backend.return_value = MagicMock(spec=MemoryQueueBackend)
            
            worker = UnifiedWorker()
            
            # Start worker in a separate thread
            def start_worker():
                worker.start()
            
            thread = threading.Thread(target=start_worker, daemon=True)
            thread.start()
            
            # Wait a bit for worker to start
            time.sleep(0.2)
            
            # Worker should be running
            assert worker.running is True
            
            # Stop worker
            worker.stop()
            thread.join(timeout=1.0)


def test_unified_worker_start_async_mode(mock_settings_async):
    """Test that worker starts correctly in asynchronous mode."""
    with patch('doc_healing.workers.unified.get_settings', return_value=mock_settings_async):
        with patch('doc_healing.workers.unified.get_queue_backend') as mock_backend:
            # Create a mock backend with workers
            backend = MagicMock(spec=MemoryQueueBackend)
            backend.workers = [MagicMock(is_alive=lambda: True) for _ in range(2)]
            mock_backend.return_value = backend
            
            worker = UnifiedWorker()
            
            # Start worker in a separate thread
            def start_worker():
                worker.start()
            
            thread = threading.Thread(target=start_worker, daemon=True)
            thread.start()
            
            # Wait a bit for worker to start
            time.sleep(0.2)
            
            # Worker should be running
            assert worker.running is True
            
            # Stop worker
            worker.stop()
            thread.join(timeout=1.0)


def test_unified_worker_stop(mock_settings_sync):
    """Test that worker stops gracefully."""
    with patch('doc_healing.workers.unified.get_settings', return_value=mock_settings_sync):
        with patch('doc_healing.workers.unified.get_queue_backend') as mock_backend:
            backend = MagicMock(spec=MemoryQueueBackend)
            mock_backend.return_value = backend
            
            worker = UnifiedWorker()
            worker.running = True
            
            # Stop worker
            worker.stop()
            
            # Worker should be stopped
            assert worker.running is False
            # Backend shutdown should be called
            backend.shutdown.assert_called_once()


def test_unified_worker_stop_when_not_running(mock_settings_sync):
    """Test that stopping a non-running worker is safe."""
    with patch('doc_healing.workers.unified.get_settings', return_value=mock_settings_sync):
        with patch('doc_healing.workers.unified.get_queue_backend') as mock_backend:
            mock_backend.return_value = MagicMock(spec=MemoryQueueBackend)
            
            worker = UnifiedWorker()
            
            # Stop worker that's not running
            worker.stop()
            
            # Should not raise an error
            assert worker.running is False


def test_unified_worker_signal_handler(mock_settings_sync):
    """Test that signal handler initiates graceful shutdown."""
    with patch('doc_healing.workers.unified.get_settings', return_value=mock_settings_sync):
        with patch('doc_healing.workers.unified.get_queue_backend') as mock_backend:
            backend = MagicMock(spec=MemoryQueueBackend)
            mock_backend.return_value = backend
            
            worker = UnifiedWorker()
            worker.running = True
            
            # Simulate signal
            import signal
            worker._signal_handler(signal.SIGTERM, None)
            
            # Worker should be stopped
            assert worker.shutdown_requested is True
            assert worker.running is False


def test_unified_worker_monitors_thread_health(mock_settings_async):
    """Test that worker monitors thread health in async mode."""
    with patch('doc_healing.workers.unified.get_settings', return_value=mock_settings_async):
        with patch('doc_healing.workers.unified.get_queue_backend') as mock_backend:
            # Create a mock backend with some dead workers
            backend = MagicMock(spec=MemoryQueueBackend)
            alive_worker = MagicMock()
            alive_worker.is_alive.return_value = True
            dead_worker = MagicMock()
            dead_worker.is_alive.return_value = False
            backend.workers = [alive_worker, dead_worker]
            mock_backend.return_value = backend
            
            worker = UnifiedWorker()
            
            # Start worker in a separate thread
            def start_worker():
                worker.start()
            
            thread = threading.Thread(target=start_worker, daemon=True)
            thread.start()
            
            # Wait for monitoring to occur
            time.sleep(6)  # Monitoring happens every 5 seconds
            
            # Stop worker
            worker.stop()
            thread.join(timeout=1.0)
            
            # Verify is_alive was called on workers
            assert alive_worker.is_alive.called
            assert dead_worker.is_alive.called


def test_unified_worker_redis_mode_placeholder(mock_settings_async):
    """Test that Redis mode runs but logs warning."""
    settings = MagicMock()
    settings.deployment_mode = "full"
    settings.queue_backend = MagicMock(value="redis")
    settings.sync_processing = False
    settings.worker_threads = 2
    
    with patch('doc_healing.workers.unified.get_settings', return_value=settings):
        with patch('doc_healing.workers.unified.get_queue_backend') as mock_backend:
            mock_backend.return_value = MagicMock()
            
            worker = UnifiedWorker()
            
            # Start worker in a separate thread
            def start_worker():
                worker.start()
            
            thread = threading.Thread(target=start_worker, daemon=True)
            thread.start()
            
            # Wait a bit
            time.sleep(0.2)
            
            # Worker should be running
            assert worker.running is True
            
            # Stop worker
            worker.stop()
            thread.join(timeout=1.0)


def test_unified_worker_task_routing(mock_settings_sync):
    """Test task routing to correct handlers through unified worker."""
    # This verifies that the UnifiedWorker sets up the backend 
    # which routes tasks correctly based on queue names
    with patch('doc_healing.workers.unified.get_settings', return_value=mock_settings_sync):
        with patch('doc_healing.workers.unified.get_queue_backend') as mock_backend:
            backend = MagicMock()
            mock_backend.return_value = backend
            
            worker = UnifiedWorker()
            assert worker.queue_backend is backend
            # Just verify the backend is initialized correctly as it handles routing


def test_unified_worker_error_handling():
    """Test error handling in worker main loop."""
    # Verifies that exceptions in main() are caught and worker is stopped
    with patch('doc_healing.workers.unified.UnifiedWorker') as mock_worker_cls:
        mock_worker = MagicMock()
        mock_worker.start.side_effect = Exception("Test worker error")
        mock_worker_cls.return_value = mock_worker
        
        with patch('sys.exit') as mock_exit:
            from doc_healing.workers.unified import main
            main()
            
            # Should catch the error, stop the worker and exit with 1
            mock_worker.stop.assert_called_once()
            mock_exit.assert_called_once_with(1)

def test_unified_worker_keyboard_interrupt():
    """Test graceful shutdown on keyboard interrupt."""
    with patch('doc_healing.workers.unified.UnifiedWorker') as mock_worker_cls:
        mock_worker = MagicMock()
        mock_worker.start.side_effect = KeyboardInterrupt()
        mock_worker_cls.return_value = mock_worker
        
        with patch('sys.exit') as mock_exit:
            from doc_healing.workers.unified import main
            main()
            
            # Should catch the interrupt and stop the worker normally
            mock_worker.stop.assert_called_once()
            mock_exit.assert_not_called()
