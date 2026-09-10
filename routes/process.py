import asyncio
from contextlib import contextmanager

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from temporalio.client import WorkflowExecutionStatus, WorkflowFailureError
from temporalio.exceptions import ApplicationError
from temporalio.service import RPCError, RPCStatusCode

from exceptions import AIAgentError, ParsingError, StorageError, ValidationError
from exceptions.validation import EmptyFileError, UnsupportedFileTypeError
from exceptions.workflow import TemporalConnectionError, WorkflowExecutionError
from schemas.process_pdf import ProcessPdfInput
from schemas.process_pdf_result import ProcessPdfResult
from utils.config import get_setting
from utils.logger import get_logger
from utils.temporal_client import get_temporal_client
from utils.utility import build_run_artifacts, upload_s3_file
from workflows.workflow_process_pdf import ProcessPdfWorkflow

router = APIRouter()

logger = get_logger(__name__)


def workflow_id_for(task_id: str) -> str:
    """One place that decides how a task id becomes a workflow id."""
    return f"process-pdf-{task_id}"


@contextmanager
def http_errors(context: str):
    """
    Maps the project's exceptions onto status codes.

    Shared by both endpoints so they cannot drift apart.
    """
    try:
        yield
    except ValidationError as exc:
        # the caller sent something unusable
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ParsingError as exc:
        # a real PDF was sent but could not be read: unprocessable, not a server fault
        logger.warning("could not parse %s: %s", context, exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StorageError as exc:
        logger.error("storage failed for %s: %s", context, exc)
        raise HTTPException(status_code=502, detail=f"storage error: {exc}") from exc
    except (TemporalConnectionError, RPCError) as exc:
        logger.error("temporal unreachable for %s: %s", context, exc)
        raise HTTPException(status_code=503, detail=f"temporal unavailable: {exc}") from exc
    except (WorkflowExecutionError, WorkflowFailureError, ApplicationError) as exc:
        logger.exception("workflow failed for %s", context)
        raise HTTPException(status_code=500, detail=f"workflow failed: {exc}") from exc
    except AIAgentError as exc:
        logger.exception("pipeline failed for %s", context)
        raise HTTPException(status_code=500, detail=f"processing failed: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        # anything unplanned is a bug; log it with a traceback
        logger.exception("unexpected failure for %s", context)
        raise HTTPException(status_code=500, detail=f"processing failed: {exc}") from exc


def _completed(result: ProcessPdfResult) -> dict:
    return {
        "status": "completed",
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


@router.post("/process")
async def process(response: Response, file: UploadFile = File(...), wait: bool = False) -> dict:
    """
    Accepts a PDF upload, stores it and starts the Temporal workflow.

    Returns 202 and a task id straight away; poll GET /process/{task_id} for
    the outcome. Pass `?wait=true` to hold the request open until the pipeline
    finishes and get the full result in one call instead.

    The PDF is uploaded here rather than inside the workflow so the document
    never travels through the workflow history.
    """
    settings = get_setting()

    with http_errors(file.filename or "<no filename>"):
        if not (file.filename or "").lower().endswith(".pdf"):
            raise UnsupportedFileTypeError("only .pdf files are accepted")

        pdf = await file.read()
        if not pdf:
            raise EmptyFileError("uploaded file is empty")

        task_id, pdf_key, md_key, local_pdf = build_run_artifacts(file.filename, settings)

        await asyncio.to_thread(local_pdf.write_bytes, pdf)
        await asyncio.to_thread(upload_s3_file, local_pdf, settings.s3_pdf_bucket, pdf_key)

        client = await get_temporal_client()

        handle = await client.start_workflow(
            ProcessPdfWorkflow.run,
            ProcessPdfInput(task_id=task_id, pdf_key=pdf_key, md_key=md_key),
            id=workflow_id_for(task_id),
            task_queue=settings.temporal_task_queue,
        )

        logger.info("[task %s] started %s", task_id, handle.id)

        if wait:
            return _completed(await handle.result())

    response.status_code = 202
    return {
        "status": "processing",
        "task_id": task_id,
        "workflow_id": handle.id,
        "pdf_bucket": settings.s3_pdf_bucket,
        "pdf_key": pdf_key,
        "md_key": md_key,
    }


@router.get("/process/{task_id}")
async def process_status(task_id: str) -> dict:
    """
    Reports where a task got to.

    `processing` while it runs, `completed` with the full result once it is
    done, and the terminal state's name (`failed`, `terminated`, `timed_out`,
    `canceled`) otherwise. Temporal holds the state, so nothing is stored here.
    """
    with http_errors(f"task {task_id}"):
        client = await get_temporal_client()
        # the typed handle knows the workflow's return type, so result() decodes
        # into a ProcessPdfResult instead of a plain dict
        handle = client.get_workflow_handle_for(ProcessPdfWorkflow.run, workflow_id_for(task_id))

        try:
            description = await handle.describe()
        except RPCError as exc:
            if exc.status == RPCStatusCode.NOT_FOUND:
                raise HTTPException(status_code=404, detail=f"no such task: {task_id}") from exc
            raise

        if description.status == WorkflowExecutionStatus.COMPLETED:
            return _completed(await handle.result())

        if description.status == WorkflowExecutionStatus.RUNNING:
            return {"status": "processing", "task_id": task_id, "workflow_id": handle.id}

        return {
            "status": description.status.name.lower(),
            "task_id": task_id,
            "workflow_id": handle.id,
        }
