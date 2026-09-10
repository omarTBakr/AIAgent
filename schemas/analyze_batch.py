from dataclasses import dataclass

from schemas.legal_advice import LegalAdvice
from schemas.page_batch import PageBatch


@dataclass
class AnalyzeBatchInput:
    """One batch of pages to send to the model."""

    task_id: str
    pdf_key: str
    batch: PageBatch
    batch_count: int


@dataclass
class AnalyzeBatchOutput:
    advice: LegalAdvice
