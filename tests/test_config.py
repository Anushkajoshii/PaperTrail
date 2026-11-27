from papertrail import __version__
from papertrail.config import LLMProvider, Settings


def test_version_is_set():
    assert __version__


def test_defaults_run_offline(monkeypatch):
    monkeypatch.delenv("PAPERTRAIL_LLM_PROVIDER", raising=False)
    settings = Settings(_env_file=None)
    assert settings.llm_provider is LLMProvider.MOCK
    assert settings.aws_region == "ap-southeast-2"


def test_provider_from_env(monkeypatch):
    monkeypatch.setenv("PAPERTRAIL_LLM_PROVIDER", "bedrock")
    assert Settings(_env_file=None).llm_provider is LLMProvider.BEDROCK
