"""The OpenRouter client is tested against httpx's MockTransport, so the shape
of the request and the handling of each failure are covered without the network
or a bill."""

import httpx
import pytest

from enums.PromptName import PromptName
from exceptions.llm import (
    LLMConfigurationError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from interfaces.openrouter_llm import OpenRouterLLM
from prompts import get_prompt

PROMPT_VARS = {
    "pdf_key": "contract.pdf",
    "batch_label": "pages 1-2",
    "batch_number": 1,
    "batch_count": 3,
    "markdown": "Clause 1. The supplier shall...",
}


def client_returning(handler, settings) -> OpenRouterLLM:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url=settings.openrouter_base_url)
    return OpenRouterLLM(settings, client=http)


def reply(content: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})


async def test_a_successful_call_returns_the_content(settings):
    llm = client_returning(lambda request: reply('{"summary": "ok"}'), settings)

    assert await llm.complete(get_prompt(PromptName.LEGAL_ADVICE), **PROMPT_VARS) == '{"summary": "ok"}'


async def test_the_request_carries_the_model_and_both_messages(settings):
    seen = {}

    def handler(request):
        seen.update(request.read() and __import__("json").loads(request.read()))
        return reply('{"summary": "ok"}')

    llm = client_returning(handler, settings)
    await llm.complete(get_prompt(PromptName.LEGAL_ADVICE), **PROMPT_VARS)

    assert seen["model"] == settings.openrouter_model
    assert [m["role"] for m in seen["messages"]] == ["system", "user"]
    assert "contract.pdf" in seen["messages"][1]["content"]
    assert seen["temperature"] == settings.llm_temperature
    assert seen["response_format"] == {"type": "json_object"}


async def test_the_api_key_is_sent(settings):
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        return reply('{"summary": "ok"}')

    http = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url=settings.openrouter_base_url,
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
    )
    await OpenRouterLLM(settings, client=http).complete(get_prompt(PromptName.LEGAL_ADVICE), **PROMPT_VARS)

    assert seen["auth"] == "Bearer test-llm-key"


async def test_complete_json_parses_the_reply(settings):
    llm = client_returning(lambda request: reply('```json\n{"summary": "ok"}\n```'), settings)

    assert await llm.complete_json(get_prompt(PromptName.LEGAL_ADVICE), **PROMPT_VARS) == {"summary": "ok"}


async def test_a_429_is_a_rate_limit_error(settings):
    llm = client_returning(lambda request: httpx.Response(429, json={}), settings)

    with pytest.raises(LLMRateLimitError):
        await llm.complete(get_prompt(PromptName.LEGAL_ADVICE), **PROMPT_VARS)


async def test_a_500_is_an_llm_error(settings):
    llm = client_returning(lambda request: httpx.Response(500, text="upstream exploded"), settings)

    with pytest.raises(LLMError, match="500"):
        await llm.complete(get_prompt(PromptName.LEGAL_ADVICE), **PROMPT_VARS)


async def test_a_timeout_is_a_timeout_error(settings):
    def handler(request):
        raise httpx.TimeoutException("too slow")

    llm = client_returning(handler, settings)

    with pytest.raises(LLMTimeoutError, match="did not answer"):
        await llm.complete(get_prompt(PromptName.LEGAL_ADVICE), **PROMPT_VARS)


async def test_a_transport_failure_is_an_llm_error(settings):
    def handler(request):
        raise httpx.ConnectError("no route to host")

    llm = client_returning(handler, settings)

    with pytest.raises(LLMError, match="could not reach OpenRouter"):
        await llm.complete(get_prompt(PromptName.LEGAL_ADVICE), **PROMPT_VARS)


async def test_an_error_body_is_surfaced(settings):
    llm = client_returning(lambda request: httpx.Response(200, json={"error": {"message": "no credits"}}), settings)

    with pytest.raises(LLMError, match="no credits"):
        await llm.complete(get_prompt(PromptName.LEGAL_ADVICE), **PROMPT_VARS)


async def test_an_unexpected_envelope_is_a_response_error(settings):
    llm = client_returning(lambda request: httpx.Response(200, json={"unexpected": True}), settings)

    with pytest.raises(LLMResponseError, match="unexpected OpenRouter response shape"):
        await llm.complete(get_prompt(PromptName.LEGAL_ADVICE), **PROMPT_VARS)


async def test_an_empty_message_is_a_response_error(settings):
    llm = client_returning(lambda request: reply(""), settings)

    with pytest.raises(LLMResponseError, match="empty message"):
        await llm.complete(get_prompt(PromptName.LEGAL_ADVICE), **PROMPT_VARS)


async def test_a_non_json_body_is_a_response_error(settings):
    llm = client_returning(lambda request: httpx.Response(200, text="<html>gateway</html>"), settings)

    with pytest.raises(LLMResponseError, match="not JSON"):
        await llm.complete(get_prompt(PromptName.LEGAL_ADVICE), **PROMPT_VARS)


def test_construction_without_a_key_fails_fast(settings, monkeypatch):
    monkeypatch.setattr(settings, "openrouter_api_key", "")

    with pytest.raises(LLMConfigurationError):
        OpenRouterLLM(settings)
