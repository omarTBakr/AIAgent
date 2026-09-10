"""The legal routes are tested without a Temporal server: get_temporal_client is
replaced with a stub client whose handles describe, query, signal and return
whatever the test needs."""

import pytest
from fastapi.testclient import TestClient
from temporalio.client import WorkflowExecutionStatus
from temporalio.service import RPCError, RPCStatusCode

import routes.legal
import utils.temporal_client
from enums.ReviewDecision import ReviewDecision
from enums.RiskSeverity import RiskSeverity
from main import app
from schemas.key_risk import KeyRisk
from schemas.legal_advice import LegalAdvice
from schemas.legal_review import DocumentAdvice, LegalReviewResult

RESULT = LegalReviewResult(
    task_id="abc123",
    documents=[
        DocumentAdvice(
            pdf_key="contract-abc123.pdf",
            advice=LegalAdvice(
                summary="A services agreement.",
                key_risks=[KeyRisk(description="Unlimited liability", severity=RiskSeverity.HIGH, location="clause 9")],
                review_decision=ReviewDecision.UNREVIEWED_TIMEOUT,
                s3_path="s3://test-advice/contract-abc123.advice.json",
            ),
        )
    ],
)


class StubDescription:
    def __init__(self, status):
        self.status = status


class StubHandle:
    """Stands in for temporalio.client.WorkflowHandle."""

    def __init__(
        self,
        workflow_id,
        status=WorkflowExecutionStatus.RUNNING,
        result=RESULT,
        questions=None,
        progress=None,
        signal_error=None,
        signals=None,
    ):
        self.id = workflow_id
        self._status = status
        self._result = result
        self._queries = {"pending_questions": questions or [], "progress": progress or {}}
        self._signal_error = signal_error
        self._signals = signals if signals is not None else []

    async def describe(self):
        if isinstance(self._status, Exception):
            raise self._status
        return StubDescription(self._status)

    async def result(self):
        return self._result

    async def query(self, query_fn):
        return self._queries[query_fn.__name__]

    async def signal(self, signal_fn, args):
        if self._signal_error is not None:
            raise self._signal_error
        self._signals.append({"id": self.id, "signal": signal_fn.__name__, "args": args})


class StubClient:
    def __init__(self):
        self.calls = []
        self.signals = []
        self.handle_kwargs = {}

    async def start_workflow(self, run_fn, arg, *, id, task_queue, **kwargs):
        self.calls.append({"arg": arg, "id": id, "task_queue": task_queue})
        return StubHandle(id, **self.handle_kwargs)

    def get_workflow_handle_for(self, run_fn, workflow_id, **kwargs):
        return StubHandle(workflow_id, signals=self.signals, **self.handle_kwargs)


@pytest.fixture
def temporal(monkeypatch):
    stub = StubClient()

    async def fake_get_client():
        return stub

    monkeypatch.setattr(routes.legal, "get_temporal_client", fake_get_client)
    monkeypatch.setattr(utils.temporal_client, "_client", None)
    return stub


@pytest.fixture
def client(s3, temporal):
    """The s3 and temporal fixtures keep these requests off the network."""
    return TestClient(app)


def submit(client, pdf_bytes, count=2):
    files = [("files", (f"contract{i}.pdf", pdf_bytes, "application/pdf")) for i in range(count)]
    return client.post("/legal", files=files)


# --- POST /legal ---------------------------------------------------------


def test_submit_returns_202_immediately(client, pdf_bytes):
    response = submit(client, pdf_bytes)

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "processing"
    assert body["workflow_id"] == f"legal-review-{body['task_id']}"
    assert body["pdf_count"] == 2


def test_every_document_reaches_the_bucket(client, pdf_bytes, s3, settings):
    body = submit(client, pdf_bytes, count=3).json()

    stored = sorted(key for bucket, key in s3.objects if bucket == settings.s3_pdf_bucket)
    assert stored == sorted(body["pdf_keys"])
    assert len(stored) == 3


def test_one_workflow_reviews_all_the_documents(client, pdf_bytes, temporal):
    body = submit(client, pdf_bytes, count=3).json()

    assert len(temporal.calls) == 1
    payload = temporal.calls[0]["arg"]
    assert payload.task_id == body["task_id"]
    assert payload.pdf_keys == body["pdf_keys"]


def test_the_workflow_gets_the_configured_limits(client, pdf_bytes, temporal, settings):
    submit(client, pdf_bytes)

    call = temporal.calls[0]
    assert call["task_queue"] == settings.legal_task_queue
    assert call["arg"].max_concurrent_pdfs == settings.legal_max_concurrent_pdfs
    assert call["arg"].pages_per_batch == settings.legal_pages_per_batch
    assert call["arg"].human_input_timeout_seconds == settings.human_input_timeout_seconds


def test_too_many_documents_is_400(client, pdf_bytes, temporal, settings):
    response = submit(client, pdf_bytes, count=settings.legal_max_pdfs + 1)

    assert response.status_code == 400
    assert f"at most {settings.legal_max_pdfs}" in response.json()["detail"]
    assert temporal.calls == []


def test_one_non_pdf_rejects_the_whole_request(client, pdf_bytes, s3, temporal):
    """Nothing is stored and nothing starts when any one file is unusable."""
    files = [
        ("files", ("contract.pdf", pdf_bytes, "application/pdf")),
        ("files", ("notes.txt", b"hello", "text/plain")),
    ]

    response = client.post("/legal", files=files)

    assert response.status_code == 400
    assert "only .pdf files are accepted" in response.json()["detail"]
    assert s3.objects == {}
    assert temporal.calls == []


def test_submit_without_files_is_422(client):
    assert client.post("/legal").status_code == 422


# --- GET /legal/{task_id} ------------------------------------------------


def test_status_while_running(client, temporal):
    temporal.handle_kwargs = {"progress": {"a.pdf": "processing", "b.pdf": "completed"}}

    body = client.get("/legal/abc123").json()

    assert body["status"] == "processing"
    assert body["documents"] == {"a.pdf": "processing", "b.pdf": "completed"}
    assert body["pending_questions"] == []


def test_status_reports_a_question_waiting_on_a_human(client, temporal):
    question = {"pdf_key": "a.pdf", "question": "Which jurisdiction governs this contract?"}
    temporal.handle_kwargs = {"questions": [question], "progress": {"a.pdf": "awaiting_human"}}

    body = client.get("/legal/abc123").json()

    assert body["status"] == "awaiting_human"
    assert body["pending_questions"] == [question]


def test_status_when_completed_returns_the_advice(client, temporal):
    temporal.handle_kwargs = {"status": WorkflowExecutionStatus.COMPLETED}

    body = client.get("/legal/abc123").json()

    assert body["status"] == "completed"
    assert body["document_count"] == 1
    document = body["documents"][0]
    assert document["summary"] == "A services agreement."
    assert document["key_risks"] == [
        {"description": "Unlimited liability", "severity": "high", "location": "clause 9"},
    ]
    assert document["review_decision"] == "unreviewed_timeout"
    assert document["needs_attention"] is True


def test_status_for_a_failed_review(client, temporal):
    temporal.handle_kwargs = {"status": WorkflowExecutionStatus.FAILED}

    assert client.get("/legal/abc123").json()["status"] == "failed"


def test_status_for_an_unknown_task_is_404(client, temporal):
    temporal.handle_kwargs = {"status": RPCError("not found", RPCStatusCode.NOT_FOUND, "")}

    response = client.get("/legal/nope")

    assert response.status_code == 404
    assert "no such task" in response.json()["detail"]


# --- POST /legal/{task_id}/respond ---------------------------------------


def test_an_answer_is_signalled_to_the_workflow(client, temporal):
    response = client.post("/legal/abc123/respond", json={"pdf_key": "a.pdf", "answer": "English law"})

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert temporal.signals == [
        {"id": "legal-review-abc123", "signal": "human_response", "args": ["a.pdf", "English law"]},
    ]


def test_an_answer_for_an_unknown_task_is_404(client, temporal):
    temporal.handle_kwargs = {"signal_error": RPCError("not found", RPCStatusCode.NOT_FOUND, "")}

    response = client.post("/legal/nope/respond", json={"pdf_key": "a.pdf", "answer": "English law"})

    assert response.status_code == 404


def test_an_answer_without_a_pdf_key_is_422(client, temporal):
    response = client.post("/legal/abc123/respond", json={"answer": "English law"})

    assert response.status_code == 422
    assert temporal.signals == []
