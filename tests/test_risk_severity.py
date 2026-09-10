import json

import pytest

from enums.RiskSeverity import RiskSeverity

LOW, MEDIUM, HIGH, CRITICAL = RiskSeverity.LOW, RiskSeverity.MEDIUM, RiskSeverity.HIGH, RiskSeverity.CRITICAL


def test_severities_are_ordered_by_seriousness():
    assert LOW < MEDIUM < HIGH < CRITICAL


def test_greater_than_is_by_seriousness_not_alphabet():
    """As a str enum, "low" > "high" alphabetically; the ranking must win."""
    assert HIGH > LOW
    assert CRITICAL > MEDIUM
    assert not LOW > HIGH


def test_the_inclusive_comparisons():
    assert HIGH >= HIGH
    assert CRITICAL >= HIGH
    assert MEDIUM <= MEDIUM
    assert LOW <= CRITICAL


def test_max_picks_the_worst():
    """LegalAdvice.worst_severity relies on this."""
    assert max([LOW, HIGH, MEDIUM]) is HIGH
    assert max([MEDIUM, LOW]) is MEDIUM


def test_sorting_is_by_seriousness():
    assert sorted([CRITICAL, LOW, HIGH, MEDIUM]) == [LOW, MEDIUM, HIGH, CRITICAL]


@pytest.mark.parametrize("raw", ["high", "HIGH", " High "])
def test_parse_is_forgiving_about_case_and_whitespace(raw):
    assert RiskSeverity.parse(raw) is HIGH


@pytest.mark.parametrize("raw", ["", "severe", "urgent", None])
def test_parse_rejects_anything_unrecognised(raw):
    with pytest.raises(ValueError, match="unknown risk severity"):
        RiskSeverity.parse(raw)


def test_it_serialises_as_its_value():
    """Temporal's JSON converter carries it between activities and the workflow."""
    assert json.dumps({"severity": HIGH}) == '{"severity": "high"}'
    assert RiskSeverity(json.loads('"high"')) is HIGH
