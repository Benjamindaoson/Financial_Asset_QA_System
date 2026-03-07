"""
Pydantic models and schemas for the application
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime


# ============================================================================
# Market Data Models
# ============================================================================

class PricePoint(BaseModel):
    """Single price point for historical data"""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketData(BaseModel):
    """Market data response"""
    symbol: str
    price: Optional[float] = None
    currency: Optional[str] = None
    name: Optional[str] = None
    source: str
    timestamp: str
    error: Optional[str] = None
    cache_hit: bool = False
    latency_ms: Optional[float] = None


class HistoryData(BaseModel):
    """Historical price data"""
    symbol: str
    days: int
    data: List[PricePoint]
    source: str
    timestamp: str


class ChangeData(BaseModel):
    """Price change data"""
    symbol: str
    days: int
    start_price: float
    end_price: float
    change_pct: float
    trend: Literal["上涨", "下跌", "震荡"]
    source: str
    timestamp: str


class CompanyInfo(BaseModel):
    """Company information"""
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


# ============================================================================
# RAG Models
# ============================================================================

class Document(BaseModel):
    """RAG document result"""
    content: str
    source: str
    score: float


class KnowledgeResult(BaseModel):
    """Knowledge search result"""
    documents: List[Document]
    total_found: int


# ============================================================================
# Web Search Models
# ============================================================================

class SearchResult(BaseModel):
    """Web search result item"""
    title: str
    snippet: str
    url: str
    published: Optional[str] = None


class WebSearchResult(BaseModel):
    """Web search response"""
    results: List[SearchResult]
    search_query: str


# ============================================================================
# API Request/Response Models
# ============================================================================

class ChatRequest(BaseModel):
    """Chat API request"""
    query: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = None


class Source(BaseModel):
    """Data source information"""
    name: str
    timestamp: str


class SSEEvent(BaseModel):
    """Server-Sent Event"""
    type: Literal["tool_start", "tool_data", "chunk", "done", "error", "model_selected"]
    name: Optional[str] = None
    display: Optional[str] = None
    tool: Optional[str] = None
    data: Optional[dict] = None
    text: Optional[str] = None
    verified: Optional[bool] = None
    sources: Optional[List[Source]] = None
    request_id: Optional[str] = None
    message: Optional[str] = None
    code: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    complexity: Optional[str] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: Literal["healthy", "degraded"]
    version: str
    timestamp: str
    components: dict


class ChartResponse(BaseModel):
    """Chart data response"""
    symbol: str
    data: List[PricePoint]
    source: str


# ============================================================================
# Tool Call Models
# ============================================================================

class ToolCall(BaseModel):
    """Tool call parameters"""
    name: str
    params: dict


class ToolResult(BaseModel):
    """Tool execution result"""
    tool: str
    data: dict
    latency_ms: int
    status: Literal["success", "error", "fallback"]
    data_source: str
    cache_hit: bool
    error_message: Optional[str] = None
