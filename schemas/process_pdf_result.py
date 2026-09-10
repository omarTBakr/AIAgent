from dataclasses import dataclass


@dataclass
class ProcessPdfResult:
    """
    What ProcessPdfWorkflow produced.

    Carries where both artefacts ended up (bucket and key, plus the local copy
    on the worker) and enough about the parse to tell whether it was worth
    anything, without shipping the Markdown itself through workflow history.
    """

    pdf_bucket: str
    pdf_key: str
    md_bucket: str
    md_key: str
    local_pdf: str
    local_md: str
    markdown_characters: int
    workflow_id: str
