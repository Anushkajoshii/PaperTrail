"""Application settings, read from environment variables (or a local .env file).

Defaults are chosen so the project runs fully offline with no keys and no AWS account.
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(StrEnum):
    MOCK = "mock"
    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    OPENAI_COMPAT = "openai_compat"
    OLLAMA = "ollama"


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    PROD = "prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PAPERTRAIL_", env_file=".env", extra="ignore")

    env: Environment = Environment.LOCAL
    log_level: str = "INFO"
    aws_region: str = "ap-south-1"

    # --- LLM ---------------------------------------------------------------------------
    llm_provider: LLMProvider = LLMProvider.MOCK
    # Per-step models. Empty means "use the provider's default" (see papertrail/llm/factory.py).
    # Extraction uses a small fast model; judging uses a stronger one (cost/quality trade-off).
    extract_model: str | None = None
    judge_model: str | None = None
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    # Bedrock may need a different region from the rest of the stack if a model is missing there.
    bedrock_region: str | None = None
    openai_compat_base_url: str | None = None
    openai_compat_api_key: SecretStr | None = None
    ollama_base_url: str = "http://localhost:11434"

    # --- Agent -------------------------------------------------------------------------
    # Safety guard for the agent's evidence loop (used from Part 5).
    max_agent_steps: int = 8
    # Upper bound on claims per check: keeps cost and latency predictable.
    max_claims_per_check: int = 25

    # --- Evidence tools ----------------------------------------------------------------
    # "offline" uses a small built-in fixture so everything runs without keys; "tavily" is live.
    search_provider: str = "offline"
    tavily_api_key: SecretStr | None = None
    search_max_results: int = 5
    fetch_timeout_seconds: float = 15.0
    fetch_max_bytes: int = 2_000_000
    fetch_max_chars: int = 20_000
    # S3 bucket for uploads and Amazon Transcribe output (created in Part 10).
    media_bucket: str | None = None
    transcribe_timeout_seconds: int = 900


@lru_cache
def get_settings() -> Settings:
    return Settings()
