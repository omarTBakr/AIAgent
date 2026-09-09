import asyncio

from temporalio.worker import Worker

from activities import ALL_ACTIVITIES
from utils.config import get_setting
from utils.logger import get_logger, setup_logging
from utils.temporal_client import get_temporal_client
from workflows import ALL_WORKFLOWS

logger = get_logger(__name__)


async def main() -> None:
    setup_logging()
    settings = get_setting()

    client = await get_temporal_client()

    logger.info("worker polling task queue %r", settings.temporal_task_queue)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=ALL_WORKFLOWS,
        activities=ALL_ACTIVITIES,
    )

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
