import asyncio
from datetime import timedelta

from temporalio import workflow

# The workflow sandbox re-imports this module; anything doing real I/O at import
# time has to be passed through rather than re-executed inside the sandbox.
with workflow.unsafe.imports_passed_through():
    from activities.analyze_batch import analyze_batch
    from activities.download_pdf import download_pdf
    from activities.human_followup import human_followup
    from activities.merge_advice import merge_advice
    from activities.split_pages import split_pages
    from activities.upload_advice import upload_advice
    from enums.RetryPolicy.LLMRetryPolicy import LLMRetryPolicy
    from enums.RetryPolicy.ParsingRetryPolicy import ParsingRetryPolicy
    from enums.RetryPolicy.StorageRetryPolicy import StorageRetryPolicy
    from enums.ReviewDecision import ReviewDecision
    from enums.TaskStatus import TaskStatus
    from schemas.analyze_batch import AnalyzeBatchInput
    from schemas.download_pdf import DownloadPdfInput
    from schemas.human_followup import HumanFollowupInput
    from schemas.legal_advice import LegalAdvice
    from schemas.legal_review import DocumentAdvice, LegalReviewInput, LegalReviewResult
    from schemas.merge_advice import MergeAdviceInput
    from schemas.split_pages import SplitPagesInput
    from schemas.upload_advice import UploadAdviceInput

STORAGE_TIMEOUT = timedelta(minutes=1)
SPLIT_TIMEOUT = timedelta(minutes=10)
# a model call is slow and the policy already backs off; leave room for retries
LLM_TIMEOUT = timedelta(minutes=10)


@workflow.defn
class LegalReviewWorkflow:
    """
    Reviews several PDFs for legal risk, pausing for a human when the model
    asks a question it cannot answer from the document.

    At most `max_concurrent_pdfs` documents are in flight at once. The limit
    lives here rather than in worker configuration, so it holds however many
    worker processes are running.
    """

    def __init__(self) -> None:
        # pdf_key -> the question the model raised
        self._pending: dict[str, str] = {}
        # pdf_key -> the human's answer
        self._answers: dict[str, str] = {}
        # pdf_key -> where each document has got to
        self._progress: dict[str, str] = {}

    @workflow.run
    async def run(self, payload: LegalReviewInput) -> LegalReviewResult:
        workflow.logger.info("[task %s] reviewing %d document(s)", payload.task_id, len(payload.pdf_keys))

        limit = max(1, payload.max_concurrent_pdfs)
        # asyncio primitives are deterministic under Temporal's event loop
        gate = asyncio.Semaphore(limit)

        for pdf_key in payload.pdf_keys:
            self._progress[pdf_key] = TaskStatus.PROCESSING.value

        documents = await asyncio.gather(*(self._review_one(payload, key, gate) for key in payload.pdf_keys))

        workflow.logger.info("[task %s] finished %d document(s)", payload.task_id, len(documents))

        return LegalReviewResult(task_id=payload.task_id, documents=list(documents))

    async def _review_one(self, payload: LegalReviewInput, pdf_key: str, gate: asyncio.Semaphore) -> DocumentAdvice:
        async with gate:
            fetched = await workflow.execute_activity(
                download_pdf,
                DownloadPdfInput(task_id=payload.task_id, key=pdf_key),
                start_to_close_timeout=STORAGE_TIMEOUT,
                retry_policy=StorageRetryPolicy(),
            )

            split = await workflow.execute_activity(
                split_pages,
                SplitPagesInput(
                    task_id=payload.task_id,
                    pdf_key=pdf_key,
                    local_pdf=fetched.local_path,
                    pages_per_batch=payload.pages_per_batch,
                ),
                start_to_close_timeout=SPLIT_TIMEOUT,
                retry_policy=ParsingRetryPolicy(),
            )

            advice = await self._advise(payload, pdf_key, split.batches)

            if advice.needs_human:
                advice = await self._ask_a_human(payload, pdf_key, advice)

            stored = await workflow.execute_activity(
                upload_advice,
                UploadAdviceInput(task_id=payload.task_id, pdf_key=pdf_key, advice=advice),
                start_to_close_timeout=STORAGE_TIMEOUT,
                retry_policy=StorageRetryPolicy(),
            )
            advice.s3_path = stored.s3_path

            self._progress[pdf_key] = TaskStatus.COMPLETED.value

            return DocumentAdvice(pdf_key=pdf_key, advice=advice)

    async def _advise(self, payload: LegalReviewInput, pdf_key: str, batches: list) -> LegalAdvice:
        """One LLM call per batch, then a merge. Batches run in order."""
        parts = []

        for batch in batches:
            analysed = await workflow.execute_activity(
                analyze_batch,
                AnalyzeBatchInput(task_id=payload.task_id, pdf_key=pdf_key, batch=batch, batch_count=len(batches)),
                start_to_close_timeout=LLM_TIMEOUT,
                retry_policy=LLMRetryPolicy(),
            )
            parts.append(analysed.advice)

        merged = await workflow.execute_activity(
            merge_advice,
            MergeAdviceInput(task_id=payload.task_id, pdf_key=pdf_key, parts=parts),
            start_to_close_timeout=LLM_TIMEOUT,
            retry_policy=LLMRetryPolicy(),
        )

        return merged.advice

    async def _ask_a_human(self, payload: LegalReviewInput, pdf_key: str, advice: LegalAdvice) -> LegalAdvice:
        """
        Blocks this document until somebody answers, or the wait runs out.

        Only this document waits: the semaphore is still held, but the other
        in-flight document carries on, and a timeout must not lose the work
        already done, so the draft is returned flagged rather than discarded.
        """
        self._pending[pdf_key] = advice.question
        self._progress[pdf_key] = TaskStatus.AWAITING_HUMAN.value

        workflow.logger.info("[task %s] %s is waiting on a human: %s", payload.task_id, pdf_key, advice.question)

        try:
            await workflow.wait_condition(
                lambda: pdf_key in self._answers,
                timeout=timedelta(seconds=payload.human_input_timeout_seconds),
            )
        except TimeoutError:
            workflow.logger.warning("[task %s] nobody answered for %s; continuing unreviewed", payload.task_id, pdf_key)
            self._pending.pop(pdf_key, None)
            self._progress[pdf_key] = TaskStatus.PROCESSING.value
            advice.review_decision = ReviewDecision.UNREVIEWED_TIMEOUT
            return advice

        answer = self._answers[pdf_key]
        self._pending.pop(pdf_key, None)
        self._progress[pdf_key] = TaskStatus.PROCESSING.value

        revised = await workflow.execute_activity(
            human_followup,
            HumanFollowupInput(
                task_id=payload.task_id,
                pdf_key=pdf_key,
                advice=advice,
                question=advice.question,
                answer=answer,
            ),
            start_to_close_timeout=LLM_TIMEOUT,
            retry_policy=LLMRetryPolicy(),
        )

        return revised.advice

    @workflow.signal
    def human_response(self, pdf_key: str, answer: str) -> None:
        """Delivers a human's answer. Unknown keys are ignored, not an error."""
        workflow.logger.info("received an answer for %s", pdf_key)
        self._answers[pdf_key] = answer

    @workflow.query
    def pending_questions(self) -> list[dict]:
        """What the workflow is currently waiting to be told."""
        return [{"pdf_key": key, "question": question} for key, question in self._pending.items()]

    @workflow.query
    def progress(self) -> dict:
        """Where each document has got to."""
        return dict(self._progress)
