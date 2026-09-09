from datetime import timedelta

from temporalio.common import RetryPolicy


def ParsingRetryPolicy() -> RetryPolicy:  # noqa: N802 - named as a policy, not a function
    """
    For PDF parsing: expensive and rarely fails transiently, so try once more
    at most and wait longer before doing it.

    A new object every call, so a caller that mutates one cannot affect
    anybody else's policy.
    """
    return RetryPolicy(
        initial_interval=timedelta(seconds=5),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(minutes=1),
        maximum_attempts=2,
    )
