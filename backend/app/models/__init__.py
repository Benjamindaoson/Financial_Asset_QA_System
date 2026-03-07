"""
Models package - Pydantic schemas and model management
"""
from app.models.schemas import (
    PricePoint,
    MarketData,
    HistoryData,
    ChangeData,
    CompanyInfo,
    Document,
    KnowledgeResult,
    SearchResult,
    WebSearchResult,
    ChatRequest,
    Source,
    SSEEvent,
    HealthResponse,
    ChartResponse,
    ToolCall,
    ToolResult,
)

from app.models.multi_model import (
    ModelProvider,
    QueryComplexity,
    ModelConfig,
    MultiModelManager,
    model_manager,
)

from app.models.model_adapter import (
    ModelAdapter,
    AnthropicAdapter,
    OpenAIAdapter,
    ModelAdapterFactory,
)

__all__ = [
    # Schemas
    "PricePoint",
    "MarketData",
    "HistoryData",
    "ChangeData",
    "CompanyInfo",
    "Document",
    "KnowledgeResult",
    "SearchResult",
    "WebSearchResult",
    "ChatRequest",
    "Source",
    "SSEEvent",
    "HealthResponse",
    "ChartResponse",
    "ToolCall",
    "ToolResult",
    # Multi-model
    "ModelProvider",
    "QueryComplexity",
    "ModelConfig",
    "MultiModelManager",
    "model_manager",
    # Adapters
    "ModelAdapter",
    "AnthropicAdapter",
    "OpenAIAdapter",
    "ModelAdapterFactory",
]
