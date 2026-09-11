import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

import parsers.pymupdf_parser
from parsers.pymupdf_parser import parse_pdf, parse_pdf_to_file


def test_parses_from_several_threads_never_overlap(pdf_bytes, monkeypatch):
    """PyMuPDF is not thread-safe; activities parse in threads, so the parser must serialise them."""
    active = 0
    most_at_once = 0
    counter_lock = threading.Lock()

    def slow_to_markdown(doc, **kwargs):
        nonlocal active, most_at_once
        with counter_lock:
            active += 1
            most_at_once = max(most_at_once, active)
        time.sleep(0.05)
        with counter_lock:
            active -= 1
        return "parsed"

    monkeypatch.setattr(parsers.pymupdf_parser.pymupdf4llm, "to_markdown", slow_to_markdown)

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: parse_pdf(pdf_bytes), range(6)))

    assert results == ["parsed"] * 6
    assert most_at_once == 1


def test_parse_from_bytes(pdf_bytes):
    markdown = parse_pdf(pdf_bytes)

    assert "Quarterly Report" in markdown
    assert "Revenue grew 12 percent" in markdown


def test_parse_from_a_path(pdf_bytes, tmp_path):
    source = tmp_path / "sample.pdf"
    source.write_bytes(pdf_bytes)

    assert "Quarterly Report" in parse_pdf(source)


def test_large_headings_become_markdown_headings(pdf_bytes):
    """The 22pt line should come out as a heading, not body text."""
    assert "# Quarterly Report" in parse_pdf(pdf_bytes)


def test_parse_a_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_pdf(tmp_path / "nope.pdf")


def test_parse_to_file_writes_utf8(pdf_bytes, tmp_path):
    destination = tmp_path / "out" / "sample.md"

    result = parse_pdf_to_file(pdf_bytes, destination)

    assert result == destination
    assert "Quarterly Report" in destination.read_text(encoding="utf-8")
