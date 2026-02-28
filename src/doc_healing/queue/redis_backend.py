"""Redis queue backend implementation.

This module implements the QueueBackend interface using Redis Queue (RQ),
wrapping the existing RQ functionality with the new unified queue interface.
"""

import logging
from typing import Callable, Optional

from redis import Redis
from rq import Queue
from rq.job import Job

from doc_healing.config import get_settings
from doc_healing.queue.base import QueueBackend, Task

logger = logging.getLogger(__name__)


class RedisQueueBackend(QueueBackend):
    """Redis-based queue backend implementation using RQ.
    
    This backend wraps Redis Queue (RQ) to provide task queuing with
    persistence and distributed worker support. Tasks are stored in Redis
    and survive application restarts.
    
    Attributes:
        redis_conn: Redis connection instance
        queues: Dictionary mapping queue names to RQ Queue instances
    """
    
    def __init__(self):
        """Initialize Redis queue backend with connection from settings."""
        import os
        settings = get_settings()
        redis_password = os.getenv("REDIS_PASSWORD", None)
        
        if settings.redis_url:
            self.redis_conn = Redis.from_url(
                settings.redis_url,
                decode_responses=False, # RQ requires bytes mode
            )
            logger.info("Initialized Redis queue backend via REDIS_URL")
        else:
            self.redis_conn = Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=redis_password,
                decode_responses=False,  # RQ requires bytes mode
            )
            logger.info(
                f"Initialized Redis queue backend: {settings.redis_host}:{settings.redis_port}"
            )
        self.queues: dict[str, Queue] = {}
    
    def _get_queue(self, queue_name: str) -> Queue:
        """Get or create an RQ Queue instance for the given queue name.
        
        Args:
            queue_name: Name of the queue
            
        Returns:
            Queue: RQ Queue instance
        """
        if queue_name not in self.queues:
            self.queues[queue_name] = Queue(queue_name, connection=self.redis_conn)
            logger.debug(f"Created queue: {queue_name}")
        return self.queues[queue_name]
    
    def enqueue(self, queue_name: str, func: Callable, *args, **kwargs) -> Task:
        """Enqueue a task for processing in Redis.
        
        Args:
            queue_name: Name of the queue to add the task to
            func: The function to execute
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Task: The created task object with RQ job ID
            
        Raises:
            Exception: If Redis connection fails or enqueue operation fails
        """
        queue = self._get_queue(queue_name)
        job: Job = queue.enqueue(func, *args, **kwargs)
        
        task = Task(
            id=job.id,
            func_name=func.__name__,
            args=args,
            kwargs=kwargs,
            queue_name=queue_name,
        )
        
        logger.info(
            f"Enqueued task {task.id} ({task.func_name}) to queue '{queue_name}'"
        )
        return task
    
    def get_task(self, queue_name: str, timeout: Optional[int] = None) -> Optional[Task]:
        """Get the next task from a Redis queue.
        
        Note: This method is primarily for monitoring/inspection. RQ workers
        handle task retrieval automatically. For manual task processing,
        use RQ's worker infrastructure.
        
        Args:
            queue_name: Name of the queue to retrieve from
            timeout: Not used in RQ implementation (workers handle this)
            
        Returns:
            Optional[Task]: The next task if available, None otherwise
        """
        queue = self._get_queue(queue_name)
        job_ids = queue.job_ids
        
        if not job_ids:
            return None
        
        # Get the first job in the queue
        job = Job.fetch(job_ids[0], connection=self.redis_conn)
        
        # Extract function name from job
        func_name = job.func_name if hasattr(job, 'func_name') else str(job.func)
        
        task = Task(
            id=job.id,
            func_name=func_name,
            args=job.args or (),
            kwargs=job.kwargs or {},
            queue_name=queue_name,
        )
        
        return task
    
    def mark_complete(self, task: Task) -> None:
        """Mark a task as successfully completed.
        
        In RQ, job completion is handled automatically by workers.
        This method is provided for interface compatibility and can be used
        for manual job status updates if needed.
        
        Args:
            task: The task to mark as complete
            
        Raises:
            Exception: If the job doesn't exist or status update fails
        """
        try:
            job = Job.fetch(task.id, connection=self.redis_conn)
            # RQ automatically marks jobs as finished when they complete
            # This is mainly for logging/monitoring
            logger.info(f"Task {task.id} ({task.func_name}) marked as complete")
        except Exception as e:
            logger.error(f"Failed to mark task {task.id} as complete: {e}")
            raise
    
    def mark_failed(self, task: Task, error: Exception) -> None:
        """Mark a task as failed.
        
        In RQ, job failures are handled automatically by workers.
        This method is provided for interface compatibility and can be used
        for manual job status updates if needed.
        
        Args:
            task: The task to mark as failed
            error: The exception that caused the failure
            
        Raises:
            Exception: If the job doesn't exist or status update fails
        """
        try:
            job = Job.fetch(task.id, connection=self.redis_conn)
            # RQ automatically marks jobs as failed when they raise exceptions
            # This is mainly for logging/monitoring
            logger.error(
                f"Task {task.id} ({task.func_name}) marked as failed: {error}"
            )
        except Exception as e:
            logger.error(f"Failed to mark task {task.id} as failed: {e}")
            raise
