"""Memory monitoring utilities.

This module provides tools for tracking and logging memory usage
across different deployment modes, allowing validation of the lightweight
mode's resource constraints.
"""

import logging
import os
import psutil
from typing import Dict, Union

logger = logging.getLogger(__name__)

def get_memory_usage() -> Dict[str, Union[int, float]]:
    """Get current memory usage statistics.
    
    Returns:
        Dictionary containing memory metrics:
        - rss: Resident Set Size (bytes)
        - vms: Virtual Memory Size (bytes)
        - percent: Percentage of total memory used
        - available_system: Available system memory (bytes)
        - total_system: Total system memory (bytes)
    """
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    sys_mem = psutil.virtual_memory()
    
    return {
        "rss": mem_info.rss,
        "vms": mem_info.vms,
        "percent": process.memory_percent(),
        "available_system": sys_mem.available,
        "total_system": sys_mem.total
    }

def log_memory_usage(context: str = "general") -> None:
    """Log current memory usage with context.
    
    Args:
        context: String identifying where/why memory is being logged
    """
    metrics = get_memory_usage()
    
    # Convert bytes to MB for readable logging
    rss_mb = metrics["rss"] / (1024 * 1024)
    vms_mb = metrics["vms"] / (1024 * 1024)
    percent = round(metrics["percent"], 2)
    
    logger.info(
        f"Memory Usage [{context}]: "
        f"RSS={rss_mb:.1f}MB, VMS={vms_mb:.1f}MB, "
        f"Process Percent={percent}%"
    )
