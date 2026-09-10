from fastapi import APIRouter, Body, File, HTTPException, Response, UploadFile
from temporalio.service import RPCError, RPCStatusCode

from enums.TaskStatus import TaskStatus
from exceptions.validation import TooManyFilesError
from schemas.legal_review import LegalReviewInput
from utils.config import get_setting
from utils.http_errors import http_errors
from utils.legal_responses import (
    accepted_response,
    answer_accepted_response,
    completed_response,
    running_response,
    status_response,
)
from utils.logger import get_logger
from utils.store_upload import store_uploads, validate_upload
from utils.temporal_client import get_temporal_client
from utils.workflow_ids import legal_workflow_id_for
from workflows.workflow_legal_review import LegalReviewWorkflow

router = APIRouter(prefix="/legal", tags=["legal"])

logger = get_logger(__name__)

ACCEPTED = 202


@router.post("")
async def submit(response: Response, files: list[UploadFile] = File(...)) -> dict:
    """
    Accepts several PDFs, stores them and starts the legal review workflow.

    Returns 202 and a task id straight away; poll GET /legal/{task_id}, which
    reports `awaiting_human` when the model has a question for you.
    """
    settings = get_setting()

    with http_errors(f"{len(files)} document(s)"):
        if len(files) > settings.legal_max_pdfs:
            raise TooManyFilesError(f"at most {settings.legal_max_pdfs} documents per request, got {len(files)}")

        uploads = []
        for upload in files:
            pdf = await upload.read()
            validate_upload(upload.filename, pdf)
            uploads.append((upload.filename, pdf))

        task_id, pdf_keys = await store_uploads(uploads, settings)

        client = await get_temporal_client()
        handle = await client.start_workflow(
            LegalReviewWorkflow.run,
            LegalReviewInput(
                task_id=task_id,
                pdf_keys=pdf_keys,
                pages_per_batch=settings.legal_pages_per_batch,
                max_concurrent_pdfs=settings.legal_max_concurrent_pdfs,
                human_input_timeout_seconds=settings.human_input_timeout_seconds,
            ),
            id=legal_workflow_id_for(task_id),
            task_queue=settings.legal_task_queue,
        )

        logger.info("[task %s] started %s for %d document(s)", task_id, handle.id, len(pdf_keys))

    response.status_code = ACCEPTED
    return accepted_response(task_id, pdf_keys, settings.s3_pdf_bucket)


@router.get("/{task_id}")
async def review_status(task_id: str) -> dict:
    """
    Reports where a review got to, and any question waiting on a human.

    Temporal holds the state, so nothing is stored here.
    """
    with http_errors(f"task {task_id}"):
        client = await get_temporal_client()

        # the typed handle knows the workflow's return type, so result() decodes
        # into a LegalReviewResult instead of a plain dict
        handle = client.get_workflow_handle_for(LegalReviewWorkflow.run, legal_workflow_id_for(task_id))

        try:
            description = await handle.describe()
        except RPCError as exc:
            if exc.status == RPCStatusCode.NOT_FOUND:
                raise HTTPException(status_code=404, detail=f"no such task: {task_id}") from exc
            raise

        status = TaskStatus.from_temporal(description.status)

        if status is TaskStatus.COMPLETED:
            return completed_response(await handle.result())

        if status is TaskStatus.PROCESSING:
            # queries reach the running workflow, so the questions are live
            questions = await handle.query(LegalReviewWorkflow.pending_questions)
            progress = await handle.query(LegalReviewWorkflow.progress)
            return running_response(task_id, progress, questions)

        return status_response(task_id, status)


@router.post("/{task_id}/respond")
async def respond(task_id: str, pdf_key: str = Body(..., embed=True), answer: str = Body(..., embed=True)) -> dict:
    """
    Answers the question the model raised about one document.

    The workflow is waiting on this signal; sending it releases that document
    and the advice is revised in light of the answer.
    """
    with http_errors(f"task {task_id}"):
        client = await get_temporal_client()
        handle = client.get_workflow_handle_for(LegalReviewWorkflow.run, legal_workflow_id_for(task_id))

        try:
            await handle.signal(LegalReviewWorkflow.human_response, args=[pdf_key, answer])
        except RPCError as exc:
            if exc.status == RPCStatusCode.NOT_FOUND:
                raise HTTPException(status_code=404, detail=f"no such task: {task_id}") from exc
            raise

        logger.info("[task %s] answer delivered for %s", task_id, pdf_key)

    return answer_accepted_response(task_id, pdf_key)
