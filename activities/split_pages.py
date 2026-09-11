import asyncio

from temporalio import activity

from parsers.pymupdf_parser import parse_pdf_pages
from schemas.split_pages import SplitPagesInput, SplitPagesOutput
from utils.batching import split_pages_into_batches


@activity.defn
async def split_pages(payload: SplitPagesInput) -> SplitPagesOutput:
    """
    Parses a local PDF page by page and groups the pages into batches.

    Parsing is CPU-bound and runs in a thread: on the event loop it would stall
    the model calls of every other document in flight while it ran.
    """
    activity.logger.info("[task %s] splitting %s into batches of %d", payload.task_id, payload.pdf_key, payload.pages_per_batch)

    try:
        pages = await asyncio.to_thread(parse_pdf_pages, payload.local_pdf)
    except Exception:
        activity.logger.exception("[task %s] failed to split %s", payload.task_id, payload.pdf_key)
        raise

    batches = split_pages_into_batches(pages, payload.pages_per_batch)

    activity.logger.info("[task %s] %s: %d pages -> %d batches", payload.task_id, payload.pdf_key, len(pages), len(batches))

    return SplitPagesOutput(batches=batches, page_count=len(pages))
