import asyncio

from parsers.pymupdf_parser import parse_pdf
from utils.config import get_setting
from utils.utility import build_run_artifacts, download_s3_file, upload_s3_file


async def workflow(pdf: bytes, filename: str) -> dict:
    """
    Full round trip for one PDF:

      1. write the PDF into TEMP_PDF_FOLDER
      2. upload it to the S3_PDF_BUCKET bucket
      3. parse it into markdown with pymupdf4llm
      4. upload the markdown to the S3_PARSED_MDS bucket
      5. download that markdown back into TEMP_MD_FOLDER

    Returns the two S3 keys and the two local paths.
    """
    settings = get_setting()
    pdf_key, md_key, local_pdf = build_run_artifacts(filename, settings)

    # 1. stash the pdf locally
    await asyncio.to_thread(local_pdf.write_bytes, pdf)

    # 2. upload the original pdf
    await asyncio.to_thread(upload_s3_file, local_pdf, settings.s3_pdf_bucket, pdf_key)

    # 3. parse it (cpu bound, keep it off the event loop)
    markdown = await asyncio.to_thread(parse_pdf, local_pdf)

    # 4. upload the parsed markdown
    await asyncio.to_thread(upload_s3_file, markdown.encode("utf-8"), settings.s3_parsed_mds, md_key)

    # 5. pull it back down into the markdown scratch folder
    local_md = await asyncio.to_thread(download_s3_file, settings.s3_parsed_mds, md_key, settings.temp_md_path)

    return {
        "pdf_key": pdf_key,
        "md_key": md_key,
        "local_pdf": str(local_pdf),
        "local_md": str(local_md),
    }
