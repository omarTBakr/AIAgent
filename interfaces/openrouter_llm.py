import httpx

from exceptions.llm import (
    LLMConfigurationError,
    LLMError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from interfaces.llm_interface import LLMInterface
from prompts.prompt import Prompt
from utils.config import Settings
from utils.logger import get_logger

logger = get_logger(__name__)


class OpenRouterLLM(LLMInterface):
    """LLMInterface over OpenRouter's chat-completions API."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        if not settings.openrouter_api_key:
            raise LLMConfigurationError("OPENROUTER_API_KEY is not set")

        self._settings = settings
        # injectable so tests can supply a MockTransport instead of the network
        self._client = client

    @property
    def model(self) -> str:
        return self._settings.openrouter_model

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._settings.openrouter_base_url,
                timeout=self._settings.llm_timeout_seconds,
                headers={"Authorization": f"Bearer {self._settings.openrouter_api_key}"},
            )
        return self._client

    async def complete(self, prompt: Prompt, **variables) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": prompt.render(**variables)},
            ],
            "max_tokens": self._settings.llm_max_tokens,
            "temperature": self._settings.llm_temperature,
            # ask for JSON; the interface still validates, because not every
            # model honours this
            "response_format": {"type": "json_object"},
        }

        logger.info("asking %s for %s", self.model, prompt.name.value)

        try:
            response = await self._http().post("/chat/completions", json=payload)
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"{self.model} did not answer within {self._settings.llm_timeout_seconds}s") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"could not reach OpenRouter: {exc}") from exc

        if response.status_code == 429:
            raise LLMRateLimitError(f"OpenRouter is throttling {self.model}")

        if response.status_code >= 400:
            raise LLMError(f"OpenRouter returned {response.status_code}: {response.text[:200]}")

        return self._content_of(response)

    @staticmethod
    def _content_of(response: httpx.Response) -> str:
        """Digs the message text out of the envelope, or says why it could not."""
        try:
            body = response.json()
        except ValueError as exc:
            raise LLMResponseError(f"OpenRouter reply was not JSON: {response.text[:200]}") from exc

        if body.get("error"):
            raise LLMError(f"OpenRouter reported an error: {body['error']}")

        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError(f"unexpected OpenRouter response shape: {str(body)[:200]}") from exc

        if not content:
            raise LLMResponseError("OpenRouter returned an empty message")

        return content

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
