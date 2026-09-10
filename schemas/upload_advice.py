from dataclasses import dataclass

from schemas.legal_advice import LegalAdvice


@dataclass
class UploadAdviceInput:
    """Finished advice to store as JSON."""

    task_id: str
    pdf_key: str
    advice: LegalAdvice


@dataclass
class UploadAdviceOutput:
    bucket: str
    key: str
    s3_path: str
