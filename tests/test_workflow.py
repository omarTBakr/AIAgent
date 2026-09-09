from utils.workflow import workflow


async def test_workflow_returns_both_keys_and_both_paths(s3, pdf_bytes):
    result = await workflow(pdf_bytes, "intro_to_stats.pdf")

    assert set(result) == {"pdf_key", "md_key", "local_pdf", "local_md"}
    assert result["pdf_key"].startswith("intro_to_stats-")
    assert result["md_key"].endswith(".md")


async def test_workflow_uploads_to_both_buckets(s3, pdf_bytes, settings):
    result = await workflow(pdf_bytes, "report.pdf")

    assert (settings.s3_pdf_bucket, result["pdf_key"]) in s3.objects
    assert (settings.s3_parsed_mds, result["md_key"]) in s3.objects


async def test_workflow_uploads_the_original_pdf_unchanged(s3, pdf_bytes, settings):
    result = await workflow(pdf_bytes, "report.pdf")

    assert s3.objects[(settings.s3_pdf_bucket, result["pdf_key"])] == pdf_bytes


async def test_workflow_uploads_parsed_markdown(s3, pdf_bytes, settings):
    result = await workflow(pdf_bytes, "report.pdf")

    stored = s3.objects[(settings.s3_parsed_mds, result["md_key"])].decode("utf-8")
    assert "Quarterly Report" in stored


async def test_workflow_writes_the_pdf_into_the_pdf_folder(s3, pdf_bytes, settings):
    from pathlib import Path

    result = await workflow(pdf_bytes, "report.pdf")

    local_pdf = Path(result["local_pdf"])
    assert local_pdf.parent == settings.temp_pdf_path
    assert local_pdf.read_bytes() == pdf_bytes


async def test_workflow_downloads_markdown_into_the_md_folder(s3, pdf_bytes, settings):
    from pathlib import Path

    result = await workflow(pdf_bytes, "report.pdf")

    local_md = Path(result["local_md"])
    assert local_md.parent == settings.temp_md_path
    assert "Quarterly Report" in local_md.read_text(encoding="utf-8")


async def test_two_runs_of_the_same_filename_do_not_collide(s3, pdf_bytes):
    first = await workflow(pdf_bytes, "report.pdf")
    second = await workflow(pdf_bytes, "report.pdf")

    assert first["pdf_key"] != second["pdf_key"]
    assert first["local_md"] != second["local_md"]
    assert len(s3.objects) == 4
