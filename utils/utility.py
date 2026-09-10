import uuid
from pathlib import Path
from typing import NamedTuple

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from exceptions.storage import (
    DownloadError,
    LocalFileNotFoundError,
    ObjectNotFoundError,
    StorageConnectionError,
    UploadError,
)
from utils.config import Settings, get_setting

_s3_client = None


def get_s3_client() -> BaseClient:
    """
    Returns a singleton boto3 S3 client pointed at the endpoint from .env.
    """
    global _s3_client
    if _s3_client is None:
        settings = get_setting()
        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
            config=Config(signature_version="s3v4"),
        )
    return _s3_client


def upload_s3_file(source: Path | str | bytes, bucket: str, key: str) -> str:
    """
    Uploads a local file (path) or raw bytes to `bucket` under `key`.

    Returns the key it was stored under.
    """
    client = get_s3_client()

    try:
        if isinstance(source, bytes):
            client.put_object(Bucket=bucket, Key=key, Body=source)
        else:
            source = Path(source)
            if not source.is_file():
                raise LocalFileNotFoundError(f"cannot upload, no such file: {source}")
            client.upload_file(str(source), bucket, key)
    except ClientError as exc:
        raise UploadError(f"could not upload {bucket}/{key}: {exc}") from exc
    except BotoCoreError as exc:
        raise StorageConnectionError(f"could not reach the object store: {exc}") from exc

    return key


def download_s3_file(bucket: str, key: str, destination: Path | str) -> Path:
    """
    Downloads `key` from `bucket` to `destination`.

    If `destination` is a directory the file keeps the basename of the key.
    Returns the path it was written to.
    """
    destination = Path(destination)

    if destination.is_dir():
        destination = destination / Path(key).name

    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        get_s3_client().download_file(bucket, key, str(destination))
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NoSuchBucket"):
            raise ObjectNotFoundError(f"no such object: {bucket}/{key}") from exc
        raise DownloadError(f"could not download {bucket}/{key}: {exc}") from exc
    except BotoCoreError as exc:
        raise StorageConnectionError(f"could not reach the object store: {exc}") from exc

    return destination


class RunArtifacts(NamedTuple):
    """Where one PDF's inputs and outputs live, for a single run."""

    task_id: str
    pdf_key: str
    md_key: str
    local_pdf: Path


def build_run_artifacts(filename: str, settings: Settings) -> RunArtifacts:
    """
    Derives the object keys and the local PDF path for one run.

    The pdf and the markdown share a random run id so that two uploads of the
    same filename cannot overwrite each other in the buckets. That same id is
    the task id: it names the workflow run and is logged by every activity.
    """
    stem = Path(filename).stem or "document"
    run_id = uuid.uuid4().hex[:8]
    pdf_key = f"{stem}-{run_id}.pdf"
    md_key = f"{stem}-{run_id}.md"

    return RunArtifacts(
        task_id=run_id,
        pdf_key=pdf_key,
        md_key=md_key,
        local_pdf=settings.temp_pdf_path / pdf_key,
    )
