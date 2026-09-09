from temporalio import activity

from schemas.download_pdf import DownloadPdfInput, DownloadPdfOutput
from utils.config import get_setting
from utils.utility import download_s3_file


@activity.defn
async def download_pdf(payload: DownloadPdfInput) -> DownloadPdfOutput:
    """Downloads a PDF from the PDF bucket into the local PDF scratch folder."""
    settings = get_setting()

    activity.logger.info("downloading pdf %s/%s", settings.s3_pdf_bucket, payload.key)

    try:
        local_path = download_s3_file(settings.s3_pdf_bucket, payload.key, settings.temp_pdf_path)
    except Exception:
        activity.logger.exception("failed to download pdf %s", payload.key)
        raise

    activity.logger.info("downloaded pdf to %s", local_path)

    return DownloadPdfOutput(local_path=str(local_path))
