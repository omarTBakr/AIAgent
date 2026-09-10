from enum import StrEnum


class ReviewDecision(StrEnum):
    """
    How a piece of advice came to be final.

    A str enum so Temporal's JSON converter can carry it inside LegalAdvice.
    """

    AUTO_APPROVED = "auto_approved"
    HUMAN_APPROVED = "human_approved"
    HUMAN_REJECTED = "human_rejected"
    UNREVIEWED_TIMEOUT = "unreviewed_timeout"

    @property
    def was_seen_by_a_human(self) -> bool:
        return self in (ReviewDecision.HUMAN_APPROVED, ReviewDecision.HUMAN_REJECTED)

    @property
    def needs_attention(self) -> bool:
        """Advice nobody signed off on, which the model itself was unsure about."""
        return self is ReviewDecision.UNREVIEWED_TIMEOUT
