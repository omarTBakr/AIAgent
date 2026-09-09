import pymupdf
import pytest
from botocore.exceptions import ClientError

import utils.config
import utils.utility


@pytest.fixture(autouse=True)
def settings(tmp_path, monkeypatch):
    """
    Points every test at a throwaway scratch directory and fake credentials,
    so the suite never needs a real .env or a real bucket.

    TEMP_PD_DIR is absolute here, which pathlib lets take over from the project
    root that Settings.temp_root would otherwise prepend.
    """
    env = {
        "AWS_ACCESS_KEY_ID": "test-key",
        "AWS_SECRET_ACCESS_KEY": "test-secret",
        "AWS_REGION": "us-east-1",
        "AWS_ENDPOINT_URL": "https://s3.example.com",
        "S3_PDF_BUCKET": "test-pdfs",
        # trailing space on purpose: the strip validator has to cope with it
        "S3_PARSED_MDS": "test-mds ",
        "TEMP_PD_DIR": str(tmp_path),
        "TEMP_PDF_FOLDER": "TEMP_PDF",
        "TEMP_MD_FOLDER": "TEMP_MD",
        "API_HOST": "127.0.0.1",
        "API_PORT": "9999",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    # both modules cache singletons, so clear them between tests
    monkeypatch.setattr(utils.config, "_settings_instance", None)
    monkeypatch.setattr(utils.utility, "_s3_client", None)

    return utils.config.get_setting()


class FakeS3Client:
    """Stands in for the boto3 client, backed by a dict of {(bucket, key): bytes}."""

    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body):  # noqa: N803 - boto3 spells them this way
        self.objects[(Bucket, Key)] = Body

    def upload_file(self, filename, bucket, key):
        self.objects[(bucket, key)] = open(filename, "rb").read()

    def download_file(self, bucket, key, filename):
        if (bucket, key) not in self.objects:
            # mirrors what boto3 raises, so the error wrapping is exercised
            raise ClientError({"Error": {"Code": "404", "Message": "Not Found"}}, "GetObject")
        with open(filename, "wb") as handle:
            handle.write(self.objects[(bucket, key)])


@pytest.fixture
def s3(monkeypatch):
    """Replaces the real S3 client with the in-memory fake."""
    client = FakeS3Client()
    monkeypatch.setattr(utils.utility, "_s3_client", client)
    return client


@pytest.fixture
def pdf_bytes():
    """A tiny one-page PDF with known text in it."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 100), "Quarterly Report", fontsize=22)
    page.insert_text((72, 140), "Revenue grew 12 percent this quarter.", fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data
