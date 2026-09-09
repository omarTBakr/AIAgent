"""Temporal serialises activity arguments as JSON, so every schema has to be a
plain dataclass that survives a round trip through the data converter."""

import dataclasses

import pytest
from temporalio.converter import DataConverter

from schemas.download_md import DownloadMdInput, DownloadMdOutput
from schemas.download_pdf import DownloadPdfInput, DownloadPdfOutput
from schemas.parse_pdf import ParsePdfInput, ParsePdfOutput
from schemas.upload_md import UploadMdInput, UploadMdOutput
from schemas.upload_pdf import UploadPdfInput, UploadPdfOutput

SCHEMAS = [
    (UploadPdfInput, {"local_path": "/tmp/a.pdf", "key": "a.pdf"}),
    (UploadPdfOutput, {"bucket": "pdfs", "key": "a.pdf"}),
    (DownloadPdfInput, {"key": "a.pdf"}),
    (DownloadPdfOutput, {"local_path": "/tmp/a.pdf"}),
    (ParsePdfInput, {"local_path": "/tmp/a.pdf"}),
    (ParsePdfOutput, {"markdown": "# heading"}),
    (UploadMdInput, {"markdown": "# heading", "key": "a.md"}),
    (UploadMdOutput, {"bucket": "mds", "key": "a.md"}),
    (DownloadMdInput, {"key": "a.md"}),
    (DownloadMdOutput, {"local_path": "/tmp/a.md"}),
]


@pytest.mark.parametrize("schema,fields", SCHEMAS)
def test_is_a_dataclass(schema, fields):
    assert dataclasses.is_dataclass(schema)


@pytest.mark.parametrize("schema,fields", SCHEMAS)
async def test_survives_temporal_serialisation(schema, fields):
    instance = schema(**fields)
    converter = DataConverter.default

    payloads = await converter.encode([instance])
    decoded = await converter.decode(payloads, [schema])

    assert decoded[0] == instance


def test_stdlib_dataclasses_is_not_shadowed():
    """A top-level package named `dataclasses` would break pydantic and temporalio."""
    assert dataclasses.__file__.endswith("lib/python3.12/dataclasses.py")
