from dataclasses import dataclass

from enums.RiskSeverity import RiskSeverity


@dataclass
class KeyRisk:
    """One thing in a document that a lawyer would want to look at."""

    description: str
    severity: RiskSeverity
    location: str = ""

    @classmethod
    def from_model(cls, raw: dict) -> "KeyRisk":
        """
        Builds a risk from whatever the model returned.

        Raises ValueError on anything missing or unrecognised, so a bad reply
        fails the activity instead of quietly producing a risk with no severity.
        """
        if not isinstance(raw, dict):
            raise ValueError(f"a risk must be an object, got {type(raw).__name__}")

        description = str(raw.get("description", "")).strip()
        if not description:
            raise ValueError("a risk needs a description")

        return cls(
            description=description,
            severity=RiskSeverity.parse(raw.get("severity", "")),
            location=str(raw.get("location", "")).strip(),
        )
