from temporalio import activity

from schemas.upload_md import UploadMdInput, UploadMdOutput
from utils.config import get_setting
from utils.utility import upload_s3_file


@activity.defn
async def upload_md(payload: UploadMdInput) -> UploadMdOutput:
    """Uploads parsed Markdown into the parsed-markdown bucket."""
    settings = get_setting()

    activity.logger.info("[task %s] uploading markdown -> %s/%s", payload.task_id, settings.s3_parsed_mds, payload.key)

    try:
        key = upload_s3_file(payload.markdown.encode("utf-8"), settings.s3_parsed_mds, payload.key)
    except Exception:
        activity.logger.exception("[task %s] failed to upload markdown %s", payload.task_id, payload.key)
        raise

    activity.logger.info("[task %s] uploaded markdown %s/%s", payload.task_id, settings.s3_parsed_mds, key)

    return UploadMdOutput(bucket=settings.s3_parsed_mds, key=key)
