"""
Configuration management using pydantic-settings
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""

    # API Keys
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: Optional[str] = None
    TAVILY_API_KEY: Optional[str] = None
    ALPHA_VANTAGE_API_KEY: Optional[str] = None

    # Multi-Model Support
    DEEPSEEK_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # ChromaDB Configuration
    CHROMA_PERSIST_DIR: str = "./vectorstore"

    # Model Configuration
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    EMBEDDING_MODEL: str = "BAAI/bge-base-zh-v1.5"
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"

    # HuggingFace Cache (must be within project directory)
    HF_HOME: str = "../models/huggingface"
    TRANSFORMERS_CACHE: str = "../models/transformers"

    # Cache TTL (seconds)
    CACHE_TTL_PRICE: int = 60
    CACHE_TTL_HISTORY: int = 86400  # 24 hours
    CACHE_TTL_INFO: int = 604800  # 7 days

    # API Configuration
    API_TIMEOUT: int = 30
    MAX_RETRIES: int = 3

    # RAG Configuration
    RAG_TOP_K: int = 10
    RAG_TOP_N: int = 3
    RAG_SCORE_THRESHOLD: float = 0.7

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "../logs/tool_calls.jsonl"

    class Config:
        env_file = ".env"
        case_sensitive = True
        env_file_encoding = 'utf-8'
        # Prioritize .env file over system environment variables
        env_prefix = ""


settings = Settings()
