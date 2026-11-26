"""Application settings, read from environment variables (or a local .env file).

Defaults are chosen so the project runs fully offline with no keys and no AWS account.
"""

from enum import StrEnum
from functools import lru_cache

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
    llm_provider: LLMProvider = LLMProvider.MOCK
    aws_region: str = "ap-south-1"

    # Safety guard for the agent's evidence loop (used from Part 4).
    max_agent_steps: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
