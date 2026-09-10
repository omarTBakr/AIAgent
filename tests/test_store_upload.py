import pytest

from exceptions.validation import EmptyFileError, UnsupportedFileTypeError
from utils.store_upload import store_upload, validate_upload


def test_validate_accepts_a_pdf():
    validate_upload("report.pdf", b"%PDF-1.4")


def test_validate_is_case_insensitive():
    validate_upload("REPORT.PDF", b"%PDF-1.4")


def test_validate_rejects_a_non_pdf():
    with pytest.raises(UnsupportedFileTypeError):
        validate_upload("notes.txt", b"hello")


def test_validate_rejects_a_missing_filename():
    with pytest.raises(UnsupportedFileTypeError):
        validate_upload(None, b"%PDF-1.4")


def test_validate_rejects_empty_bytes():
    with pytest.raises(EmptyFileError):
        validate_upload("report.pdf", b"")


async def test_store_writes_the_pdf_locally(s3, settings, pdf_bytes):
    from pathlib import Path

    stored = await store_upload(pdf_bytes, "report.pdf", settings)

    assert Path(stored.local_pdf).read_bytes() == pdf_bytes
    assert Path(stored.local_pdf).parent == settings.temp_pdf_path


async def test_store_uploads_to_the_pdf_bucket(s3, settings, pdf_bytes):
    stored = await store_upload(pdf_bytes, "report.pdf", settings)

    assert s3.objects[(settings.s3_pdf_bucket, stored.pdf_key)] == pdf_bytes


async def test_store_does_not_touch_the_markdown_bucket(s3, settings, pdf_bytes):
    """Only the workflow writes markdown."""
    await store_upload(pdf_bytes, "report.pdf", settings)

    assert not any(bucket == settings.s3_parsed_mds for bucket, _ in s3.objects)


async def test_the_task_id_ties_both_keys_together(s3, settings, pdf_bytes):
    stored = await store_upload(pdf_bytes, "report.pdf", settings)

    assert stored.task_id in stored.pdf_key
    assert stored.task_id in stored.md_key


async def test_two_uploads_do_not_collide(s3, settings, pdf_bytes):
    first = await store_upload(pdf_bytes, "report.pdf", settings)
    second = await store_upload(pdf_bytes, "report.pdf", settings)

    assert first.task_id != second.task_id
    assert first.pdf_key != second.pdf_key
