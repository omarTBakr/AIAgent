from dataclasses import dataclass


@dataclass
class UploadPdfInput:
    """Local PDF to push into the PDF bucket."""

    task_id: str
    local_path: str
    key: str


@dataclass
class UploadPdfOutput:
    bucket: str
    key: str
