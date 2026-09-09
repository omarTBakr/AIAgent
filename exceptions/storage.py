from exceptions.base import AIAgentError


class StorageError(AIAgentError):
    """Anything that went wrong talking to the object store."""


class StorageConnectionError(StorageError):
    """The endpoint could not be reached, or refused the credentials."""


class UploadError(StorageError):
    """An object could not be written to a bucket."""


class DownloadError(StorageError):
    """An object could not be read from a bucket."""


class ObjectNotFoundError(DownloadError):
    """The requested key does not exist in the bucket."""


class LocalFileNotFoundError(StorageError, FileNotFoundError):
    """
    A local file due to be uploaded is not there.

    Also a FileNotFoundError, so callers that only care that a file is missing
    keep working without knowing about this hierarchy.
    """
