#!/usr/bin/env python3
"""Run RQ worker with AWS Secrets Manager backend context.

This script loads the correct configuration including REDIS_HOST from Secrets Manager,
and then directly invokes the RQ worker logic so that it connects to the right Redis instance.
"""

import sys
import os
import logging

# Add the src directory to the path so doc_healing imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

from doc_healing.config import get_settings
from redis import Redis
from rq import Worker, Queue, Connection

def main():
    # Calling get_settings() initializes the global configuration
    # which includes authenticating with AWS Secrets Manager and overriding vars
    settings = get_settings()
    
    if settings.redis_url:
        redis_url = settings.redis_url
        print(f"Starting RQ Worker connecting to Redis URL")
    else:
        redis_url = f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
        print(f"Starting RQ Worker connecting to {settings.redis_host}:{settings.redis_port}")
    
    # The arguments to pass to rq worker. We extract them from sys.argv
    # Typically this is called as: python scripts/run_rq_worker.py webhooks validation healing
    queues = sys.argv[1:] if len(sys.argv) > 1 else ["webhooks", "validation", "healing"]
    
    try:
        redis_conn = Redis.from_url(redis_url)
        with Connection(redis_conn):
            worker = Worker(queues)
            worker.work()
    except Exception as e:
        print(f"Error running RQ worker: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
