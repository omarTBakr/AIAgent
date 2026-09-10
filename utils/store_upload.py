import asyncio
from typing import NamedTuple

from exceptions.validation import EmptyFileError, UnsupportedFileTypeError
from utils.config import Settings
from utils.logger import get_logger
from utils.utility import build_run_artifacts, upload_s3_file

logger = get_logger(__name__)


class StoredUpload(NamedTuple):
    """A PDF that is now in the bucket and ready for a workflow to pick up."""

    task_id: str
    pdf_key: str
    md_key: str
    local_pdf: str


def validate_upload(filename: str | None, pdf: bytes) -> None:
    """
    Rejects anything the pipeline cannot process.

    Raises ValidationError subclasses, which the HTTP layer turns into 400s.
    """
    if not (filename or "").lower().endswith(".pdf"):
        raise UnsupportedFileTypeError("only .pdf files are accepted")

    if not pdf:
        raise EmptyFileError("uploaded file is empty")


async def store_upload(pdf: bytes, filename: str, settings: Settings) -> StoredUpload:
    """
    Writes the PDF to the local scratch folder and uploads it to the PDF bucket.

    This happens before the workflow starts so the document never travels
    through the workflow history; the workflow is given keys, not bytes.
    """
    task_id, pdf_key, md_key, local_pdf = build_run_artifacts(filename, settings)

    # blocking work, kept off the event loop
    await asyncio.to_thread(local_pdf.write_bytes, pdf)
    await asyncio.to_thread(upload_s3_file, local_pdf, settings.s3_pdf_bucket, pdf_key)

    logger.info("[task %s] stored %s/%s", task_id, settings.s3_pdf_bucket, pdf_key)

    return StoredUpload(task_id=task_id, pdf_key=pdf_key, md_key=md_key, local_pdf=str(local_pdf))
