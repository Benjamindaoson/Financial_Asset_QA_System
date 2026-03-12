"""Pydantic models and schemas for the application."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PricePoint(BaseModel):
    """Single price point for historical data."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketData(BaseModel):
    """Latest market data response."""

    symbol: str
    price: Optional[float] = None
    currency: Optional[str] = None
    name: Optional[str] = None
    asset_type: Optional[str] = None
    source: str
    timestamp: str
    error: Optional[str] = None
    cache_hit: bool = False
    latency_ms: Optional[float] = None


class HistoryData(BaseModel):
    """Historical OHLCV data."""

    symbol: str
    days: int
    range_key: Optional[str] = None
    data: List[PricePoint]
    source: str
    timestamp: str


class ChangeData(BaseModel):
    """Price change summary."""

    symbol: str
    days: int
    start_price: float
    end_price: float
    change_pct: float
    trend: str
    source: str
    timestamp: str


class CompanyInfo(BaseModel):
    """Company or asset profile."""

    symbol: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[int] = None
    pe_ratio: Optional[float] = None
    week_52_high: Optional[float] = Field(None, alias="52w_high")
    week_52_low: Optional[float] = Field(None, alias="52w_low")
    description: Optional[str] = None
    source: str
    timestamp: str

    class Config:
        populate_by_name = True


class RiskMetrics(BaseModel):
    """Return and risk metrics derived from price history."""

    symbol: str
    range_key: str
    annualized_volatility: Optional[float] = None
    total_return_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    annualized_return_pct: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    source: str
    timestamp: str
    error: Optional[str] = None


class ComparisonRow(BaseModel):
    """Single row in a comparison table."""

    symbol: str
    name: Optional[str] = None
    price: Optional[float] = None
    total_return_pct: Optional[float] = None
    annualized_volatility: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    source: str
    timestamp: str


class ComparisonPoint(BaseModel):
    """Chart point used for normalized comparison charts."""

    date: str
    values: Dict[str, float]


class ComparisonData(BaseModel):
    """Multi-asset comparison payload."""

    symbols: List[str]
    range_key: str
    rows: List[ComparisonRow]
    chart: List[ComparisonPoint]
    source: str
    timestamp: str


class MarketIndexSnapshot(BaseModel):
    """Snapshot for a market index or macro instrument."""

    symbol: str
    name: str
    price: Optional[float] = None
    change_pct: Optional[float] = None
    source: str
    timestamp: str


class MarketSignal(BaseModel):
    """Intraday or daily signal card payload."""

    symbol: str
    change_pct: float
    signal_type: str
    signal_score: int
    volume_ratio: Optional[float] = None
    source: str
    timestamp: str


class SectorSnapshot(BaseModel):
    """Sector/industry performance card payload."""

    name: str
    symbol: str
    change_pct: float
    source: str
    timestamp: str


class MarketSummary(BaseModel):
    """Market overview summary."""

    text: str
    confidence: str


class MarketOverviewResponse(BaseModel):
    """Market overview API response."""

    indices: List[MarketIndexSnapshot]
    signals: List[MarketSignal]
    sectors: List[SectorSnapshot]
    summary: MarketSummary


class Document(BaseModel):
    """RAG document result."""

    content: str
    source: str
    score: float
    title: Optional[str] = None
    section: Optional[str] = None
    chunk_id: Optional[str] = None
    retrieval_stage: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class KnowledgeResult(BaseModel):
    """Knowledge search result."""

    documents: List[Document]
    total_found: int
    query: Optional[str] = None
    retrieval_meta: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    """Web or filing search result item."""

    title: str
    snippet: str
    url: str
    published: Optional[str] = None
    source: Optional[str] = None


class WebSearchResult(BaseModel):
    """Web search response."""

    results: List[SearchResult]
    search_query: str


class ChatRequest(BaseModel):
    """Chat API request."""

    query: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = None
    model_name: Optional[str] = None


class Source(BaseModel):
    """Data source information."""

    name: str
    timestamp: str
    url: Optional[str] = None


class StructuredBlock(BaseModel):
    """Rich UI block emitted with the final answer."""

    type: Literal["bullets", "table", "chart", "warning", "quote"]
    title: str
    data: Dict[str, Any]
    supporting_chunks: Optional[List[Dict[str, Any]]] = None


class SSEEvent(BaseModel):
    """Server-Sent Event."""

    type: Literal["tool_start", "tool_data", "chunk", "done", "error", "model_selected", "blocks"]
    name: Optional[str] = None
    display: Optional[str] = None
    tool: Optional[str] = None
    data: Optional[Any] = None
    text: Optional[str] = None
    verified: Optional[bool] = None
    sources: Optional[List[Source]] = None
    stock_data: Optional[dict] = None
    request_id: Optional[str] = None
    message: Optional[str] = None
    code: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    complexity: Optional[str] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["healthy", "degraded"]
    version: str
    timestamp: str
    components: dict
    reason: Optional[str] = None
    available_features: Optional[List[str]] = None


class ChartResponse(BaseModel):
    """Chart data response."""

    symbol: str
    data: List[PricePoint]
    source: str
    range_key: Optional[str] = None


class ToolCall(BaseModel):
    """Tool call parameters."""

    name: str
    params: dict


class ToolResult(BaseModel):
    """Normalized tool execution result."""

    tool: str
    data: dict
    latency_ms: int
    status: Literal["success", "error", "fallback"]
    data_source: str
    cache_hit: bool
    error_message: Optional[str] = None


# ============================================================================
# Layered Attribution System Models
# ============================================================================


class DataPoint(BaseModel):
    """单个数据点"""
    metric: str  # "price", "change_pct", "volume"
    value: float
    unit: str
    timestamp: str
    source: str
    confidence: Optional[str] = None


class Event(BaseModel):
    """Time-bound event with attribution."""

    date: str = Field(..., description="Event date (YYYY-MM-DD)")
    title: str = Field(..., description="Event title")
    description: Optional[str] = Field(None, description="Event description")
    source: str = Field(..., description="Source of the event information")
    url: Optional[str] = Field(None, description="Reference URL")


class Factor(BaseModel):
    """Causal or correlational factor with explanation."""

    name: str = Field(..., description="Factor name")
    impact: Literal["positive", "negative", "neutral"] = Field(..., description="Impact direction")
    strength: Optional[Literal["strong", "moderate", "weak"]] = Field(None, description="Impact strength")
    explanation: str = Field(..., description="Explanation of the factor's impact")
    sources: List[str] = Field(default_factory=list, description="Supporting sources")


class FactLayer(BaseModel):
    """事实层：客观数据平衡"""
    data_points: List[DataPoint] = Field(default_factory=list)
    timestamp: str
    sources: List[Source] = Field(default_factory=list)
    summary: Optional[str] = None


class ContextLayer(BaseModel):
    """Context layer: background information and related events."""

    events: List[Event] = Field(default_factory=list, description="Related events")
    background: Optional[str] = Field(None, description="Background context")
    market_conditions: Optional[str] = Field(None, description="Current market conditions")


class AttributionLayer(BaseModel):
    """归因层：因果推理"""
    primary_factors: List[Factor] = Field(default_factory=list)
    confidence: str  # "high", "medium", "low"
    reasoning: str


class DisclaimerLayer(BaseModel):
    """免责层"""
    text: str
    risk_level: str  # "high", "medium", "low"
    limitations: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)


class LayeredResponse(BaseModel):
    """Complete layered response with fact/context/attribution/disclaimer separation."""

    query: str = Field(..., description="Original user query")
    answer: str = Field(..., description="Natural language answer")
    fact_layer: Optional[FactLayer] = Field(None, description="Objective facts with attribution")
    context_layer: Optional[ContextLayer] = Field(None, description="Background and events")
    attribution_layer: Optional[AttributionLayer] = Field(None, description="Causal analysis")
    disclaimer_layer: Optional[DisclaimerLayer] = Field(None, description="Limitations and risks")
    timestamp: str = Field(..., description="Response generation timestamp")
    request_id: Optional[str] = Field(None, description="Request tracking ID")
