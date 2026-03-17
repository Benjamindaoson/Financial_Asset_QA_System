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
    WEB_SEARCH_TIMEOUT: int = 10  # Tavily 等外部搜索，降低首屏等待
    MAX_RETRIES: int = 3

    # RAG configuration
    RAG_TOP_K: int = 5
    RAG_TOP_N: int = 3
    RAG_SCORE_THRESHOLD: float = 0.75

    # Demo cache (演示前预热答案，匹配时直接返回)
    DEMO_CACHE_ENABLED: bool = False
    DEMO_CACHE_PATH: str = "data/demo_cache.json"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "../logs/tool_calls.jsonl"

    # ========== Prompt 配置 ==========
    PROMPTS_CONFIG_PATH: str = "prompts.yaml"

    # ========== 混合路由配置 ==========
    HYBRID_ROUTING_ENABLED: bool = True
    HYBRID_ROUTING_CONFIDENCE_THRESHOLD: float = 0.8
    HYBRID_ROUTING_FALLBACK_TO_RULE: bool = True

    # ========== LLM 调用配置 ==========
    # Router
    LLM_ROUTER_TEMPERATURE: float = 0.0
    LLM_ROUTER_MAX_TOKENS: int = 500
    LLM_ROUTER_TIMEOUT: int = 10

    # Generator
    LLM_GENERATOR_TEMPERATURE: float = 0.3
    LLM_GENERATOR_MAX_TOKENS: int = 2000
    LLM_GENERATOR_TIMEOUT: int = 30

    # Compliance
    LLM_COMPLIANCE_TEMPERATURE: float = 0.0
    LLM_COMPLIANCE_MAX_TOKENS: int = 800
    LLM_COMPLIANCE_TIMEOUT: int = 10

    # ========== 合规检查配置 ==========
    COMPLIANCE_RULE_CHECK_ENABLED: bool = True
    COMPLIANCE_LLM_CHECK_ENABLED: bool = True
    COMPLIANCE_STRICT_MODE: bool = True

    # ========== 查询处理配置 ==========
    QUERY_REWRITE_ENABLED: bool = True
    QUERY_SYNONYM_EXPANSION: bool = True
    FINANCIAL_DICT_PATH: str = "data/financial_dictionary.txt"

    # ========== 多查询生成配置 ==========
    MULTI_QUERY_ENABLED: bool = True
    MULTI_QUERY_NUM_VARIANTS: int = 3

    # ========== 动态Top-K配置 ==========
    DYNAMIC_TOPK_ENABLED: bool = True
    DYNAMIC_TOPK_BASE: int = 5
    DYNAMIC_TOPK_MAX: int = 15

    # ========== MMR重排序配置 ==========
    MMR_ENABLED: bool = True
    MMR_LAMBDA: float = 0.7  # 0.7 = 70% relevance, 30% diversity

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
