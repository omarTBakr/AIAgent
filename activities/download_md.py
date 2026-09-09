from temporalio import activity

from schemas.download_md import DownloadMdInput, DownloadMdOutput
from utils.config import get_setting
from utils.utility import download_s3_file


@activity.defn
async def download_md(payload: DownloadMdInput) -> DownloadMdOutput:
    """Downloads Markdown from the parsed bucket into the local Markdown folder."""
    settings = get_setting()

    activity.logger.info("downloading markdown %s/%s", settings.s3_parsed_mds, payload.key)

    try:
        local_path = download_s3_file(settings.s3_parsed_mds, payload.key, settings.temp_md_path)
    except Exception:
        activity.logger.exception("failed to download markdown %s", payload.key)
        raise

    activity.logger.info("downloaded markdown to %s", local_path)

    return DownloadMdOutput(local_path=str(local_path))
