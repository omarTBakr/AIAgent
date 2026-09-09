from dataclasses import dataclass


@dataclass
class DownloadMdInput:
    """Markdown to pull out of the parsed bucket into the local Markdown folder."""

    key: str


@dataclass
class DownloadMdOutput:
    local_path: str
