"""Retry policies, one per kind of work, one per file.

    from enums import StorageRetryPolicy

    execute_activity(..., retry_policy=StorageRetryPolicy())

`RetryProfile` resolves the same policies by name, for tuning that comes from
configuration rather than from the call site.
"""

from enums.ParsingRetryPolicy import ParsingRetryPolicy
from enums.RetryProfile import RetryProfile, get_retry_policy
from enums.StorageRetryPolicy import StorageRetryPolicy
from enums.StrictRetryPolicy import StrictRetryPolicy

__all__ = [
    "ParsingRetryPolicy",
    "RetryProfile",
    "StorageRetryPolicy",
    "StrictRetryPolicy",
    "get_retry_policy",
]
