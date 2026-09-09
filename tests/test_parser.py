import pytest

from parsers.pymupdf_parser import parse_pdf, parse_pdf_to_file


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
