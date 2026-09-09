from temporalio import activity

from schemas.upload_pdf import UploadPdfInput, UploadPdfOutput
from utils.config import get_setting
from utils.utility import upload_s3_file


@activity.defn
async def upload_pdf(payload: UploadPdfInput) -> UploadPdfOutput:
    """Uploads a local PDF into the PDF bucket."""
    settings = get_setting()

    activity.logger.info("uploading pdf %s -> %s/%s", payload.local_path, settings.s3_pdf_bucket, payload.key)

    try:
        key = upload_s3_file(payload.local_path, settings.s3_pdf_bucket, payload.key)
    except Exception:
        activity.logger.exception("failed to upload pdf %s", payload.key)
        raise

    activity.logger.info("uploaded pdf %s/%s", settings.s3_pdf_bucket, key)

    return UploadPdfOutput(bucket=settings.s3_pdf_bucket, key=key)
