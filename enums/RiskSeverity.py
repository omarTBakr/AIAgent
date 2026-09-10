from enum import StrEnum


class RiskSeverity(StrEnum):
    """
    How serious a flagged risk is.

    A str enum so Temporal's JSON converter can carry it between activities
    and the workflow; a plain Enum is not serialisable.

    Ordered, so a list of risks can be sorted worst-first and a threshold like
    "anything at or above HIGH" is expressible. Every comparison is defined
    here, because the str base would otherwise compare the values
    alphabetically ("low" > "high").
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return _ORDER.index(self)

    def __lt__(self, other: "RiskSeverity") -> bool:
        if not isinstance(other, RiskSeverity):
            return NotImplemented
        return self.rank < other.rank

    def __le__(self, other: "RiskSeverity") -> bool:
        if not isinstance(other, RiskSeverity):
            return NotImplemented
        return self.rank <= other.rank

    def __gt__(self, other: "RiskSeverity") -> bool:
        if not isinstance(other, RiskSeverity):
            return NotImplemented
        return self.rank > other.rank

    def __ge__(self, other: "RiskSeverity") -> bool:
        if not isinstance(other, RiskSeverity):
            return NotImplemented
        return self.rank >= other.rank

    @classmethod
    def parse(cls, value: str) -> "RiskSeverity":
        """
        Turns whatever the model wrote into a severity.

        Raises ValueError for anything unrecognised rather than guessing: a
        mislabelled risk is worse than a failed parse the caller can retry.
        """
        try:
            return cls(str(value).strip().lower())
        except ValueError as exc:
            raise ValueError(f"unknown risk severity: {value!r}") from exc


_ORDER = [RiskSeverity.LOW, RiskSeverity.MEDIUM, RiskSeverity.HIGH, RiskSeverity.CRITICAL]
