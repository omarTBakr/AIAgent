"""create_worker only wires arguments together, so the tests capture what it
hands to Worker rather than standing up a real one."""

import pytest

import utils.create_worker
from activities import ALL_ACTIVITIES
from utils.create_worker import create_worker
from workers.process_pdf_worker import create_process_pdf_worker
from workflows import ALL_WORKFLOWS
from workflows.workflow_process_pdf import ProcessPdfWorkflow


class FakeWorker:
    def __init__(self, client, *, task_queue, workflows, activities, **kwargs):
        self.client = client
        self.task_queue = task_queue
        self.workflows = workflows
        self.activities = activities
        self.kwargs = kwargs


@pytest.fixture
def captured(monkeypatch):
    """Replaces Worker and the client connect, and hands back what was built."""
    sentinel_client = object()

    async def fake_get_client():
        return sentinel_client

    monkeypatch.setattr(utils.create_worker, "Worker", FakeWorker)
    monkeypatch.setattr(utils.create_worker, "get_temporal_client", fake_get_client)
    return sentinel_client


async def test_defaults_to_the_configured_task_queue(captured, settings):
    worker = await create_worker(workflows=[], activities=[])

    assert worker.task_queue == settings.temporal_task_queue
    assert worker.task_queue == "process_pdf_queue"


async def test_an_explicit_task_queue_wins(captured):
    worker = await create_worker(workflows=[], activities=[], task_queue="other-queue")

    assert worker.task_queue == "other-queue"


async def test_it_connects_a_client_when_none_is_given(captured):
    worker = await create_worker(workflows=[], activities=[])

    assert worker.client is captured


async def test_an_explicit_client_is_used_as_is(captured):
    mine = object()

    worker = await create_worker(workflows=[], activities=[], client=mine)

    assert worker.client is mine


async def test_workflows_and_activities_are_registered(captured):
    worker = await create_worker(workflows=ALL_WORKFLOWS, activities=ALL_ACTIVITIES)

    assert worker.workflows == list(ALL_WORKFLOWS)
    assert worker.activities == list(ALL_ACTIVITIES)


async def test_extra_kwargs_reach_the_worker(captured):
    worker = await create_worker(workflows=[], activities=[], max_concurrent_activities=7)

    assert worker.kwargs["max_concurrent_activities"] == 7


async def test_the_pdf_worker_registers_the_workflow_and_every_activity(captured):
    worker = await create_process_pdf_worker()

    assert ProcessPdfWorkflow in worker.workflows
    assert len(worker.activities) == len(ALL_ACTIVITIES)


async def test_the_pdf_worker_polls_the_process_pdf_queue(captured):
    worker = await create_process_pdf_worker()

    assert worker.task_queue == "process_pdf_queue"


async def test_the_pdf_worker_accepts_an_override(captured):
    worker = await create_process_pdf_worker(task_queue="temp-queue")

    assert worker.task_queue == "temp-queue"
