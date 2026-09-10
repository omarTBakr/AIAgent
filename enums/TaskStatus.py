from enum import Enum

from temporalio.client import WorkflowExecutionStatus


class TaskStatus(Enum):
    """
    The states a task can be reported in.

    Temporal owns the real state; this is the vocabulary the API speaks, so a
    change in Temporal's enum does not leak into responses.
    """

    PROCESSING = "processing"
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
        return self is not TaskStatus.PROCESSING
