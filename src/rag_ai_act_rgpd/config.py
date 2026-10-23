"""Configuration lue depuis l'environnement (.env)."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://rag:rag@localhost:5432/rag"

    # Retrieval
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    chunk_strategy: Literal["fixed", "structural"] = "structural"
    top_k_chunks: int = 10
    max_passages: int = 8

    # Génération (LLM local via Ollama)
    llm_model: str = "qwen3:8b"
    ollama_url: str = "http://localhost:11434"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
