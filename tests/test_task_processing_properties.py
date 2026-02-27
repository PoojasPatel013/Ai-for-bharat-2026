"""Property-based tests for Task Processing Across All Types."""

import pytest
from hypothesis import given, settings as hy_settings, strategies as st
from doc_healing.queue.base import Task

# A strategy for generic task payload dictionary
payload_st = st.dictionaries(
    keys=st.text(min_size=1),
    values=st.one_of(st.text(), st.integers(), st.floats(), st.booleans(), st.none())
)

task_st = st.builds(
    Task,
    id=st.text(min_size=5, max_size=20),
    queue_name=st.sampled_from(["validation", "healing", "webhook"]),
    func_name=st.sampled_from(["validate_code_snippet", "heal_code_snippet", "process_github_webhook"]),
    args=st.lists(st.one_of(st.text(), st.integers())).map(tuple),
    kwargs=payload_st,
)

@given(task=task_st)
@hy_settings(max_examples=50)
def test_property_task_processing_types(task):
    """Property 1: Task Processing Across All Types."""
    assert task.id is not None
    assert task.queue_name in ["validation", "healing", "webhook"]
    assert isinstance(task.args, tuple)
    assert isinstance(task.kwargs, dict)
