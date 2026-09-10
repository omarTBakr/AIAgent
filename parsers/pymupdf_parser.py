from pathlib import Path

import pymupdf
import pymupdf4llm

from exceptions.parsing import InvalidPdfError, PdfNotFoundError


def parse_pdf(source: Path | str | bytes, **kwargs):
    """
    Converts a PDF into markdown using pymupdf4llm.

    `source` is either a path to a PDF or the raw PDF bytes. Extra keyword
    arguments are handed straight to pymupdf4llm.to_markdown (page_chunks,
    write_images, table_strategy, ...).

    Returns a Markdown string, or a list of per-page dicts when the caller
    passes page_chunks=True.
    """
    try:
        if isinstance(source, bytes):
            doc = pymupdf.open(stream=source, filetype="pdf")
        else:
            source = Path(source)
            if not source.is_file():
                raise PdfNotFoundError(f"cannot parse, no such file: {source}")
            doc = pymupdf.open(source)
    except pymupdf.FileDataError as exc:
        raise InvalidPdfError(f"not a readable PDF: {source!r}") from exc

    try:
        return pymupdf4llm.to_markdown(doc, **kwargs)
    except Exception as exc:
        raise InvalidPdfError(f"could not convert the PDF to markdown: {exc}") from exc
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


def parse_pdf_pages(source: Path | str | bytes, **kwargs) -> list[str]:
    """
    Converts a PDF into one Markdown string per page.

    Same conversion as parse_pdf, but page by page, so a long document can be
    split into batches without guessing where the page boundaries were.
    """
    chunks = parse_pdf(source, page_chunks=True, **kwargs)

    # page_chunks makes to_markdown return a list of per-page dicts
    return [str(chunk.get("text", "")) for chunk in chunks]
