import pytest
from temporalio.client import WorkflowExecutionStatus

from enums.TaskStatus import TaskStatus


@pytest.mark.parametrize(
    "temporal_status,expected",
    [
        (WorkflowExecutionStatus.RUNNING, TaskStatus.PROCESSING),
        (WorkflowExecutionStatus.COMPLETED, TaskStatus.COMPLETED),
        (WorkflowExecutionStatus.FAILED, TaskStatus.FAILED),
        (WorkflowExecutionStatus.CANCELED, TaskStatus.CANCELED),
        (WorkflowExecutionStatus.TERMINATED, TaskStatus.TERMINATED),
        (WorkflowExecutionStatus.TIMED_OUT, TaskStatus.TIMED_OUT),
        (WorkflowExecutionStatus.CONTINUED_AS_NEW, TaskStatus.CONTINUED_AS_NEW),
    ],
)
def test_every_temporal_status_maps(temporal_status, expected):
    assert TaskStatus.from_temporal(temporal_status) is expected


def test_running_is_reported_as_processing():
    """'running' is Temporal's word; the API says 'processing'."""
    assert TaskStatus.from_temporal(WorkflowExecutionStatus.RUNNING).value == "processing"


@pytest.mark.parametrize("status", list(WorkflowExecutionStatus))
def test_no_temporal_status_is_unmapped(status):
    """A new state in Temporal's enum must not blow up the status endpoint."""
    assert isinstance(TaskStatus.from_temporal(status), TaskStatus)


@pytest.mark.parametrize("status", list(TaskStatus))
def test_values_are_lowercase_strings(status):
    assert status.value == status.value.lower()


def test_only_processing_is_unfinished():
    assert TaskStatus.PROCESSING.is_finished is False
    for status in TaskStatus:
        if status is not TaskStatus.PROCESSING:
            assert status.is_finished is True
