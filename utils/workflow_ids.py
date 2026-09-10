"""One place that decides how a task id becomes a workflow id.

The API and the status endpoint have to agree on this, and a task started
under one convention can only be found again under the same one.
"""

WORKFLOW_ID_PREFIX = "process-pdf-"


def workflow_id_for(task_id: str) -> str:
    """`a1b2c3d4` -> `process-pdf-a1b2c3d4`."""
    return f"{WORKFLOW_ID_PREFIX}{task_id}"


def task_id_from(workflow_id: str) -> str:
    """`process-pdf-a1b2c3d4` -> `a1b2c3d4`; unprefixed ids are returned as-is."""
    return workflow_id.removeprefix(WORKFLOW_ID_PREFIX)
