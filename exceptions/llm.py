from exceptions.base import AIAgentError


class LLMError(AIAgentError):
    """Anything that went wrong talking to the language model."""


class LLMConfigurationError(LLMError):
    """The provider is unknown, or its credentials are missing."""


class LLMTimeoutError(LLMError):
    """The model did not answer in time."""


class LLMRateLimitError(LLMError):
    """The provider is throttling us."""


class LLMResponseError(LLMError):
    """
    The model answered, but not with something usable.

    Raised when the reply is not JSON, or does not match the shape the caller
    asked for. This is the boundary where the model stops being trusted.
    """
