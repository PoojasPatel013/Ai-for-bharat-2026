"""Queue backend factory for selecting the appropriate queue implementation.

This module provides a factory function that returns the correct queue backend
based on the application configuration. It maintains a singleton instance to
ensure consistent queue backend usage throughout the application lifecycle.
"""

import logging
from typing import Optional

from doc_healing.config import QueueBackend as QueueBackendEnum
from doc_healing.config import get_settings
from doc_healing.queue.base import QueueBackend

logger = logging.getLogger(__name__)

# Global singleton instance
_queue_backend: Optional[QueueBackend] = None


def get_queue_backend() -> QueueBackend:
    """Get the configured queue backend instance.
    
    This function returns a singleton instance of the appropriate queue backend
    based on the application configuration. The backend is determined by the
    `queue_backend` setting, which can be either 'redis' or 'memory'.
    
    The instance is created on first call and reused for subsequent calls,
    ensuring consistent queue behavior throughout the application.
    
    Returns:
        QueueBackend: The configured queue backend instance (RedisQueueBackend
                     or MemoryQueueBackend)
    
    Example:
        >>> from doc_healing.queue.factory import get_queue_backend
        >>> queue = get_queue_backend()
        >>> task = queue.enqueue('webhooks', process_webhook, payload)
    
    Note:
        The backend selection is based on the DOC_HEALING_QUEUE_BACKEND
        environment variable. In lightweight mode, this is typically set to
        'memory' for reduced resource usage.
    """
    global _queue_backend
    
    if _queue_backend is None:
        settings = get_settings()
        
        if settings.queue_backend == QueueBackendEnum.REDIS:
            # Lazy import to avoid Windows fork context issues
            from doc_healing.queue.redis_backend import RedisQueueBackend
            logger.info("Initializing Redis queue backend")
            _queue_backend = RedisQueueBackend()
        else:  # QueueBackendEnum.MEMORY
            # Lazy import for consistency
            from doc_healing.queue.memory_backend import MemoryQueueBackend
            logger.info("Initializing in-memory queue backend")
            _queue_backend = MemoryQueueBackend()
        
        logger.info(
            f"Queue backend initialized: {settings.queue_backend.value} "
            f"(deployment_mode={settings.deployment_mode.value})"
        )
    
    return _queue_backend


def reset_queue_backend() -> None:
    """Reset the queue backend singleton instance.
    
    This function is primarily used for testing purposes to allow switching
    between different queue backends within the same process. It should not
    be called during normal application operation.
    
    Warning:
        Calling this function will discard the current queue backend instance,
        potentially losing any in-flight tasks in memory-based queues.
    """
    global _queue_backend
    
    if _queue_backend is not None:
        # Lazy import for type checking
        from doc_healing.queue.memory_backend import MemoryQueueBackend
        
        # Gracefully shutdown memory backend if applicable
        if isinstance(_queue_backend, MemoryQueueBackend):
            _queue_backend.shutdown()
        
        logger.info("Queue backend instance reset")
        _queue_backend = None
