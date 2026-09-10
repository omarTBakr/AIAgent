from dataclasses import dataclass


@dataclass
class ParsePdfInput:
    """Local PDF to convert to Markdown."""

    task_id: str
    local_path: str


@dataclass
class ParsePdfOutput:
    markdown: str
