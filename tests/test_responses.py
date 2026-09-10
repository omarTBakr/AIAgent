from enums.TaskStatus import TaskStatus
from schemas.process_pdf_result import ProcessPdfResult
from utils.responses import accepted_response, completed_response, status_response
from utils.store_upload import StoredUpload

STORED = StoredUpload(task_id="abc123", pdf_key="r-abc123.pdf", md_key="r-abc123.md", local_pdf="/tmp/r.pdf")

RESULT = ProcessPdfResult(
    task_id="abc123",
    pdf_bucket="pdfs",
    pdf_key="r-abc123.pdf",
    md_bucket="mds",
    md_key="r-abc123.md",
    local_pdf="/tmp/r.pdf",
    local_md="/tmp/r.md",
    markdown_characters=80,
    workflow_id="process-pdf-abc123",
)


def test_accepted_reports_processing():
    body = accepted_response(STORED, "pdfs")

    assert body["status"] == TaskStatus.PROCESSING.value
    assert body["task_id"] == "abc123"
    assert body["workflow_id"] == "process-pdf-abc123"


def test_accepted_does_not_promise_a_result():
    """Nothing has been parsed yet, so no markdown fields."""
    body = accepted_response(STORED, "pdfs")

    assert "md_bucket" not in body
    assert "markdown_characters" not in body


def test_completed_carries_the_whole_result():
    body = completed_response(RESULT)

    assert body["status"] == TaskStatus.COMPLETED.value
    assert body["markdown_characters"] == 80
    assert body["md_bucket"] == "mds"


def test_status_response_uses_the_enum_value():
    body = status_response("abc123", TaskStatus.TERMINATED)

    assert body["status"] == "terminated"
    assert body["workflow_id"] == "process-pdf-abc123"


def test_every_body_identifies_the_task():
    """Whatever the state, the caller can always tell which task replied."""
    bodies = [
        accepted_response(STORED, "pdfs"),
        completed_response(RESULT),
        status_response("abc123", TaskStatus.FAILED),
    ]

    for body in bodies:
        assert body["task_id"] == "abc123"
        assert body["workflow_id"] == "process-pdf-abc123"
        assert body["status"]
