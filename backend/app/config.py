"""Configuration management using pydantic-settings."""

from typing import Optional

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
