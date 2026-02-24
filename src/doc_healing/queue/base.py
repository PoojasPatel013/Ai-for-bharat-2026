"""Queue backend abstraction layer.

This module provides an abstract interface for queue backends, allowing the system
to work with different queue implementations (Redis, in-memory) through a unified API.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class Task:
    """Represents a task in the queue system.
    
    Attributes:
        id: Unique identifier for the task
        func_name: Name of the function to execute
        args: Positional arguments for the function
        kwargs: Keyword arguments for the function
        queue_name: Name of the queue this task belongs to
    """
    id: str
    func_name: str
    args: tuple
    kwargs: dict
    queue_name: str


class QueueBackend(ABC):
    """Abstract base class for queue backend implementations.
    
    This interface defines the contract that all queue backends must implement,
    enabling the system to switch between different queue implementations
    (e.g., Redis-based, in-memory) without changing application code.
    """
    
    @abstractmethod
    def enqueue(self, queue_name: str, func: Callable, *args, **kwargs) -> Task:
        """Enqueue a task for processing.
        
        Args:
            queue_name: Name of the queue to add the task to
            func: The function to execute
            *args: Positional arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
            
        Returns:
            Task: The created task object with a unique ID
            
        Raises:
            QueueFullError: If the queue has reached its capacity
            QueueError: For other queue-related errors
        """
        pass
    
    @abstractmethod
    def get_task(self, queue_name: str, timeout: Optional[int] = None) -> Optional[Task]:
        """Get the next task from a queue.
        
        Args:
            queue_name: Name of the queue to retrieve from
            timeout: Maximum time to wait for a task (in seconds).
                    None means wait indefinitely, 0 means non-blocking.
                    
        Returns:
            Optional[Task]: The next task, or None if no task is available
                           within the timeout period
                           
        Raises:
            QueueError: If there's an error accessing the queue
        """
        pass
    
    @abstractmethod
    def mark_complete(self, task: Task) -> None:
        """Mark a task as successfully completed.
        
        Args:
            task: The task to mark as complete
            
        Raises:
            TaskNotFoundError: If the task doesn't exist
            QueueError: For other queue-related errors
        """
        pass
    
    @abstractmethod
    def mark_failed(self, task: Task, error: Exception) -> None:
        """Mark a task as failed.
        
        Args:
            task: The task to mark as failed
            error: The exception that caused the failure
            
        Raises:
            TaskNotFoundError: If the task doesn't exist
            QueueError: For other queue-related errors
        """
        pass
