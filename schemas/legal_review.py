from dataclasses import dataclass, field

from schemas.legal_advice import LegalAdvice


@dataclass
class LegalReviewInput:
    """PDFs already in the PDF bucket, to be reviewed together."""

    task_id: str
    pdf_keys: list[str]
    pages_per_batch: int = 10
    max_concurrent_pdfs: int = 2
    human_input_timeout_seconds: float = 3600


@dataclass
class DocumentAdvice:
    """One document's advice, paired with the key it came from."""

    pdf_key: str
    advice: LegalAdvice


@dataclass
class LegalReviewResult:
    task_id: str
    documents: list[DocumentAdvice] = field(default_factory=list)

    @property
    def document_count(self) -> int:
        return len(self.documents)
