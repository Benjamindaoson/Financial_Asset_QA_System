"""
TrustRAG Unified Configuration.
All thresholds, weights, patterns, and settings in one place.

Supports:
- Environment-based configuration (dev/test/prod)
- Hot reload from config files
- Runtime configuration updates
"""
import os
import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)

# ============================================================================
# Environment & Paths
# ============================================================================

class PathConfig(BaseModel):
    """Path configuration for artifacts and data."""
    artifacts_dir: str = "artifacts"
    ingestion_dir: str = "artifacts/ingestion"
    canonical_facts_dir: str = "artifacts/canonical_facts"
    fact_store_file: str = "artifacts/canonical_facts/fact_store.jsonl"
    raw_docs_dir: str = "artifacts/raw_docs"
    logs_dir: str = "logs"
    bm25_index_file: str = "artifacts/bm25_index.json"
    
    def ensure_dirs(self):
        """Create directories if they don't exist."""
        for path in [self.artifacts_dir, self.ingestion_dir, 
                     self.canonical_facts_dir, self.raw_docs_dir, self.logs_dir]:
            os.makedirs(path, exist_ok=True)


# ============================================================================
# Query Processing Configuration
# ============================================================================

class QueryBudgetConfig(BaseModel):
    """Budget constraints for query processing."""
    max_recall: int = 50
    max_rerank: int = 20
    max_llm_calls: int = 0  # Default: 0 LLM calls
    max_latency_ms: int = 500
    max_tokens: int = 0
    
    # Mode overrides
    regulatory_max_recall: int = 100
    regulatory_max_rerank: int = 30
    research_max_recall: int = 200
    research_max_rerank: int = 50

class QueryThresholds(BaseModel):
    """Thresholds for query classification and routing."""
    # Confidence thresholds
    confidence_threshold: float = 0.7
    low_confidence_threshold: float = 0.5
    
    # Score gap thresholds
    top_gap_threshold: float = 0.3
    coverage_threshold: float = 0.5
    duplicate_ratio_threshold: float = 0.4
    
    # Timeouts (ms)
    llm_timeout_ms: int = 2000
    rerank_timeout_ms: int = 1000
    retrieval_timeout_ms: int = 300

# ============================================================================
# Scoring Configuration
# ============================================================================

class ScoringWeightsConfig(BaseModel):
    """Weights for score fusion."""
    # Default weights
    default_w_dense: float = 0.4
    default_w_sparse: float = 0.4
    default_w_anchor: float = 0.2
    
    # Profile-specific weights
    factual_w_dense: float = 0.2
    factual_w_sparse: float = 0.5
    factual_w_anchor: float = 0.3
    
    summary_w_dense: float = 0.6
    summary_w_sparse: float = 0.2
    summary_w_anchor: float = 0.2
    
    cross_lingual_w_dense: float = 0.3
    cross_lingual_w_sparse: float = 0.3
    cross_lingual_w_anchor: float = 0.4
    
    comparative_w_dense: float = 0.4
    comparative_w_sparse: float = 0.4
    comparative_w_anchor: float = 0.2

class ModalityTrustConfig(BaseModel):
    """Trust scores for different modalities."""
    text_native: float = 1.0
    table_native: float = 0.95
    text_ocr: float = 0.70
    table_ocr: float = 0.65
    chart: float = 0.40

class IngestStatusPenalties(BaseModel):
    """Penalties for different ingest statuses."""
    ok: float = 0.0
    degraded: float = 0.3
    failed: float = 0.7

class SourceAuthorityConfig(BaseModel):
    """Authority rankings for different source types."""
    annual_report: float = 1.0
    audit: float = 0.9
    prospectus: float = 0.85
    regulatory_filing: float = 0.8
    news: float = 0.5
    draft: float = 0.3
    unknown: float = 0.4

# ============================================================================
# Pattern Configuration
# ============================================================================

class PatternConfig(BaseModel):
    """Regex patterns for query and content analysis."""
    
    # Numeric patterns
    numeric_patterns: List[str] = [
        r'\d+[%％]',           # Percentages
        r'[\$¥€£]\s*[\d,]+',   # Currency
        r'\d{4}年',            # Year in Chinese
        r'\d{4}[/-]\d{1,2}',   # Dates YYYY-MM
        r'\d+\s*(万|亿|千|百|million|billion|k|m|b)',  # Units
        r'\d+\.?\d*\s*(元|美元|港币|RMB|USD|CNY)',
        r'FY\d{4}',            # Fiscal year
        r'Q[1-4]\s*\d{4}',     # Quarter
    ]
    
    # Intent keywords
    factual_keywords: List[str] = [
        r'是多少', r'what is', r'how much', r'数字', r'金额', r'比例',
        r'收入', r'利润', r'revenue', r'profit', r'margin', r'rate',
        r'条款', r'clause', r'定义', r'definition', r'第.*条',
    ]
    
    summary_keywords: List[str] = [
        r'总结', r'概述', r'summarize', r'summary', r'overview',
        r'什么是', r'介绍', r'explain', r'describe',
    ]
    
    comparative_keywords: List[str] = [
        r'比较', r'对比', r'compare', r'vs', r'versus', r'相比',
        r'增长', r'下降', r'变化', r'increase', r'decrease', r'change',
    ]
    
    procedural_keywords: List[str] = [
        r'如何', r'怎么', r'how to', r'步骤', r'流程', r'process',
    ]
    
    table_keywords: List[str] = [
        r'表', r'table', r'如上表', r'见表', r'表格',
    ]
    
    chart_keywords: List[str] = [
        r'图', r'chart', r'graph', r'如上图', r'见图',
    ]
    
    high_risk_keywords: List[str] = [
        r'法律', r'legal', r'合规', r'compliance', r'监管', r'regulatory',
        r'责任', r'liability', r'违约', r'breach', r'处罚', r'penalty',
    ]
    
    # Value extraction patterns for answer generation
    value_extraction_patterns: List[str] = [
        r'(\$?[\d,]+\.?\d*)\s*(billion|million|B|M|USD|CNY|元|万|亿)',
        r'(\d+\.?\d*)\s*%',
        r'revenue\s+(?:was|of|:)?\s*(\$?[\d,]+\.?\d*)',
        r'net income\s+(?:was|of|:)?\s*(\$?[\d,]+\.?\d*)',
        r'profit\s+(?:was|of|:)?\s*(\$?[\d,]+\.?\d*)',
        r'margin\s+(?:was|of|:)?\s*(\$?[\d,]+\.?\d*)',
    ]
    
    # OCR artifact patterns for preflight
    ocr_artifact_patterns: List[str] = [
        r'[○●◯◉]{2,}',           # Circle sequences
        r'[□■◻◼]{2,}',           # Square sequences
        r'\d+[%％]\s*→\s*[a-zA-Z][%％]',
        r'[Il1]{5,}',             # Confusable chars
        r'[\u0000-\u001F]',       # Control characters
        r'[^\x00-\x7F\u4e00-\u9fff\u3000-\u303f]{10,}',
    ]

# ============================================================================
# Preflight & Quality Configuration
# ============================================================================

class PreflightConfig(BaseModel):
    """Configuration for preflight validation."""
    anomaly_threshold_degraded: float = 0.15
    anomaly_threshold_failed: float = 0.40
    illegal_char_density_threshold: float = 0.05
    min_entropy_threshold: float = 2.0
    min_text_length_for_entropy: int = 50

class QualityConfig(BaseModel):
    """Configuration for quality gate."""
    ocr_confidence_threshold: float = 0.70
    min_chunk_length: int = 10

# ============================================================================
# Evidence Selection Configuration
# ============================================================================

class EvidenceSelectionConfig(BaseModel):
    """Configuration for evidence selection."""
    max_core_factual: int = 3
    max_core_summary: int = 5
    max_per_source: int = 1
    max_per_source_summary: int = 2
    prefer_numeric: bool = True
    block_ocr_top1: bool = True  # OCR-only cannot be Top-1 for numerics

# ============================================================================
# Rerank Configuration
# ============================================================================

class RerankConfig(BaseModel):
    """Configuration for reranking - MANDATORY for production."""
    enabled: bool = True  # P0: Reranker is MANDATORY
    model_name: str = "BAAI/bge-reranker-v2-gemma"
    cache_dir: str = "./models"
    device: str = "auto"
    max_length: int = 1024
    batch_size: int = 8
    use_fp16: bool = True
    max_candidates: int = 20
    top_gap_threshold: float = 0.3
    force_on_risk: bool = True

# ============================================================================
# Feature Flags
# ============================================================================

class FeatureFlagsConfig(BaseModel):
    """Feature toggles for query processing."""
    enable_llm_classifier: bool = False
    enable_rerank: bool = False
    enable_cross_modal: bool = True
    enable_glossary_rewrite: bool = True
    enable_progressive_upgrade: bool = True
    enable_conflict_protocol: bool = True
    enable_post_binding_verification: bool = True  # New
    enable_evidence_selector: bool = True  # New
    enable_shadow_arbitration: bool = False  # Shadow mode for algorithm comparison
    shadow_arbitration_mode: str = "shadow_mode"  # legacy_only, shadow_mode, canary_mode, gradual_rollout, full_new


# ============================================================================
# Ingest Configuration
# ============================================================================

class IngestFeatureFlags(BaseModel):
    """Feature flags for ingestion."""
    cross_page_table: bool = True
    chart_weak_semantics: bool = True
    layout_chunking: bool = True
    title_isolation: bool = True
    free_text_merge: bool = True

class IngestConfig(BaseModel):
    """Configuration for document ingestion."""
    default_profile: str = "generic"
    chunk_size: int = 1500
    chunk_overlap: int = 200
    features: IngestFeatureFlags = Field(default_factory=IngestFeatureFlags)

# ============================================================================
# Language Detection Configuration
# ============================================================================

class LanguageConfig(BaseModel):
    """Configuration for language detection."""
    sample_size: int = 2000
    zh_threshold: float = 0.10  # If > 10% CJK chars, likely Chinese
    en_threshold: float = 0.80  # If > 80% ASCII, likely English

# ============================================================================
# Answer Generation Configuration
# ============================================================================

class AnswerConfig(BaseModel):
    """Configuration for answer generation."""
    max_extracted_values: int = 3
    max_snippet_length: int = 200
    default_source_label: str = "verified source"

# ============================================================================
# Embedding Configuration
# ============================================================================

class EmbeddingConfig(BaseModel):
    """Configuration for embedding models."""
    provider: str = "bge"  # Changed default to match system design
    model_name: str = "BAAI/bge-m3"  # Fixed: Use BGE-M3 as default
    api_key_env: str = "OPENAI_API_KEY"
    base_url: Optional[str] = None
    dimension: int = 1024  # Fixed: BGE-M3 dimension
    batch_size: int = 16
    max_seq_length: int = 8192
    cache_dir: str = "./models"
    enable_cache: bool = True
    normalize_embeddings: bool = True

    # BGE-M3 specific settings
    use_sparse: bool = True  # Enable sparse retrieval
    use_dense: bool = True   # Enable dense retrieval
    use_colbert: bool = False  # Enable ColBERT for advanced reranking


# ============================================================================
# Fast Path Configuration
# ============================================================================

class FastPathConfig(BaseModel):
    """Configuration for FastPath entity and metric recognition."""
    entity_keywords: Dict[str, List[str]] = Field(default_factory=lambda: {
        "Nvidia": ["nvidia", "英伟达"],
        "Apple": ["apple", "苹果"],
        "Microsoft": ["microsoft", "微软"],
        "Google": ["google", "alphabet", "谷歌"],
        "Amazon": ["amazon", "亚马逊"],
    })
    
    metric_keywords: Dict[str, List[str]] = Field(default_factory=lambda: {
        "revenue": ["revenue", "sales", "收入"],
        "net_income": ["net income", "net profit", "净利润", "净收入"],
        "gross_profit": ["gross profit", "毛利"],
        "margin": ["margin", "利润率"],
    })

# ============================================================================
# Document Processing Configuration
# ============================================================================

class DocumentProcessingConfig(BaseModel):
    """Configuration for document processing."""
    # PDF
    pdf_extract_tables: bool = True
    pdf_ocr_fallback: bool = True
    pdf_max_pages: int = 1000

    # DOCX
    docx_preserve_formatting: bool = True

    # HTML
    html_remove_scripts: bool = True
    html_remove_styles: bool = True
    html_extract_metadata: bool = True

    # Images
    ocr_languages: str = "eng+chi_sim"  # Tesseract languages
    ocr_min_confidence: float = 60.0

    # Audio
    asr_language: str = "en-US"  # Speech recognition language
    asr_timeout: int = 30  # Seconds
    audio_sample_rate: int = 16000

    # General
    max_file_size_mb: int = 100
    supported_formats: List[str] = Field(default_factory=lambda: [
        "pdf", "docx", "html", "htm", "txt", "png", "jpg", "jpeg", "webp", "mp3", "wav", "m4a"
    ])

# ============================================================================
# API Configuration
# ============================================================================

class DatabaseConfig(BaseModel):
    """PostgreSQL database configuration for vector storage."""
    host: str = "localhost"
    port: int = 5432
    database: str = "trust_rag"
    user: str = "trust_rag"
    password: str = "password"
    table_name: str = "vector_chunks"
    vector_dim: int = 1024  # BGE-M3 dimension
    hnsw_m: int = 16
    hnsw_ef_construction: int = 64
    index_name: str = "vector_chunks_embedding_idx"
    ssl_mode: str = "prefer"
    connection_timeout: int = 30
    max_connections: int = 20

    @property
    def connection_string(self) -> str:
        """Generate PostgreSQL connection string."""
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
            f"?sslmode={self.ssl_mode}"
        )

class TaskQueueConfig(BaseModel):
    """Celery task queue configuration."""
    broker_url: str = "amqp://guest:guest@localhost:5672//"
    backend_url: str = "redis://localhost:6379/1"
    result_expires: int = 3600  # 1 hour
    task_default_queue: str = "default"
    worker_prefetch_multiplier: int = 1
    worker_max_tasks_per_child: int = 1000

class ObservabilityConfig(BaseModel):
    """OpenTelemetry and monitoring configuration."""
    otlp_endpoint: str = "http://localhost:4317"
    service_name: str = "trust_rag"
    service_version: str = "2.0.0"
    enable_tracing: bool = True
    enable_metrics: bool = True
    enable_langsmith: bool = True
    langsmith_api_key: Optional[str] = None
    langsmith_project: str = "trust_rag_prod"
    trace_sampling_rate: float = 1.0  # Sample all traces in production

class VLMConfig(BaseModel):
    """Vision-Language Model configuration."""
    model_name: str = "Qwen/Qwen2-VL-7B-Instruct"
    device: str = "auto"
    max_tokens: int = 2048
    temperature: float = 0.1
    cache_dir: Optional[str] = None
    enable_fallback: bool = True  # Fallback to OCR if VLM fails

class APIConfig(BaseModel):
    """Configuration for API server."""
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["*"]
    max_upload_size_mb: int = 50
    enable_health_checks: bool = True
    request_timeout: int = 300  # 5 minutes for complex queries

# ============================================================================
# Master Configuration
# ============================================================================

class MultiTenantConfig(BaseModel):
    """Multi-tenant configuration and data isolation settings."""
    enabled: bool = False
    default_tenant_id: str = "default"
    tenant_id_field: str = "tenant_id"
    enforce_isolation: bool = True  # Strict data isolation when enabled
    shared_resources: List[str] = Field(default_factory=lambda: ["fact_store"])  # Resources shared across tenants


class TrustRAGConfig(BaseModel):
    """Master configuration for TrustRAG system."""
    paths: PathConfig = Field(default_factory=PathConfig)
    query_budget: QueryBudgetConfig = Field(default_factory=QueryBudgetConfig)
    query_thresholds: QueryThresholds = Field(default_factory=QueryThresholds)
    scoring_weights: ScoringWeightsConfig = Field(default_factory=ScoringWeightsConfig)
    modality_trust: ModalityTrustConfig = Field(default_factory=ModalityTrustConfig)
    ingest_penalties: IngestStatusPenalties = Field(default_factory=IngestStatusPenalties)
    source_authority: SourceAuthorityConfig = Field(default_factory=SourceAuthorityConfig)
    patterns: PatternConfig = Field(default_factory=PatternConfig)
    preflight: PreflightConfig = Field(default_factory=PreflightConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    evidence_selection: EvidenceSelectionConfig = Field(default_factory=EvidenceSelectionConfig)
    rerank: RerankConfig = Field(default_factory=RerankConfig)
    feature_flags: FeatureFlagsConfig = Field(default_factory=FeatureFlagsConfig)
    ingest: IngestConfig = Field(default_factory=IngestConfig)
    language: LanguageConfig = Field(default_factory=LanguageConfig)
    answer: AnswerConfig = Field(default_factory=AnswerConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    multi_tenant: MultiTenantConfig = Field(default_factory=MultiTenantConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    document_processing: DocumentProcessingConfig = Field(default_factory=DocumentProcessingConfig)

    # 2026 Production Upgrades
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    task_queue: TaskQueueConfig = Field(default_factory=TaskQueueConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    vlm: VLMConfig = Field(default_factory=VLMConfig)
    fast_path: FastPathConfig = Field(default_factory=FastPathConfig)

# ============================================================================
# Global Instance
# ============================================================================

_config: Optional[TrustRAGConfig] = None
_config_file: Optional[str] = None
_config_last_modified: Optional[float] = None


def get_config(env: Optional[str] = None) -> TrustRAGConfig:
    """
    Get or create the global configuration instance.
    
    Args:
        env: Environment name (dev/test/prod). If None, uses TRUSTRAG_ENV env var or 'dev'
        
    Returns:
        TrustRAGConfig instance
    """
    global _config, _config_file, _config_last_modified
    
    # Check for environment-specific config file
    if env is None:
        env = os.getenv("TRUSTRAG_ENV", "dev")
    
    config_file = os.getenv("TRUSTRAG_CONFIG", f"config_{env}.json")
    
    # Reload if config file changed or not loaded
    if _config is None or _config_file != config_file:
        _config = _load_config_from_file(config_file, env)
        _config_file = config_file
        if os.path.exists(config_file):
            _config_last_modified = os.path.getmtime(config_file)
        _config.paths.ensure_dirs()
    
    # Check for file modification (hot reload)
    elif os.path.exists(config_file):
        current_mtime = os.path.getmtime(config_file)
        if current_mtime != _config_last_modified:
            logger.info(f"Config file modified, reloading: {config_file}")
            _config = _load_config_from_file(config_file, env)
            _config_last_modified = current_mtime
            _config.paths.ensure_dirs()
    
    return _config


def _load_config_from_file(config_file: str, env: str) -> TrustRAGConfig:
    """
    Load configuration from file or create default.
    
    Args:
        config_file: Path to config file
        env: Environment name
        
    Returns:
        TrustRAGConfig instance
    """
    if os.path.exists(config_file):
        try:
            import json
            with open(config_file, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
            # Merge with defaults
            default_config = TrustRAGConfig()
            config_dict = _deep_merge(default_config.model_dump(), config_dict)
            return TrustRAGConfig(**config_dict)
        except Exception as e:
            logger.warning(f"Failed to load config from {config_file}: {e}, using defaults")
    
    # Return default config
    return TrustRAGConfig()


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def reload_config(env: Optional[str] = None) -> TrustRAGConfig:
    """
    Force reload configuration (for testing or runtime updates).
    
    Args:
        env: Environment name (dev/test/prod)
        
    Returns:
        Reloaded TrustRAGConfig instance
    """
    global _config, _config_file, _config_last_modified
    _config = None
    _config_file = None
    _config_last_modified = None
    return get_config(env=env)


def save_config(config: TrustRAGConfig, config_file: Optional[str] = None) -> str:
    """
    Save configuration to file.
    
    Args:
        config: Configuration to save
        config_file: Output file path (optional)
        
    Returns:
        Path to saved file
    """
    import json
    
    if config_file is None:
        env = os.getenv("TRUSTRAG_ENV", "dev")
        config_file = f"config_{env}.json"
    
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)
    
    logger.info(f"Configuration saved to {config_file}")
    return config_file

# Convenience exports
def get_paths() -> PathConfig:
    return get_config().paths

def get_patterns() -> PatternConfig:
    return get_config().patterns

def get_feature_flags() -> FeatureFlagsConfig:
    return get_config().feature_flags

