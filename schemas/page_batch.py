from dataclasses import dataclass


@dataclass
class PageBatch:
    """A slice of one document's pages, small enough for a single LLM call."""

    index: int
    first_page: int
    last_page: int
    markdown: str

    @property
    def label(self) -> str:
        """Human-readable range, used in prompts and logs."""
        if self.first_page == self.last_page:
            return f"page {self.first_page}"
        return f"pages {self.first_page}-{self.last_page}"
