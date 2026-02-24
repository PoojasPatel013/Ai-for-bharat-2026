"""In-memory queue backend implementation.

This module implements the QueueBackend interface using Python's threading.Queue,
providing a lightweight alternative to Redis for development environments.
Supports both synchronous (immediate execution) and asynchronous (thread pool) modes.
"""

import logging
import queue
import threading
import uuid
from typing import Callable, Dict, Optional

from doc_healing.config import get_settings
from doc_healing.queue.base import QueueBackend, Task

logger = logging.getLogger(__name__)


class MemoryQueueBackend(QueueBackend):
    """In-memory queue backend implementation using threading.Queue.
    
    This backend provides a lightweight alternative to Redis for development
    environments. It supports two execution modes:
    
    1. Synchronous mode (sync_processing=True): Tasks execute immediately
       when enqueued, blocking until completion.
    
    2. Asynchronous mode (sync_processing=False): Tasks are queued and
       processed by a pool of worker threads.
    
    Note: Tasks do not persist across application restarts.
    
    Attributes:
        queues: Dictionary mapping queue names to Queue instances
        tasks: Dictionary mapping task IDs to Task objects
        lock: Thread lock for synchronizing access to shared state
        workers: List of worker threads (async mode only)
        running: Flag indicating if workers are running
    """
    
    def __init__(self):
        """Initialize in-memory queue backend with configuration from settings."""
        self.queues: Dict[str, queue.Queue] = {}
        self.tasks: Dict[str, Task] = {}
        self.lock = threading.Lock()
        self.workers = []
        self.running = False
        
        settings = get_settings()
        self.sync_processing = settings.sync_processing
        self.worker_threads = settings.worker_threads
        
        # Start worker threads if not in sync mode
        if not self.sync_processing:
            self._start_workers()
            logger.info(
                f"Initialized memory queue backend with {self.worker_threads} worker threads"
            )
        else:
            logger.info("Initialized memory queue backend in synchronous mode")
    
    def _get_queue(self, queue_name: str) -> queue.Queue:
        """Get or create a Queue instance for the given queue name.
        
        Args:
            queue_name: Name of the queue
            
        Returns:
            queue.Queue: Queue instance
        """
        if queue_name not in self.queues:
            with self.lock:
                # Double-check after acquiring lock
                if queue_name not in self.queues:
                    self.queues[queue_name] = queue.Queue()
                    logger.debug(f"Created in-memory queue: {queue_name}")
        return self.queues[queue_name]
    
    def enqueue(self, queue_name: str, func: Callable, *args, **kwargs) -> Task:
        """Enqueue a task for processing.
        
        In synchronous mode, the task executes immediately before returning.
        In asynchronous mode, the task is queued for worker thread processing.
        
        Args:
            queue_name: Name of the queue to add the task to
            func: The function to execute
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Task: The created task object with a unique ID
            
        Raises:
            Exception: If task execution fails in synchronous mode
        """
        task = Task(
            id=str(uuid.uuid4()),
            func_name=func.__name__,
            args=args,
            kwargs=kwargs,
            queue_name=queue_name,
        )
        
        if self.sync_processing:
            # Execute immediately in sync mode
            logger.debug(
                f"Executing task {task.id} ({task.func_name}) synchronously"
            )
            try:
                func(*args, **kwargs)
                self.mark_complete(task)
                logger.info(
                    f"Task {task.id} ({task.func_name}) completed synchronously"
                )
            except Exception as e:
                self.mark_failed(task, e)
                logger.error(
                    f"Task {task.id} ({task.func_name}) failed synchronously: {e}"
                )
                raise
        else:
            # Queue for async processing
            q = self._get_queue(queue_name)
            with self.lock:
                self.tasks[task.id] = task
            q.put((func, args, kwargs, task))
            logger.info(
                f"Enqueued task {task.id} ({task.func_name}) to queue '{queue_name}'"
            )
        
        return task
    
    def get_task(self, queue_name: str, timeout: Optional[int] = None) -> Optional[Task]:
        """Get the next task from a queue.
        
        This method retrieves a task without executing it. Primarily used
        for monitoring and inspection.
        
        Args:
            queue_name: Name of the queue to retrieve from
            timeout: Maximum time to wait for a task (in seconds).
                    None means wait indefinitely, 0 means non-blocking.
                    
        Returns:
            Optional[Task]: The next task, or None if no task is available
        """
        q = self._get_queue(queue_name)
        
        try:
            if timeout == 0:
                # Non-blocking
                func, args, kwargs, task = q.get_nowait()
            else:
                # Blocking with timeout
                func, args, kwargs, task = q.get(timeout=timeout)
            
            # Put it back for processing
            q.put((func, args, kwargs, task))
            return task
        except queue.Empty:
            return None
    
    def mark_complete(self, task: Task) -> None:
        """Mark a task as successfully completed.
        
        Args:
            task: The task to mark as complete
        """
        with self.lock:
            if task.id in self.tasks:
                del self.tasks[task.id]
        logger.debug(f"Task {task.id} ({task.func_name}) marked as complete")
    
    def mark_failed(self, task: Task, error: Exception) -> None:
        """Mark a task as failed.
        
        Args:
            task: The task to mark as failed
            error: The exception that caused the failure
        """
        with self.lock:
            if task.id in self.tasks:
                del self.tasks[task.id]
        logger.error(f"Task {task.id} ({task.func_name}) marked as failed: {error}")
    
    def _start_workers(self):
        """Start worker threads for asynchronous task processing."""
        self.running = True
        for i in range(self.worker_threads):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"MemoryQueueWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
            logger.debug(f"Started worker thread: {worker.name}")
    
    def _worker_loop(self):
        """Worker thread main loop for processing tasks from all queues.
        
        This method runs in each worker thread, continuously polling all queues
        for tasks to process. Uses a round-robin approach with short timeouts
        to balance load across queues.
        """
        logger.debug(f"Worker thread {threading.current_thread().name} started")
        
        while self.running:
            processed = False
            
            # Try to get a task from any queue
            for queue_name, q in list(self.queues.items()):
                try:
                    func, args, kwargs, task = q.get(timeout=0.1)
                    processed = True
                    
                    logger.debug(
                        f"Worker {threading.current_thread().name} processing "
                        f"task {task.id} ({task.func_name}) from queue '{queue_name}'"
                    )
                    
                    try:
                        func(*args, **kwargs)
                        self.mark_complete(task)
                        logger.info(
                            f"Task {task.id} ({task.func_name}) completed successfully"
                        )
                    except Exception as e:
                        self.mark_failed(task, e)
                        logger.error(
                            f"Task {task.id} ({task.func_name}) failed: {e}",
                            exc_info=True
                        )
                    
                    break  # Process one task then check all queues again
                    
                except queue.Empty:
                    continue
            
            # If no task was processed, sleep briefly to avoid busy-waiting
            if not processed:
                threading.Event().wait(0.1)
        
        logger.debug(f"Worker thread {threading.current_thread().name} stopped")
    
    def shutdown(self):
        """Gracefully shutdown the worker threads.
        
        This method stops all worker threads and waits for them to complete
        their current tasks. Should be called during application shutdown.
        """
        if not self.sync_processing:
            logger.info("Shutting down memory queue backend workers")
            self.running = False
            
            # Wait for workers to finish
            for worker in self.workers:
                worker.join(timeout=5.0)
                if worker.is_alive():
                    logger.warning(f"Worker {worker.name} did not stop gracefully")
            
            logger.info("Memory queue backend shutdown complete")
