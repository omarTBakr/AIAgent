import asyncio

from fastapi import APIRouter, File, HTTPException, UploadFile
from temporalio.exceptions import ApplicationError
from temporalio.service import RPCError

from exceptions import AIAgentError, ParsingError, StorageError, ValidationError
from exceptions.validation import EmptyFileError, UnsupportedFileTypeError
from exceptions.workflow import TemporalConnectionError, WorkflowExecutionError
from schemas.process_pdf import ProcessPdfInput
from utils.config import get_setting
from utils.logger import get_logger
from utils.temporal_client import get_temporal_client
from utils.utility import build_run_artifacts, upload_s3_file
from workflows.workflow_process_pdf import ProcessPdfWorkflow

router = APIRouter()

logger = get_logger(__name__)


@router.post("/process")
async def process(file: UploadFile = File(...)) -> dict:
    """
    Accepts a PDF upload, stores it, then runs it through the Temporal
    workflow and reports where the original and the parsed Markdown ended up.

    The PDF is uploaded here rather than inside the workflow so the document
    never travels through the workflow history.
    """
    settings = get_setting()

    try:
        if not (file.filename or "").lower().endswith(".pdf"):
            raise UnsupportedFileTypeError("only .pdf files are accepted")

        pdf = await file.read()
        if not pdf:
            raise EmptyFileError("uploaded file is empty")

        task_id, pdf_key, md_key, local_pdf = build_run_artifacts(file.filename, settings)

        await asyncio.to_thread(local_pdf.write_bytes, pdf)
        await asyncio.to_thread(upload_s3_file, local_pdf, settings.s3_pdf_bucket, pdf_key)

        client = await get_temporal_client()

        result = await client.execute_workflow(
            ProcessPdfWorkflow.run,
            ProcessPdfInput(task_id=task_id, pdf_key=pdf_key, md_key=md_key),
            id=f"process-pdf-{task_id}",
            task_queue=settings.temporal_task_queue,
        )

    except ValidationError as exc:
        # the caller sent something unusable
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ParsingError as exc:
        # a real PDF was sent but could not be read: unprocessable, not a server fault
        logger.warning("could not parse %s: %s", file.filename, exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StorageError as exc:
        logger.error("storage failed for %s: %s", file.filename, exc)
        raise HTTPException(status_code=502, detail=f"storage error: {exc}") from exc
    except (TemporalConnectionError, RPCError) as exc:
        logger.error("temporal unreachable for %s: %s", file.filename, exc)
        raise HTTPException(status_code=503, detail=f"temporal unavailable: {exc}") from exc
    except (WorkflowExecutionError, ApplicationError) as exc:
        logger.exception("workflow failed for %s", file.filename)
        raise HTTPException(status_code=500, detail=f"workflow failed: {exc}") from exc
    except AIAgentError as exc:
        logger.exception("pipeline failed for %s", file.filename)
        raise HTTPException(status_code=500, detail=f"processing failed: {exc}") from exc
    except Exception as exc:
        # anything unplanned is a bug; log it with a traceback
        logger.exception("unexpected failure for %s", file.filename)
        raise HTTPException(status_code=500, detail=f"processing failed: {exc}") from exc

    return {
        "status": "ok",
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
