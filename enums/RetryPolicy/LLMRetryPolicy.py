from datetime import timedelta

from temporalio.common import RetryPolicy


def LLMRetryPolicy() -> RetryPolicy:  # noqa: N802 - named as a policy, not a function
    """
    For model calls: rate limits and malformed replies are both worth another
    go, but each attempt costs money and time, so back off hard and stop at
    three.

    A new object every call, so a caller that mutates one cannot affect
    anybody else's policy.
    """
    return RetryPolicy(
        initial_interval=timedelta(seconds=10),
        backoff_coefficient=3.0,
        maximum_interval=timedelta(minutes=2),
        maximum_attempts=3,
    )
