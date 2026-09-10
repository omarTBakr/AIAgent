import pytest

from utils.utility import build_run_artifacts, download_s3_file, get_s3_client, upload_s3_file


def test_build_run_artifacts_shares_one_run_id(settings):
    artifacts = build_run_artifacts("intro_to_stats.pdf", settings)

    assert artifacts.pdf_key.startswith("intro_to_stats-")
    assert artifacts.pdf_key.endswith(".pdf")
    assert artifacts.md_key.endswith(".md")
    # same stem and run id, only the extension differs
    assert artifacts.pdf_key[: -len(".pdf")] == artifacts.md_key[: -len(".md")]


def test_build_run_artifacts_is_unique_per_call(settings):
    first = build_run_artifacts("report.pdf", settings)
    second = build_run_artifacts("report.pdf", settings)

    assert first.pdf_key != second.pdf_key


def test_build_run_artifacts_falls_back_for_a_blank_name(settings):
    assert build_run_artifacts("", settings).pdf_key.startswith("document-")


def test_build_run_artifacts_strips_any_directory(settings):
    artifacts = build_run_artifacts("/home/omar/papers/report.pdf", settings)

    assert artifacts.pdf_key.startswith("report-")
    assert "/" not in artifacts.pdf_key


def test_build_run_artifacts_local_path_sits_in_the_pdf_folder(settings):
    artifacts = build_run_artifacts("report.pdf", settings)

    assert artifacts.local_pdf.parent == settings.temp_pdf_path
    assert artifacts.local_pdf.name == artifacts.pdf_key


def test_get_s3_client_is_a_singleton(settings):
    assert get_s3_client() is get_s3_client()


def test_upload_bytes(s3):
    key = upload_s3_file(b"hello", "test-pdfs", "greeting.txt")

    assert key == "greeting.txt"
    assert s3.objects[("test-pdfs", "greeting.txt")] == b"hello"


def test_upload_a_file_from_disk(s3, tmp_path):
    source = tmp_path / "note.md"
    source.write_text("# heading")

    upload_s3_file(source, "test-mds", "note.md")

    assert s3.objects[("test-mds", "note.md")] == b"# heading"


def test_upload_a_missing_file_raises(s3, tmp_path):
    with pytest.raises(FileNotFoundError):
        upload_s3_file(tmp_path / "nope.pdf", "test-pdfs", "nope.pdf")


def test_download_to_an_explicit_path(s3, tmp_path):
    s3.objects[("test-mds", "note.md")] = b"# downloaded"
    destination = tmp_path / "out" / "renamed.md"

    result = download_s3_file("test-mds", "note.md", destination)

    assert result == destination
    assert destination.read_text() == "# downloaded"


def test_download_into_a_directory_keeps_the_key_name(s3, tmp_path):
    s3.objects[("test-mds", "note.md")] = b"# downloaded"

    result = download_s3_file("test-mds", "note.md", tmp_path)

    assert result == tmp_path / "note.md"
    assert result.read_text() == "# downloaded"


def test_download_creates_missing_parent_directories(s3, tmp_path):
    s3.objects[("test-mds", "note.md")] = b"x"
    destination = tmp_path / "deeply" / "nested" / "note.md"

    download_s3_file("test-mds", "note.md", destination)

    assert destination.is_file()


def test_the_task_id_is_shared_by_both_keys(settings):
    artifacts = build_run_artifacts("report.pdf", settings)

    assert artifacts.task_id
    assert artifacts.task_id in artifacts.pdf_key
    assert artifacts.task_id in artifacts.md_key


def test_the_task_id_is_unique_per_call(settings):
    first = build_run_artifacts("report.pdf", settings)
    second = build_run_artifacts("report.pdf", settings)

    assert first.task_id != second.task_id
