from dataclasses import dataclass

from schemas.legal_advice import LegalAdvice


@dataclass
class HumanFollowupInput:
    """Draft advice plus the human's answer to the question it raised."""

    task_id: str
    pdf_key: str
    advice: LegalAdvice
    question: str
    answer: str


@dataclass
class HumanFollowupOutput:
    advice: LegalAdvice
