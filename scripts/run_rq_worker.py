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
from rq.cli import worker as rq_worker_cli
from click.testing import CliRunner

def main():
    # Calling get_settings() initializes the global configuration
    # which includes authenticating with AWS Secrets Manager and overriding vars
    settings = get_settings()
    
    # We must explicitly set the redis URL for the RQ CLI format
    if settings.redis_url:
        redis_url = settings.redis_url
        print(f"Starting RQ Worker connecting to Redis URL")
    else:
        redis_url = f"redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}"
        print(f"Starting RQ Worker connecting to {settings.redis_host}:{settings.redis_port}")
    
    # The arguments to pass to rq worker. We extract them from sys.argv
    # Typically this is called as: python scripts/run_rq_worker.py webhooks validation healing
    queues = sys.argv[1:] if len(sys.argv) > 1 else ["webhooks", "validation", "healing"]
    
    args = queues + ["--url", redis_url]
    
    try:
        # Re-map sys.argv so click picks up the right arguments
        sys.argv = ["rq", "worker"] + args
        rq_worker_cli()
    except SystemExit as e:
        # rq_worker_cli calls sys.exit() when it's done
        sys.exit(e.code)
    except Exception as e:
        print(f"Error running RQ worker: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
