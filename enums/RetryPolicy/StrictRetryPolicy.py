from temporalio.common import RetryPolicy


def StrictRetryPolicy() -> RetryPolicy:  # noqa: N802 - named as a policy, not a function
    """
    For steps that must not be repeated: run once, surface the failure.

    A new object every call, so a caller that mutates one cannot affect
    anybody else's policy.
    """
    return RetryPolicy(maximum_attempts=1)
