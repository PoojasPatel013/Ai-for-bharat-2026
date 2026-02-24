"""Unified worker implementation for all queue types.

This module provides a unified worker process that handles webhook, validation,
and healing tasks from all queue types. It supports both synchronous and
asynchronous processing modes and includes graceful shutdown handling.
"""

import logging
import signal
import sys
import time
from typing import Optional

from doc_healing.config import get_settings
from doc_healing.queue.factory import get_queue_backend
from doc_healing.queue.memory_backend import MemoryQueueBackend

logger = logging.getLogger(__name__)


class UnifiedWorker:
    """Unified worker that handles all queue types.
    
    This worker consolidates webhook, validation, and healing task processing
    into a single process. It supports both synchronous (immediate execution)
    and asynchronous (thread pool) processing modes.
    
    In synchronous mode, tasks execute immediately when enqueued, so the worker
    process simply keeps the application alive.
    
    In asynchronous mode with memory backend, worker threads are managed by
    MemoryQueueBackend. The worker process monitors and keeps threads alive.
    
    In asynchronous mode with Redis backend, this worker would poll queues
    and process tasks (to be implemented when needed).
    
    Attributes:
        queue_backend: The queue backend instance (Redis or Memory)
        settings: Application settings
        running: Flag indicating if the worker is running
        shutdown_requested: Flag indicating if shutdown has been requested
    """
    
    def __init__(self):
        """Initialize the unified worker with queue backend and settings."""
        self.queue_backend = get_queue_backend()
        self.settings = get_settings()
        self.running = False
        self.shutdown_requested = False
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("Unified worker initialized")
        logger.info(f"Deployment mode: {self.settings.deployment_mode}")
        logger.info(f"Queue backend: {self.settings.queue_backend}")
        logger.info(f"Sync processing: {self.settings.sync_processing}")
    
    def start(self):
        """Start the unified worker.
        
        The behavior depends on the processing mode:
        
        - Synchronous mode: Tasks execute immediately when enqueued.
          The worker just keeps the process alive.
        
        - Asynchronous mode with memory backend: Worker threads are already
          started by MemoryQueueBackend. The worker monitors them.
        
        - Asynchronous mode with Redis backend: The worker would poll queues
          and process tasks (to be implemented).
        
        This method blocks until shutdown is requested.
        """
        self.running = True
        logger.info("Starting unified worker")
        
        if self.settings.sync_processing:
            logger.info(
                "Running in synchronous mode - tasks execute immediately when enqueued"
            )
            self._run_sync_mode()
        else:
            if self.settings.queue_backend.value == "memory":
                logger.info(
                    f"Running with memory backend and {self.settings.worker_threads} worker threads"
                )
                self._run_memory_async_mode()
            else:
                logger.info("Running with Redis backend")
                self._run_redis_async_mode()
    
    def _run_sync_mode(self):
        """Run in synchronous mode.
        
        In sync mode, tasks execute immediately when enqueued, so this method
        just keeps the process alive and monitors for shutdown signals.
        """
        logger.info("Worker running in synchronous mode")
        
        while self.running and not self.shutdown_requested:
            time.sleep(1)
        
        logger.info("Synchronous mode worker stopped")
    
    def _run_memory_async_mode(self):
        """Run in asynchronous mode with memory backend.
        
        Worker threads are managed by MemoryQueueBackend. This method monitors
        the threads and keeps the process alive.
        """
        logger.info("Worker running in asynchronous mode with memory backend")
        
        # Verify worker threads are running
        if isinstance(self.queue_backend, MemoryQueueBackend):
            if not self.queue_backend.workers:
                logger.warning("No worker threads found in memory backend")
            else:
                logger.info(
                    f"Monitoring {len(self.queue_backend.workers)} worker threads"
                )
        
        while self.running and not self.shutdown_requested:
            # Monitor worker threads health
            if isinstance(self.queue_backend, MemoryQueueBackend):
                alive_workers = sum(
                    1 for w in self.queue_backend.workers if w.is_alive()
                )
                if alive_workers < len(self.queue_backend.workers):
                    logger.warning(
                        f"Only {alive_workers}/{len(self.queue_backend.workers)} "
                        "worker threads are alive"
                    )
            
            time.sleep(5)  # Check every 5 seconds
        
        logger.info("Asynchronous mode worker stopped")
    
    def _run_redis_async_mode(self):
        """Run in asynchronous mode with Redis backend.
        
        This would poll Redis queues and process tasks. Currently a placeholder
        that keeps the process alive, as Redis workers are typically run
        separately using RQ worker processes.
        """
        logger.info("Worker running in asynchronous mode with Redis backend")
        logger.warning(
            "Redis backend typically uses separate RQ worker processes. "
            "This unified worker is running but not processing tasks."
        )
        
        while self.running and not self.shutdown_requested:
            time.sleep(1)
        
        logger.info("Redis mode worker stopped")
    
    def stop(self):
        """Stop the unified worker gracefully.
        
        This method initiates shutdown and waits for current tasks to complete.
        For memory backend, it delegates to MemoryQueueBackend.shutdown().
        """
        if not self.running:
            logger.warning("Worker is not running")
            return
        
        logger.info("Stopping unified worker")
        self.running = False
        
        # Shutdown queue backend if it supports it
        if isinstance(self.queue_backend, MemoryQueueBackend):
            logger.info("Shutting down memory queue backend")
            self.queue_backend.shutdown()
        
        logger.info("Unified worker stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals (SIGINT, SIGTERM).
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        signal_name = signal.Signals(signum).name
        logger.info(f"Received {signal_name} signal, initiating graceful shutdown")
        self.shutdown_requested = True
        self.stop()


def main():
    """Main entry point for the unified worker process.
    
    This function creates and starts a UnifiedWorker instance, handling
    keyboard interrupts and other shutdown signals gracefully.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    logger.info("Starting unified worker process")
    
    worker = UnifiedWorker()
    try:
        worker.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        worker.stop()
    except Exception as e:
        logger.error(f"Unexpected error in worker: {e}", exc_info=True)
        worker.stop()
        sys.exit(1)
    
    logger.info("Unified worker process exited")


if __name__ == "__main__":
    main()
