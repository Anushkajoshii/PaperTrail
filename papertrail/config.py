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
    # Groq's free tier: an OpenAI-compatible endpoint with open models (no card needed).
    GROQ = "groq"


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    PROD = "prod"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PAPERTRAIL_", env_file=".env", extra="ignore")

    env: Environment = Environment.LOCAL
    log_level: str = "INFO"
    aws_region: str = "ap-southeast-2"

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
    groq_api_key: SecretStr | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    # Reasoning models (e.g. gpt-oss) accept "low" | "medium" | "high"; empty means not sent.
    reasoning_effort: str | None = None

    # --- Agent -------------------------------------------------------------------------
    # Safety guards for the agent (Part 5): total graph steps, and search rounds per claim.
    max_agent_steps: int = 40
    max_search_rounds: int = 2
    pages_to_fetch_per_claim: int = 2
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

    # --- SEBI register ------------------------------------------------------------------
    # Local copy of SEBI's public list of registered investment advisers / research analysts.
    # Only names, registration numbers and validity are stored (never contact details).
    registry_snapshot_path: str = "data/sebi_registry/snapshot.json"

    # --- API, storage and jobs (Part 7) --------------------------------------------------
    # store: "sqlite" (local file, shared by API and worker) or "memory" (tests)
    store_backend: str = "sqlite"
    sqlite_path: str = "data/papertrail.db"
    upload_dir: str = "data/uploads"
    # queue: "inline" runs checks in the API process (simplest for dev);
    #        "sqlite" hands them to the separate worker process (like SQS + worker Lambda)
    queue_mode: str = "inline"
    max_text_chars: int = 50_000
    max_upload_bytes: int = 25_000_000
    rate_limit_per_minute: int = 20
    cors_origins: list[str] = ["http://localhost:5173"]

    # --- AWS (Part 10) --------------------------------------------------------------------
    # store_backend="dynamodb" uses this table; queue_mode="sqs" sends jobs to this queue;
    # upload_backend="s3" keeps uploads in media_bucket.
    dynamodb_table: str | None = None
    sqs_queue_url: str | None = None
    upload_backend: str = "local"
    # In Lambda, secrets (e.g. the Groq key) are read from SSM Parameter Store under this path,
    # never from Terraform or environment variables.
    ssm_secrets_path: str | None = None
    # --- Tracing (Part 11) ----------------------------------------------------------------
    # Langfuse (free cloud tier or self-hosted). Both keys set: every check is traced.
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # Built web app to serve at "/" (the API then lives under /api). Empty: API only.
    web_dist_dir: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
