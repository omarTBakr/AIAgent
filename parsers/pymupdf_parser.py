from pathlib import Path

import pymupdf
import pymupdf4llm


def parse_pdf(source: Path | str | bytes, **kwargs) -> str:
    """
    Converts a PDF into markdown using pymupdf4llm.

    `source` is either a path to a PDF or the raw PDF bytes. Extra keyword
    arguments are handed straight to pymupdf4llm.to_markdown (page_chunks,
    write_images, table_strategy, ...).
    """
    if isinstance(source, bytes):
        doc = pymupdf.open(stream=source, filetype="pdf")
    else:
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(f"cannot parse, no such file: {source}")
        doc = pymupdf.open(source)

    try:
        return pymupdf4llm.to_markdown(doc, **kwargs)
    finally:
        doc.close()


def parse_pdf_to_file(source: Path | str | bytes, destination: Path | str, **kwargs) -> Path:
    """
    Parses a PDF and writes the markdown to `destination`. Returns that path.
    """
    markdown = parse_pdf(source, **kwargs)

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(markdown, encoding="utf-8")

    return destination
