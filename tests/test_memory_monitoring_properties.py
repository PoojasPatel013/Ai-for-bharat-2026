"""Property-based tests for memory metrics logging."""

import pytest
from hypothesis import given, settings, HealthCheck, strategies as st
from unittest.mock import patch, MagicMock
from doc_healing.monitoring.memory import get_memory_usage, log_memory_usage

# Strategy to generate simulated memory usage values
memory_st = st.fixed_dictionaries({
    "rss": st.integers(min_value=0, max_value=16 * 1024 * 1024 * 1024),
    "vms": st.integers(min_value=0, max_value=32 * 1024 * 1024 * 1024),
    "percent": st.floats(min_value=0.0, max_value=100.0),
    "available_system": st.integers(min_value=0, max_value=64 * 1024 * 1024 * 1024),
    "total_system": st.integers(min_value=1, max_value=128 * 1024 * 1024 * 1024)
})

import logging

@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(memory_dict=memory_st)
def test_property_memory_metrics_logging(memory_dict, caplog):
    """Property 11: Memory Metrics Logging."""
    caplog.set_level(logging.INFO)
    with patch('doc_healing.monitoring.memory.get_memory_usage', return_value=memory_dict):
        log_memory_usage("test_context")
        assert "Memory Usage [test_context]:" in caplog.text
        assert str(round(memory_dict["percent"], 2)) in caplog.text
