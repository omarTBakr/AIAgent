"""The hierarchy is only useful if the subtype relationships actually hold and
the code raises the specific types rather than bare builtins."""

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

import utils.utility
from exceptions import (
    AIAgentError,
    ConfigurationError,
    DownloadError,
    EmptyFileError,
    InvalidPdfError,
    LocalFileNotFoundError,
    ObjectNotFoundError,
    ParsingError,
    PdfNotFoundError,
    StorageConnectionError,
    StorageError,
    UnsupportedFileTypeError,
    UploadError,
    ValidationError,
    WorkflowError,
)
from parsers.pymupdf_parser import parse_pdf
from utils.utility import download_s3_file, upload_s3_file

DOMAINS = [ConfigurationError, ValidationError, StorageError, ParsingError, WorkflowError]

SUBTYPES = [
    (UploadError, StorageError),
    (DownloadError, StorageError),
    (ObjectNotFoundError, DownloadError),
    (StorageConnectionError, StorageError),
    (LocalFileNotFoundError, StorageError),
    (PdfNotFoundError, ParsingError),
    (InvalidPdfError, ParsingError),
    (UnsupportedFileTypeError, ValidationError),
    (EmptyFileError, ValidationError),
]


@pytest.mark.parametrize("domain", DOMAINS)
def test_every_domain_descends_from_the_root(domain):
    assert issubclass(domain, AIAgentError)


@pytest.mark.parametrize("child,parent", SUBTYPES)
def test_subtype_relationships(child, parent):
    assert issubclass(child, parent)


@pytest.mark.parametrize("child,parent", SUBTYPES)
def test_catching_the_root_catches_everything(child, parent):
    with pytest.raises(AIAgentError):
        raise child("boom")


def test_object_not_found_is_caught_as_a_download_error():
    """A caller that only cares 'the download failed' should not need the leaf type."""
    with pytest.raises(DownloadError):
        raise ObjectNotFoundError("missing")


def test_local_file_not_found_is_also_a_builtin_file_not_found():
    """Keeps callers that catch the builtin working."""
    assert issubclass(LocalFileNotFoundError, FileNotFoundError)
    with pytest.raises(FileNotFoundError):
        raise LocalFileNotFoundError("gone")


def test_pdf_not_found_is_also_a_builtin_file_not_found():
    assert issubclass(PdfNotFoundError, FileNotFoundError)


def test_storage_and_parsing_do_not_overlap():
    assert not issubclass(StorageError, ParsingError)
    assert not issubclass(ParsingError, StorageError)


def test_upload_of_a_missing_file_raises_local_file_not_found(s3, tmp_path):
    with pytest.raises(LocalFileNotFoundError):
        upload_s3_file(tmp_path / "nope.pdf", "test-pdfs", "nope.pdf")


def test_download_of_a_missing_key_raises_object_not_found(s3, tmp_path):
    with pytest.raises(ObjectNotFoundError):
        download_s3_file("test-mds", "missing.md", tmp_path)


def test_a_client_error_on_upload_becomes_an_upload_error(s3, monkeypatch, tmp_path):
    source = tmp_path / "a.pdf"
    source.write_bytes(b"x")

    def explode(*args, **kwargs):
        raise ClientError({"Error": {"Code": "AccessDenied", "Message": "nope"}}, "PutObject")

    monkeypatch.setattr(s3, "upload_file", explode)

    with pytest.raises(UploadError):
        upload_s3_file(source, "test-pdfs", "a.pdf")


def test_an_unreachable_endpoint_becomes_a_connection_error(s3, monkeypatch):
    def explode(*args, **kwargs):
        raise EndpointConnectionError(endpoint_url="https://s3.example.com")

    monkeypatch.setattr(s3, "put_object", explode)

    with pytest.raises(StorageConnectionError):
        upload_s3_file(b"x", "test-pdfs", "a.pdf")


def test_a_non_404_client_error_on_download_stays_a_download_error(s3, monkeypatch, tmp_path):
    def explode(*args, **kwargs):
        raise ClientError({"Error": {"Code": "AccessDenied", "Message": "nope"}}, "GetObject")

    monkeypatch.setattr(s3, "download_file", explode)

    with pytest.raises(DownloadError) as caught:
        download_s3_file("test-mds", "a.md", tmp_path)

    assert not isinstance(caught.value, ObjectNotFoundError)


def test_parsing_a_missing_file_raises_pdf_not_found(tmp_path):
    with pytest.raises(PdfNotFoundError):
        parse_pdf(tmp_path / "nope.pdf")


def test_parsing_junk_bytes_raises_invalid_pdf():
    with pytest.raises(InvalidPdfError):
        parse_pdf(b"this is definitely not a pdf")


def test_the_original_error_is_kept_as_the_cause(s3, tmp_path):
    """`raise ... from exc` keeps the boto3 error attached for debugging."""
    with pytest.raises(ObjectNotFoundError) as caught:
        download_s3_file("test-mds", "missing.md", tmp_path)

    assert isinstance(caught.value.__cause__, ClientError)


def test_exceptions_package_exports_match_the_module(s3):
    import exceptions

    for name in exceptions.__all__:
        assert hasattr(exceptions, name), name
    assert utils.utility.ObjectNotFoundError is exceptions.ObjectNotFoundError
