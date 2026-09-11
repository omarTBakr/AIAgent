"""Each legal activity through Temporal's ActivityEnvironment, with the FakeLLM
standing in for the model."""

import asyncio
import importlib
import json
import time

import pytest
from temporalio.testing import ActivityEnvironment

from activities import analyze_batch, human_followup, merge_advice, split_pages, upload_advice
from enums.PromptName import PromptName
from enums.ReviewDecision import ReviewDecision
from enums.RiskSeverity import RiskSeverity
from exceptions.llm import LLMResponseError
from schemas.analyze_batch import AnalyzeBatchInput
from schemas.human_followup import HumanFollowupInput
from schemas.key_risk import KeyRisk
from schemas.legal_advice import LegalAdvice
from schemas.merge_advice import MergeAdviceInput
from schemas.page_batch import PageBatch
from schemas.split_pages import SplitPagesInput
from schemas.upload_advice import UploadAdviceInput


@pytest.fixture
def env():
    return ActivityEnvironment()


BATCH = PageBatch(index=0, first_page=1, last_page=2, markdown="Clause 1. Unlimited liability.")

ADVICE = LegalAdvice(
    summary="A services agreement.",
    key_risks=[KeyRisk(description="Unlimited liability", severity=RiskSeverity.HIGH, location="clause 9")],
)


# --- split_pages ---------------------------------------------------------


async def test_split_pages_batches_a_real_pdf(env, settings, multi_page_pdf_bytes, tmp_path):
    source = tmp_path / "contract.pdf"
    source.write_bytes(multi_page_pdf_bytes)

    result = await env.run(
        split_pages,
        SplitPagesInput(task_id="t1", pdf_key="contract.pdf", local_pdf=str(source), pages_per_batch=2),
    )

    assert result.page_count == 6
    assert len(result.batches) == 3
    assert result.batches[0].label == "pages 1-2"


async def test_split_pages_keeps_the_document_text(env, multi_page_pdf_bytes, tmp_path):
    source = tmp_path / "contract.pdf"
    source.write_bytes(multi_page_pdf_bytes)

    result = await env.run(
        split_pages,
        SplitPagesInput(task_id="t1", pdf_key="contract.pdf", local_pdf=str(source), pages_per_batch=2),
    )

    joined = " ".join(b.markdown for b in result.batches)
    assert "Clause 1" in joined and "Clause 6" in joined


async def test_split_pages_does_not_block_the_event_loop(env, monkeypatch):
    """With several documents in flight, one parse must not stall the model calls of the others."""

    def slow_parse(source):
        time.sleep(0.3)
        return ["page one"]

    # the package re-exports the activity function under the module's name
    monkeypatch.setattr(importlib.import_module("activities.split_pages"), "parse_pdf_pages", slow_parse)

    ticks = 0

    async def tick():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    ticker = asyncio.create_task(tick())
    try:
        result = await env.run(
            split_pages,
            SplitPagesInput(task_id="t1", pdf_key="contract.pdf", local_pdf="unused.pdf", pages_per_batch=10),
        )
    finally:
        ticker.cancel()

    assert result.page_count == 1
    # a parse run on the loop itself would leave the ticker where it started
    assert ticks >= 10


# --- analyze_batch -------------------------------------------------------


async def test_analyze_batch_returns_validated_advice(env, llm):
    result = await env.run(
        analyze_batch,
        AnalyzeBatchInput(task_id="t1", pdf_key="contract.pdf", batch=BATCH, batch_count=1),
    )

    assert result.advice.summary
    assert result.advice.key_risks[0].severity is RiskSeverity.HIGH


async def test_analyze_batch_sends_the_batch_to_the_model(env, llm):
    await env.run(
        analyze_batch,
        AnalyzeBatchInput(task_id="t1", pdf_key="contract.pdf", batch=BATCH, batch_count=3),
    )

    call = llm.calls_for(PromptName.LEGAL_ADVICE)[0]
    assert call["variables"]["markdown"] == BATCH.markdown
    assert call["variables"]["batch_label"] == "pages 1-2"
    assert call["variables"]["batch_count"] == 3


async def test_analyze_batch_rejects_advice_with_no_summary(env, llm):
    llm.script(PromptName.LEGAL_ADVICE, {"key_risks": []})

    with pytest.raises(LLMResponseError, match="unusable"):
        await env.run(
            analyze_batch,
            AnalyzeBatchInput(task_id="t1", pdf_key="contract.pdf", batch=BATCH, batch_count=1),
        )


async def test_analyze_batch_rejects_an_unknown_severity(env, llm):
    """A mislabelled risk is worse than a failure the workflow can retry."""
    llm.script(
        PromptName.LEGAL_ADVICE,
        {"summary": "ok", "key_risks": [{"description": "d", "severity": "apocalyptic"}]},
    )

    with pytest.raises(LLMResponseError):
        await env.run(
            analyze_batch,
            AnalyzeBatchInput(task_id="t1", pdf_key="contract.pdf", batch=BATCH, batch_count=1),
        )


async def test_analyze_batch_rejects_a_question_with_no_question(env, llm):
    llm.script(PromptName.LEGAL_ADVICE, {"summary": "ok", "needs_human": True, "question": ""})

    with pytest.raises(LLMResponseError):
        await env.run(
            analyze_batch,
            AnalyzeBatchInput(task_id="t1", pdf_key="contract.pdf", batch=BATCH, batch_count=1),
        )


# --- merge_advice --------------------------------------------------------


async def test_merging_one_part_skips_the_model(env, llm):
    """A single-batch document cannot be improved by a merge, so don't pay for one."""
    result = await env.run(merge_advice, MergeAdviceInput(task_id="t1", pdf_key="a.pdf", parts=[ADVICE]))

    assert result.advice is ADVICE
    assert llm.calls_for(PromptName.MERGE_ADVICE) == []


async def test_merging_several_parts_calls_the_model(env, llm):
    llm.script(PromptName.MERGE_ADVICE, {"summary": "Merged.", "key_risks": []})

    result = await env.run(merge_advice, MergeAdviceInput(task_id="t1", pdf_key="a.pdf", parts=[ADVICE, ADVICE]))

    assert result.advice.summary == "Merged."
    assert len(llm.calls_for(PromptName.MERGE_ADVICE)) == 1


async def test_the_merge_prompt_receives_every_part(env, llm):
    llm.script(PromptName.MERGE_ADVICE, {"summary": "Merged.", "key_risks": []})

    await env.run(merge_advice, MergeAdviceInput(task_id="t1", pdf_key="a.pdf", parts=[ADVICE, ADVICE]))

    parts_text = llm.calls_for(PromptName.MERGE_ADVICE)[0]["variables"]["parts"]
    assert parts_text.count("Unlimited liability") == 2


async def test_merging_nothing_is_an_error(env, llm):
    with pytest.raises(LLMResponseError, match="nothing to merge"):
        await env.run(merge_advice, MergeAdviceInput(task_id="t1", pdf_key="a.pdf", parts=[]))


# --- human_followup ------------------------------------------------------


async def test_followup_revises_the_advice(env, llm):
    llm.script(PromptName.HUMAN_FOLLOWUP, {"summary": "Revised for UK law.", "key_risks": []})

    result = await env.run(
        human_followup,
        HumanFollowupInput(task_id="t1", pdf_key="a.pdf", advice=ADVICE, question="Which law?", answer="UK"),
    )

    assert result.advice.summary == "Revised for UK law."


async def test_followup_marks_the_advice_human_approved(env, llm):
    llm.script(PromptName.HUMAN_FOLLOWUP, {"summary": "Revised.", "key_risks": []})

    result = await env.run(
        human_followup,
        HumanFollowupInput(task_id="t1", pdf_key="a.pdf", advice=ADVICE, question="Which law?", answer="UK"),
    )

    assert result.advice.review_decision is ReviewDecision.HUMAN_APPROVED
    assert result.advice.review_decision.was_seen_by_a_human


async def test_followup_clears_the_question(env, llm):
    """Otherwise a document could bounce between model and human forever."""
    llm.script(PromptName.HUMAN_FOLLOWUP, {"summary": "Revised.", "key_risks": [], "needs_human": True, "question": "again?"})

    result = await env.run(
        human_followup,
        HumanFollowupInput(task_id="t1", pdf_key="a.pdf", advice=ADVICE, question="Which law?", answer="UK"),
    )

    assert result.advice.needs_human is False
    assert result.advice.question == ""


async def test_followup_gives_the_model_the_answer(env, llm):
    llm.script(PromptName.HUMAN_FOLLOWUP, {"summary": "Revised.", "key_risks": []})

    await env.run(
        human_followup,
        HumanFollowupInput(task_id="t1", pdf_key="a.pdf", advice=ADVICE, question="Which law?", answer="UK law"),
    )

    variables = llm.calls_for(PromptName.HUMAN_FOLLOWUP)[0]["variables"]
    assert variables["answer"] == "UK law"
    assert "Unlimited liability" in variables["draft"]


# --- upload_advice -------------------------------------------------------


async def test_upload_advice_stores_json(env, s3, settings):
    result = await env.run(upload_advice, UploadAdviceInput(task_id="t1", pdf_key="contract.pdf", advice=ADVICE))

    assert result.bucket == settings.s3_legal_advice
    assert result.key == "contract.advice.json"
    assert result.s3_path == f"s3://{settings.s3_legal_advice}/contract.advice.json"


async def test_the_stored_document_is_readable(env, s3, settings):
    await env.run(upload_advice, UploadAdviceInput(task_id="t1", pdf_key="contract.pdf", advice=ADVICE))

    stored = json.loads(s3.objects[(settings.s3_legal_advice, "contract.advice.json")])
    assert stored["summary"] == ADVICE.summary
    assert stored["key_risks"][0]["severity"] == "high"
    assert stored["review_decision"] == "auto_approved"
