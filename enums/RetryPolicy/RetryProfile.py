from enum import Enum

from temporalio.common import RetryPolicy

from enums.RetryPolicy.ParsingRetryPolicy import ParsingRetryPolicy
from enums.RetryPolicy.StorageRetryPolicy import StorageRetryPolicy
from enums.RetryPolicy.StrictRetryPolicy import StrictRetryPolicy


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
