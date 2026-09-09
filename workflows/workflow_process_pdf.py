from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# The workflow sandbox re-imports this module; anything doing real I/O at import
# time has to be passed through rather than re-executed inside the sandbox.
with workflow.unsafe.imports_passed_through():
    from activities.download_md import download_md
    from activities.download_pdf import download_pdf
    from activities.parse_pdf import parse_pdf
    from activities.upload_md import upload_md
    from schemas.download_md import DownloadMdInput
    from schemas.download_pdf import DownloadPdfInput
    from schemas.parse_pdf import ParsePdfInput
    from schemas.process_pdf import ProcessPdfInput, ProcessPdfOutput
    from schemas.upload_md import UploadMdInput

# S3 round trips are quick; a parse of a large PDF is not.
STORAGE_TIMEOUT = timedelta(minutes=1)
PARSE_TIMEOUT = timedelta(minutes=10)

RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
    maximum_attempts=3,
)


@workflow.defn
class ProcessPdfWorkflow:
    """
    Turns a PDF that is already in the PDF bucket into Markdown.

    The caller uploads the PDF first and passes only the keys, so the document
    itself never travels through the workflow history.

      1. download the PDF onto the worker
      2. parse it into Markdown
      3. upload the Markdown to the parsed bucket
      4. download the Markdown back into the local Markdown folder
    """

    @workflow.run
    async def run(self, payload: ProcessPdfInput) -> ProcessPdfOutput:
        workflow.logger.info("processing %s -> %s", payload.pdf_key, payload.md_key)

        fetched = await workflow.execute_activity(
            download_pdf,
            DownloadPdfInput(key=payload.pdf_key),
            start_to_close_timeout=STORAGE_TIMEOUT,
            retry_policy=RETRY_POLICY,
        )

        parsed = await workflow.execute_activity(
            parse_pdf,
            ParsePdfInput(local_path=fetched.local_path),
            start_to_close_timeout=PARSE_TIMEOUT,
            retry_policy=RETRY_POLICY,
        )

        await workflow.execute_activity(
            upload_md,
            UploadMdInput(markdown=parsed.markdown, key=payload.md_key),
            start_to_close_timeout=STORAGE_TIMEOUT,
            retry_policy=RETRY_POLICY,
        )

        final = await workflow.execute_activity(
            download_md,
            DownloadMdInput(key=payload.md_key),
            start_to_close_timeout=STORAGE_TIMEOUT,
            retry_policy=RETRY_POLICY,
        )

        workflow.logger.info("finished %s", payload.md_key)

        return ProcessPdfOutput(
            pdf_key=payload.pdf_key,
            md_key=payload.md_key,
            local_pdf=fetched.local_path,
            local_md=final.local_path,
        )
