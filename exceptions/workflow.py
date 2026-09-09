from exceptions.base import AIAgentError


class WorkflowError(AIAgentError):
    """A step of the pipeline failed for a reason not covered above."""


class ActivityFailedError(WorkflowError):
    """A single activity failed and the pipeline cannot continue."""
