from datetime import timedelta

import pytest
from temporalio.common import RetryPolicy as TemporalRetryPolicy

from enums import RetryPolicies, get_retry_policy


@pytest.mark.parametrize("profile", list(RetryPolicies))
def test_every_profile_returns_a_temporal_retry_policy(profile):
    assert isinstance(profile.policy, TemporalRetryPolicy)


@pytest.mark.parametrize("profile", list(RetryPolicies))
def test_every_profile_returns_a_fresh_object(profile):
    """A caller mutating one policy must not affect anybody else's."""
    first = profile.policy
    second = profile.policy

    assert first is not second
    assert first == second


def test_mutating_a_returned_policy_does_not_leak(profile=RetryPolicies.STORAGE):
    borrowed = profile.policy
    borrowed.maximum_attempts = 99

    assert profile.policy.maximum_attempts != 99


def test_storage_retries_more_than_parsing():
    """Storage blips are transient; a parse failure usually is not."""
    assert RetryPolicies.STORAGE.policy.maximum_attempts > RetryPolicies.PARSING.policy.maximum_attempts


def test_parsing_backs_off_further_before_the_first_retry():
    assert RetryPolicies.PARSING.policy.initial_interval > RetryPolicies.STORAGE.policy.initial_interval


def test_strict_does_not_retry():
    assert RetryPolicies.STRICT.policy.maximum_attempts == 1


@pytest.mark.parametrize("profile", list(RetryPolicies))
def test_intervals_are_timedeltas(profile):
    policy = profile.policy

    if policy.initial_interval is not None:
        assert isinstance(policy.initial_interval, timedelta)
    if policy.maximum_interval is not None:
        assert isinstance(policy.maximum_interval, timedelta)


@pytest.mark.parametrize("profile", [RetryPolicies.STORAGE, RetryPolicies.PARSING])
def test_backoff_actually_grows(profile):
    policy = profile.policy

    assert policy.backoff_coefficient > 1.0
    assert policy.maximum_interval >= policy.initial_interval


def test_get_retry_policy_accepts_a_member():
    assert get_retry_policy(RetryPolicies.STORAGE) == RetryPolicies.STORAGE.policy


def test_get_retry_policy_accepts_a_name():
    assert get_retry_policy("storage") == RetryPolicies.STORAGE.policy


def test_get_retry_policy_is_case_insensitive():
    assert get_retry_policy("STORAGE") == RetryPolicies.STORAGE.policy


def test_get_retry_policy_rejects_an_unknown_name():
    with pytest.raises(ValueError):
        get_retry_policy("does-not-exist")


def test_the_workflow_uses_the_named_profiles():
    """Guards against someone re-inlining a policy in the workflow."""
    import inspect

    from workflows import workflow_process_pdf

    source = inspect.getsource(workflow_process_pdf)
    assert "RetryPolicies.STORAGE.policy" in source
    assert "RetryPolicies.PARSING.policy" in source
    assert "RetryPolicy(" not in source
