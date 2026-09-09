from datetime import timedelta

import pytest
from temporalio.common import RetryPolicy as TemporalRetryPolicy

from enums import ParsingRetryPolicy, RetryProfile, StorageRetryPolicy, StrictRetryPolicy, get_retry_policy
from enums.RetryPolicy.ParsingRetryPolicy import ParsingRetryPolicy as ParsingFromItsOwnModule
from enums.RetryPolicy.StorageRetryPolicy import StorageRetryPolicy as StorageFromItsOwnModule
from enums.RetryPolicy.StrictRetryPolicy import StrictRetryPolicy as StrictFromItsOwnModule

POLICIES = [StorageRetryPolicy, ParsingRetryPolicy, StrictRetryPolicy]


@pytest.mark.parametrize("build", POLICIES)
def test_every_policy_returns_a_temporal_retry_policy(build):
    assert isinstance(build(), TemporalRetryPolicy)


@pytest.mark.parametrize("build", POLICIES)
def test_every_policy_returns_a_fresh_object(build):
    """A caller mutating one policy must not affect anybody else's."""
    first = build()
    second = build()

    assert first is not second
    assert first == second


def test_mutating_a_returned_policy_does_not_leak():
    borrowed = StorageRetryPolicy()
    borrowed.maximum_attempts = 99

    assert StorageRetryPolicy().maximum_attempts != 99


def test_storage_retries_more_than_parsing():
    """Storage blips are transient; a parse failure usually is not."""
    assert StorageRetryPolicy().maximum_attempts > ParsingRetryPolicy().maximum_attempts


def test_parsing_backs_off_further_before_the_first_retry():
    assert ParsingRetryPolicy().initial_interval > StorageRetryPolicy().initial_interval


def test_strict_does_not_retry():
    assert StrictRetryPolicy().maximum_attempts == 1


@pytest.mark.parametrize("build", POLICIES)
def test_intervals_are_timedeltas(build):
    policy = build()

    if policy.initial_interval is not None:
        assert isinstance(policy.initial_interval, timedelta)
    if policy.maximum_interval is not None:
        assert isinstance(policy.maximum_interval, timedelta)


@pytest.mark.parametrize("build", [StorageRetryPolicy, ParsingRetryPolicy])
def test_backoff_actually_grows(build):
    policy = build()

    assert policy.backoff_coefficient > 1.0
    assert policy.maximum_interval >= policy.initial_interval


def test_get_retry_policy_accepts_a_member():
    assert get_retry_policy(RetryProfile.STORAGE) == StorageRetryPolicy()


def test_get_retry_policy_accepts_a_name():
    assert get_retry_policy("storage") == StorageRetryPolicy()


def test_get_retry_policy_is_case_insensitive():
    assert get_retry_policy("STORAGE") == StorageRetryPolicy()


@pytest.mark.parametrize("profile", list(RetryProfile))
def test_every_profile_resolves_to_a_policy(profile):
    assert isinstance(profile.policy, TemporalRetryPolicy)


def test_get_retry_policy_rejects_an_unknown_name():
    with pytest.raises(ValueError):
        get_retry_policy("does-not-exist")


def test_the_workflow_uses_the_named_profiles():
    """Guards against someone re-inlining a policy in the workflow."""
    import inspect

    from workflows import workflow_process_pdf

    source = inspect.getsource(workflow_process_pdf)
    assert "StorageRetryPolicy()" in source
    assert "ParsingRetryPolicy()" in source
    # the tuning must not be re-inlined into the workflow
    assert "maximum_attempts" not in source


def test_each_policy_lives_in_its_own_module():
    """Each policy is importable directly from the file named after it."""
    assert StorageFromItsOwnModule is StorageRetryPolicy
    assert ParsingFromItsOwnModule is ParsingRetryPolicy
    assert StrictFromItsOwnModule is StrictRetryPolicy


def test_module_names_match_the_policy_names():
    assert StorageRetryPolicy.__module__ == "enums.RetryPolicy.StorageRetryPolicy"
    assert ParsingRetryPolicy.__module__ == "enums.RetryPolicy.ParsingRetryPolicy"
    assert StrictRetryPolicy.__module__ == "enums.RetryPolicy.StrictRetryPolicy"
    assert RetryProfile.__module__ == "enums.RetryPolicy.RetryProfile"


def test_policies_are_grouped_under_the_retry_policy_package():
    """All four live under enums.RetryPolicy, not directly in enums."""
    import enums.RetryPolicy as package

    for name in ("StorageRetryPolicy", "ParsingRetryPolicy", "StrictRetryPolicy", "RetryProfile"):
        assert hasattr(package, name), name
        assert getattr(package, name).__module__.startswith("enums.RetryPolicy.")


def test_the_package_re_export_is_the_same_object():
    """`from enums import X` and the deep import must not diverge."""
    import enums
    import enums.RetryPolicy as package

    assert enums.StorageRetryPolicy is package.StorageRetryPolicy
    assert enums.get_retry_policy is package.get_retry_policy
