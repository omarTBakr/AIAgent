from dataclasses import dataclass


@dataclass
class ProcessPdfInput:
    """A PDF already sitting in the PDF bucket, and where its Markdown should go."""

    pdf_key: str
    md_key: str


@dataclass
class ProcessPdfOutput:
    pdf_key: str
    md_key: str
    local_pdf: str
    local_md: str
