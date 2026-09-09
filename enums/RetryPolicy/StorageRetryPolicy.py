from datetime import timedelta

from temporalio.common import RetryPolicy


def StorageRetryPolicy() -> RetryPolicy:  # noqa: N802 - named as a policy, not a function
    """
    For S3 round trips: blips against the object store are usually transient,
    so retry a few times and back off quickly.

    A new object every call, so a caller that mutates one cannot affect
    anybody else's policy.
    """
    return RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=30),
        maximum_attempts=3,
    )
