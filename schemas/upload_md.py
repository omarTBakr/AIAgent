from dataclasses import dataclass


@dataclass
class UploadMdInput:
    """Markdown to push into the parsed-markdown bucket."""

    markdown: str
    key: str


@dataclass
class UploadMdOutput:
    bucket: str
    key: str
