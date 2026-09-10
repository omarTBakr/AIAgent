from dataclasses import dataclass


@dataclass
class ProcessPdfInput:
    """A PDF already sitting in the PDF bucket, and where its Markdown should go."""

    task_id: str
    pdf_key: str
    md_key: str
