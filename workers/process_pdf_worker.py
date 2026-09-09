"""Worker for the PDF processing pipeline.

Run it with the root entrypoint:

    uv run worker.py

or as a module:

    uv run python -m workers.process_pdf_worker
"""

import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from activities import ALL_ACTIVITIES
from utils.create_worker import create_worker
from utils.logger import get_logger, setup_logging
from workflows import ALL_WORKFLOWS

logger = get_logger(__name__)


async def create_process_pdf_worker(task_queue: str | None = None, client: Client | None = None) -> Worker:
    """
    Builds the worker that serves ProcessPdfWorkflow and its activities.

    Defaults to TEMPORAL_TASK_QUEUE, which is `process_pdf_queue`.
    """
    return await create_worker(
        workflows=ALL_WORKFLOWS,
        activities=ALL_ACTIVITIES,
        task_queue=task_queue,
        client=client,
    )


async def run_process_pdf_worker() -> None:
    """Builds the worker and polls until the process is stopped."""
    setup_logging()

    worker = await create_process_pdf_worker()

    logger.info("pdf worker polling %r", worker.task_queue)

    await worker.run()


if __name__ == "__main__":
    asyncio.run(run_process_pdf_worker())
