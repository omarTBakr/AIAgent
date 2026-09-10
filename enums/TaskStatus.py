from enum import Enum

from temporalio.client import WorkflowExecutionStatus


class TaskStatus(Enum):
    """
    The states a task can be reported in.

    Temporal owns the real state; this is the vocabulary the API speaks, so a
    change in Temporal's enum does not leak into responses.
    """

    PROCESSING = "processing"
    AWAITING_HUMAN = "awaiting_human"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"
    TERMINATED = "terminated"
    TIMED_OUT = "timed_out"
    CONTINUED_AS_NEW = "continued_as_new"

    @classmethod
    def from_temporal(cls, status: WorkflowExecutionStatus) -> "TaskStatus":
        """Translates a Temporal execution status into ours."""
        if status == WorkflowExecutionStatus.RUNNING:
            # "running" is Temporal's word; the caller cares that it is not done yet
            return cls.PROCESSING

        return cls[status.name]

    @property
    def is_finished(self) -> bool:
        return self not in _IN_PROGRESS


# AWAITING_HUMAN never comes from Temporal; the workflow query reports it, and
# the task is still running while it waits.
_IN_PROGRESS = (TaskStatus.PROCESSING, TaskStatus.AWAITING_HUMAN)
