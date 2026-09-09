"""Temporal activities, one per file.

Each activity is a thin wrapper: it takes a dataclass from `schemas`, does one
side-effecting step, and returns a dataclass. The real work stays in `utils`
and `parsers` so it can be tested without a Temporal server.
"""

from activities.download_md import download_md
from activities.download_pdf import download_pdf
from activities.parse_pdf import parse_pdf
from activities.upload_md import upload_md
from activities.upload_pdf import upload_pdf

# hand this to the Worker's `activities=` argument
ALL_ACTIVITIES = [upload_pdf, download_pdf, parse_pdf, upload_md, download_md]

__all__ = ["ALL_ACTIVITIES", "download_md", "download_pdf", "parse_pdf", "upload_md", "upload_pdf"]
