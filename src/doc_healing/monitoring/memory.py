"""Memory monitoring utilities for lightweight deployment validation."""

import os
import psutil
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def get_memory_usage() -> Dict[str, Any]:
    """Get current memory usage metrics for the process.
    
    Returns:
        Dictionary containing memory metrics:
        - rss: Resident Set Size (bytes)
        - vms: Virtual Memory Size (bytes)
        - percent: Percentage of system memory used
        - available_system: Total available system memory (bytes)
    """
    try:
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        sys_mem = psutil.virtual_memory()
        
        metrics = {
            "rss": mem_info.rss,
            "vms": mem_info.vms,
            "percent": process.memory_percent(),
            "available_system": sys_mem.available,
            "total_system": sys_mem.total
        }
        
        return metrics
    except Exception as e:
        logger.error(f"Failed to get memory metrics: {str(e)}")
        return {}

def log_memory_usage(context: str = "current") -> None:
    """Log the current memory usage with standard formatting.
    
    Args:
        context: String to describe when/where this measurement was taken.
    """
    metrics = get_memory_usage()
    if metrics:
        rss_mb = metrics["rss"] / (1024 * 1024)
        logger.info(f"Memory Usage [{context}]: {rss_mb:.2f} MB RSS ({metrics['percent']:.2f}%)")
