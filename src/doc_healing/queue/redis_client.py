"""Redis client configuration."""

import os
from redis import Redis
from typing import Optional

# Redis connection settings
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Global Redis client instance
redis_client: Optional[Redis] = None


def get_redis_client() -> Redis:
    """Get or create Redis client instance."""
    global redis_client
    if redis_client is None:
        redis_client = Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True,
        )
    return redis_client
