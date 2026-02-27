#!/usr/bin/env python3
"""Run unified worker for processing all queue types.

This script starts the unified worker that handles webhook, validation,
and healing tasks from all queue types. It supports both synchronous
and asynchronous processing modes based on configuration.

Usage:
    python scripts/run_unified_worker.py

Configuration is loaded from environment variables with DOC_HEALING_ prefix.
See .env.example for available configuration options.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from doc_healing.workers.unified import main


if __name__ == "__main__":
    main()
