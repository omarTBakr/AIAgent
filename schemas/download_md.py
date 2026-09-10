from dataclasses import dataclass


@dataclass
class DownloadMdInput:
    """Markdown to pull out of the parsed bucket into the local Markdown folder."""

    task_id: str
    key: str


@dataclass
class DownloadMdOutput:
    bucket: str
    local_path: str
