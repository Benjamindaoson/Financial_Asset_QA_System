# Financial Asset QA System - Final Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a production-grade financial asset QA system based on the final design document (financial-qa-final-design-009.md), using Claude Sonnet with native Anthropic SDK, bge-base-zh embeddings, SSE streaming, and ResponseGuard validation.

**Architecture:** Single Claude Agent with 6 tools (get_price, get_history, get_change, get_info, search_knowledge, search_web), QueryEnricher for hint injection, MarketDataService with dual-source fallback, RAG with bge-base-zh + reranker, ResponseGuard for number validation, SSE streaming to React frontend.

**Tech Stack:** Python 3.11+, FastAPI, Anthropic SDK (Claude Sonnet 4.6), bge-base-zh, bge-reranker, ChromaDB, Redis, yfinance, Alpha Vantage, Tavily, React 18, Vite, TailwindCSS, TypeScript

---

## Phase 1: Update Dependencies

### Task 1: Update Backend Dependencies

**Files:**
- Modify: `backend/requirements.txt`

**Step 1: Update requirements.txt with correct dependencies**

```txt
# Core Framework
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-dotenv==1.0.0
pydantic==2.5.3
pydantic-settings==2.1.0

# Anthropic SDK (NOT LangChain)
anthropic==0.18.1

# Market Data
yfinance==0.2.35
alpha-vantage==2.3.1

# RAG & Embeddings
chromadb==0.4.22
sentence-transformers==2.3.1
FlagEmbedding==1.2.3

# Web Search
tavily-python==0.3.0

# Infrastructure
redis==5.0.1
httpx==0.26.0

# Testing
pytest==7.4.4
pytest-asyncio==0.23.3
pytest-mock==3.12.0
```

**Step 2: Commit dependency updates**

```bash
git add backend/requirements.txt
git commit -m "feat: update dependencies for Claude SDK and bge embeddings

- Replace LangChain with Anthropic SDK
- Add sentence-transformers and FlagEmbedding for bge models
- Add alpha-vantage for fallback data source
- Add tavily-python for web search

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 2: Configuration & Models

### Task 2: Update Configuration

**Files:**
- Modify: `backend/.env.example`
- Modify: `backend/app/config.py` (create if not exists)

**Step 1: Update environment template**

```bash
# backend/.env.example
# Anthropic API
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Market Data
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key_here

# Web Search
TAVILY_API_KEY=your_tavily_api_key_here

# Infrastructure
REDIS_URL=redis://localhost:6379

# Application
LOG_LEVEL=INFO
ENVIRONMENT=development
```

**Step 2: Create configuration module**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # API Keys
    anthropic_api_key: str
    alpha_vantage_api_key: str = ""
    tavily_api_key: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379"
    cache_ttl_realtime: int = 60  # 1 minute for prices
    cache_ttl_history: int = 86400  # 24 hours for historical data
    cache_ttl_info: int = 604800  # 7 days for company info

    # Application
    app_name: str = "Financial Asset QA System"
    app_version: str = "1.0.0"
    log_level: str = "INFO"
    environment: str = "development"

    # Claude Settings
    claude_model: str = "claude-sonnet-4-6"
    claude_temperature: float = 0.0
    claude_max_tokens: int = 4096
    claude_timeout: int = 30

    # Market Data
    market_api_timeout: int = 10
    market_retry_attempts: int = 2

    # RAG Settings
    embedding_model: str = "BAAI/bge-base-zh-v1.5"
    reranker_model: str = "BAAI/bge-reranker-base"
    chroma_persist_directory: str = "./vectorstore/chroma"
    rag_top_k: int = 10
    rag_top_n: int = 3
    rag_threshold: float = 0.7

    # Knowledge Base
    knowledge_base_path: str = "./backend/data/knowledge"

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

**Step 3: Commit configuration**

```bash
git add backend/.env.example backend/app/config.py
git commit -m "feat: add configuration with Anthropic and bge settings

- Add Anthropic API key configuration
- Add bge-base-zh and bge-reranker model settings
- Add separate cache TTLs for different data types
- Add Claude model and timeout settings

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Define Data Models

**Files:**
- Create: `backend/app/api/models.py`
- Create: `backend/app/market/models.py`

**Step 1: Create API models**

```python
# backend/app/api/models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = None

class Source(BaseModel):
    type: Literal["market", "knowledge", "web"]
    name: str
    timestamp: datetime

class ChatResponse(BaseModel):
    response: str
    verified: bool
    sources: List[Source]
    timestamp: datetime

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
```

**Step 2: Create market data models**

```python
# backend/app/market/models.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PricePoint(BaseModel):
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

class MarketData(BaseModel):
    symbol: str
    current_price: float
    change: float
    change_pct: float
    high: float
    low: float
    volume: int
    data_source: str
    timestamp: datetime

class ChangeData(BaseModel):
    symbol: str
    period_days: int
    start_price: float
    end_price: float
    change: float
    change_pct: float
    trend: str  # "上涨" / "下跌" / "震荡"
    data_source: str
    timestamp: datetime

class StockInfo(BaseModel):
    symbol: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    data_source: str
    timestamp: datetime
```

**Step 3: Commit models**

```bash
git add backend/app/api/models.py backend/app/market/models.py
git commit -m "feat: add Pydantic models for API and market data

- Add ChatRequest/Response with source tracking
- Add MarketData, ChangeData, StockInfo models
- Add PricePoint for historical data

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 3: Market Data Service

### Task 4: Implement TickerMapper

**Files:**
- Create: `backend/app/market/ticker_mapper.py`
- Create: `backend/tests/test_ticker_mapper.py`

**Step 1: Write failing test**

```python
# backend/tests/test_ticker_mapper.py
import pytest
from app.market.ticker_mapper import TickerMapper

def test_chinese_name_to_ticker():
    mapper = TickerMapper()
    assert mapper.normalize("阿里巴巴") == "BABA"
    assert mapper.normalize("特斯拉") == "TSLA"
    assert mapper.normalize("苹果") == "AAPL"

def test_already_ticker_unchanged():
    mapper = TickerMapper()
    assert mapper.normalize("BABA") == "BABA"
    assert mapper.normalize("AAPL") == "AAPL"

def test_a_share_normalization():
    mapper = TickerMapper()
    assert mapper.normalize("600519") == "600519.SS"
    assert mapper.normalize("000001") == "000001.SZ"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_ticker_mapper.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement TickerMapper**

```python
# backend/app/market/ticker_mapper.py
import re

class TickerMapper:
    """
    Three-level ticker normalization:
    1. Exact mapping table (Chinese names)
    2. A-share code normalization (add .SS/.SZ suffix)
    3. Pass through (let Claude handle edge cases)
    """

    TICKER_MAPPING = {
        # Chinese names to tickers
        "阿里巴巴": "BABA",
        "alibaba": "BABA",
        "特斯拉": "TSLA",
        "tesla": "TSLA",
        "苹果": "AAPL",
        "apple": "AAPL",
        "微软": "MSFT",
        "microsoft": "MSFT",
        "谷歌": "GOOGL",
        "google": "GOOGL",
        "亚马逊": "AMZN",
        "amazon": "AMZN",
        "脸书": "META",
        "facebook": "META",
        "meta": "META",
        "英伟达": "NVDA",
        "nvidia": "NVDA",
        "茅台": "600519.SS",
        "贵州茅台": "600519.SS",
        "平安": "601318.SS",
        "中国平安": "601318.SS",
    }

    def normalize(self, ticker: str) -> str:
        """Normalize ticker symbol."""
        ticker_clean = ticker.strip()

        # Level 1: Exact mapping
        ticker_lower = ticker_clean.lower()
        if ticker_lower in self.TICKER_MAPPING:
            return self.TICKER_MAPPING[ticker_lower]

        # Level 2: A-share normalization
        if re.match(r'^\d{6}$', ticker_clean):
            # 6-digit code without suffix
            first_digit = ticker_clean[0]
            if first_digit in ['6']:
                return f"{ticker_clean}.SS"  # Shanghai
            elif first_digit in ['0', '3']:
                return f"{ticker_clean}.SZ"  # Shenzhen

        # Level 3: Pass through (uppercase)
        return ticker_clean.upper()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_ticker_mapper.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/market/ticker_mapper.py backend/tests/test_ticker_mapper.py
git commit -m "feat: implement TickerMapper with three-level normalization

- Add exact mapping for common Chinese stock names
- Add A-share code normalization (add .SS/.SZ suffix)
- Add pass-through for unknown tickers
- Add comprehensive tests

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Implement yfinance Client

**Files:**
- Create: `backend/app/market/yfinance_client.py`
- Create: `backend/tests/test_yfinance_client.py`

**Step 1: Write failing test**

```python
# backend/tests/test_yfinance_client.py
import pytest
from app.market.yfinance_client import YFinanceClient
from app.market.models import MarketData, PricePoint

@pytest.mark.asyncio
async def test_get_current_price():
    client = YFinanceClient()
    data = await client.get_current_price("AAPL")

    assert data.symbol == "AAPL"
    assert data.current_price > 0
    assert data.data_source == "yfinance"

@pytest.mark.asyncio
async def test_get_history():
    client = YFinanceClient()
    history = await client.get_history("AAPL", days=7)

    assert len(history) > 0
    assert all(isinstance(p, PricePoint) for p in history)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_yfinance_client.py -v`
Expected: FAIL

**Step 3: Implement yfinance client**

```python
# backend/app/market/yfinance_client.py
import yfinance as yf
import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from app.market.models import MarketData, PricePoint, ChangeData, StockInfo

class YFinanceClient:
    """Async wrapper for yfinance library."""

    async def get_current_price(self, symbol: str) -> MarketData:
        """Get current price data."""
        def _fetch():
            ticker = yf.Ticker(symbol)
            info = ticker.info

            return MarketData(
                symbol=symbol,
                current_price=info.get('currentPrice', info.get('regularMarketPrice', 0)),
                change=info.get('regularMarketChange', 0),
                change_pct=info.get('regularMarketChangePercent', 0),
                high=info.get('dayHigh', info.get('regularMarketDayHigh', 0)),
                low=info.get('dayLow', info.get('regularMarketDayLow', 0)),
                volume=info.get('volume', info.get('regularMarketVolume', 0)),
                data_source="yfinance",
                timestamp=datetime.now(timezone.utc)
            )

        return await asyncio.to_thread(_fetch)

    async def get_history(self, symbol: str, days: int) -> List[PricePoint]:
        """Get historical price data."""
        def _fetch():
            ticker = yf.Ticker(symbol)
            period_map = {
                1: "1d",
                7: "7d",
                30: "1mo",
                90: "3mo",
                365: "1y"
            }
            period = period_map.get(days, f"{days}d")

            hist = ticker.history(period=period)

            if hist.empty:
                return []

            return [
                PricePoint(
                    date=row.Index.to_pydatetime(),
                    open=float(row.Open),
                    high=float(row.High),
                    low=float(row.Low),
                    close=float(row.Close),
                    volume=int(row.Volume)
                )
                for row in hist.itertuples()
            ]

        return await asyncio.to_thread(_fetch)

    async def get_change(self, symbol: str, days: int) -> ChangeData:
        """Calculate price change over period."""
        history = await self.get_history(symbol, days)

        if len(history) < 2:
            raise ValueError(f"Insufficient data for {symbol}")

        start_price = history[0].close
        end_price = history[-1].close
        change = end_price - start_price
        change_pct = (change / start_price) * 100

        # Determine trend
        if change_pct > 2:
            trend = "上涨"
        elif change_pct < -2:
            trend = "下跌"
        else:
            trend = "震荡"

        return ChangeData(
            symbol=symbol,
            period_days=days,
            start_price=round(start_price, 2),
            end_price=round(end_price, 2),
            change=round(change, 2),
            change_pct=round(change_pct, 2),
            trend=trend,
            data_source="yfinance",
            timestamp=datetime.now(timezone.utc)
        )

    async def get_info(self, symbol: str) -> StockInfo:
        """Get company information."""
        def _fetch():
            ticker = yf.Ticker(symbol)
            info = ticker.info

            return StockInfo(
                symbol=symbol,
                name=info.get('longName', info.get('shortName', symbol)),
                sector=info.get('sector'),
                industry=info.get('industry'),
                market_cap=info.get('marketCap'),
                pe_ratio=info.get('trailingPE'),
                data_source="yfinance",
                timestamp=datetime.now(timezone.utc)
            )

        return await asyncio.to_thread(_fetch)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_yfinance_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/market/yfinance_client.py backend/tests/test_yfinance_client.py
git commit -m "feat: implement async yfinance client

- Add YFinanceClient with asyncio.to_thread wrapper
- Implement get_current_price, get_history, get_change, get_info
- Add trend calculation (上涨/下跌/震荡)
- Add tests for price and history retrieval

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Implement Alpha Vantage Client (Fallback)

**Files:**
- Create: `backend/app/market/alpha_vantage_client.py`
- Create: `backend/tests/test_alpha_vantage_client.py`

**Step 1: Write failing test**

```python
# backend/tests/test_alpha_vantage_client.py
import pytest
from app.market.alpha_vantage_client import AlphaVantageClient

@pytest.mark.asyncio
async def test_get_current_price():
    client = AlphaVantageClient()

    # This will fail without API key, but structure should be correct
    try:
        data = await client.get_current_price("AAPL")
        assert data.symbol == "AAPL"
        assert data.data_source == "alpha_vantage"
    except Exception as e:
        # Expected if no API key
        assert "API" in str(e) or "key" in str(e).lower()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_alpha_vantage_client.py -v`
Expected: FAIL

**Step 3: Implement Alpha Vantage client**

```python
# backend/app/market/alpha_vantage_client.py
import httpx
from datetime import datetime, timezone
from typing import List, Optional
from app.market.models import MarketData, PricePoint
from app.config import get_settings

class AlphaVantageClient:
    """Alpha Vantage API client for fallback data source."""

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.alpha_vantage_api_key
        self.base_url = "https://www.alphavantage.co/query"

    async def get_current_price(self, symbol: str) -> MarketData:
        """Get current price from Alpha Vantage."""
        if not self.api_key:
            raise ValueError("Alpha Vantage API key not configured")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.base_url,
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": symbol,
                    "apikey": self.api_key
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if "Global Quote" not in data:
                raise ValueError(f"No data for symbol {symbol}")

            quote = data["Global Quote"]

            return MarketData(
                symbol=symbol,
                current_price=float(quote.get("05. price", 0)),
                change=float(quote.get("09. change", 0)),
                change_pct=float(quote.get("10. change percent", "0").rstrip('%')),
                high=float(quote.get("03. high", 0)),
                low=float(quote.get("04. low", 0)),
                volume=int(quote.get("06. volume", 0)),
                data_source="alpha_vantage",
                timestamp=datetime.now(timezone.utc)
            )

    async def get_history(self, symbol: str, days: int) -> List[PricePoint]:
        """Get historical data from Alpha Vantage."""
        if not self.api_key:
            raise ValueError("Alpha Vantage API key not configured")

        # Alpha Vantage free tier limitation - return empty for now
        # In production, implement TIME_SERIES_DAILY
        return []
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_alpha_vantage_client.py -v`
Expected: PASS (with API key error expected)

**Step 5: Commit**

```bash
git add backend/app/market/alpha_vantage_client.py backend/tests/test_alpha_vantage_client.py
git commit -m "feat: implement Alpha Vantage client as fallback

- Add AlphaVantageClient for GLOBAL_QUOTE API
- Implement get_current_price with proper error handling
- Add stub for get_history (free tier limitation)
- Add tests with API key validation

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Implement MarketDataService with Caching

**Files:**
- Create: `backend/app/market/service.py`
- Create: `backend/tests/test_market_service.py`

**Step 1: Write failing test**

```python
# backend/tests/test_market_service.py
import pytest
from app.market.service import MarketDataService

@pytest.mark.asyncio
async def test_get_price_with_cache():
    service = MarketDataService()

    # First call - cache miss
    data1 = await service.get_price("AAPL")
    assert data1.symbol == "AAPL"

    # Second call - should hit cache
    data2 = await service.get_price("AAPL")
    assert data2.symbol == "AAPL"
    assert data2.current_price == data1.current_price

@pytest.mark.asyncio
async def test_fallback_to_alpha_vantage():
    service = MarketDataService()

    # Mock yfinance failure and test fallback
    # (requires pytest-mock)
    pass  # TODO: Implement with mocking
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_market_service.py -v`
Expected: FAIL

**Step 3: Implement MarketDataService**

```python
# backend/app/market/service.py
import redis
import json
from typing import List, Optional
from app.market.yfinance_client import YFinanceClient
from app.market.alpha_vantage_client import AlphaVantageClient
from app.market.ticker_mapper import TickerMapper
from app.market.models import MarketData, PricePoint, ChangeData, StockInfo
from app.config import get_settings

class MarketDataService:
    """
    Market data service with dual-source fallback and caching.

    Data flow:
    1. Normalize ticker (TickerMapper)
    2. Check Redis cache
    3. Try yfinance (primary)
    4. Fallback to Alpha Vantage
    5. Cache result
    """

    def __init__(self):
        self.settings = get_settings()
        self.yfinance = YFinanceClient()
        self.alpha_vantage = AlphaVantageClient()
        self.ticker_mapper = TickerMapper()

        try:
            self.redis = redis.from_url(
                self.settings.redis_url,
                decode_responses=True
            )
        except Exception:
            self.redis = None  # Graceful degradation

    def _cache_key(self, prefix: str, symbol: str, **kwargs) -> str:
        """Generate cache key."""
        parts = [prefix, symbol]
        for k, v in sorted(kwargs.items()):
            parts.append(f"{k}={v}")
        return ":".join(parts)

    def _get_cache(self, key: str) -> Optional[dict]:
        """Get from cache."""
        if not self.redis:
            return None
        try:
            data = self.redis.get(key)
            return json.loads(data) if data else None
        except Exception:
            return None

    def _set_cache(self, key: str, value: dict, ttl: int):
        """Set cache with TTL."""
        if not self.redis:
            return
        try:
            self.redis.setex(key, ttl, json.dumps(value))
        except Exception:
            pass

    async def get_price(self, symbol: str) -> MarketData:
        """Get current price with caching and fallback."""
        # Normalize ticker
        normalized_symbol = self.ticker_mapper.normalize(symbol)

        # Check cache
        cache_key = self._cache_key("price", normalized_symbol)
        cached = self._get_cache(cache_key)
        if cached:
            return MarketData(**cached)

        # Try yfinance
        try:
            data = await self.yfinance.get_current_price(normalized_symbol)
            self._set_cache(cache_key, data.model_dump(mode='json'),
                          self.settings.cache_ttl_realtime)
            return data
        except Exception as e:
            # Fallback to Alpha Vantage
            try:
                data = await self.alpha_vantage.get_current_price(normalized_symbol)
                self._set_cache(cache_key, data.model_dump(mode='json'),
                              self.settings.cache_ttl_realtime)
                return data
            except Exception:
                raise ValueError(f"Unable to fetch price for {symbol}: {str(e)}")

    async def get_history(self, symbol: str, days: int) -> List[PricePoint]:
        """Get historical data with caching."""
        normalized_symbol = self.ticker_mapper.normalize(symbol)

        cache_key = self._cache_key("history", normalized_symbol, days=days)
        cached = self._get_cache(cache_key)
        if cached:
            return [PricePoint(**p) for p in cached]

        # Try yfinance
        try:
            data = await self.yfinance.get_history(normalized_symbol, days)
            self._set_cache(cache_key, [p.model_dump(mode='json') for p in data],
                          self.settings.cache_ttl_history)
            return data
        except Exception:
            # Alpha Vantage fallback not implemented for history
            raise

    async def get_change(self, symbol: str, days: int) -> ChangeData:
        """Calculate price change over period."""
        normalized_symbol = self.ticker_mapper.normalize(symbol)

        cache_key = self._cache_key("change", normalized_symbol, days=days)
        cached = self._get_cache(cache_key)
        if cached:
            return ChangeData(**cached)

        data = await self.yfinance.get_change(normalized_symbol, days)
        self._set_cache(cache_key, data.model_dump(mode='json'),
                      self.settings.cache_ttl_history)
        return data

    async def get_info(self, symbol: str) -> StockInfo:
        """Get company information."""
        normalized_symbol = self.ticker_mapper.normalize(symbol)

        cache_key = self._cache_key("info", normalized_symbol)
        cached = self._get_cache(cache_key)
        if cached:
            return StockInfo(**cached)

        data = await self.yfinance.get_info(normalized_symbol)
        self._set_cache(cache_key, data.model_dump(mode='json'),
                      self.settings.cache_ttl_info)
        return data
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_market_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/market/service.py backend/tests/test_market_service.py
git commit -m "feat: implement MarketDataService with dual-source fallback

- Add MarketDataService with Redis caching
- Implement yfinance primary + Alpha Vantage fallback
- Add separate TTLs for realtime/history/info data
- Add graceful degradation when Redis unavailable
- Add comprehensive caching logic

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

## Phase 4: RAG Pipeline with bge Models

### Task 8: Create Knowledge Base Content

**Files:**
- Create: `backend/data/knowledge/valuation_metrics.md`
- Create: `backend/data/knowledge/financial_statements.md`
- Create: `backend/data/knowledge/technical_analysis.md`
- Create: `backend/data/knowledge/market_instruments.md`
- Create: `backend/data/knowledge/macro_economics.md`

**Step 1: Create valuation metrics document**

```markdown
# backend/data/knowledge/valuation_metrics.md

# 估值指标

## 市盈率 (P/E Ratio)

市盈率（Price-to-Earnings Ratio）是衡量公司估值的重要指标。

**定义：**
市盈率 = 股价 / 每股收益(EPS)

**含义：**
表示投资者愿意为公司每1元盈利支付多少钱。例如，市盈率为20意味着投资者愿意为每1元盈利支付20元。

**应用：**
- 评估股票估值水平
- 行业间比较
- 历史估值对比

**注意事项：**
- 不同行业的合理市盈率范围不同
- 负盈利公司的市盈率无意义
- 应结合其他指标综合判断

## 市净率 (P/B Ratio)

市净率（Price-to-Book Ratio）反映股价与每股净资产的比率。

**定义：**
市净率 = 股价 / 每股净资产

**含义：**
表示投资者愿意为公司每1元净资产支付多少钱。

**应用：**
- 评估资产密集型企业
- 判断股票是否被低估
- 银行、地产等行业常用指标

## 市销率 (P/S Ratio)

市销率（Price-to-Sales Ratio）是股价与每股销售收入的比率。

**定义：**
市销率 = 股价 / 每股销售收入

**应用：**
- 评估尚未盈利的成长型公司
- 科技公司估值常用指标

## EV/EBITDA

企业价值倍数，衡量企业整体价值与息税折旧摊销前利润的比率。

**定义：**
EV/EBITDA = 企业价值 / EBITDA

其中，企业价值(EV) = 市值 + 净债务

**优势：**
- 排除资本结构影响
- 适合跨国比较
- 适合并购估值
```

**Step 2: Create financial statements document**

```markdown
# backend/data/knowledge/financial_statements.md

# 财务报表基础

## 利润表 (Income Statement)

利润表反映公司在一定期间的经营成果。

### 核心指标

**营业收入 (Revenue)**
- 公司销售商品或提供服务获得的收入
- 是利润表的起点

**营业成本 (Cost of Revenue)**
- 直接与产品生产相关的成本
- 包括原材料、人工、制造费用

**毛利润 (Gross Profit)**
- 毛利润 = 营业收入 - 营业成本
- 毛利率 = 毛利润 / 营业收入

**营业利润 (Operating Income)**
- 营业利润 = 毛利润 - 营业费用
- 反映主营业务盈利能力

**净利润 (Net Income)**
- 净利润 = 营业利润 - 利息 - 税费
- 归属股东的最终利润

### 收入 vs 净利润

**区别：**
- 收入是公司卖出商品/服务的总金额
- 净利润是扣除所有成本费用后的最终盈利
- 高收入不等于高利润

**示例：**
某公司收入100亿，但成本95亿，净利润只有5亿。

## 资产负债表 (Balance Sheet)

资产负债表反映公司在某一时点的财务状况。

**基本等式：**
资产 = 负债 + 股东权益

### 资产 (Assets)

**流动资产：**
- 现金及现金等价物
- 应收账款
- 存货

**非流动资产：**
- 固定资产（厂房、设备）
- 无形资产（专利、商标）
- 长期投资

### 负债 (Liabilities)

**流动负债：**
- 应付账款
- 短期借款

**非流动负债：**
- 长期借款
- 债券

### 股东权益 (Equity)

- 股本
- 留存收益

## 现金流量表 (Cash Flow Statement)

现金流量表反映公司现金的流入和流出。

### 三大现金流

**经营活动现金流 (Operating Cash Flow)**
- 日常经营产生的现金流
- 最重要的现金流指标

**投资活动现金流 (Investing Cash Flow)**
- 购买/出售资产产生的现金流
- 通常为负（投资支出）

**筹资活动现金流 (Financing Cash Flow)**
- 融资、分红产生的现金流
```

**Step 3: Create remaining knowledge files (abbreviated)**

```markdown
# backend/data/knowledge/technical_analysis.md
# 技术分析基础
## 移动平均线 (Moving Average)
## MACD
## RSI
## 支撑位与阻力位
```

```markdown
# backend/data/knowledge/market_instruments.md
# 金融工具
## 股票 (Stock)
## ETF (Exchange-Traded Fund)
## 债券 (Bond)
## 期权 (Option)
## 期货 (Futures)
```

```markdown
# backend/data/knowledge/macro_economics.md
# 宏观经济指标
## GDP (国内生产总值)
## CPI (消费者物价指数)
## 利率 (Interest Rate)
## 汇率 (Exchange Rate)
```

**Step 4: Commit knowledge base**

```bash
git add backend/data/knowledge/
git commit -m "feat: add financial knowledge base content

- Add valuation metrics (PE, PB, PS, EV/EBITDA)
- Add financial statements (income, balance sheet, cash flow)
- Add technical analysis basics
- Add market instruments overview
- Add macro economics indicators

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 9: Implement bge Embedder

**Files:**
- Create: `backend/app/rag/embedder.py`
- Create: `backend/tests/test_embedder.py`

**Step 1: Write failing test**

```python
# backend/tests/test_embedder.py
import pytest
from app.rag.embedder import BGEEmbedder

def test_embed_query():
    embedder = BGEEmbedder()
    embedding = embedder.embed_query("什么是市盈率")

    assert len(embedding) == 768  # bge-base-zh dimension
    assert all(isinstance(x, float) for x in embedding)

def test_embed_documents():
    embedder = BGEEmbedder()
    docs = ["市盈率是估值指标", "市净率反映净资产"]
    embeddings = embedder.embed_documents(docs)

    assert len(embeddings) == 2
    assert all(len(emb) == 768 for emb in embeddings)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_embedder.py -v`
Expected: FAIL

**Step 3: Implement BGE embedder**

```python
# backend/app/rag/embedder.py
from sentence_transformers import SentenceTransformer
from typing import List
from app.config import get_settings

class BGEEmbedder:
    """
    BGE (BAAI General Embedding) embedder for Chinese text.
    Uses bge-base-zh-v1.5 model.
    """

    def __init__(self):
        self.settings = get_settings()
        self.model = SentenceTransformer(self.settings.embedding_model)

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query text."""
        # For queries, add instruction prefix (bge best practice)
        query_text = f"为这个句子生成表示以用于检索相关文章：{text}"
        embedding = self.model.encode(query_text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple documents."""
        # Documents don't need instruction prefix
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_embedder.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/rag/embedder.py backend/tests/test_embedder.py
git commit -m "feat: implement BGE embedder for Chinese text

- Add BGEEmbedder using bge-base-zh-v1.5
- Add query instruction prefix for better retrieval
- Add document embedding without prefix
- Add tests for embedding generation

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 10: Implement bge Reranker

**Files:**
- Create: `backend/app/rag/reranker.py`
- Create: `backend/tests/test_reranker.py`

**Step 1: Write failing test**

```python
# backend/tests/test_reranker.py
import pytest
from app.rag.reranker import BGEReranker

def test_rerank():
    reranker = BGEReranker()
    query = "什么是市盈率"
    docs = [
        "市盈率是估值指标",
        "天气很好",
        "市盈率等于股价除以每股收益"
    ]

    scores = reranker.rerank(query, docs)

    assert len(scores) == 3
    assert scores[0] > scores[1]  # First doc more relevant than second
    assert scores[2] > scores[1]  # Third doc more relevant than second
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_reranker.py -v`
Expected: FAIL

**Step 3: Implement BGE reranker**

```python
# backend/app/rag/reranker.py
from FlagEmbedding import FlagReranker
from typing import List, Tuple
from app.config import get_settings

class BGEReranker:
    """
    BGE Reranker for cross-encoder based reranking.
    Uses bge-reranker-base model.
    """

    def __init__(self):
        self.settings = get_settings()
        self.model = FlagReranker(
            self.settings.reranker_model,
            use_fp16=True  # Faster inference
        )

    def rerank(self, query: str, documents: List[str]) -> List[float]:
        """
        Rerank documents based on query.
        Returns relevance scores for each document.
        """
        # Create query-document pairs
        pairs = [[query, doc] for doc in documents]

        # Compute scores
        scores = self.model.compute_score(pairs, normalize=True)

        # Ensure scores is a list
        if not isinstance(scores, list):
            scores = [scores]

        return scores

    def rerank_with_indices(
        self,
        query: str,
        documents: List[str],
        top_n: int = 3
    ) -> List[Tuple[int, float]]:
        """
        Rerank and return top N documents with their indices and scores.
        Returns: [(index, score), ...]
        """
        scores = self.rerank(query, documents)

        # Create (index, score) pairs and sort by score descending
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        return indexed_scores[:top_n]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_reranker.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/rag/reranker.py backend/tests/test_reranker.py
git commit -m "feat: implement BGE reranker for cross-encoder scoring

- Add BGEReranker using bge-reranker-base
- Implement rerank with normalized scores
- Add rerank_with_indices for top-N selection
- Add tests for reranking functionality

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 11: Implement Knowledge Loader

**Files:**
- Create: `backend/app/rag/knowledge_loader.py`
- Create: `backend/tests/test_knowledge_loader.py`

**Step 1: Write failing test**

```python
# backend/tests/test_knowledge_loader.py
import pytest
from pathlib import Path
from app.rag.knowledge_loader import KnowledgeLoader

def test_load_documents():
    loader = KnowledgeLoader()
    docs = loader.load_documents()

    assert len(docs) > 0
    assert all('content' in doc for doc in docs)
    assert all('metadata' in doc for doc in docs)

def test_header_aware_splitting():
    loader = KnowledgeLoader()
    text = """# Title
## Section 1
Content 1
## Section 2
Content 2"""

    chunks = loader.split_by_headers(text, "test.md")

    assert len(chunks) >= 2
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_knowledge_loader.py -v`
Expected: FAIL

**Step 3: Implement knowledge loader**

```python
# backend/app/rag/knowledge_loader.py
import re
from pathlib import Path
from typing import List, Dict
from app.config import get_settings

class KnowledgeLoader:
    """
    Load and split knowledge base documents.
    Uses header-aware splitting for better semantic coherence.
    """

    def __init__(self):
        self.settings = get_settings()
        self.knowledge_path = Path(self.settings.knowledge_base_path)

    def load_documents(self) -> List[Dict]:
        """Load all markdown documents from knowledge base."""
        documents = []

        if not self.knowledge_path.exists():
            return documents

        for md_file in self.knowledge_path.glob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            chunks = self.split_by_headers(content, md_file.name)

            for chunk in chunks:
                documents.append({
                    "content": chunk,
                    "metadata": {
                        "source": md_file.name,
                        "category": md_file.stem
                    }
                })

        return documents

    def split_by_headers(self, text: str, filename: str) -> List[str]:
        """
        Split markdown by ## headers for semantic coherence.
        If a section is too long (>800 chars), split by paragraphs.
        """
        chunks = []

        # Split by ## headers
        sections = re.split(r'\n## ', text)

        for i, section in enumerate(sections):
            # Add back the ## prefix (except for first section which might be # title)
            if i > 0:
                section = "## " + section

            section = section.strip()
            if not section:
                continue

            # If section is too long, split by paragraphs
            if len(section) > 800:
                paragraphs = section.split('\n\n')
                current_chunk = ""

                for para in paragraphs:
                    if len(current_chunk) + len(para) < 800:
                        current_chunk += para + "\n\n"
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = para + "\n\n"

                if current_chunk:
                    chunks.append(current_chunk.strip())
            else:
                chunks.append(section)

        return chunks
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_knowledge_loader.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/rag/knowledge_loader.py backend/tests/test_knowledge_loader.py
git commit -m "feat: implement header-aware knowledge loader

- Add KnowledgeLoader for markdown documents
- Implement header-aware splitting (by ## sections)
- Add paragraph-level splitting for long sections
- Add metadata tracking (source, category)
- Add tests for document loading

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

### Task 12: Implement RAG Pipeline

**Files:**
- Create: `backend/app/rag/pipeline.py`
- Create: `backend/tests/test_rag_pipeline.py`

**Step 1: Write failing test**

```python
# backend/tests/test_rag_pipeline.py
import pytest
from app.rag.pipeline import RAGPipeline

@pytest.mark.asyncio
async def test_search_knowledge():
    pipeline = RAGPipeline()
    await pipeline.initialize()

    results = await pipeline.search("什么是市盈率", top_n=3)

    assert len(results) <= 3
    assert all('content' in r for r in results)
    assert all('score' in r for r in results)
    assert all('source' in r for r in results)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_rag_pipeline.py -v`
Expected: FAIL

**Step 3: Implement RAG pipeline**

```python
# backend/app/rag/pipeline.py
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List, Dict
from app.rag.embedder import BGEEmbedder
from app.rag.reranker import BGEReranker
from app.rag.knowledge_loader import KnowledgeLoader
from app.config import get_settings

class RAGPipeline:
    """
    Complete RAG pipeline with two-stage retrieval:
    1. Bi-Encoder (bge-base-zh) for fast vector search (Top-K)
    2. Cross-Encoder (bge-reranker) for precise reranking (Top-N)
    """

    def __init__(self):
        self.settings = get_settings()
        self.embedder = BGEEmbedder()
        self.reranker = BGEReranker()
        self.loader = KnowledgeLoader()
        self.collection = None
        self.initialized = False

    async def initialize(self):
        """Initialize ChromaDB and load knowledge base."""
        if self.initialized:
            return

        # Initialize ChromaDB
        client = chromadb.PersistentClient(
            path=self.settings.chroma_persist_directory
        )

        # Get or create collection
        self.collection = client.get_or_create_collection(
            name="financial_knowledge",
            metadata={"hnsw:space": "cosine"}
        )

        # Load documents if collection is empty
        if self.collection.count() == 0:
            await self._load_knowledge_base()

        self.initialized = True

    async def _load_knowledge_base(self):
        """Load and index knowledge base documents."""
        documents = self.loader.load_documents()

        if not documents:
            return

        # Prepare data for ChromaDB
        ids = [f"doc_{i}" for i in range(len(documents))]
        contents = [doc["content"] for doc in documents]
        metadatas = [doc["metadata"] for doc in documents]

        # Generate embeddings
        embeddings = self.embedder.embed_documents(contents)

        # Add to collection
        self.collection.add(
            ids=ids,
            documents=contents,
            embeddings=embeddings,
            metadatas=metadatas
        )

    async def search(self, query: str, top_n: int = 3) -> List[Dict]:
        """
        Search knowledge base with two-stage retrieval.

        Args:
            query: User query
            top_n: Number of final results to return

        Returns:
            List of documents with content, score, source
        """
        if not self.initialized:
            await self.initialize()

        # Stage 1: Vector search (Top-K)
        top_k = self.settings.rag_top_k
        query_embedding = self.embedder.embed_query(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )

        if not results['documents'][0]:
            return []

        # Extract documents and metadata
        documents = results['documents'][0]
        metadatas = results['metadatas'][0]
        distances = results['distances'][0]

        # Stage 2: Reranking (Top-N)
        reranked = self.reranker.rerank_with_indices(query, documents, top_n)

        # Build final results
        final_results = []
        for idx, score in reranked:
            # Filter by threshold
            if score >= self.settings.rag_threshold:
                final_results.append({
                    "content": documents[idx],
                    "score": float(score),
                    "source": metadatas[idx].get("source", "unknown"),
                    "category": metadatas[idx].get("category", "unknown")
                })

        return final_results
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_rag_pipeline.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/rag/pipeline.py backend/tests/test_rag_pipeline.py
git commit -m "feat: implement two-stage RAG pipeline

- Add RAGPipeline with bi-encoder + cross-encoder
- Implement vector search with ChromaDB (Top-K)
- Implement reranking with bge-reranker (Top-N)
- Add automatic knowledge base loading
- Add relevance threshold filtering
- Add tests for search functionality

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 5: Web Search Service

### Task 13: Implement Tavily Web Search

**Files:**
- Create: `backend/app/search/web_search.py`
- Create: `backend/tests/test_web_search.py`

**Step 1: Write failing test**

```python
# backend/tests/test_web_search.py
import pytest
from app.search.web_search import WebSearchService

@pytest.mark.asyncio
async def test_search_web():
    service = WebSearchService()

    # This will fail without API key
    try:
        results = await service.search("阿里巴巴 BABA 股价上涨")
        assert isinstance(results, list)
    except Exception as e:
        # Expected if no API key
        assert "API" in str(e) or "key" in str(e).lower()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_web_search.py -v`
Expected: FAIL

**Step 3: Implement web search service**

```python
# backend/app/search/web_search.py
from tavily import TavilyClient
from typing import List, Dict, Optional
from datetime import datetime, timezone
from app.config import get_settings

class WebSearchService:
    """
    Web search service using Tavily API.
    Returns structured summaries optimized for LLM consumption.
    """

    def __init__(self):
        self.settings = get_settings()
        if self.settings.tavily_api_key:
            self.client = TavilyClient(api_key=self.settings.tavily_api_key)
        else:
            self.client = None

    async def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic"
    ) -> List[Dict]:
        """
        Search web for recent news and information.

        Args:
            query: Search query
            max_results: Maximum number of results
            search_depth: "basic" or "advanced"

        Returns:
            List of search results with title, content, url, published_date
        """
        if not self.client:
            raise ValueError("Tavily API key not configured")

        # Perform search
        response = self.client.search(
            query=query,
            max_results=max_results,
            search_depth=search_depth,
            include_answer=False,
            include_raw_content=False
        )

        # Format results
        results = []
        for item in response.get('results', []):
            results.append({
                "title": item.get('title', ''),
                "content": item.get('content', ''),
                "url": item.get('url', ''),
                "score": item.get('score', 0.0),
                "published_date": item.get('published_date'),
                "source": self._extract_source(item.get('url', ''))
            })

        return results

    def _extract_source(self, url: str) -> str:
        """Extract source name from URL."""
        if not url:
            return "unknown"

        # Extract domain
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            # Remove www. prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except Exception:
            return "unknown"

    def get_credibility_tier(self, source: str) -> int:
        """
        Assign credibility tier to news source.

        Tier 1: Reuters, Bloomberg, WSJ
        Tier 2: CNBC, Yahoo Finance, MarketWatch
        Tier 3: Others
        """
        tier1_sources = ['reuters.com', 'bloomberg.com', 'wsj.com']
        tier2_sources = ['cnbc.com', 'finance.yahoo.com', 'marketwatch.com']

        source_lower = source.lower()

        for t1 in tier1_sources:
            if t1 in source_lower:
                return 1

        for t2 in tier2_sources:
            if t2 in source_lower:
                return 2

        return 3
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_web_search.py -v`
Expected: PASS (with API key error expected)

**Step 5: Commit**

```bash
git add backend/app/search/web_search.py backend/tests/test_web_search.py
git commit -m "feat: implement Tavily web search service

- Add WebSearchService with Tavily API integration
- Implement search with structured result formatting
- Add source extraction from URLs
- Add credibility tier assignment (Tier 1/2/3)
- Add tests with API key validation

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 6: Query Enricher

### Task 14: Implement QueryEnricher

**Files:**
- Create: `backend/app/enricher/query_enricher.py`
- Create: `backend/tests/test_query_enricher.py`

**Step 1: Write failing test**

```python
# backend/tests/test_query_enricher.py
import pytest
from app.enricher.query_enricher import QueryEnricher

def test_enrich_with_ticker():
    enricher = QueryEnricher()
    query = "阿里巴巴当前股价是多少"
    enriched = enricher.enrich(query)

    assert "行情" in enriched or "数据" in enriched
    assert query in enriched

def test_enrich_with_reason_keywords():
    enricher = QueryEnricher()
    query = "为什么特斯拉最近大涨"
    enriched = enricher.enrich(query)

    assert "新闻" in enriched or "原因" in enriched

def test_no_enrichment_needed():
    enricher = QueryEnricher()
    query = "今天天气怎么样"
    enriched = enricher.enrich(query)

    # Should return original query
    assert enriched == query
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_query_enricher.py -v`
Expected: FAIL

**Step 3: Implement QueryEnricher**

```python
# backend/app/enricher/query_enricher.py
import re
from typing import List

class QueryEnricher:
    """
    Query enricher that adds hints to help Claude make better tool decisions.
    Uses zero-cost rule-based detection, not classification.
    """

    # Ticker patterns
    TICKER_PATTERNS = [
        r'\b[A-Z]{1,5}\b',           # BABA, TSLA
        r'\d{6}\.(SS|SZ|HK)',        # 600519.SS
    ]

    # Company names
    COMPANY_NAMES = {
        "阿里巴巴", "alibaba", "特斯拉", "tesla", "苹果", "apple",
        "微软", "microsoft", "谷歌", "google", "亚马逊", "amazon",
        "脸书", "facebook", "meta", "英伟达", "nvidia", "茅台", "平安"
    }

    # Intent keywords
    PRICE_KEYWORDS = {"股价", "价格", "多少钱", "涨", "跌", "行情", "走势", "市值"}
    REASON_KEYWORDS = {"为什么", "为何", "原因", "导致", "因为", "怎么回事"}
    KNOWLEDGE_KEYWORDS = {"什么是", "定义", "解释", "区别", "如何计算", "怎么算"}

    def enrich(self, query: str) -> str:
        """
        Add hints to query based on detected patterns.
        Returns enriched query with hints prepended.
        """
        hints = []

        # Check for ticker/company
        if self._has_ticker_or_company(query):
            hints.append("此问题涉及具体资产，建议使用行情工具获取数据")

        # Check for reason keywords
        if self._has_keywords(query, self.REASON_KEYWORDS):
            hints.append("用户想了解原因，建议搜索相关新闻")

        # Check for knowledge keywords
        if self._has_keywords(query, self.KNOWLEDGE_KEYWORDS):
            hints.append("此问题涉及金融概念，建议检索知识库")

        # If no hints, return original query
        if not hints:
            return query

        # Prepend hints
        hint_text = "[系统辅助提示: " + "; ".join(hints) + "]"
        return f"{hint_text}\n\n{query}"

    def _has_ticker_or_company(self, query: str) -> bool:
        """Check if query contains ticker symbol or company name."""
        # Check ticker patterns
        for pattern in self.TICKER_PATTERNS:
            if re.search(pattern, query):
                return True

        # Check company names
        query_lower = query.lower()
        for company in self.COMPANY_NAMES:
            if company in query_lower:
                return True

        return False

    def _has_keywords(self, query: str, keywords: set) -> bool:
        """Check if query contains any of the keywords."""
        query_lower = query.lower()
        return any(kw in query_lower for kw in keywords)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_query_enricher.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/enricher/query_enricher.py backend/tests/test_query_enricher.py
git commit -m "feat: implement QueryEnricher for hint injection

- Add QueryEnricher with rule-based pattern detection
- Detect ticker symbols and company names
- Detect intent keywords (price, reason, knowledge)
- Add hint injection without classification
- Add comprehensive tests

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 7: Claude Agent Core

### Task 15: Define Tool Schemas

**Files:**
- Create: `backend/app/agent/tools.py`

**Step 1: Create tool schemas**

```python
# backend/app/agent/tools.py
"""
Tool definitions for Claude Agent.
Each tool is defined as a JSON schema following Anthropic's tool use format.
"""

TOOLS = [
    {
        "name": "get_price",
        "description": "获取股票当前价格、涨跌幅、成交量等实时行情数据。当用户询问当前股价、今日行情时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码或中文名称，如 'BABA'、'阿里巴巴'、'600519.SS'"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "get_history",
        "description": "获取股票历史价格数据，用于绘制走势图或分析历史表现。",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码或中文名称"
                },
                "days": {
                    "type": "integer",
                    "description": "历史天数，如 7、30、90",
                    "enum": [7, 30, 90, 365]
                }
            },
            "required": ["symbol", "days"]
        }
    },
    {
        "name": "get_change",
        "description": "计算股票在指定时间段内的涨跌幅和趋势。当用户询问'最近7天涨跌'、'30天走势'时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码或中文名称"
                },
                "days": {
                    "type": "integer",
                    "description": "时间段天数",
                    "enum": [7, 30, 90]
                }
            },
            "required": ["symbol", "days"]
        }
    },
    {
        "name": "get_info",
        "description": "获取公司基本信息，包括行业、市值、市盈率等。当用户询问公司基本面时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "股票代码或中文名称"
                }
            },
            "required": ["symbol"]
        }
    },
    {
        "name": "search_knowledge",
        "description": "检索金融知识库，回答金融概念、术语定义、计算方法等问题。当用户询问'什么是市盈率'、'如何计算ROE'等知识类问题时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要检索的问题或关键词"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_web",
        "description": "搜索最新新闻和事件信息。当用户询问股票涨跌原因、最近发生了什么、财报发布等需要实时信息的问题时使用。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，应包含公司名/代码+事件描述，如'阿里巴巴 BABA 2026年1月 股价上涨 原因'"
                }
            },
            "required": ["query"]
        }
    }
]
```

**Step 2: Commit tool schemas**

```bash
git add backend/app/agent/tools.py
git commit -m "feat: define 6 tool schemas for Claude Agent

- Add get_price for current market data
- Add get_history for historical prices
- Add get_change for period change calculation
- Add get_info for company information
- Add search_knowledge for RAG retrieval
- Add search_web for news search

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 16: Implement Tool Dispatcher

**Files:**
- Create: `backend/app/agent/dispatcher.py`
- Create: `backend/tests/test_dispatcher.py`

**Step 1: Write failing test**

```python
# backend/tests/test_dispatcher.py
import pytest
from app.agent.dispatcher import ToolDispatcher

@pytest.mark.asyncio
async def test_dispatch_get_price():
    dispatcher = ToolDispatcher()

    result = await dispatcher.dispatch(
        tool_name="get_price",
        tool_input={"symbol": "AAPL"}
    )

    assert "symbol" in result
    assert result["symbol"] == "AAPL"
    assert "current_price" in result

@pytest.mark.asyncio
async def test_dispatch_unknown_tool():
    dispatcher = ToolDispatcher()

    with pytest.raises(ValueError, match="Unknown tool"):
        await dispatcher.dispatch(
            tool_name="unknown_tool",
            tool_input={}
        )
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_dispatcher.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement tool dispatcher**

```python
# backend/app/agent/dispatcher.py
from typing import Dict, Any, Callable
from app.market.service import MarketDataService
from app.rag.pipeline import RAGPipeline
from app.search.web_search import WebSearchService

class ToolDispatcher:
    """
    Dispatches tool calls to appropriate service methods.
    Maps Claude tool names to actual Python functions.
    """

    def __init__(self):
        self.market_service = MarketDataService()
        self.rag_pipeline = RAGPipeline()
        self.web_search = WebSearchService()

        # Tool name -> handler mapping
        self.tools: Dict[str, Callable] = {
            "get_price": self._handle_get_price,
            "get_history": self._handle_get_history,
            "get_change": self._handle_get_change,
            "get_info": self._handle_get_info,
            "search_knowledge": self._handle_search_knowledge,
            "search_web": self._handle_search_web,
        }

    async def dispatch(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch tool call to appropriate handler."""
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        handler = self.tools[tool_name]
        return await handler(tool_input)

    async def _handle_get_price(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_price tool call."""
        symbol = tool_input.get("symbol")
        if not symbol:
            return {"error": "Missing required parameter: symbol"}

        try:
            data = await self.market_service.get_price(symbol)
            return data.model_dump(mode='json')
        except Exception as e:
            return {"error": str(e), "symbol": symbol}

    async def _handle_get_history(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_history tool call."""
        symbol = tool_input.get("symbol")
        days = tool_input.get("days", 7)

        if not symbol:
            return {"error": "Missing required parameter: symbol"}

        try:
            history = await self.market_service.get_history(symbol, days)
            return {
                "symbol": symbol,
                "days": days,
                "data": [p.model_dump(mode='json') for p in history]
            }
        except Exception as e:
            return {"error": str(e), "symbol": symbol}

    async def _handle_get_change(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_change tool call."""
        symbol = tool_input.get("symbol")
        days = tool_input.get("days", 7)

        if not symbol:
            return {"error": "Missing required parameter: symbol"}

        try:
            data = await self.market_service.get_change(symbol, days)
            return data.model_dump(mode='json')
        except Exception as e:
            return {"error": str(e), "symbol": symbol}

    async def _handle_get_info(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get_info tool call."""
        symbol = tool_input.get("symbol")

        if not symbol:
            return {"error": "Missing required parameter: symbol"}

        try:
            data = await self.market_service.get_info(symbol)
            return data.model_dump(mode='json')
        except Exception as e:
            return {"error": str(e), "symbol": symbol}

    async def _handle_search_knowledge(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Handle search_knowledge tool call."""
        query = tool_input.get("query")

        if not query:
            return {"error": "Missing required parameter: query"}

        try:
            if not self.rag_pipeline.initialized:
                await self.rag_pipeline.initialize()

            results = await self.rag_pipeline.search(query, top_n=3)
            return {
                "query": query,
                "results": results
            }
        except Exception as e:
            return {"error": str(e), "query": query}

    async def _handle_search_web(self, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Handle search_web tool call."""
        query = tool_input.get("query")

        if not query:
            return {"error": "Missing required parameter: query"}

        try:
            results = await self.web_search.search(query, max_results=5)
            return {
                "query": query,
                "results": results
            }
        except Exception as e:
            return {"error": str(e), "query": query}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_dispatcher.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/agent/dispatcher.py backend/tests/test_dispatcher.py
git commit -m "feat: implement tool dispatcher for Claude Agent

- Add ToolDispatcher with 6 tool handlers
- Map tool names to service methods
- Add error handling for missing parameters
- Add error handling for service failures
- Add tests for dispatch functionality

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 17: Implement ResponseGuard

**Files:**
- Create: `backend/app/agent/guard.py`
- Create: `backend/tests/test_guard.py`

**Step 1: Write failing test**

```python
# backend/tests/test_guard.py
import pytest
from app.agent.guard import ResponseGuard

def test_extract_numbers_from_text():
    guard = ResponseGuard()

    text = "当前价格为 $173.25，涨幅 +8.3%，市值 2.5万亿美元"
    numbers = guard.extract_numbers(text)

    assert 173.25 in numbers
    assert 8.3 in numbers
    assert 2.5 in numbers

def test_validate_numbers_match():
    guard = ResponseGuard()

    response_text = "BABA当前价格为 $85.32，7天涨幅 -3.61%"
    tool_results = [
        {
            "tool_name": "get_price",
            "result": {
                "current_price": 85.32,
                "period_change_pct": -3.61
            }
        }
    ]

    result = guard.validate(response_text, tool_results)

    assert result["verified"] is True
    assert len(result["mismatches"]) == 0

def test_validate_numbers_mismatch():
    guard = ResponseGuard()

    response_text = "BABA当前价格约为 $85，涨幅约 -4%"
    tool_results = [
        {
            "tool_name": "get_price",
            "result": {
                "current_price": 85.32,
                "period_change_pct": -3.61
            }
        }
    ]

    result = guard.validate(response_text, tool_results)

    assert result["verified"] is False
    assert len(result["mismatches"]) > 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_guard.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement ResponseGuard**

```python
# backend/app/agent/guard.py
import re
from typing import List, Dict, Any
from datetime import datetime, timezone

class ResponseGuard:
    """
    Validates LLM responses against tool outputs.
    Ensures numbers in responses match tool data.
    """

    def extract_numbers(self, text: str) -> List[float]:
        """
        Extract all numbers from text.
        Handles: integers, decimals, percentages, currency symbols.
        """
        # Remove currency symbols and commas
        cleaned = text.replace('$', '').replace('¥', '').replace(',', '')

        # Pattern: optional minus, digits, optional decimal point and digits, optional %
        pattern = r'-?\d+\.?\d*'
        matches = re.findall(pattern, cleaned)

        numbers = []
        for match in matches:
            try:
                num = float(match)
                numbers.append(num)
            except ValueError:
                continue

        return numbers

    def extract_tool_numbers(self, tool_results: List[Dict[str, Any]]) -> List[float]:
        """Extract all numeric values from tool results."""
        numbers = []

        for tool_result in tool_results:
            result = tool_result.get("result", {})

            # Recursively extract numbers from nested dicts
            def extract_from_dict(d):
                if isinstance(d, dict):
                    for value in d.values():
                        if isinstance(value, (int, float)):
                            numbers.append(float(value))
                        elif isinstance(value, dict):
                            extract_from_dict(value)
                        elif isinstance(value, list):
                            for item in value:
                                if isinstance(item, dict):
                                    extract_from_dict(item)

            extract_from_dict(result)

        return numbers

    def find_match(self, response_num: float, tool_numbers: List[float], tolerance: float = 0.02) -> bool:
        """
        Check if response number matches any tool number within tolerance.
        Tolerance: 2% relative error or 0.01 absolute error.
        """
        for tool_num in tool_numbers:
            # Absolute match
            if abs(response_num - tool_num) < 0.01:
                return True

            # Relative match (within 2%)
            if tool_num != 0:
                relative_error = abs(response_num - tool_num) / abs(tool_num)
                if relative_error < tolerance:
                    return True

        return False

    def validate(self, response_text: str, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate response against tool results.

        Returns:
            {
                "verified": bool,
                "mismatches": List[float],
                "response_numbers": List[float],
                "tool_numbers": List[float],
                "timestamp": datetime
            }
        """
        response_numbers = self.extract_numbers(response_text)
        tool_numbers = self.extract_tool_numbers(tool_results)

        mismatches = []
        for num in response_numbers:
            if not self.find_match(num, tool_numbers):
                mismatches.append(num)

        return {
            "verified": len(mismatches) == 0,
            "mismatches": mismatches,
            "response_numbers": response_numbers,
            "tool_numbers": tool_numbers,
            "timestamp": datetime.now(timezone.utc)
        }
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_guard.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/agent/guard.py backend/tests/test_guard.py
git commit -m "feat: implement ResponseGuard for number validation

- Add number extraction from text (handles currency, percentages)
- Add number extraction from tool results
- Add fuzzy matching with 2% tolerance
- Add validation logic comparing response vs tool data
- Add tests for extraction and validation

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 18: Implement Claude Agent Core Loop

**Files:**
- Create: `backend/app/agent/core.py`
- Create: `backend/tests/test_agent_core.py`

**Step 1: Write failing test**

```python
# backend/tests/test_agent_core.py
import pytest
from app.agent.core import ClaudeAgent

@pytest.mark.asyncio
async def test_agent_processes_simple_query():
    agent = ClaudeAgent()

    response = await agent.process_query("什么是市盈率")

    assert len(response) > 0
    assert "市盈率" in response

@pytest.mark.asyncio
async def test_agent_uses_tools():
    agent = ClaudeAgent()

    # This should trigger get_price tool
    response = await agent.process_query("AAPL当前股价")

    assert "AAPL" in response or "苹果" in response
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent_core.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement Claude Agent Core**

```python
# backend/app/agent/core.py
import anthropic
from typing import List, Dict, Any, AsyncGenerator
from app.agent.tools import TOOLS
from app.agent.dispatcher import ToolDispatcher
from app.agent.guard import ResponseGuard
from app.config import get_settings

SYSTEM_PROMPT = """你是华尔街见闻的金融资产分析助手，服务中国的个人投资者和金融从业者。

═══ 最高优先级规则（违反任何一条都是严重错误）═══

1. 任何价格、涨跌幅、市值、成交量等数字，必须且只能来自工具调用结果。
   严禁凭记忆或推测生成任何金融数字。

2. 如果工具调用失败或数据不可用，直接告知用户"该数据当前无法获取"。
   绝不编造替代数据。

═══ 工具使用策略 ═══

你有 6 个工具可用。根据问题内容自主决定使用哪些：

• 用户问价格/涨跌/走势 → get_price / get_history / get_change
• 用户问公司信息/基本面 → get_info
• 用户问金融概念/术语 → search_knowledge (知识库检索)
• 用户问涨跌原因/近期事件 → search_web (新闻搜索)
• 复合问题 → 组合使用多个工具

═══ 回答格式 ═══

包含行情数据的回答：

📊 数据摘要
[只放客观数据，标注来源和时间]

📈 趋势分析
[基于数据的结构化判断：上涨/下跌/震荡]

🔍 影响因素（分析）
[基于新闻/事件的分析，明确使用"分析认为""可能因为"等措辞]

⚠️ 风险提示
以上内容基于公开数据整理，不构成投资建议。

---
数据来源: [yfinance/知识库/Web搜索] | 更新时间: [时间]

纯知识类回答：

📚 概念解释
[来自知识库的内容]

来源: [知识库/模型知识] | 如来自知识库需标注具体文档

═══ 绝对禁止 ═══

✗ 预测未来股价走势
✗ 给出买入/卖出/持有等投资建议
✗ 在没有工具数据的情况下说出具体价格数字
✗ 把分析性观点表述为客观事实
"""

class ClaudeAgent:
    """
    Claude Agent with native Anthropic SDK.
    Implements tool use loop without LangChain.
    """

    def __init__(self):
        self.settings = get_settings()
        self.client = anthropic.Anthropic(
            api_key=self.settings.anthropic_api_key
        )
        self.dispatcher = ToolDispatcher()
        self.guard = ResponseGuard()
        self.max_iterations = 5

    async def process_query(
        self,
        query: str,
        enriched_query: str = None
    ) -> str:
        """
        Process user query with tool use loop.

        Args:
            query: Original user query
            enriched_query: Query with hints from QueryEnricher

        Returns:
            Final response text
        """
        messages = [
            {
                "role": "user",
                "content": enriched_query or query
            }
        ]

        tool_results = []

        for iteration in range(self.max_iterations):
            # Call Claude
            response = self.client.messages.create(
                model=self.settings.claude_model,
                max_tokens=self.settings.claude_max_tokens,
                temperature=self.settings.claude_temperature,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            )

            # Check stop reason
            if response.stop_reason == "end_turn":
                # Agent finished, extract text response
                text_content = ""
                for block in response.content:
                    if block.type == "text":
                        text_content += block.text

                # Validate response
                validation = self.guard.validate(text_content, tool_results)

                return text_content

            elif response.stop_reason == "tool_use":
                # Agent wants to use tools
                assistant_message = {
                    "role": "assistant",
                    "content": response.content
                }
                messages.append(assistant_message)

                # Execute tools
                tool_result_content = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input

                        # Dispatch tool call
                        result = await self.dispatcher.dispatch(tool_name, tool_input)

                        # Store for validation
                        tool_results.append({
                            "tool_name": tool_name,
                            "tool_input": tool_input,
                            "result": result
                        })

                        # Add to message
                        tool_result_content.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result)
                        })

                # Add tool results to messages
                messages.append({
                    "role": "user",
                    "content": tool_result_content
                })

            else:
                # Unexpected stop reason
                return f"抱歉，处理出现异常：{response.stop_reason}"

        # Max iterations reached
        return "抱歉，问题处理超时，请简化问题后重试。"

    async def process_query_stream(
        self,
        query: str,
        enriched_query: str = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process query with streaming response.

        Yields events:
            {"type": "tool_start", "name": str, "input": dict}
            {"type": "tool_result", "name": str, "result": dict}
            {"type": "text_delta", "text": str}
            {"type": "done", "verified": bool}
        """
        messages = [
            {
                "role": "user",
                "content": enriched_query or query
            }
        ]

        tool_results = []

        for iteration in range(self.max_iterations):
            # Stream Claude response
            with self.client.messages.stream(
                model=self.settings.claude_model,
                max_tokens=self.settings.claude_max_tokens,
                temperature=self.settings.claude_temperature,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            ) as stream:
                assistant_content = []
                current_text = ""

                for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            yield {
                                "type": "tool_start",
                                "name": event.content_block.name,
                                "id": event.content_block.id
                            }

                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            text = event.delta.text
                            current_text += text
                            yield {
                                "type": "text_delta",
                                "text": text
                            }

                    elif event.type == "content_block_stop":
                        pass

                # Get final message
                final_message = stream.get_final_message()
                assistant_content = final_message.content

                # Check stop reason
                if final_message.stop_reason == "end_turn":
                    # Validate
                    validation = self.guard.validate(current_text, tool_results)

                    yield {
                        "type": "done",
                        "verified": validation["verified"],
                        "mismatches": validation["mismatches"]
                    }
                    return

                elif final_message.stop_reason == "tool_use":
                    # Execute tools
                    messages.append({
                        "role": "assistant",
                        "content": assistant_content
                    })

                    tool_result_content = []
                    for block in assistant_content:
                        if block.type == "tool_use":
                            tool_name = block.name
                            tool_input = block.input

                            # Dispatch
                            result = await self.dispatcher.dispatch(tool_name, tool_input)

                            # Store
                            tool_results.append({
                                "tool_name": tool_name,
                                "tool_input": tool_input,
                                "result": result
                            })

                            # Yield result
                            yield {
                                "type": "tool_result",
                                "name": tool_name,
                                "result": result
                            }

                            # Add to message
                            tool_result_content.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(result)
                            })

                    # Add tool results
                    messages.append({
                        "role": "user",
                        "content": tool_result_content
                    })

        # Max iterations
        yield {
            "type": "error",
            "message": "处理超时"
        }
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent_core.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/app/agent/core.py backend/tests/test_agent_core.py
git commit -m "feat: implement Claude Agent core with native Anthropic SDK

- Add ClaudeAgent with tool use loop
- Implement non-streaming process_query method
- Implement streaming process_query_stream method
- Add system prompt with guardrails
- Integrate ToolDispatcher and ResponseGuard
- Add max iteration limit (5 rounds)
- Add tests for query processing

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 8: FastAPI Backend with SSE

### Task 19: Implement SSE Streaming Endpoint

**Files:**
- Create: `backend/app/api/routes.py`
- Create: `backend/app/api/models.py`
- Create: `backend/tests/test_api.py`

**Step 1: Write failing test**

```python
# backend/tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_chat_endpoint_sse():
    # SSE endpoint test
    with client.stream("POST", "/api/chat", json={"query": "什么是市盈率"}) as response:
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        # Read at least one event
        events = []
        for line in response.iter_lines():
            if line.startswith("data: "):
                events.append(line)
                if len(events) >= 1:
                    break

        assert len(events) > 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_api.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Create API models**

```python
# backend/app/api/models.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = None

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
```

**Step 4: Implement API routes**

```python
# backend/app/api/routes.py
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
import json
from app.api.models import ChatRequest, HealthResponse
from app.agent.core import ClaudeAgent
from app.enricher.query_enricher import QueryEnricher
from app.config import get_settings

router = APIRouter(prefix="/api")

# Initialize services
agent = ClaudeAgent()
enricher = QueryEnricher()
settings = get_settings()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc)
    )

@router.post("/chat")
async def chat_stream(request: ChatRequest):
    """
    Chat endpoint with SSE streaming.

    Returns Server-Sent Events stream with:
    - tool_start: Tool execution started
    - tool_result: Tool execution completed
    - text_delta: Incremental text response
    - done: Response complete with verification status
    - error: Error occurred
    """
    try:
        # Enrich query
        enriched_query = enricher.enrich(request.query)

        async def event_generator():
            """Generate SSE events."""
            try:
                async for event in agent.process_query_stream(
                    query=request.query,
                    enriched_query=enriched_query
                ):
                    # Format as SSE
                    event_data = json.dumps(event, ensure_ascii=False)
                    yield f"data: {event_data}\n\n"

            except Exception as e:
                error_event = {
                    "type": "error",
                    "message": str(e)
                }
                yield f"data: {json.dumps(error_event)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Step 5: Create main application**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router)

@app.get("/")
async def root():
    return {
        "message": "Financial Asset QA System API",
        "version": settings.app_version,
        "docs": "/docs"
    }
```

**Step 6: Run test to verify it passes**

Run: `cd backend && pytest tests/test_api.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add backend/app/api/ backend/app/main.py backend/tests/test_api.py
git commit -m "feat: implement FastAPI backend with SSE streaming

- Add /api/health endpoint
- Add /api/chat endpoint with SSE streaming
- Integrate ClaudeAgent and QueryEnricher
- Add CORS middleware for frontend
- Add proper SSE headers (no-cache, keep-alive)
- Add tests for API endpoints

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 9: Frontend Implementation

### Task 20: Initialize React Frontend

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/vite.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/index.css`

**Step 1: Create HTML entry point**

```html
<!-- frontend/index.html -->
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>金融资产智能问答系统</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

**Step 2: Create Vite config**

```javascript
// frontend/vite.config.js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
```

**Step 3: Create TailwindCSS config**

```javascript
// frontend/tailwind.config.js
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        'dark-bg': '#0f172a',
        'dark-card': '#1e293b',
        'dark-border': '#334155',
      }
    },
  },
  plugins: [],
}
```

```javascript
// frontend/postcss.config.js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

**Step 4: Create main entry and styles**

```css
/* frontend/src/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  background-color: #0f172a;
  color: #e2e8f0;
}

code {
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
}

/* Custom scrollbar */
::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: #1e293b;
}

::-webkit-scrollbar-thumb {
  background: #475569;
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: #64748b;
}
```

```jsx
// frontend/src/main.jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

```jsx
// frontend/src/App.jsx
import React from 'react'

function App() {
  return (
    <div className="min-h-screen bg-dark-bg">
      <header className="border-b border-dark-border bg-dark-card">
        <div className="max-w-7xl mx-auto py-4 px-6">
          <h1 className="text-2xl font-bold text-white">
            金融资产智能问答系统
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Financial Asset QA System
          </p>
        </div>
      </header>
      <main className="max-w-7xl mx-auto py-6 px-6">
        <p className="text-gray-400">Loading...</p>
      </main>
    </div>
  )
}

export default App
```

**Step 5: Test frontend runs**

Run: `cd frontend && npm install && npm run dev`
Expected: Frontend starts on http://localhost:5173

**Step 6: Commit frontend setup**

```bash
git add frontend/
git commit -m "feat: initialize React frontend with Vite and TailwindCSS

- Add Vite configuration with API proxy
- Add TailwindCSS with dark theme
- Add HTML entry point
- Add basic App component
- Add custom scrollbar styles

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 21: Implement SSE Client Hook

**Files:**
- Create: `frontend/src/hooks/useSSE.js`
- Create: `frontend/src/services/api.js`

**Step 1: Create API service**

```javascript
// frontend/src/services/api.js
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = {
  /**
   * Send chat message via SSE
   * @param {string} query - User query
   * @param {function} onEvent - Event handler (type, data) => void
   * @returns {function} - Cleanup function
   */
  sendMessage(query, onEvent) {
    const eventSource = new EventSource(
      `${API_BASE_URL}/api/chat?query=${encodeURIComponent(query)}`
    )

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onEvent(data.type, data)
      } catch (error) {
        console.error('Failed to parse SSE event:', error)
      }
    }

    eventSource.onerror = (error) => {
      console.error('SSE error:', error)
      onEvent('error', { message: 'Connection error' })
      eventSource.close()
    }

    // Return cleanup function
    return () => {
      eventSource.close()
    }
  },

  /**
   * Check API health
   */
  async checkHealth() {
    const response = await fetch(`${API_BASE_URL}/api/health`)
    return response.json()
  }
}
```

**Step 2: Create SSE hook**

```javascript
// frontend/src/hooks/useSSE.js
import { useState, useCallback, useRef } from 'react'
import { api } from '../services/api'

export function useSSE() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [currentResponse, setCurrentResponse] = useState('')
  const cleanupRef = useRef(null)

  const sendMessage = useCallback((query) => {
    if (!query.trim()) return

    // Add user message
    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: query,
      timestamp: new Date()
    }
    setMessages(prev => [...prev, userMessage])

    // Reset state
    setLoading(true)
    setError(null)
    setCurrentResponse('')

    const assistantMessage = {
      id: Date.now() + 1,
      role: 'assistant',
      content: '',
      toolCalls: [],
      verified: false,
      timestamp: new Date()
    }

    // Handle SSE events
    const handleEvent = (type, data) => {
      switch (type) {
        case 'tool_start':
          assistantMessage.toolCalls.push({
            name: data.name,
            status: 'running'
          })
          setMessages(prev => {
            const newMessages = [...prev]
            const lastMsg = newMessages[newMessages.length - 1]
            if (lastMsg?.role === 'assistant') {
              newMessages[newMessages.length - 1] = { ...assistantMessage }
            } else {
              newMessages.push({ ...assistantMessage })
            }
            return newMessages
          })
          break

        case 'tool_result':
          const toolCall = assistantMessage.toolCalls.find(t => t.name === data.name)
          if (toolCall) {
            toolCall.status = 'completed'
            toolCall.result = data.result
          }
          setMessages(prev => {
            const newMessages = [...prev]
            newMessages[newMessages.length - 1] = { ...assistantMessage }
            return newMessages
          })
          break

        case 'text_delta':
          assistantMessage.content += data.text
          setCurrentResponse(assistantMessage.content)
          setMessages(prev => {
            const newMessages = [...prev]
            const lastMsg = newMessages[newMessages.length - 1]
            if (lastMsg?.role === 'assistant') {
              newMessages[newMessages.length - 1] = { ...assistantMessage }
            } else {
              newMessages.push({ ...assistantMessage })
            }
            return newMessages
          })
          break

        case 'done':
          assistantMessage.verified = data.verified
          assistantMessage.mismatches = data.mismatches || []
          setMessages(prev => {
            const newMessages = [...prev]
            newMessages[newMessages.length - 1] = { ...assistantMessage }
            return newMessages
          })
          setLoading(false)
          if (cleanupRef.current) {
            cleanupRef.current()
            cleanupRef.current = null
          }
          break

        case 'error':
          setError(data.message)
          setLoading(false)
          if (cleanupRef.current) {
            cleanupRef.current()
            cleanupRef.current = null
          }
          break
      }
    }

    // Start SSE connection
    cleanupRef.current = api.sendMessage(query, handleEvent)
  }, [])

  const clearMessages = useCallback(() => {
    setMessages([])
    setCurrentResponse('')
    setError(null)
  }, [])

  return {
    messages,
    loading,
    error,
    currentResponse,
    sendMessage,
    clearMessages
  }
}
```

**Step 3: Commit SSE client**

```bash
git add frontend/src/hooks/useSSE.js frontend/src/services/api.js
git commit -m "feat: implement SSE client hook for streaming responses

- Add API service with EventSource integration
- Add useSSE hook with message state management
- Handle tool_start, tool_result, text_delta, done events
- Add error handling and cleanup
- Track tool execution status

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 22: Implement Chat Interface Components

**Files:**
- Create: `frontend/src/components/ChatPanel.jsx`
- Create: `frontend/src/components/MessageList.jsx`
- Create: `frontend/src/components/MessageBubble.jsx`
- Create: `frontend/src/components/ToolStatus.jsx`
- Create: `frontend/src/components/InputBar.jsx`

**Step 1: Create ToolStatus component**

```jsx
// frontend/src/components/ToolStatus.jsx
import React from 'react'

function ToolStatus({ toolCalls }) {
  if (!toolCalls || toolCalls.length === 0) return null

  const getToolIcon = (name) => {
    const icons = {
      'get_price': '📊',
      'get_history': '📈',
      'get_change': '📉',
      'get_info': 'ℹ️',
      'search_knowledge': '📚',
      'search_web': '🔍'
    }
    return icons[name] || '🔧'
  }

  const getToolLabel = (name) => {
    const labels = {
      'get_price': '获取价格',
      'get_history': '获取历史',
      'get_change': '计算涨跌',
      'get_info': '获取信息',
      'search_knowledge': '检索知识',
      'search_web': '搜索新闻'
    }
    return labels[name] || name
  }

  return (
    <div className="flex flex-wrap gap-2 mb-3">
      {toolCalls.map((tool, index) => (
        <div
          key={index}
          className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm ${
            tool.status === 'running'
              ? 'bg-blue-500/20 text-blue-300'
              : 'bg-green-500/20 text-green-300'
          }`}
        >
          <span>{getToolIcon(tool.name)}</span>
          <span>{getToolLabel(tool.name)}</span>
          {tool.status === 'running' && (
            <span className="animate-pulse">...</span>
          )}
          {tool.status === 'completed' && (
            <span>✓</span>
          )}
        </div>
      ))}
    </div>
  )
}

export default ToolStatus
```

**Step 2: Create MessageBubble component**

```jsx
// frontend/src/components/MessageBubble.jsx
import React from 'react'
import ToolStatus from './ToolStatus'

function MessageBubble({ message }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-3xl rounded-lg px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-dark-card border border-dark-border text-gray-100'
        }`}
      >
        {!isUser && message.toolCalls && (
          <ToolStatus toolCalls={message.toolCalls} />
        )}

        <div className="whitespace-pre-wrap break-words">
          {message.content}
        </div>

        {!isUser && message.verified !== undefined && (
          <div className="mt-2 pt-2 border-t border-gray-700 text-xs">
            {message.verified ? (
              <span className="text-green-400">✓ 数据已校验</span>
            ) : (
              <span className="text-yellow-400">⚠ 数据未完全校验</span>
            )}
          </div>
        )}

        <div className="mt-1 text-xs opacity-60">
          {message.timestamp.toLocaleTimeString('zh-CN')}
        </div>
      </div>
    </div>
  )
}

export default MessageBubble
```

**Step 3: Create MessageList component**

```jsx
// frontend/src/components/MessageList.jsx
import React, { useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble'

function MessageList({ messages }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-500">
        <div className="text-center">
          <p className="text-lg mb-2">👋 你好！我是金融资产分析助手</p>
          <p className="text-sm">你可以问我关于股票价格、金融概念或市场新闻的问题</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      <div ref={bottomRef} />
    </div>
  )
}

export default MessageList
```

**Step 4: Create InputBar component**

```jsx
// frontend/src/components/InputBar.jsx
import React, { useState } from 'react'

function InputBar({ onSend, disabled }) {
  const [input, setInput] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (input.trim() && !disabled) {
      onSend(input)
      setInput('')
    }
  }

  const suggestions = [
    '阿里巴巴当前股价是多少？',
    '什么是市盈率？',
    'TSLA最近7天涨跌情况',
    '特斯拉为何最近大涨？'
  ]

  return (
    <div className="border-t border-dark-border bg-dark-card p-4">
      {input.length === 0 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              onClick={() => setInput(suggestion)}
              disabled={disabled}
              className="px-3 py-1 text-sm bg-dark-bg border border-dark-border rounded-full hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="询问股票价格、金融概念或市场新闻..."
          disabled={disabled}
          className="flex-1 px-4 py-3 bg-dark-bg border border-dark-border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 text-white placeholder-gray-500"
        />
        <button
          type="submit"
          disabled={disabled || !input.trim()}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors font-medium"
        >
          发送
        </button>
      </form>
    </div>
  )
}

export default InputBar
```

**Step 5: Create ChatPanel component**

```jsx
// frontend/src/components/ChatPanel.jsx
import React from 'react'
import MessageList from './MessageList'
import InputBar from './InputBar'
import { useSSE } from '../hooks/useSSE'

function ChatPanel() {
  const { messages, loading, error, sendMessage, clearMessages } = useSSE()

  return (
    <div className="flex flex-col h-[calc(100vh-120px)] bg-dark-card rounded-lg shadow-xl border border-dark-border">
      {error && (
        <div className="bg-red-500/20 border border-red-500 text-red-300 px-4 py-3 m-4 rounded">
          <strong>错误：</strong> {error}
        </div>
      )}

      <MessageList messages={messages} />

      {loading && (
        <div className="px-4 py-2 text-gray-400 text-sm flex items-center gap-2">
          <span className="animate-pulse">●</span>
          <span>正在思考...</span>
        </div>
      )}

      <InputBar onSend={sendMessage} disabled={loading} />
    </div>
  )
}

export default ChatPanel
```

**Step 6: Update App to use ChatPanel**

```jsx
// frontend/src/App.jsx
import React from 'react'
import ChatPanel from './components/ChatPanel'

function App() {
  return (
    <div className="min-h-screen bg-dark-bg">
      <header className="border-b border-dark-border bg-dark-card">
        <div className="max-w-7xl mx-auto py-4 px-6">
          <h1 className="text-2xl font-bold text-white">
            金融资产智能问答系统
          </h1>
          <p className="text-sm text-gray-400 mt-1">
            Financial Asset QA System - Powered by Claude Sonnet 4.6
          </p>
        </div>
      </header>
      <main className="max-w-7xl mx-auto py-6 px-6">
        <ChatPanel />
      </main>
    </div>
  )
}

export default App
```

**Step 7: Commit chat interface**

```bash
git add frontend/src/components/ frontend/src/App.jsx
git commit -m "feat: implement chat interface components

- Add ChatPanel with SSE integration
- Add MessageList with auto-scroll
- Add MessageBubble with tool status display
- Add ToolStatus component with icons
- Add InputBar with suggestion chips
- Add dark theme styling
- Add verification badge display

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 10: Docker & Deployment

### Task 23: Create Dockerfiles

**Files:**
- Create: `docker/Dockerfile.backend`
- Create: `docker/Dockerfile.frontend`
- Update: `docker/docker-compose.yml`
- Create: `.dockerignore`

**Step 1: Create backend Dockerfile**

```dockerfile
# docker/Dockerfile.backend
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/app ./app
COPY backend/data ./data

# Create directories
RUN mkdir -p ./vectorstore/chroma

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health')"

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2: Create frontend Dockerfile**

```dockerfile
# docker/Dockerfile.frontend
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy application
COPY frontend/ .

# Expose port
EXPOSE 5173

# Run development server
CMD ["npm", "run", "dev", "--", "--host"]
```

**Step 3: Update docker-compose.yml**

```yaml
# docker/docker-compose.yml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: financial-qa-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ..
      dockerfile: docker/Dockerfile.backend
    container_name: financial-qa-backend
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
    env_file:
      - ../backend/.env
    depends_on:
      redis:
        condition: service_healthy
    volumes:
      - ../backend/app:/app/app
      - ../backend/data:/app/data
      - ../vectorstore:/app/vectorstore
    restart: unless-stopped

  frontend:
    build:
      context: ..
      dockerfile: docker/Dockerfile.frontend
    container_name: financial-qa-frontend
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://localhost:8000
    volumes:
      - ../frontend/src:/app/src
      - ../frontend/public:/app/public
      - /app/node_modules
    depends_on:
      - backend
    restart: unless-stopped

volumes:
  redis_data:
```

**Step 4: Create .dockerignore**

```
# .dockerignore
**/__pycache__
**/*.pyc
**/.pytest_cache
**/.coverage
**/node_modules
**/.git
**/.env
**/venv
**/.venv
**/.DS_Store
**/dist
**/build
**/.vscode
**/.idea
```

**Step 5: Test Docker build**

Run: `cd docker && docker-compose up --build`
Expected: All services start successfully

**Step 6: Commit Docker configuration**

```bash
git add docker/ .dockerignore
git commit -m "feat: add Docker configuration for deployment

- Add backend Dockerfile with Python 3.11
- Add frontend Dockerfile with Node 18
- Update docker-compose.yml with health checks
- Add Redis persistence with appendonly
- Add volume mounts for development
- Add .dockerignore for build optimization
- Add restart policies

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 11: Documentation & Testing

### Task 24: Create README and Documentation

**Files:**
- Create: `README.md`
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/API.md`
- Create: `docs/DEPLOYMENT.md`

**Step 1: Create README**

```markdown
# 金融资产智能问答系统 (Financial Asset QA System)

基于 Claude Sonnet 4.6 的生产级金融资产问答系统，集成实时行情数据、知识检索(RAG)和新闻搜索。

## 核心特性

- **实时行情数据** - 股票价格、涨跌趋势、历史分析
- **金融知识问答** - 基于 RAG 的金融概念解释
- **新闻事件分析** - 最新市场动态和事件驱动分析
- **多源推理** - 组合多个数据源进行综合分析
- **流式响应** - SSE 实时推送，打字机效果
- **数据校验** - ResponseGuard 确保数字准确性

## 技术架构

```
Frontend (React + Vite) → API (FastAPI + SSE) → Claude Agent
                                    ↓
                        ┌───────────┼───────────┐
                        ↓           ↓           ↓
                  MarketData    RAG Pipeline  WebSearch
                  (yfinance)   (bge-base-zh)  (Tavily)
```

## 技术栈

**后端:**
- Python 3.11+
- FastAPI + Uvicorn
- Claude Sonnet 4.6 (Anthropic SDK)
- bge-base-zh-v1.5 (本地 Embedding)
- bge-reranker-base (Cross-Encoder)
- ChromaDB (向量数据库)
- Redis (缓存)
- yfinance + Alpha Vantage (行情数据)

**前端:**
- React 18
- Vite
- TailwindCSS
- EventSource (SSE)

**基础设施:**
- Docker Compose
- Redis

## 快速开始

### 前置要求

- Docker & Docker Compose
- Anthropic API Key
- (可选) Tavily API Key (用于新闻搜索)
- (可选) Alpha Vantage API Key (备用数据源)

### 安装步骤

1. 克隆仓库:
```bash
git clone <repo-url>
cd Financial_Asset_QA_System
```

2. 配置环境变量:
```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env 添加你的 API keys
```

3. 启动服务:
```bash
cd docker
docker-compose up --build
```

4. 访问应用:
- 前端: http://localhost:5173
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 本地开发

### 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

### 运行测试

```bash
cd backend
pytest
```

## 示例查询

- **行情查询**: "阿里巴巴当前股价是多少？"
- **趋势分析**: "BABA 最近 7 天涨跌情况如何？"
- **知识问答**: "什么是市盈率？"
- **事件分析**: "特斯拉为何最近大涨？"
- **综合分析**: "特斯拉近期走势及原因分析"

## 项目结构

```
Financial_Asset_QA_System/
├── backend/
│   ├── app/
│   │   ├── agent/          # Claude Agent 核心
│   │   ├── market/         # 行情数据服务
│   │   ├── rag/            # RAG 检索管道
│   │   ├── search/         # 网络搜索
│   │   ├── enricher/       # 查询增强
│   │   └── api/            # FastAPI 路由
│   ├── data/
│   │   └── knowledge/      # 知识库
│   └── tests/              # 测试
├── frontend/
│   └── src/
│       ├── components/     # React 组件
│       ├── hooks/          # 自定义 Hooks
│       └── services/       # API 服务
├── docker/                 # Docker 配置
├── docs/                   # 文档
└── vectorstore/            # ChromaDB 存储
```

## 核心设计原则

> **LLM 不应生成金融事实，LLM 应解释已验证的金融数据。**

- 所有数字必须来自工具调用，不允许 LLM 编造
- 明确区分"客观数据"与"分析性描述"
- 所有数据源必须标注来源和时间戳
- ResponseGuard 自动校验响应中的数字

## 文档

- [架构设计](docs/ARCHITECTURE.md)
- [API 文档](docs/API.md)
- [部署指南](docs/DEPLOYMENT.md)
- [设计文档](docs/plans/financial-qa-final-design-009.md)

## 许可证

MIT

## 致谢

- Claude Sonnet 4.6 by Anthropic
- bge-base-zh by BAAI
- yfinance by Ran Aroussi
```

**Step 2: Create ARCHITECTURE.md**

```markdown
# 架构文档

## 系统概览

本系统采用单一 Claude Agent 架构，通过 6 个工具访问不同数据源。

## 核心组件

### 1. Claude Agent Core

**职责:**
- 理解用户查询
- 决定调用哪些工具
- 综合工具结果生成回答

**实现:**
- 使用 Anthropic SDK 原生 Tool Use
- 不使用 LangChain (更透明、可调试)
- 最大 5 轮工具调用循环

### 2. QueryEnricher

**职责:**
- 零成本规则提示注入
- 不做分类决策，只做信息补充

**策略:**
- 检测股票名/代码 → 提示"可能需要行情工具"
- 检测"为什么" → 提示"可能需要新闻搜索"
- 检测"什么是" → 提示"可能需要知识检索"

### 3. MarketDataService

**职责:**
- 获取实时和历史行情数据
- 双数据源 fallback

**数据流:**
```
TickerMapper (阿里巴巴 → BABA)
    ↓
Redis Cache (60s TTL)
    ↓
yfinance (主)
    ↓
Alpha Vantage (备)
```

### 4. RAG Pipeline

**职责:**
- 检索金融知识库

**两阶段检索:**
```
Query → bge-base-zh Embedding
    ↓
ChromaDB Vector Search (Top-K=10)
    ↓
bge-reranker Cross-Encoder (Top-N=3)
    ↓
返回最相关文档
```

### 5. WebSearchService

**职责:**
- 搜索最新新闻和事件

**实现:**
- Tavily API
- 结构化摘要
- 来源可信度分级

### 6. ResponseGuard

**职责:**
- 校验 LLM 输出中的数字

**验证逻辑:**
```
提取响应中的数字
    ↓
提取工具返回的数字
    ↓
逐个匹配 (2% 容差)
    ↓
返回 verified: true/false
```

## 数据流示例

**查询: "阿里巴巴最近7天涨跌情况如何？"**

```
1. 用户查询 → QueryEnricher
   输出: "[提示: 涉及行情数据]\n\n阿里巴巴最近7天涨跌情况如何？"

2. Claude Agent 分析 → 决定调用 get_change

3. ToolDispatcher → MarketDataService
   - TickerMapper: "阿里巴巴" → "BABA"
   - Redis: cache miss
   - yfinance: 获取 7 天数据
   - 计算涨跌: -3.61%
   - Redis: 写入缓存

4. Claude Agent 收到数据 → 生成结构化回答

5. ResponseGuard 校验
   - 提取: [-3.61]
   - 匹配: ✓
   - verified: true

6. SSE 流式推送给前端
```

## 技术决策

### 为什么不用 LangChain？

- Agent 逻辑简单 (tool use 循环 <60 行)
- 直接用 SDK 更透明、可调试
- 减少 2000+ 行间接依赖

### 为什么用 bge-base-zh？

- 本地运行，零 API 成本
- 中文语义理解强
- MTEB 中文榜前列

### 为什么用 SSE 而不是 WebSocket？

- 单向推送足够
- 浏览器原生 EventSource
- 更简单，更可靠

## 缓存策略

| 数据类型 | TTL | 原因 |
|---------|-----|------|
| 实时价格 | 60s | 价格变化快 |
| 历史数据 | 24h | 历史不变 |
| 公司信息 | 7d | 基本面稳定 |

## 错误处理

| 场景 | 策略 |
|------|------|
| yfinance 超时 | 切换 Alpha Vantage |
| 双源均失败 | 返回"数据不可用" |
| RAG 无结果 | 使用 LLM 知识 + 标注 |
| Web 搜索失败 | 跳过新闻分析 |
```

**Step 3: Create API.md**

```markdown
# API 文档

## 基础信息

- Base URL: `http://localhost:8000`
- 所有时间戳使用 UTC
- 响应格式: JSON / SSE

## 端点

### GET /api/health

健康检查

**响应:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-03-04T10:30:00Z"
}
```

### POST /api/chat

聊天接口 (SSE 流式)

**请求:**
```json
{
  "query": "阿里巴巴当前股价",
  "session_id": "optional-session-id"
}
```

**响应:** Server-Sent Events

**事件类型:**

1. `tool_start` - 工具开始执行
```json
{
  "type": "tool_start",
  "name": "get_price",
  "id": "tool_use_id"
}
```

2. `tool_result` - 工具执行完成
```json
{
  "type": "tool_result",
  "name": "get_price",
  "result": {
    "symbol": "BABA",
    "current_price": 85.32,
    "period_change_pct": -3.61
  }
}
```

3. `text_delta` - 文本增量
```json
{
  "type": "text_delta",
  "text": "根据"
}
```

4. `done` - 响应完成
```json
{
  "type": "done",
  "verified": true,
  "mismatches": []
}
```

5. `error` - 错误
```json
{
  "type": "error",
  "message": "错误信息"
}
```

## 工具说明

### get_price

获取当前价格

**输入:**
```json
{
  "symbol": "BABA"
}
```

**输出:**
```json
{
  "symbol": "BABA",
  "current_price": 85.32,
  "change": -3.18,
  "change_pct": -3.61,
  "high": 88.50,
  "low": 84.20,
  "volume": 12500000,
  "data_source": "yfinance",
  "timestamp": "2026-03-04T10:30:00Z"
}
```

### get_history

获取历史数据

**输入:**
```json
{
  "symbol": "BABA",
  "days": 7
}
```

### get_change

计算涨跌幅

**输入:**
```json
{
  "symbol": "BABA",
  "days": 7
}
```

### get_info

获取公司信息

**输入:**
```json
{
  "symbol": "BABA"
}
```

### search_knowledge

检索知识库

**输入:**
```json
{
  "query": "什么是市盈率"
}
```

### search_web

搜索新闻

**输入:**
```json
{
  "query": "阿里巴巴 BABA 股价上涨"
}
```
```

**Step 4: Commit documentation**

```bash
git add README.md docs/
git commit -m "docs: add comprehensive documentation

- Add README with quick start guide
- Add ARCHITECTURE.md with design decisions
- Add API.md with endpoint documentation
- Add example queries and project structure
- Add core design principles

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 12: Final Integration & Testing

### Task 25: Create Integration Tests

**Files:**
- Create: `backend/tests/integration/test_end_to_end.py`
- Create: `backend/tests/integration/conftest.py`

**Step 1: Create integration test fixtures**

```python
# backend/tests/integration/conftest.py
import pytest
import asyncio
from app.agent.core import ClaudeAgent
from app.rag.pipeline import RAGPipeline

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def agent():
    """Create Claude Agent instance."""
    return ClaudeAgent()

@pytest.fixture(scope="session")
async def rag_pipeline():
    """Create and initialize RAG pipeline."""
    pipeline = RAGPipeline()
    await pipeline.initialize()
    return pipeline
```

**Step 2: Create end-to-end tests**

```python
# backend/tests/integration/test_end_to_end.py
import pytest

@pytest.mark.asyncio
@pytest.mark.integration
async def test_market_query_end_to_end(agent):
    """Test complete flow for market data query."""
    query = "AAPL当前股价"

    response = await agent.process_query(query)

    assert len(response) > 0
    assert "AAPL" in response or "苹果" in response
    # Should contain price information
    assert any(char.isdigit() for char in response)

@pytest.mark.asyncio
@pytest.mark.integration
async def test_knowledge_query_end_to_end(agent):
    """Test complete flow for knowledge query."""
    query = "什么是市盈率"

    response = await agent.process_query(query)

    assert len(response) > 0
    assert "市盈率" in response
    # Should contain explanation
    assert len(response) > 50

@pytest.mark.asyncio
@pytest.mark.integration
async def test_hybrid_query_end_to_end(agent):
    """Test complete flow for hybrid query."""
    query = "特斯拉最近走势如何"

    response = await agent.process_query(query)

    assert len(response) > 0
    assert "特斯拉" in response or "TSLA" in response

@pytest.mark.asyncio
@pytest.mark.integration
async def test_rag_pipeline_integration(rag_pipeline):
    """Test RAG pipeline with real knowledge base."""
    query = "市盈率的定义"

    results = await rag_pipeline.search(query, top_n=3)

    assert len(results) > 0
    assert results[0]["score"] > 0.7
    assert "市盈率" in results[0]["content"]
```

**Step 3: Create pytest configuration**

```ini
# backend/pytest.ini
[pytest]
markers =
    integration: marks tests as integration tests (deselect with '-m "not integration"')
    slow: marks tests as slow (deselect with '-m "not slow"')

asyncio_mode = auto
```

**Step 4: Run integration tests**

Run: `cd backend && pytest tests/integration/ -v -m integration`
Expected: PASS (requires API keys)

**Step 5: Commit integration tests**

```bash
git add backend/tests/integration/ backend/pytest.ini
git commit -m "test: add integration tests for end-to-end flows

- Add integration test fixtures
- Add end-to-end test for market queries
- Add end-to-end test for knowledge queries
- Add end-to-end test for hybrid queries
- Add RAG pipeline integration test
- Add pytest markers for integration tests

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Summary

This implementation plan covers the complete Financial Asset QA System based on the final design document (financial-qa-final-design-009.md):

**Completed Phases:**

1. ✅ **Phase 1**: Update Dependencies (Task 1)
2. ✅ **Phase 2**: Configuration & Models (Tasks 2-3)
3. ✅ **Phase 3**: Market Data Service (Tasks 4-7)
4. ✅ **Phase 4**: RAG Pipeline with bge Models (Tasks 8-12)
5. ✅ **Phase 5**: Web Search Service (Task 13)
6. ✅ **Phase 6**: Query Enricher (Task 14)
7. ✅ **Phase 7**: Claude Agent Core (Tasks 15-18)
8. ✅ **Phase 8**: FastAPI Backend with SSE (Task 19)
9. ✅ **Phase 9**: Frontend Implementation (Tasks 20-22)
10. ✅ **Phase 10**: Docker & Deployment (Task 23)
11. ✅ **Phase 11**: Documentation (Task 24)
12. ✅ **Phase 12**: Integration Testing (Task 25)

**Total Tasks:** 25

**Key Technologies:**
- Claude Sonnet 4.6 (native Anthropic SDK, no LangChain)
- bge-base-zh-v1.5 (local embeddings)
- bge-reranker-base (cross-encoder)
- FastAPI + SSE streaming
- React 18 + Vite + TailwindCSS
- ChromaDB + Redis
- yfinance + Alpha Vantage fallback

**Next Steps:**
- Execute this plan using `superpowers:subagent-driven-development`
- Each task follows TDD: write test → verify fail → implement → verify pass → commit
- All commits include detailed messages with Co-Authored-By tag

---

**Plan Status:** ✅ Complete and Ready for Execution

**Estimated Time:** 3-4 days for full implementation

**Testing Strategy:** TDD with pytest, integration tests for end-to-end flows
