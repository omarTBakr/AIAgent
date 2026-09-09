from datetime import timedelta
from enum import Enum

from temporalio.common import RetryPolicy as TemporalRetryPolicy


class RetryPolicies(Enum):
    """
    Named retry profiles for activities, so the tuning lives in one place
    instead of being spelled out at every call site.

    Each member builds a fresh `temporalio.common.RetryPolicy`:

        execute_activity(..., retry_policy=RetryPolicies.STORAGE.policy)
    """

    STORAGE = "storage"
    PARSING = "parsing"
    STRICT = "strict"

    @property
    def policy(self) -> TemporalRetryPolicy:
        """Returns a RetryPolicy object for this profile."""
        return _build(self)


def _build(profile: RetryPolicies) -> TemporalRetryPolicy:
    """
    A new object every call, so a caller that mutates one cannot affect
    anybody else's policy.
    """
    if profile is RetryPolicies.STORAGE:
        # network blips against the object store are worth retrying quickly
        return TemporalRetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )

    if profile is RetryPolicies.PARSING:
        # parsing is expensive and rarely fails transiently, so back off harder
        return TemporalRetryPolicy(
            initial_interval=timedelta(seconds=5),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(minutes=1),
            maximum_attempts=2,
        )

    # STRICT: run once, surface the failure immediately
    return TemporalRetryPolicy(maximum_attempts=1)


def get_retry_policy(profile: RetryPolicies | str) -> TemporalRetryPolicy:
    """
    Returns a RetryPolicy object for a profile, given the member or its name.

        get_retry_policy("storage")
        get_retry_policy(RetryPolicies.PARSING)
    """
    if isinstance(profile, str):
        profile = RetryPolicies(profile.lower())

    return profile.policy
