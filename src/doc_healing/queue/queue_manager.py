"""Queue manager for webhook event processing."""

from typing import Optional
from rq import Queue
from rq.job import Job
from doc_healing.queue.redis_client import get_redis_client


class QueueManager:
    """Manages event queues with Redis Queue."""

    def __init__(self) -> None:
        """Initialize queue manager."""
        self.redis_client = get_redis_client()
        self.webhook_queue = Queue("webhooks", connection=self.redis_client)
        self.validation_queue = Queue("validation", connection=self.redis_client)
        self.healing_queue = Queue("healing", connection=self.redis_client)

    def enqueue_webhook(self, func: callable, *args, **kwargs) -> Job:
        """Enqueue a webhook processing job."""
        return self.webhook_queue.enqueue(func, *args, **kwargs)

    def enqueue_validation(self, func: callable, *args, **kwargs) -> Job:
        """Enqueue a validation job."""
        return self.validation_queue.enqueue(func, *args, **kwargs)

    def enqueue_healing(self, func: callable, *args, **kwargs) -> Job:
        """Enqueue a healing job."""
        return self.healing_queue.enqueue(func, *args, **kwargs)

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return Job.fetch(job_id, connection=self.redis_client)

    def get_queue_length(self, queue_name: str) -> int:
        """Get the length of a queue."""
        queue = Queue(queue_name, connection=self.redis_client)
        return len(queue)


# Global queue manager instance
_queue_manager: Optional[QueueManager] = None


def get_queue_manager() -> QueueManager:
    """Get or create queue manager instance."""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = QueueManager()
    return _queue_manager
