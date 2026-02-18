#!/usr/bin/env python3
"""Run RQ worker for processing jobs."""

import sys
import os
import argparse

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from rq import Worker
from doc_healing.queue.redis_client import get_redis_client


def main() -> None:
    """Run the worker."""
    parser = argparse.ArgumentParser(description="Run RQ worker")
    parser.add_argument(
        "queue",
        choices=["webhooks", "validation", "healing"],
        help="Queue to process",
    )
    args = parser.parse_args()

    redis_client = get_redis_client()
    worker = Worker([args.queue], connection=redis_client)
    
    print(f"Starting worker for queue: {args.queue}")
    worker.work()


if __name__ == "__main__":
    main()
