"""Central configuration for D-BUG."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    GROQ = "groq"
    OLLAMA = "ollama"
    HUGGINGFACE = "huggingface"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="DBUG_",
        extra="ignore",
    )

    # LLM
    llm_provider: LLMProvider = LLMProvider.GROQ
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = "llama-3.3-70b-versatile"
    groq_fast_model: str = "llama-3.1-8b-instant"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "deepseek-coder-v2:latest"
    hf_api_token: Optional[str] = Field(default=None, alias="HF_API_TOKEN")
    hf_model: str = "meta-llama/Llama-3.3-70B-Instruct"

    # RAG
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_max_tokens: int = 512
    similarity_top_k: int = 10
    similarity_threshold: float = 0.35

    # Paths
    project_root: Path = Path(".")
    chroma_db_path: Path = Path("./chroma_db")
    sqlite_db_path: Path = Path("./dbug_data.db")

    # MCP External Servers

    github_token: Optional[str] = Field(default=None, alias="GITHUB_TOKEN")
    sentry_dsn: Optional[str] = Field(default=None, alias="SENTRY_DSN")

    # Pipeline
    max_retry_loops: int = 3
    max_concurrent_agents: int = 4
    timeout_seconds: int = 120

    @property
    def has_groq(self) -> bool:
        return bool(self.groq_api_key)


    @property
    def has_github(self) -> bool:
        return bool(self.github_token)

    @property
    def has_sentry(self) -> bool:
        return bool(self.sentry_dsn)


# Singleton
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
