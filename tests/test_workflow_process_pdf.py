"""The workflow is exercised against a real (in-process) Temporal server, with
the activities running for real against the in-memory S3 fake.

If the test server cannot be started (no network on a first run, for example)
the whole module skips rather than failing the suite.
"""

import uuid

import pytest
import pytest_asyncio
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from activities import ALL_ACTIVITIES
from schemas.process_pdf import ProcessPdfInput
from workers.process_pdf_worker import create_process_pdf_worker
from workflows import ALL_WORKFLOWS
from workflows.workflow_process_pdf import ProcessPdfWorkflow

# The Temporal server and its client are created once for the module, so every
# test in here has to run on that same event loop; a per-test loop would leave
# the client's calls waiting on a loop that is no longer running.
pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def temporal_env():
    try:
        env = await WorkflowEnvironment.start_time_skipping()
    except Exception as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"temporal test server unavailable: {exc}")
    yield env
    await env.shutdown()


@pytest_asyncio.fixture(loop_scope="module")
async def worker(temporal_env):
    """A worker polling a queue unique to this test, so tests cannot cross-talk."""
    task_queue = f"test-{uuid.uuid4()}"
    async with Worker(
        temporal_env.client,
        task_queue=task_queue,
        workflows=ALL_WORKFLOWS,
        activities=ALL_ACTIVITIES,
    ):
        yield temporal_env.client, task_queue


async def run_workflow(worker, pdf_key, md_key, task_id="t1"):
    client, task_queue = worker
    return await client.execute_workflow(
        ProcessPdfWorkflow.run,
        ProcessPdfInput(task_id=task_id, pdf_key=pdf_key, md_key=md_key),
        id=f"test-{uuid.uuid4()}",
        task_queue=task_queue,
    )


async def test_workflow_produces_markdown(worker, s3, settings, pdf_bytes):
    s3.objects[(settings.s3_pdf_bucket, "report.pdf")] = pdf_bytes

    result = await run_workflow(worker, "report.pdf", "report.md")

    assert result.pdf_key == "report.pdf"
    assert result.md_key == "report.md"


async def test_workflow_uploads_markdown_to_the_parsed_bucket(worker, s3, settings, pdf_bytes):
    s3.objects[(settings.s3_pdf_bucket, "report.pdf")] = pdf_bytes

    result = await run_workflow(worker, "report.pdf", "report.md")

    stored = s3.objects[(settings.s3_parsed_mds, result.md_key)].decode("utf-8")
    assert "Quarterly Report" in stored


async def test_workflow_downloads_markdown_locally(worker, s3, settings, pdf_bytes):
    from pathlib import Path

    s3.objects[(settings.s3_pdf_bucket, "report.pdf")] = pdf_bytes

    result = await run_workflow(worker, "report.pdf", "report.md")

    local_md = Path(result.local_md)
    assert local_md.parent == settings.temp_md_path
    assert "Quarterly Report" in local_md.read_text(encoding="utf-8")


async def test_workflow_downloads_the_pdf_onto_the_worker(worker, s3, settings, pdf_bytes):
    from pathlib import Path

    s3.objects[(settings.s3_pdf_bucket, "report.pdf")] = pdf_bytes

    result = await run_workflow(worker, "report.pdf", "report.md")

    assert Path(result.local_pdf).parent == settings.temp_pdf_path


async def test_a_missing_pdf_fails_the_workflow(worker, s3):
    """download_pdf raises ObjectNotFoundError, which surfaces as a workflow failure."""
    with pytest.raises(WorkflowFailureError):
        await run_workflow(worker, "does-not-exist.pdf", "nope.md")


async def test_the_workflow_is_registered():
    assert ProcessPdfWorkflow in ALL_WORKFLOWS


async def test_the_pdf_worker_builds_against_a_real_client(temporal_env):
    """create_process_pdf_worker must produce a Worker Temporal actually accepts."""
    worker = await create_process_pdf_worker(task_queue="smoke-queue", client=temporal_env.client)

    assert worker.task_queue == "smoke-queue"


async def test_the_workflow_reports_a_full_result(worker, s3, settings, pdf_bytes):
    """The result carries both buckets, both local paths and the parse size."""
    s3.objects[(settings.s3_pdf_bucket, "report.pdf")] = pdf_bytes

    result = await run_workflow(worker, "report.pdf", "report.md")

    assert result.pdf_bucket == settings.s3_pdf_bucket
    assert result.md_bucket == settings.s3_parsed_mds
    assert result.markdown_characters > 0
    assert result.workflow_id.startswith("test-")


async def test_the_reported_character_count_matches_the_markdown(worker, s3, settings, pdf_bytes):
    s3.objects[(settings.s3_pdf_bucket, "report.pdf")] = pdf_bytes

    result = await run_workflow(worker, "report.pdf", "report.md")

    stored = s3.objects[(settings.s3_parsed_mds, result.md_key)].decode("utf-8")
    assert result.markdown_characters == len(stored)


async def test_the_task_id_survives_the_round_trip(worker, s3, settings, pdf_bytes):
    s3.objects[(settings.s3_pdf_bucket, "report.pdf")] = pdf_bytes

    result = await run_workflow(worker, "report.pdf", "report.md", task_id="deadbeef")

    assert result.task_id == "deadbeef"
