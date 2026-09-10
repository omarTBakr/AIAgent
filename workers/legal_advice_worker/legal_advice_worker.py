"""Worker for the legal review pipeline.

Runs on its own task queue (LEGAL_TASK_QUEUE), so LLM work cannot starve the
PDF-to-markdown pipeline and the two can be scaled apart.

Run it as a module:

    uv run python -m workers.legal_advice_worker

or as a container (see Docker/Dockerfile):

    docker build -f workers/legal_advice_worker/Docker/Dockerfile -t aiagent-legal-advice-worker .
    docker run --rm --env-file .env aiagent-legal-advice-worker
"""

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from activities import LEGAL_ACTIVITIES
from utils.config import get_setting
from utils.create_worker import create_worker
from utils.logger import get_logger, setup_logging
from workflows import LEGAL_WORKFLOWS

logger = get_logger(__name__)


async def create_legal_advice_worker(task_queue: str | None = None, client: Client | None = None) -> Worker:
    """
    Builds the worker that serves LegalReviewWorkflow and its activities.

    Defaults to LEGAL_TASK_QUEUE, which is `legal_advice_queue`.
    """
    return await create_worker(
        workflows=LEGAL_WORKFLOWS,
        activities=LEGAL_ACTIVITIES,
        task_queue=task_queue or get_setting().legal_task_queue,
        client=client,
    )


async def run_legal_advice_worker() -> None:
    """Builds the worker and polls until the process is stopped."""
    setup_logging()

    worker = await create_legal_advice_worker()

    logger.info("legal advice worker polling %r", worker.task_queue)

    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_legal_advice_worker())
