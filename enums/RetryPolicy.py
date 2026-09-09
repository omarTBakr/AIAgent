from datetime import timedelta
from enum import Enum

from temporalio.common import RetryPolicy


def StorageRetryPolicy() -> RetryPolicy:  # noqa: N802 - named as a policy, not a function
    """
    For S3 round trips: blips against the object store are usually transient,
    so retry a few times and back off quickly.
    """
    return RetryPolicy(
        initial_interval=timedelta(seconds=1),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(seconds=30),
        maximum_attempts=3,
    )


def ParsingRetryPolicy() -> RetryPolicy:  # noqa: N802
    """
    For PDF parsing: expensive and rarely fails transiently, so try once more
    at most and wait longer before doing it.
    """
    return RetryPolicy(
        initial_interval=timedelta(seconds=5),
        backoff_coefficient=2.0,
        maximum_interval=timedelta(minutes=1),
        maximum_attempts=2,
    )


def StrictRetryPolicy() -> RetryPolicy:  # noqa: N802
    """For steps that must not be repeated: run once, surface the failure."""
    return RetryPolicy(maximum_attempts=1)


class RetryProfile(Enum):
    """Lets a policy be picked by name, e.g. from configuration."""

    STORAGE = "storage"
    PARSING = "parsing"
    STRICT = "strict"

    @property
    def policy(self) -> RetryPolicy:
        return _BUILDERS[self]()


_BUILDERS = {
    RetryProfile.STORAGE: StorageRetryPolicy,
    RetryProfile.PARSING: ParsingRetryPolicy,
    RetryProfile.STRICT: StrictRetryPolicy,
}


def get_retry_policy(profile: RetryProfile | str) -> RetryPolicy:
    """
    Returns a RetryPolicy object for a profile, given the member or its name.

        get_retry_policy("storage")
        get_retry_policy(RetryProfile.PARSING)
    """
    if isinstance(profile, str):
        profile = RetryProfile(profile.lower())

    return profile.policy
