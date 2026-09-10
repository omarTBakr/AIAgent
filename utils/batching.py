from schemas.page_batch import PageBatch


def split_pages_into_batches(pages: list[str], pages_per_batch: int) -> list[PageBatch]:
    """
    Groups a document's pages into LLM-sized batches.

    Page numbers are 1-based and refer to the original document, so a batch can
    say where it came from. Blank pages are kept: dropping them would make the
    numbering lie.
    """
    if pages_per_batch < 1:
        raise ValueError(f"pages_per_batch must be at least 1, got {pages_per_batch}")

    batches = []

    for index, start in enumerate(range(0, len(pages), pages_per_batch)):
        chunk = pages[start : start + pages_per_batch]

        batches.append(
            PageBatch(
                index=index,
                first_page=start + 1,
                last_page=start + len(chunk),
                markdown="\n\n".join(chunk).strip(),
            )
        )

    return batches
