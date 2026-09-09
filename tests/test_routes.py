import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client(s3):
    """The s3 fixture keeps these requests off the network."""
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
    assert body["pdf_key"].startswith("report-")
    assert body["md_key"].endswith(".md")


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


def test_process_reports_a_failure_as_500(client, pdf_bytes, monkeypatch):
    import routes.process

    async def boom(*args, **kwargs):
        raise RuntimeError("bucket is on fire")

    monkeypatch.setattr(routes.process, "workflow", boom)

    response = client.post("/process", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})

    assert response.status_code == 500
    assert "bucket is on fire" in response.json()["detail"]


def test_a_parsing_failure_is_422(client, pdf_bytes, monkeypatch):
    """A real upload that cannot be parsed is the caller's problem, not a 500."""
    import routes.process
    from exceptions import InvalidPdfError

    async def boom(*args, **kwargs):
        raise InvalidPdfError("corrupt document")

    monkeypatch.setattr(routes.process, "workflow", boom)

    response = client.post("/process", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})

    assert response.status_code == 422
    assert "corrupt document" in response.json()["detail"]


def test_a_storage_failure_is_502(client, pdf_bytes, monkeypatch):
    """The object store is an upstream dependency, so surface it as a bad gateway."""
    import routes.process
    from exceptions import UploadError

    async def boom(*args, **kwargs):
        raise UploadError("bucket unreachable")

    monkeypatch.setattr(routes.process, "workflow", boom)

    response = client.post("/process", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})

    assert response.status_code == 502
    assert "bucket unreachable" in response.json()["detail"]


def test_an_object_not_found_is_also_502(client, pdf_bytes, monkeypatch):
    """Leaf storage types inherit the StorageError handling."""
    import routes.process
    from exceptions import ObjectNotFoundError

    async def boom(*args, **kwargs):
        raise ObjectNotFoundError("no such key")

    monkeypatch.setattr(routes.process, "workflow", boom)

    response = client.post("/process", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})

    assert response.status_code == 502


def test_an_unexpected_error_is_still_500(client, pdf_bytes, monkeypatch):
    import routes.process

    async def boom(*args, **kwargs):
        raise RuntimeError("something nobody planned for")

    monkeypatch.setattr(routes.process, "workflow", boom)

    response = client.post("/process", files={"file": ("report.pdf", pdf_bytes, "application/pdf")})

    assert response.status_code == 500
