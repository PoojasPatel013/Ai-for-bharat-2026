"""Redis client configuration."""

import os
from redis import Redis
from typing import Optional

from doc_healing.config import get_settings

# Global Redis client instance
redis_client: Optional[Redis] = None


def get_redis_client() -> Redis:
    """Get or create Redis client instance."""
    global redis_client
    if redis_client is None:
        settings = get_settings()
        # Redis connection settings via central config
        redis_host = settings.redis_host
        redis_port = settings.redis_port
        redis_db = settings.redis_db
        redis_password = os.getenv("REDIS_PASSWORD", None) # Fallback if setting not defined

        redis_client = Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True,
        )
    return redis_client
