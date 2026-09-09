"""Exception hierarchy for the project.

    AIAgentError
    |
    +-- ConfigurationError
    |     +-- MissingSettingError
    |     +-- InvalidSettingError
    |
    +-- ValidationError
    |     +-- UnsupportedFileTypeError
    |     +-- EmptyFileError
    |
    +-- StorageError
    |     +-- StorageConnectionError
    |     +-- UploadError
    |     +-- DownloadError
    |     |     +-- ObjectNotFoundError
    |     +-- LocalFileNotFoundError      (also a FileNotFoundError)
    |
    +-- ParsingError
    |     +-- PdfNotFoundError            (also a FileNotFoundError)
    |     +-- InvalidPdfError
    |
    +-- WorkflowError
          +-- ActivityFailedError
          +-- TemporalConnectionError
          +-- WorkflowExecutionError

Catch `AIAgentError` for anything the project raised on purpose; catch a
subtree (`StorageError`) when the handling is the same across a domain.
"""

from exceptions.base import AIAgentError
from exceptions.config import ConfigurationError, InvalidSettingError, MissingSettingError
from exceptions.parsing import InvalidPdfError, ParsingError, PdfNotFoundError
from exceptions.storage import (
    DownloadError,
    LocalFileNotFoundError,
    ObjectNotFoundError,
    StorageConnectionError,
    StorageError,
    UploadError,
)
from exceptions.validation import EmptyFileError, UnsupportedFileTypeError, ValidationError
from exceptions.workflow import ActivityFailedError, TemporalConnectionError, WorkflowError, WorkflowExecutionError

__all__ = [
    "AIAgentError",
    "ActivityFailedError",
    "ConfigurationError",
    "DownloadError",
    "EmptyFileError",
    "InvalidPdfError",
    "InvalidSettingError",
    "LocalFileNotFoundError",
    "MissingSettingError",
    "ObjectNotFoundError",
    "ParsingError",
    "PdfNotFoundError",
    "StorageConnectionError",
    "StorageError",
    "TemporalConnectionError",
    "UnsupportedFileTypeError",
    "UploadError",
    "ValidationError",
    "WorkflowError",
    "WorkflowExecutionError",
]
