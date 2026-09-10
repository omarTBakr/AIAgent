from temporalio import activity

from parsers.pymupdf_parser import parse_pdf as parse_pdf_to_markdown
from schemas.parse_pdf import ParsePdfInput, ParsePdfOutput


@activity.defn
async def parse_pdf(payload: ParsePdfInput) -> ParsePdfOutput:
    """Converts a local PDF into Markdown with pymupdf4llm."""
    activity.logger.info("[task %s] parsing pdf %s", payload.task_id, payload.local_path)

    try:
        markdown = parse_pdf_to_markdown(payload.local_path)
    except Exception:
        activity.logger.exception("[task %s] failed to parse pdf %s", payload.task_id, payload.local_path)
        raise

    activity.logger.info(
        "[task %s] parsed pdf %s into %d characters of markdown", payload.task_id, payload.local_path, len(markdown)
    )

    return ParsePdfOutput(markdown=markdown)
