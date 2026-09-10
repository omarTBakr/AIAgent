"""Response bodies for the process endpoints, in one place so POST and GET
report the same task the same way."""

from enums.TaskStatus import TaskStatus
from schemas.process_pdf_result import ProcessPdfResult
from utils.store_upload import StoredUpload
from utils.workflow_ids import workflow_id_for


def accepted_response(stored: StoredUpload, pdf_bucket: str) -> dict:
    """The 202 body: what was stored, and the id to poll with."""
    return {
        "status": TaskStatus.PROCESSING.value,
        "task_id": stored.task_id,
        "workflow_id": workflow_id_for(stored.task_id),
        "pdf_bucket": pdf_bucket,
        "pdf_key": stored.pdf_key,
        "md_key": stored.md_key,
    }


def completed_response(result: ProcessPdfResult) -> dict:
    """The finished task, as both endpoints report it."""
    return {
        "status": TaskStatus.COMPLETED.value,
        "task_id": result.task_id,
        "workflow_id": result.workflow_id,
        "pdf_bucket": result.pdf_bucket,
        "pdf_key": result.pdf_key,
        "md_bucket": result.md_bucket,
        "md_key": result.md_key,
        "local_pdf": result.local_pdf,
        "local_md": result.local_md,
        "markdown_characters": result.markdown_characters,
    }


def status_response(task_id: str, status: TaskStatus) -> dict:
    """A task that is either still running or ended without a result."""
    return {
        "status": status.value,
        "task_id": task_id,
        "workflow_id": workflow_id_for(task_id),
    }
