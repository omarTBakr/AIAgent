"""The route is tested without a Temporal server: get_temporal_client is
replaced with a stub client whose execute_workflow returns or raises whatever
the test needs."""

import pytest
from fastapi.testclient import TestClient

import routes.process
import utils.temporal_client
from main import app
from schemas.process_pdf import ProcessPdfOutput


class StubClient:
    """Stands in for temporalio.client.Client."""

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def execute_workflow(self, run_fn, arg, *, id, task_queue, **kwargs):
        self.calls.append({"arg": arg, "id": id, "task_queue": task_queue})
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def temporal(monkeypatch):
    """Installs a stub Temporal client and hands it back so tests can assert on it."""
    stub = StubClient(
        result=ProcessPdfOutput(
            pdf_key="report-abc123.pdf",
            md_key="report-abc123.md",
            local_pdf="/tmp/TEMP_PDF/report-abc123.pdf",
            local_md="/tmp/TEMP_MD/report-abc123.md",
        )
    )

    async def fake_get_client():
        return stub

    monkeypatch.setattr(routes.process, "get_temporal_client", fake_get_client)
    monkeypatch.setattr(utils.temporal_client, "_client", None)
    return stub


@pytest.fixture
def client(s3, temporal):
    """The s3 and temporal fixtures keep these requests off the network."""
    return TestClient(app)


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_process_accepts_a_pdf(client, pdf_bytes):
    response = client.post("/process", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["md_key"].endswith(".md")


def test_process_uploads_the_pdf_before_starting_the_workflow(client, s3, settings, pdf_bytes, temporal):
    """The document must reach the bucket, not the workflow history."""
    client.post("/process", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})

    uploaded = [key for (bucket, key) in s3.objects if bucket == settings.s3_pdf_bucket]
    assert len(uploaded) == 1
    assert uploaded[0].startswith("report-")


def test_process_starts_the_workflow_with_only_the_keys(client, pdf_bytes, temporal):
    client.post("/process", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})

    assert len(temporal.calls) == 1
    payload = temporal.calls[0]["arg"]
    assert payload.pdf_key.startswith("report-")
    assert payload.md_key.endswith(".md")


def test_process_uses_the_configured_task_queue(client, pdf_bytes, settings, temporal):
    client.post("/process", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})

    assert temporal.calls[0]["task_queue"] == settings.temporal_task_queue


def test_process_gives_the_workflow_a_deterministic_id(client, pdf_bytes, temporal):
    """The id is derived from the key, so a retry of the same upload dedupes."""
    client.post("/process", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})

    call = temporal.calls[0]
    assert call["id"] == f"process-pdf-{call['arg'].pdf_key}"


def test_process_rejects_a_non_pdf(client):
    response = client.post("/process", files={"file": ("notes.txt", b"hello", "text/plain")})

    assert response.status_code == 400
    assert "only .pdf files are accepted" in response.json()["detail"]


def test_process_rejects_an_empty_file(client):
    response = client.post("/process", files={"file": ("empty.pdf", b"", "application/pdf")})

    assert response.status_code == 400
    assert "empty" in response.json()["detail"]


def test_process_without_a_file_field_is_422(client):
    """This is the error you get from Postman when the form key is not 'file'."""
    response = client.post("/process")

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "file"]


def test_process_with_the_wrong_field_name_is_422(client, pdf_bytes):
    response = client.post("/process", files={"intro_to_stats": ("report.pdf", pdf_bytes, "application/pdf")})

    assert response.status_code == 422


def test_a_storage_failure_is_502(client, s3, monkeypatch, pdf_bytes):
    """The upload happens in the route, so a bucket failure surfaces directly."""
    from botocore.exceptions import ClientError

    def explode(*args, **kwargs):
        raise ClientError({"Error": {"Code": "AccessDenied", "Message": "nope"}}, "PutObject")

    monkeypatch.setattr(s3, "upload_file", explode)

    response = client.post("/process", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})

    assert response.status_code == 502
    assert "storage error" in response.json()["detail"]


def test_an_unreachable_temporal_is_503(client, monkeypatch, pdf_bytes):
    from exceptions.workflow import TemporalConnectionError

    async def explode():
        raise TemporalConnectionError("could not reach Temporal at localhost:7233")

    monkeypatch.setattr(routes.process, "get_temporal_client", explode)

    response = client.post("/process", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})

    assert response.status_code == 503
    assert "temporal unavailable" in response.json()["detail"]


def test_a_workflow_failure_is_500(client, temporal, pdf_bytes):
    from exceptions.workflow import WorkflowExecutionError

    temporal.error = WorkflowExecutionError("activity gave up after 3 attempts")

    response = client.post("/process", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})

    assert response.status_code == 500
    assert "workflow failed" in response.json()["detail"]


def test_an_unexpected_error_is_still_500(client, temporal, pdf_bytes):
    temporal.error = RuntimeError("something nobody planned for")

    response = client.post("/process", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})

    assert response.status_code == 500
