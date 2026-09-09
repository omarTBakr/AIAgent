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

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding='utf-8',
        extra='ignore'
    )

    @field_validator('*', mode='after')
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        # values quoted in .env can carry stray spaces (e.g. "parsedmds ")
        return value.strip() if isinstance(value, str) else value

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
