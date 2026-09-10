from dataclasses import dataclass

from schemas.page_batch import PageBatch


@dataclass
class SplitPagesInput:
    """A parsed document to break into LLM-sized pieces."""

    task_id: str
    pdf_key: str
    local_pdf: str
    pages_per_batch: int


@dataclass
class SplitPagesOutput:
    batches: list[PageBatch]
    page_count: int
