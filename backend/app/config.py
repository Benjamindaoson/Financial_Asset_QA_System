"""Configuration management using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # Model configuration
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL: str = "deepseek-chat"

    # Optional external services
    TAVILY_API_KEY: Optional[str] = None
    ALPHA_VANTAGE_API_KEY: Optional[str] = None
    MINERU_API_TOKEN: Optional[str] = None
    MINERU_BASE_URL: str = "https://mineru.net/api/v4"
    MINERU_LANGUAGE: str = "ch"
    MINERU_MODEL_VERSION: str = "pipeline"
    MINERU_ENABLE_TABLE: bool = True
    MINERU_ENABLE_FORMULA: bool = True
    MINERU_OCR_BY_DEFAULT: bool = True
    MINERU_POLL_INTERVAL_SECONDS: int = 5
    MINERU_POLL_TIMEOUT_SECONDS: int = 900
    MINERU_MAX_BATCH_FILES: int = 20

    # Financial data API keys
    FINNHUB_API_KEY: Optional[str] = None
    FRED_API_KEY: Optional[str] = None
    POLYGON_API_KEY: Optional[str] = None
    TWELVE_DATA_API_KEY: Optional[str] = None
    FMP_API_KEY: Optional[str] = None
    NEWSAPI_API_KEY: Optional[str] = None

    # Redis configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # ChromaDB configuration
    CHROMA_PERSIST_DIR: str = "../vectorstore/chroma"

    # Retrieval models
    EMBEDDING_MODEL: str = "BAAI/bge-base-zh-v1.5"
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"

    # HuggingFace cache
    HF_HOME: str = "../models/huggingface"
    TRANSFORMERS_CACHE: str = "../models/transformers"

    # Cache TTL (seconds)
    CACHE_TTL_PRICE: int = 60
    CACHE_TTL_HISTORY: int = 86400
    CACHE_TTL_INFO: int = 604800
    CACHE_WARM_ENABLED: bool = True
    CACHE_WARM_INTERVAL_SECONDS: int = 1800
    CACHE_WARM_LIMIT: int = 5
    CACHE_WARM_CONCURRENCY: int = 2

    # API configuration
    API_TIMEOUT: int = 30
    MAX_RETRIES: int = 3

    # RAG configuration
    RAG_TOP_K: int = 5
    RAG_TOP_N: int = 3
    RAG_SCORE_THRESHOLD: float = 0.75
    RAG_CHUNK_SIZE: int = 600
    RAG_CHUNK_OVERLAP: int = 120
    RAG_LEXICAL_TOP_K: int = 8
    RAG_VECTOR_TOP_K: int = 8
    RAG_FUSION_LOCAL_WEIGHT: float = 0.5
    RAG_FUSION_BM25_WEIGHT: float = 0.35
    RAG_FUSION_VECTOR_WEIGHT: float = 0.15
    RAG_AUTO_INDEX_ON_START: bool = False

    # Query rewriting configuration
    RAG_USE_QUERY_REWRITING: bool = True
    RAG_QUERY_REWRITE_STRATEGY: str = "multi_query"  # "hyde", "multi_query", "both"
    RAG_MULTI_QUERY_NUM: int = 3

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "../logs/tool_calls.jsonl"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def _load_prompt_catalog() -> Dict[str, Dict[str, str]]:
    path = _repo_root() / "prompts.yaml"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    catalog: Dict[str, Dict[str, str]] = {}
    in_prompts = False
    current_section: Optional[str] = None
    i = 0
    while i < len(lines):
        line = lines[i]
        if not in_prompts:
            if line.strip() == "prompts:":
                in_prompts = True
            i += 1
            continue

        if line.startswith("  ") and not line.startswith("    ") and line.rstrip().endswith(":"):
            current_section = line.strip().rstrip(":")
            catalog.setdefault(current_section, {})
            i += 1
            continue

        if current_section and line.startswith("    ") and ":" in line:
            key_part = line.strip()
            key, rest = key_part.split(":", 1)
            key = key.strip()
            rest = rest.strip()

            if rest == "|":
                i += 1
                captured: list[str] = []
                while i < len(lines):
                    body_line = lines[i]
                    if body_line.startswith("      "):
                        captured.append(body_line[6:])
                        i += 1
                        continue
                    if body_line.startswith("    ") and not body_line.startswith("      "):
                        break
                    if body_line.startswith("  ") and not body_line.startswith("    "):
                        break
                    i += 1
                catalog[current_section][key] = "\n".join(captured).rstrip()
                continue

            if rest:
                catalog[current_section][key] = rest.strip('"').strip("'")
            i += 1
            continue

        i += 1

    return catalog


def get_prompt(section: str, name: str) -> Optional[str]:
    return _load_prompt_catalog().get(section, {}).get(name)
