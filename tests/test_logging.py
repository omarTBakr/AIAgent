"""Every activity has to log through Temporal's activity.logger, so the records
carry activity context (workflow id, activity type, attempt) when a worker runs."""

import logging

import pytest
from temporalio.testing import ActivityEnvironment

from activities import ALL_ACTIVITIES, download_md, download_pdf, parse_pdf, upload_md, upload_pdf
from exceptions import ObjectNotFoundError
from schemas.download_md import DownloadMdInput
from schemas.download_pdf import DownloadPdfInput
from schemas.parse_pdf import ParsePdfInput
from schemas.upload_md import UploadMdInput
from schemas.upload_pdf import UploadPdfInput
from utils import logger as logger_module
from utils.logger import get_logger, setup_logging


@pytest.fixture
def env():
    return ActivityEnvironment()


@pytest.fixture
def sample_pdf_on_disk(pdf_bytes, tmp_path):
    source = tmp_path / "report.pdf"
    source.write_bytes(pdf_bytes)
    return source


async def test_upload_pdf_logs(env, s3, caplog, sample_pdf_on_disk):
    with caplog.at_level(logging.INFO):
        await env.run(upload_pdf, UploadPdfInput(local_path=str(sample_pdf_on_disk), key="report.pdf"))

    assert any("uploading pdf" in r.message for r in caplog.records)
    assert any("uploaded pdf" in r.message for r in caplog.records)


async def test_download_pdf_logs(env, s3, settings, pdf_bytes, caplog):
    s3.objects[(settings.s3_pdf_bucket, "report.pdf")] = pdf_bytes

    with caplog.at_level(logging.INFO):
        await env.run(download_pdf, DownloadPdfInput(key="report.pdf"))

    assert any("downloaded pdf to" in r.message for r in caplog.records)


async def test_parse_pdf_logs(env, caplog, sample_pdf_on_disk):
    with caplog.at_level(logging.INFO):
        await env.run(parse_pdf, ParsePdfInput(local_path=str(sample_pdf_on_disk)))

    assert any("parsing pdf" in r.message for r in caplog.records)


async def test_upload_md_logs(env, s3, caplog):
    with caplog.at_level(logging.INFO):
        await env.run(upload_md, UploadMdInput(markdown="# heading", key="report.md"))

    assert any("uploaded markdown" in r.message for r in caplog.records)


async def test_download_md_logs(env, s3, settings, caplog):
    s3.objects[(settings.s3_parsed_mds, "report.md")] = b"# heading"

    with caplog.at_level(logging.INFO):
        await env.run(download_md, DownloadMdInput(key="report.md"))

    assert any("downloaded markdown to" in r.message for r in caplog.records)


async def test_activities_log_through_the_temporal_logger(env, s3, caplog, sample_pdf_on_disk):
    """temporalio.activity is the logger name that carries activity context."""
    with caplog.at_level(logging.INFO):
        await env.run(upload_pdf, UploadPdfInput(local_path=str(sample_pdf_on_disk), key="report.pdf"))

    assert any(r.name.startswith("temporalio.activity") for r in caplog.records)


async def test_a_failing_activity_logs_the_exception(env, s3, caplog):
    """The download has nothing to fetch, so it must log and re-raise."""
    with caplog.at_level(logging.ERROR), pytest.raises(ObjectNotFoundError):
        await env.run(download_md, DownloadMdInput(key="missing.md"))

    assert any(r.levelno == logging.ERROR for r in caplog.records)
    assert any("failed to download markdown" in r.message for r in caplog.records)


@pytest.mark.parametrize("fn", ALL_ACTIVITIES)
async def test_every_activity_emits_at_least_one_log_line(fn):
    """Guards against a new activity being added without logging."""
    import inspect

    source = inspect.getsource(fn)
    assert "activity.logger" in source


def test_setup_logging_uses_the_configured_level(settings, monkeypatch):
    monkeypatch.setattr(logger_module, "_configured", False)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setattr("utils.config._settings_instance", None)

    setup_logging()

    assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_is_idempotent(settings, monkeypatch):
    monkeypatch.setattr(logger_module, "_configured", False)
    setup_logging()
    setup_logging()

    assert logger_module._configured is True


def test_get_logger_returns_a_named_logger():
    assert get_logger("aiagent.test").name == "aiagent.test"
