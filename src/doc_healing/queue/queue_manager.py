"""Queue manager for webhook event processing.

This module provides a high-level interface for enqueueing tasks using the
queue abstraction layer. It works with both Redis and in-memory queue backends.
"""

from typing import Callable, Optional

from doc_healing.queue.base import Task
from doc_healing.queue.factory import get_queue_backend


class QueueManager:
    """Manages event queues using the queue abstraction layer.
    
    This class provides a high-level interface for enqueueing webhook,
    validation, and healing tasks. It uses the queue backend abstraction
    to work with both Redis and in-memory queue implementations.
    """

    def __init__(self) -> None:
        """Initialize queue manager with the configured queue backend."""
        self.queue_backend = get_queue_backend()

    def enqueue_webhook(self, func: Callable, *args, **kwargs) -> Task:
        """Enqueue a webhook processing job.
        
        Args:
            func: The task function to execute
            *args: Positional arguments for the task function
            **kwargs: Keyword arguments for the task function
            
        Returns:
            Task object representing the enqueued task
        """
        return self.queue_backend.enqueue("webhooks", func, *args, **kwargs)

    def enqueue_validation(self, func: Callable, *args, **kwargs) -> Task:
        """Enqueue a validation job.
        
        Args:
            func: The task function to execute
            *args: Positional arguments for the task function
            **kwargs: Keyword arguments for the task function
            
        Returns:
            Task object representing the enqueued task
        """
        return self.queue_backend.enqueue("validation", func, *args, **kwargs)

    def enqueue_healing(self, func: Callable, *args, **kwargs) -> Task:
        """Enqueue a healing job.
        
        Args:
            func: The task function to execute
            *args: Positional arguments for the task function
            **kwargs: Keyword arguments for the task function
            
        Returns:
            Task object representing the enqueued task
        """
        return self.queue_backend.enqueue("healing", func, *args, **kwargs)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID.
        
        Note: This method is a placeholder. Task retrieval by ID is not
        currently implemented in the queue backend abstraction.
        
        Args:
            task_id: The task ID to retrieve
            
        Returns:
            Task object if found, None otherwise
        """
        # TODO: Implement task retrieval in queue backend abstraction
        return None

    def get_queue_length(self, queue_name: str) -> int:
        """Get the length of a queue.
        
        Note: This method is a placeholder. Queue length retrieval is not
        currently implemented in the queue backend abstraction.
        
        Args:
            queue_name: Name of the queue
            
        Returns:
            Number of tasks in the queue (currently always returns 0)
        """
        # TODO: Implement queue length in queue backend abstraction
        return 0



# Global queue manager instance
_queue_manager: Optional[QueueManager] = None


def get_queue_manager() -> QueueManager:
    """Get or create queue manager instance.
    
    Returns:
        Singleton QueueManager instance
    """
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = QueueManager()
    return _queue_manager
