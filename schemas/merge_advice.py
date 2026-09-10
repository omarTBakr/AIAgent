from dataclasses import dataclass

from schemas.legal_advice import LegalAdvice


@dataclass
class MergeAdviceInput:
    """The per-batch advice for one document, to be reduced to a single answer."""

    task_id: str
    pdf_key: str
    parts: list[LegalAdvice]


@dataclass
class MergeAdviceOutput:
    advice: LegalAdvice
