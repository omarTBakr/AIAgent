import json

import pytest

from enums.ReviewDecision import ReviewDecision


@pytest.mark.parametrize("decision", [ReviewDecision.HUMAN_APPROVED, ReviewDecision.HUMAN_REJECTED])
def test_human_decisions_were_seen_by_a_human(decision):
    assert decision.was_seen_by_a_human


@pytest.mark.parametrize("decision", [ReviewDecision.AUTO_APPROVED, ReviewDecision.UNREVIEWED_TIMEOUT])
def test_the_others_were_not(decision):
    assert not decision.was_seen_by_a_human


def test_only_a_timeout_needs_attention():
    assert [decision for decision in ReviewDecision if decision.needs_attention] == [ReviewDecision.UNREVIEWED_TIMEOUT]


def test_it_serialises_as_its_value():
    """Temporal's JSON converter carries it inside LegalAdvice."""
    assert json.dumps(ReviewDecision.HUMAN_APPROVED) == '"human_approved"'
    assert ReviewDecision(json.loads('"unreviewed_timeout"')) is ReviewDecision.UNREVIEWED_TIMEOUT
