from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from routes.legal import router as legal_router
from routes.process import router as process_router
from utils.config import get_setting
from utils.logger import get_logger, setup_logging
from workers.process_pdf_worker import create_process_pdf_worker

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Optionally runs the Temporal worker alongside the API.

    With RUN_WORKER_IN_API set, one process serves requests and executes
    workflows, which is convenient locally. In production leave it off and run
    workers/process_pdf_worker.py separately: a slow parse then cannot starve
    request handling, and in-flight work survives an API restart.
    """
    settings = get_setting()

    if not settings.run_worker_in_api:
        logger.info("worker not started in-process; run worker.py separately")
        yield
        return

    # Failing here is deliberate: an API that was asked to host the worker but
    # has none would accept uploads that nothing ever picks up.
    worker = await create_process_pdf_worker()

    logger.info("worker running inside the API on %r", worker.task_queue)

    async with worker:
        yield


app = FastAPI(title="AIAgent", description="PDF -> markdown pipeline", lifespan=lifespan)
app.include_router(process_router)
app.include_router(legal_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


def main():
    setup_logging()
    settings = get_setting()
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    main()
