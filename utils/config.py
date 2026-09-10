from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    aws_access_key_id: str = Field(..., description="AWS Access Key ID")
    aws_secret_access_key: str = Field(..., description="AWS Secret Access Key")
    aws_region: str = Field(..., description="AWS Region Code")
    aws_endpoint_url: str = Field(..., description="AWS Endpoint URL for S3/Drive")
    s3_pdf_bucket: str = Field(..., description="Bucket holding the uploaded PDFs")
    s3_parsed_mds: str = Field(..., description="Bucket holding the parsed markdown files")
    temp_pd_dir: str = Field(..., description="Local root directory for scratch files")
    temp_pdf_folder: str = Field(..., description="Sub-folder of TEMP_PD_DIR for PDFs")
    temp_md_folder: str = Field(..., description="Sub-folder of TEMP_PD_DIR for markdown")
    api_host: str = Field("0.0.0.0", description="Host the FastAPI server binds to")
    api_port: int = Field(8000, description="Port the FastAPI server listens on")
    temporal_host: str = Field("localhost:7233", description="host:port of the Temporal frontend service")
    temporal_namespace: str = Field("default", description="Temporal namespace the worker and client use")
    temporal_task_queue: str = Field("process_pdf_queue", description="Task queue the workflow and activities are polled from")
    log_level: str = Field("INFO", description="Root log level: DEBUG, INFO, WARNING, ERROR")
    run_worker_in_api: bool = Field(False, description="Run the Temporal worker inside the API process")

    # LLM
    llm_provider: str = Field("openrouter", description="Which LLMInterface implementation the factory returns")
    llm_timeout_seconds: float = Field(120, description="Per-call timeout for an LLM request")
    llm_max_tokens: int = Field(4096, description="Maximum tokens the model may generate")
    llm_temperature: float = Field(0.2, description="Sampling temperature; legal advice wants determinism")
    openrouter_api_key: str = Field("", description="OpenRouter API key")
    openrouter_model: str = Field("deepseek/deepseek-v4-flash", description="OpenRouter model id")
    openrouter_base_url: str = Field("https://openrouter.ai/api/v1", description="OpenRouter API base URL")

    # legal advice pipeline
    s3_legal_advice: str = Field("legaladvice", description="Bucket the advice JSON lands in")
    legal_task_queue: str = Field("legal_advice_queue", description="Task queue for the legal review workflow")
    legal_max_concurrent_pdfs: int = Field(2, description="How many PDFs the workflow processes at once")
    legal_pages_per_batch: int = Field(10, description="Pages per LLM call")
    legal_max_pdfs: int = Field(20, description="Most PDFs accepted in one request")
    human_input_timeout_seconds: float = Field(3600, description="How long to wait for a human before continuing")

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    @field_validator("*", mode="after")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        """
        Cleans up values that arrive with stray spaces or quotes.

        python-dotenv strips surrounding quotes, docker's --env-file does not,
        so the same .env line can reach us either way.
        """
        if not isinstance(value, str):
            return value

        value = value.strip()

        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1].strip()

        return value

    @property
    def temp_root(self) -> Path:
        # anchored to the project root so the scratch dirs do not follow the cwd
        return Path(__file__).parent.parent / self.temp_pd_dir

    @property
    def temp_pdf_path(self) -> Path:

        path = self.temp_root / self.temp_pdf_folder

        # maek sure tha path exits
        path.mkdir(parents=True, exist_ok=True)

        return path

    @property
    def temp_md_path(self) -> Path:

        path = self.temp_root / self.temp_md_folder

        # maek sure tha path exits
        path.mkdir(parents=True, exist_ok=True)

        return path


_settings_instance = None


def get_setting() -> Settings:
    """
    Returns a singleton instance of the Settings object,
    automatically loaded from the .env file by Pydantic.
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
