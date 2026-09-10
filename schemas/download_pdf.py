from dataclasses import dataclass


@dataclass
class DownloadPdfInput:
    """PDF to pull out of the PDF bucket into the local PDF scratch folder."""

    key: str


@dataclass
class DownloadPdfOutput:
    bucket: str
    local_path: str
