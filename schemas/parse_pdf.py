from dataclasses import dataclass


@dataclass
class ParsePdfInput:
    """Local PDF to convert to Markdown."""

    local_path: str


@dataclass
class ParsePdfOutput:
    markdown: str
