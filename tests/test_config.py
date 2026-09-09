from pathlib import Path

from utils.config import get_setting


def test_all_env_variables_load(settings):
    assert settings.aws_access_key_id == "test-key"
    assert settings.aws_region == "us-east-1"
    assert settings.aws_endpoint_url == "https://s3.example.com"
    assert settings.s3_pdf_bucket == "test-pdfs"
    assert settings.temp_pdf_folder == "TEMP_PDF"
    assert settings.temp_md_folder == "TEMP_MD"
    assert settings.api_host == "127.0.0.1"
    assert settings.api_port == 9999


def test_trailing_whitespace_is_stripped(settings):
    """S3_PARSED_MDS is set to 'test-mds ' in the fixture."""
    assert settings.s3_parsed_mds == "test-mds"


def test_api_port_is_an_int(settings):
    assert isinstance(settings.api_port, int)


def test_temp_paths_are_created_on_access(settings):
    assert settings.temp_pdf_path.is_dir()
    assert settings.temp_md_path.is_dir()
    assert settings.temp_pdf_path.name == "TEMP_PDF"
    assert settings.temp_md_path.name == "TEMP_MD"


def test_temp_paths_are_absolute_and_distinct(settings):
    assert settings.temp_pdf_path.is_absolute()
    assert settings.temp_md_path.is_absolute()
    assert settings.temp_pdf_path != settings.temp_md_path


def test_temp_root_does_not_follow_the_cwd(settings, monkeypatch, tmp_path):
    """Resolving the scratch dirs must not depend on where the process started."""
    before = settings.temp_pdf_path
    monkeypatch.chdir(Path(tmp_path))
    assert settings.temp_pdf_path == before


def test_get_setting_is_a_singleton():
    assert get_setting() is get_setting()
