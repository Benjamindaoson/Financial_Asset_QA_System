# Financial Asset QA System - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a production-grade financial asset QA system with LangChain agent orchestration, multi-source data integration (market data, RAG, web search), and streaming responses.

**Architecture:** Monolithic agent with query router, three core tools (Market Data, RAG, Web Search), FastAPI backend, React frontend, Docker Compose deployment.

**Tech Stack:** Python 3.11+, FastAPI, LangChain, OpenAI GPT-4, ChromaDB, Redis, React 18, Vite, TailwindCSS

---

## Phase 1: Project Setup & Infrastructure

### Task 1: Initialize Project Structure

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `frontend/package.json`
- Create: `docker/docker-compose.yml`

**Step 1: Create backend requirements**

```txt
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-dotenv==1.0.0
pydantic==2.5.3
pydantic-settings==2.1.0
langchain==0.1.6
langchain-openai==0.0.5
openai==1.10.0
yfinance==0.2.35
chromadb==0.4.22
redis==5.0.1
httpx==0.26.0
pytest==7.4.4
pytest-asyncio==0.23.3
```

**Step 2: Create environment template**

```bash
# backend/.env.example
OPENAI_API_KEY=your_openai_api_key_here
REDIS_URL=redis://localhost:6379
TAVILY_API_KEY=your_tavily_api_key_here
LOG_LEVEL=INFO
```

**Step 3: Create frontend package.json**

```json
{
  "name": "financial-qa-frontend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "recharts": "^2.10.3"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.1",
    "vite": "^5.0.11",
    "tailwindcss": "^3.4.1",
    "autoprefixer": "^10.4.17",
    "postcss": "^8.4.33"
  }
}
```

**Step 4: Create Docker Compose configuration**

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  backend:
    build:
      context: ../backend
      dockerfile: ../docker/Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      - REDIS_URL=redis://redis:6379
    env_file:
      - ../backend/.env
    depends_on:
      - redis
    volumes:
      - ../backend:/app
      - ../data:/app/data
      - ../vectorstore:/app/vectorstore

  frontend:
    build:
      context: ../frontend
      dockerfile: ../docker/Dockerfile.frontend
    ports:
      - "5173:5173"
    volumes:
      - ../frontend:/app
      - /app/node_modules

volumes:
  redis_data:
```

**Step 5: Commit project setup**

```bash
git add backend/requirements.txt backend/.env.example backend/app/__init__.py
git add frontend/package.json docker/docker-compose.yml
git commit -m "feat: initialize project structure with dependencies and Docker config

- Add Python dependencies (FastAPI, LangChain, OpenAI, ChromaDB, Redis)
- Add React frontend with Vite and TailwindCSS
- Add Docker Compose for Redis, backend, frontend services
- Add environment template for API keys

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 2: Backend Core - Models & Configuration

### Task 2: Define Pydantic Models and Schemas

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/schemas.py`
- Create: `backend/app/models/tool_schemas.py`
- Create: `backend/app/config.py`

**Step 1: Create base schemas**

```python
# backend/app/models/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class QueryType(str, Enum):
    MARKET = "market"
    KNOWLEDGE = "knowledge"
    NEWS = "news"
    HYBRID = "hybrid"

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    query_type: QueryType
    sources: List[str]
    timestamp: datetime

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
```

**Step 2: Create tool schemas**

```python
# backend/app/models/tool_schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class MarketDataInput(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol or Chinese name")
    period: str = Field(default="7d", description="Time period: 1d, 7d, 1mo, 3mo")
    metrics: List[str] = Field(default=["price", "change_pct"], description="Metrics to retrieve")

class MarketDataOutput(BaseModel):
    ticker: str
    current_price: float
    period_change: float
    period_change_pct: float
    trend: str
    high: float
    low: float
    data_source: str
    timestamp: datetime

class RAGInput(BaseModel):
    query: str = Field(..., description="User question for knowledge retrieval")
    top_k: int = Field(default=3, description="Number of documents to retrieve")
    threshold: float = Field(default=0.7, description="Relevance threshold")

class RAGDocument(BaseModel):
    content: str
    source: str
    relevance_score: float
    category: Optional[str] = None

class RAGOutput(BaseModel):
    documents: List[RAGDocument]
    total_found: int

class WebSearchInput(BaseModel):
    query: str = Field(..., description="Search keywords")
    ticker: Optional[str] = Field(None, description="Stock ticker for context")
    date_range: str = Field(default="7d", description="Date range: 1d, 7d, 30d")
    max_results: int = Field(default=5, description="Maximum results")

class WebSearchResult(BaseModel):
    title: str
    snippet: str
    url: str
    published_date: Optional[str] = None
    source: str
    credibility_tier: int

class WebSearchOutput(BaseModel):
    results: List[WebSearchResult]
    total_results: int
    search_query: str
```

**Step 3: Create configuration management**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # API Keys
    openai_api_key: str
    tavily_api_key: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379"
    cache_ttl: int = 300  # 5 minutes

    # Application
    app_name: str = "Financial Asset QA System"
    app_version: str = "1.0.0"
    log_level: str = "INFO"

    # LLM Settings
    llm_model: str = "gpt-4"
    llm_temperature: float = 0.0
    classifier_model: str = "gpt-3.5-turbo"
    embedding_model: str = "text-embedding-3-small"

    # Tool Settings
    market_api_timeout: int = 10
    market_retry_attempts: int = 2

    # Vector Store
    chroma_persist_directory: str = "./vectorstore/chroma"

    class Config:
        env_file = ".env"
        case_sensitive = False

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

**Step 4: Commit models and config**

```bash
git add backend/app/models/ backend/app/config.py
git commit -m "feat: add Pydantic models and configuration

- Define ChatRequest/Response schemas
- Define tool input/output schemas (Market, RAG, WebSearch)
- Add Settings with environment variable management
- Add QueryType enum for classification

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 3: Services Layer

### Task 3: Implement Market Data Service

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/market_service.py`
- Create: `backend/app/services/ticker_mapper.py`
- Create: `backend/app/services/cache_service.py`
- Create: `backend/tests/test_market_service.py`

**Step 1: Write failing test for market service**

```python
# backend/tests/test_market_service.py
import pytest
from app.services.market_service import MarketService
from app.models.tool_schemas import MarketDataInput

@pytest.mark.asyncio
async def test_get_market_data_returns_valid_data():
    service = MarketService()
    input_data = MarketDataInput(ticker="AAPL", period="7d")

    result = await service.get_market_data(input_data)

    assert result.ticker == "AAPL"
    assert result.current_price > 0
    assert -50 <= result.period_change_pct <= 50
    assert result.trend in ["上涨", "下跌", "震荡"]
    assert result.data_source == "yfinance"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_market_service.py::test_get_market_data_returns_valid_data -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.market_service'"

**Step 3: Implement ticker mapper**

```python
# backend/app/services/ticker_mapper.py
from typing import Optional

TICKER_MAPPING = {
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
}

class TickerMapper:
    @staticmethod
    def normalize_ticker(ticker: str) -> str:
        """Normalize ticker symbol from Chinese name or variations."""
        ticker_lower = ticker.lower().strip()

        # Check if already a valid ticker (all uppercase letters)
        if ticker.isupper() and len(ticker) <= 5:
            return ticker

        # Try mapping
        return TICKER_MAPPING.get(ticker_lower, ticker.upper())
```

**Step 4: Implement cache service**

```python
# backend/app/services/cache_service.py
import redis
import json
from typing import Optional
from app.config import get_settings

class CacheService:
    def __init__(self):
        settings = get_settings()
        self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
        self.ttl = settings.cache_ttl

    def get(self, key: str) -> Optional[dict]:
        """Get cached data."""
        try:
            data = self.redis_client.get(key)
            return json.loads(data) if data else None
        except Exception:
            return None

    def set(self, key: str, value: dict) -> bool:
        """Set cached data with TTL."""
        try:
            self.redis_client.setex(key, self.ttl, json.dumps(value))
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """Delete cached data."""
        try:
            self.redis_client.delete(key)
            return True
        except Exception:
            return False
```

**Step 5: Implement market service**

```python
# backend/app/services/market_service.py
import yfinance as yf
from datetime import datetime, timezone
from typing import Optional
from app.models.tool_schemas import MarketDataInput, MarketDataOutput
from app.services.ticker_mapper import TickerMapper
from app.services.cache_service import CacheService
from app.config import get_settings

class MarketService:
    def __init__(self):
        self.settings = get_settings()
        self.cache = CacheService()
        self.ticker_mapper = TickerMapper()

    async def get_market_data(self, input_data: MarketDataInput) -> MarketDataOutput:
        """Fetch market data with caching."""
        # Normalize ticker
        ticker = self.ticker_mapper.normalize_ticker(input_data.ticker)

        # Check cache
        cache_key = f"market:{ticker}:{input_data.period}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return MarketDataOutput(**cached_data)

        # Fetch from yfinance
        stock = yf.Ticker(ticker)
        hist = stock.history(period=input_data.period)

        if hist.empty:
            raise ValueError(f"No data found for ticker: {ticker}")

        # Calculate metrics
        current_price = float(hist['Close'].iloc[-1])
        period_start_price = float(hist['Close'].iloc[0])
        period_change = current_price - period_start_price
        period_change_pct = (period_change / period_start_price) * 100

        # Determine trend
        if period_change_pct > 2:
            trend = "上涨"
        elif period_change_pct < -2:
            trend = "下跌"
        else:
            trend = "震荡"

        # Create output
        output = MarketDataOutput(
            ticker=ticker,
            current_price=round(current_price, 2),
            period_change=round(period_change, 2),
            period_change_pct=round(period_change_pct, 2),
            trend=trend,
            high=round(float(hist['High'].max()), 2),
            low=round(float(hist['Low'].min()), 2),
            data_source="yfinance",
            timestamp=datetime.now(timezone.utc)
        )

        # Cache result
        self.cache.set(cache_key, output.model_dump(mode='json'))

        return output
```

**Step 6: Run test to verify it passes**

Run: `cd backend && pytest tests/test_market_service.py::test_get_market_data_returns_valid_data -v`
Expected: PASS

**Step 7: Commit market service**

```bash
git add backend/app/services/ backend/tests/test_market_service.py
git commit -m "feat: implement market data service with caching

- Add TickerMapper for Chinese name to ticker conversion
- Add CacheService with Redis integration
- Add MarketService with yfinance integration
- Implement caching strategy with 5min TTL
- Add trend calculation (上涨/下跌/震荡)
- Add test for market data retrieval

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Implement RAG Service

**Files:**
- Create: `backend/app/services/rag_service.py`
- Create: `data/knowledge_base/financial_concepts/valuation_metrics.md`
- Create: `backend/tests/test_rag_service.py`

**Step 1: Create sample knowledge base content**

```markdown
# data/knowledge_base/financial_concepts/valuation_metrics.md

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
```

**Step 2: Write failing test for RAG service**

```python
# backend/tests/test_rag_service.py
import pytest
from app.services.rag_service import RAGService
from app.models.tool_schemas import RAGInput

@pytest.mark.asyncio
async def test_rag_retrieval_returns_relevant_documents():
    service = RAGService()
    await service.initialize()  # Load knowledge base

    input_data = RAGInput(query="什么是市盈率", top_k=3)

    result = await service.retrieve(input_data)

    assert result.total_found > 0
    assert len(result.documents) > 0
    assert result.documents[0].relevance_score >= 0.7
    assert "市盈率" in result.documents[0].content
```

**Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_rag_service.py::test_rag_retrieval_returns_relevant_documents -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.rag_service'"

**Step 4: Implement RAG service**

```python
# backend/app/services/rag_service.py
import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pathlib import Path
from typing import List
from app.models.tool_schemas import RAGInput, RAGOutput, RAGDocument
from app.config import get_settings

class RAGService:
    def __init__(self):
        self.settings = get_settings()
        self.embeddings = OpenAIEmbeddings(
            model=self.settings.embedding_model,
            openai_api_key=self.settings.openai_api_key
        )
        self.vectorstore = None
        self.initialized = False

    async def initialize(self):
        """Initialize vector store and load knowledge base."""
        if self.initialized:
            return

        # Create persist directory if not exists
        persist_dir = Path(self.settings.chroma_persist_directory)
        persist_dir.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB
        self.vectorstore = Chroma(
            persist_directory=str(persist_dir),
            embedding_function=self.embeddings,
            collection_name="financial_knowledge"
        )

        # Load documents if collection is empty
        if self.vectorstore._collection.count() == 0:
            await self._load_knowledge_base()

        self.initialized = True

    async def _load_knowledge_base(self):
        """Load and index knowledge base documents."""
        knowledge_base_path = Path("data/knowledge_base")

        if not knowledge_base_path.exists():
            return

        # Text splitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            length_function=len
        )

        documents = []
        metadatas = []

        # Load all markdown files
        for md_file in knowledge_base_path.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")

            # Split into chunks
            chunks = text_splitter.split_text(content)

            # Get category from path
            category = md_file.parent.name

            for chunk in chunks:
                documents.append(chunk)
                metadatas.append({
                    "source": str(md_file.relative_to(knowledge_base_path)),
                    "category": category
                })

        # Add to vector store
        if documents:
            self.vectorstore.add_texts(texts=documents, metadatas=metadatas)

    async def retrieve(self, input_data: RAGInput) -> RAGOutput:
        """Retrieve relevant documents."""
        if not self.initialized:
            await self.initialize()

        # Perform similarity search
        results = self.vectorstore.similarity_search_with_score(
            query=input_data.query,
            k=input_data.top_k
        )

        # Filter by threshold and format
        documents = []
        for doc, score in results:
            # ChromaDB returns distance, convert to similarity (1 - distance)
            relevance_score = 1 - score

            if relevance_score >= input_data.threshold:
                documents.append(RAGDocument(
                    content=doc.page_content,
                    source=doc.metadata.get("source", "unknown"),
                    relevance_score=round(relevance_score, 2),
                    category=doc.metadata.get("category")
                ))

        return RAGOutput(
            documents=documents,
            total_found=len(documents)
        )
```

**Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_rag_service.py::test_rag_retrieval_returns_relevant_documents -v`
Expected: PASS

**Step 6: Commit RAG service**

```bash
git add backend/app/services/rag_service.py backend/tests/test_rag_service.py
git add data/knowledge_base/
git commit -m "feat: implement RAG service with ChromaDB

- Add RAGService with OpenAI embeddings
- Implement document loading and chunking
- Add similarity search with relevance filtering
- Create sample financial knowledge base
- Add test for document retrieval

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Implement Web Search Service (Stub)

**Files:**
- Create: `backend/app/services/web_search_service.py`
- Create: `backend/tests/test_web_search_service.py`

**Step 1: Write failing test**

```python
# backend/tests/test_web_search_service.py
import pytest
from app.services.web_search_service import WebSearchService
from app.models.tool_schemas import WebSearchInput

@pytest.mark.asyncio
async def test_web_search_returns_results():
    service = WebSearchService()
    input_data = WebSearchInput(
        query="阿里巴巴财报",
        ticker="BABA",
        date_range="7d"
    )

    result = await service.search(input_data)

    assert result.total_results >= 0
    assert isinstance(result.results, list)
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_web_search_service.py::test_web_search_returns_results -v`
Expected: FAIL

**Step 3: Implement web search service (stub for now)**

```python
# backend/app/services/web_search_service.py
from app.models.tool_schemas import WebSearchInput, WebSearchOutput, WebSearchResult
from app.config import get_settings

class WebSearchService:
    def __init__(self):
        self.settings = get_settings()

    async def search(self, input_data: WebSearchInput) -> WebSearchOutput:
        """Search for news and events (stub implementation)."""
        # TODO: Integrate Tavily or SerpAPI
        # For now, return empty results

        enhanced_query = input_data.query
        if input_data.ticker:
            enhanced_query = f"{input_data.ticker} {input_data.query}"

        return WebSearchOutput(
            results=[],
            total_results=0,
            search_query=enhanced_query
        )
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_web_search_service.py::test_web_search_returns_results -v`
Expected: PASS

**Step 5: Commit web search stub**

```bash
git add backend/app/services/web_search_service.py backend/tests/test_web_search_service.py
git commit -m "feat: add web search service stub

- Add WebSearchService with stub implementation
- Add query enhancement with ticker context
- Add test for search functionality
- TODO: Integrate Tavily/SerpAPI in future

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 4: Query Router

### Task 6: Implement Query Classifier

**Files:**
- Create: `backend/app/routing/__init__.py`
- Create: `backend/app/routing/rules.py`
- Create: `backend/app/routing/query_classifier.py`
- Create: `backend/tests/test_query_classifier.py`

**Step 1: Write failing test**

```python
# backend/tests/test_query_classifier.py
import pytest
from app.routing.query_classifier import QueryClassifier
from app.models.schemas import QueryType

@pytest.mark.asyncio
async def test_classify_market_query():
    classifier = QueryClassifier()

    result = await classifier.classify("阿里巴巴当前股价是多少")

    assert result.query_type == QueryType.MARKET
    assert result.confidence > 0.7

@pytest.mark.asyncio
async def test_classify_knowledge_query():
    classifier = QueryClassifier()

    result = await classifier.classify("什么是市盈率")

    assert result.query_type == QueryType.KNOWLEDGE
    assert result.confidence > 0.7
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_query_classifier.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement rule-based patterns**

```python
# backend/app/routing/rules.py
from app.models.schemas import QueryType
from typing import Optional, Tuple
import re

MARKET_KEYWORDS = ["股价", "价格", "涨跌", "行情", "市值", "收盘价", "开盘价", "最高价", "最低价"]
KNOWLEDGE_KEYWORDS = ["什么是", "如何计算", "定义", "解释", "区别", "含义", "概念"]
NEWS_KEYWORDS = ["为何", "为什么", "原因", "最近", "新闻", "事件", "影响", "导致"]

TICKER_PATTERN = re.compile(r'\b[A-Z]{1,5}\b')

class RuleBasedClassifier:
    @staticmethod
    def classify(query: str) -> Optional[Tuple[QueryType, float]]:
        """Rule-based classification. Returns (QueryType, confidence) or None."""
        query_lower = query.lower()

        # Check for ticker symbols
        has_ticker = bool(TICKER_PATTERN.search(query))

        # Count keyword matches
        market_score = sum(1 for kw in MARKET_KEYWORDS if kw in query_lower)
        knowledge_score = sum(1 for kw in KNOWLEDGE_KEYWORDS if kw in query_lower)
        news_score = sum(1 for kw in NEWS_KEYWORDS if kw in query_lower)

        # Boost market score if ticker present
        if has_ticker:
            market_score += 2

        # Determine type with confidence
        max_score = max(market_score, knowledge_score, news_score)

        if max_score == 0:
            return None  # Ambiguous, use LLM fallback

        if max_score >= 2:
            confidence = 0.9
        elif max_score == 1:
            confidence = 0.75
        else:
            return None

        if market_score == max_score:
            return (QueryType.MARKET, confidence)
        elif knowledge_score == max_score:
            return (QueryType.KNOWLEDGE, confidence)
        elif news_score == max_score:
            return (QueryType.NEWS, confidence)

        return None
```

**Step 4: Implement query classifier with LLM fallback**

```python
# backend/app/routing/query_classifier.py
from pydantic import BaseModel
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from app.models.schemas import QueryType
from app.routing.rules import RuleBasedClassifier
from app.config import get_settings

class ClassificationResult(BaseModel):
    query_type: QueryType
    confidence: float
    method: str  # "rule" or "llm"

class QueryClassifier:
    def __init__(self):
        settings = get_settings()
        self.rule_classifier = RuleBasedClassifier()
        self.llm = ChatOpenAI(
            model=settings.classifier_model,
            temperature=0,
            openai_api_key=settings.openai_api_key
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a query classifier for a financial QA system.
Classify the user query into one of these types:
- MARKET: Stock prices, trends, historical data
- KNOWLEDGE: Financial concepts, definitions, calculations
- NEWS: Recent events, news analysis, reasons for price changes
- HYBRID: Requires multiple data sources

Respond with JSON: {{"type": "MARKET|KNOWLEDGE|NEWS|HYBRID", "confidence": 0.0-1.0}}"""),
            ("user", "{query}")
        ])

    async def classify(self, query: str) -> ClassificationResult:
        """Classify query using rule-based first, LLM fallback."""
        # Try rule-based first
        rule_result = self.rule_classifier.classify(query)

        if rule_result:
            query_type, confidence = rule_result
            return ClassificationResult(
                query_type=query_type,
                confidence=confidence,
                method="rule"
            )

        # Fallback to LLM
        chain = self.prompt | self.llm
        response = await chain.ainvoke({"query": query})

        # Parse LLM response (simplified)
        content = response.content.lower()

        if "market" in content:
            query_type = QueryType.MARKET
        elif "knowledge" in content:
            query_type = QueryType.KNOWLEDGE
        elif "news" in content:
            query_type = QueryType.NEWS
        else:
            query_type = QueryType.HYBRID

        return ClassificationResult(
            query_type=query_type,
            confidence=0.8,
            method="llm"
        )
```

**Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_query_classifier.py -v`
Expected: PASS

**Step 6: Commit query classifier**

```bash
git add backend/app/routing/ backend/tests/test_query_classifier.py
git commit -m "feat: implement query classifier with rule-based + LLM fallback

- Add RuleBasedClassifier with keyword matching
- Add ticker symbol detection
- Add QueryClassifier with GPT-3.5 fallback
- Implement confidence scoring
- Add tests for market and knowledge queries

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 5: LangChain Tools

### Task 7: Implement Market Data Tool

**Files:**
- Create: `backend/app/tools/__init__.py`
- Create: `backend/app/tools/market_data.py`
- Create: `backend/tests/test_market_tool.py`

**Step 1: Write failing test**

```python
# backend/tests/test_market_tool.py
import pytest
from app.tools.market_data import MarketDataTool

@pytest.mark.asyncio
async def test_market_data_tool_execution():
    tool = MarketDataTool()

    result = await tool._arun(ticker="AAPL", period="7d")

    assert "ticker" in result
    assert "current_price" in result
    assert result["ticker"] == "AAPL"
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_market_tool.py::test_market_data_tool_execution -v`
Expected: FAIL

**Step 3: Implement market data tool**

```python
# backend/app/tools/market_data.py
from langchain.tools import BaseTool
from pydantic import Field
from typing import Type, Optional
from app.models.tool_schemas import MarketDataInput, MarketDataOutput
from app.services.market_service import MarketService

class MarketDataTool(BaseTool):
    name: str = "market_data_tool"
    description: str = """Useful for getting real-time stock prices, historical data, and trend analysis.
    Input should include:
    - ticker: Stock ticker symbol (e.g., BABA, TSLA) or Chinese name (e.g., 阿里巴巴)
    - period: Time period (1d, 7d, 1mo, 3mo)

    Returns current price, period change, trend, high/low prices."""

    args_schema: Type[MarketDataInput] = MarketDataInput
    service: MarketService = Field(default_factory=MarketService)

    async def _arun(
        self,
        ticker: str,
        period: str = "7d",
        metrics: Optional[list] = None
    ) -> dict:
        """Async execution."""
        if metrics is None:
            metrics = ["price", "change_pct"]

        input_data = MarketDataInput(
            ticker=ticker,
            period=period,
            metrics=metrics
        )

        try:
            result = await self.service.get_market_data(input_data)
            return result.model_dump()
        except Exception as e:
            return {
                "error": str(e),
                "ticker": ticker,
                "data_source": "yfinance"
            }

    def _run(self, ticker: str, period: str = "7d", metrics: Optional[list] = None) -> dict:
        """Sync execution (not implemented)."""
        raise NotImplementedError("Use async version")
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_market_tool.py::test_market_data_tool_execution -v`
Expected: PASS

**Step 5: Commit market data tool**

```bash
git add backend/app/tools/market_data.py backend/tests/test_market_tool.py
git commit -m "feat: implement market data LangChain tool

- Add MarketDataTool with async execution
- Integrate with MarketService
- Add error handling for failed API calls
- Add test for tool execution

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 8: Implement RAG Tool

**Files:**
- Create: `backend/app/tools/rag_tool.py`
- Create: `backend/tests/test_rag_tool.py`

**Step 1: Write failing test**

```python
# backend/tests/test_rag_tool.py
import pytest
from app.tools.rag_tool import RAGTool

@pytest.mark.asyncio
async def test_rag_tool_execution():
    tool = RAGTool()
    await tool.service.initialize()

    result = await tool._arun(query="什么是市盈率")

    assert "documents" in result
    assert result["total_found"] >= 0
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_rag_tool.py::test_rag_tool_execution -v`
Expected: FAIL

**Step 3: Implement RAG tool**

```python
# backend/app/tools/rag_tool.py
from langchain.tools import BaseTool
from pydantic import Field
from typing import Type
from app.models.tool_schemas import RAGInput, RAGOutput
from app.services.rag_service import RAGService

class RAGTool(BaseTool):
    name: str = "rag_tool"
    description: str = """Useful for retrieving financial knowledge from the knowledge base.
    Use this for questions about:
    - Financial concepts and definitions (市盈率, 市净率, ROE)
    - Financial statement terms (收入, 净利润, 现金流)
    - Market basics (股票, 债券, 基金)

    Input should be a natural language question."""

    args_schema: Type[RAGInput] = RAGInput
    service: RAGService = Field(default_factory=RAGService)

    async def _arun(
        self,
        query: str,
        top_k: int = 3,
        threshold: float = 0.7
    ) -> dict:
        """Async execution."""
        input_data = RAGInput(
            query=query,
            top_k=top_k,
            threshold=threshold
        )

        try:
            if not self.service.initialized:
                await self.service.initialize()

            result = await self.service.retrieve(input_data)
            return result.model_dump()
        except Exception as e:
            return {
                "error": str(e),
                "documents": [],
                "total_found": 0
            }

    def _run(self, query: str, top_k: int = 3, threshold: float = 0.7) -> dict:
        """Sync execution (not implemented)."""
        raise NotImplementedError("Use async version")
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_rag_tool.py::test_rag_tool_execution -v`
Expected: PASS

**Step 5: Commit RAG tool**

```bash
git add backend/app/tools/rag_tool.py backend/tests/test_rag_tool.py
git commit -m "feat: implement RAG LangChain tool

- Add RAGTool with async execution
- Integrate with RAGService
- Add error handling for retrieval failures
- Add test for tool execution

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

### Task 9: Implement Web Search Tool (Stub)

**Files:**
- Create: `backend/app/tools/web_search.py`
- Create: `backend/tests/test_web_search_tool.py`

**Step 1: Write failing test**

```python
# backend/tests/test_web_search_tool.py
import pytest
from app.tools.web_search import WebSearchTool

@pytest.mark.asyncio
async def test_web_search_tool_execution():
    tool = WebSearchTool()

    result = await tool._arun(query="阿里巴巴财报", ticker="BABA")

    assert "results" in result
    assert "search_query" in result
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_web_search_tool.py::test_web_search_tool_execution -v`
Expected: FAIL

**Step 3: Implement web search tool**

```python
# backend/app/tools/web_search.py
from langchain.tools import BaseTool
from pydantic import Field
from typing import Type, Optional
from app.models.tool_schemas import WebSearchInput, WebSearchOutput
from app.services.web_search_service import WebSearchService

class WebSearchTool(BaseTool):
    name: str = "web_search_tool"
    description: str = """Useful for finding recent news, events, and market analysis.
    Use this for questions about:
    - Recent news affecting stock prices
    - Company announcements and earnings reports
    - Market events and their impact

    Input should include:
    - query: Search keywords
    - ticker: (optional) Stock ticker for context
    - date_range: Time range (1d, 7d, 30d)"""

    args_schema: Type[WebSearchInput] = WebSearchInput
    service: WebSearchService = Field(default_factory=WebSearchService)

    async def _arun(
        self,
        query: str,
        ticker: Optional[str] = None,
        date_range: str = "7d",
        max_results: int = 5
    ) -> dict:
        """Async execution."""
        input_data = WebSearchInput(
            query=query,
            ticker=ticker,
            date_range=date_range,
            max_results=max_results
        )

        try:
            result = await self.service.search(input_data)
            return result.model_dump()
        except Exception as e:
            return {
                "error": str(e),
                "results": [],
                "total_results": 0,
                "search_query": query
            }

    def _run(self, query: str, ticker: Optional[str] = None, date_range: str = "7d", max_results: int = 5) -> dict:
        """Sync execution (not implemented)."""
        raise NotImplementedError("Use async version")
```

**Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_web_search_tool.py::test_web_search_tool_execution -v`
Expected: PASS

**Step 5: Commit web search tool**

```bash
git add backend/app/tools/web_search.py backend/tests/test_web_search_tool.py
git commit -m "feat: implement web search LangChain tool

- Add WebSearchTool with async execution
- Integrate with WebSearchService
- Add error handling for search failures
- Add test for tool execution

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 6: LangChain Agent

### Task 10: Implement Agent Core

**Files:**
- Create: `backend/app/agent/__init__.py`
- Create: `backend/app/agent/prompts.py`
- Create: `backend/app/agent/orchestrator.py`
- Create: `backend/tests/test_agent.py`

**Step 1: Create system prompts**

```python
# backend/app/agent/prompts.py
SYSTEM_PROMPT = """你是一个专业的金融资产分析助手。

核心职责：
1. 基于可靠数据源回答金融问题
2. 区分"客观数据"与"分析性描述"
3. 明确标注信息来源
4. 不预测未来走势

核心原则：
- 永远不要编造金融数据
- 必须使用工具获取实时数据
- 数据来源必须明确标注
- 不确定时明确告知用户

数据分类：
• 客观数据（价格、涨跌幅）→ 使用 market_data_tool
• 金融知识（概念、定义）→ 使用 rag_tool
• 市场事件（新闻、原因）→ 使用 web_search_tool

回答格式（必须遵守）：

### Market Data
- Current Price: $XX.XX
- Period Change: ±X.XX%
- Trend: 上涨/下跌/震荡

### Analysis
[基于数据的分析，不要编造]

### Sources
- Market Data: Yahoo Finance
- Updated: YYYY-MM-DD HH:MM UTC

禁止行为：
✗ 预测未来股价
✗ 提供投资建议
✗ 编造数据或新闻
✗ 使用过时数据而不标注

不确定时的表述：
"根据当前可获取的数据..."
"需要注意的是，该信息可能不完整..."
"""

RESPONSE_FORMAT_REMINDER = """
Remember to format your response with clear sections:
1. Market Data (if applicable)
2. Analysis (data-driven only)
3. Sources (always include)
"""
```

**Step 2: Write failing test for agent**

```python
# backend/tests/test_agent.py
import pytest
from app.agent.orchestrator import FinancialAgent

@pytest.mark.asyncio
async def test_agent_handles_market_query():
    agent = FinancialAgent()

    response = await agent.process_query("AAPL当前股价是多少")

    assert "AAPL" in response or "苹果" in response
    assert "Market Data" in response or "价格" in response
```

**Step 3: Run test to verify it fails**

Run: `cd backend && pytest tests/test_agent.py::test_agent_handles_market_query -v`
Expected: FAIL

**Step 4: Implement agent orchestrator**

```python
# backend/app/agent/orchestrator.py
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from app.tools.market_data import MarketDataTool
from app.tools.rag_tool import RAGTool
from app.tools.web_search import WebSearchTool
from app.agent.prompts import SYSTEM_PROMPT, RESPONSE_FORMAT_REMINDER
from app.config import get_settings

class FinancialAgent:
    def __init__(self):
        settings = get_settings()

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            openai_api_key=settings.openai_api_key
        )

        # Initialize tools
        self.tools = [
            MarketDataTool(),
            RAGTool(),
            WebSearchTool()
        ]

        # Create prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
            ("system", RESPONSE_FORMAT_REMINDER)
        ])

        # Create agent
        self.agent = create_openai_functions_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )

        # Create executor
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=True,
            max_iterations=5,
            handle_parsing_errors=True
        )

    async def process_query(self, query: str, session_id: str = None) -> str:
        """Process user query and return response."""
        try:
            result = await self.executor.ainvoke({
                "input": query,
                "chat_history": []
            })

            return result["output"]
        except Exception as e:
            return f"抱歉，处理您的问题时出现错误：{str(e)}"
```

**Step 5: Run test to verify it passes**

Run: `cd backend && pytest tests/test_agent.py::test_agent_handles_market_query -v`
Expected: PASS

**Step 6: Commit agent implementation**

```bash
git add backend/app/agent/ backend/tests/test_agent.py
git commit -m "feat: implement LangChain agent orchestrator

- Add system prompts with guardrails
- Add FinancialAgent with OpenAI functions
- Integrate all three tools (Market, RAG, WebSearch)
- Add conversation memory support
- Add test for agent query processing

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 7: FastAPI Backend

### Task 11: Implement API Routes

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/routes.py`
- Create: `backend/app/api/websocket.py`
- Create: `backend/tests/test_api.py`

**Step 1: Write failing test for API**

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

def test_chat_endpoint():
    response = client.post(
        "/api/chat",
        json={"query": "什么是市盈率"}
    )
    assert response.status_code == 200
    assert "response" in response.json()
```

**Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_api.py -v`
Expected: FAIL

**Step 3: Implement API routes**

```python
# backend/app/api/routes.py
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from app.models.schemas import ChatRequest, ChatResponse, HealthResponse, QueryType
from app.agent.orchestrator import FinancialAgent
from app.routing.query_classifier import QueryClassifier
from app.config import get_settings

router = APIRouter(prefix="/api")

# Initialize services
agent = FinancialAgent()
classifier = QueryClassifier()
settings = get_settings()

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc)
    )

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process chat query."""
    try:
        # Classify query
        classification = await classifier.classify(request.query)

        # Process with agent
        response = await agent.process_query(request.query, request.session_id)

        return ChatResponse(
            response=response,
            query_type=classification.query_type,
            sources=["Yahoo Finance", "Knowledge Base"],  # TODO: Extract from agent
            timestamp=datetime.now(timezone.utc)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Step 4: Implement WebSocket handler**

```python
# backend/app/api/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.agent.orchestrator import FinancialAgent
import json

router = APIRouter()

agent = FinancialAgent()

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """WebSocket endpoint for streaming responses."""
    await websocket.accept()

    try:
        while True:
            # Receive query
            data = await websocket.receive_text()
            query_data = json.loads(data)
            query = query_data.get("query", "")

            if not query:
                continue

            # Process query (TODO: Add streaming support)
            response = await agent.process_query(query)

            # Send response
            await websocket.send_json({
                "type": "response",
                "content": response
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "content": str(e)
        })
```

**Step 5: Create main application**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router as api_router
from app.api.websocket import router as ws_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(api_router)
app.include_router(ws_router)

@app.get("/")
async def root():
    return {"message": "Financial Asset QA System API"}
```

**Step 6: Run test to verify it passes**

Run: `cd backend && pytest tests/test_api.py -v`
Expected: PASS

**Step 7: Commit API implementation**

```bash
git add backend/app/api/ backend/app/main.py backend/tests/test_api.py
git commit -m "feat: implement FastAPI backend with REST and WebSocket

- Add health check endpoint
- Add chat endpoint with query classification
- Add WebSocket handler for streaming
- Add CORS middleware for frontend
- Add tests for API endpoints

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

## Phase 8: Frontend Implementation

### Task 12: Initialize React Frontend

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/vite.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/styles/index.css`

**Step 1: Create HTML entry point**

```html
<!-- frontend/index.html -->
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Financial Asset QA System</title>
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
    host: true
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
    extend: {},
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
/* frontend/src/styles/index.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
```

```jsx
// frontend/src/main.jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles/index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

**Step 5: Create basic App component**

```jsx
// frontend/src/App.jsx
import React from 'react'

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4">
          <h1 className="text-3xl font-bold text-gray-900">
            Financial Asset QA System
          </h1>
        </div>
      </header>
      <main className="max-w-7xl mx-auto py-6 px-4">
        <p className="text-gray-600">Loading...</p>
      </main>
    </div>
  )
}

export default App
```

**Step 6: Test frontend runs**

Run: `cd frontend && npm install && npm run dev`
Expected: Frontend starts on http://localhost:5173

**Step 7: Commit frontend setup**

```bash
git add frontend/
git commit -m "feat: initialize React frontend with Vite and TailwindCSS

- Add Vite configuration
- Add TailwindCSS setup
- Add basic App component
- Add HTML entry point

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 13: Implement Chat Interface Components

**Files:**
- Create: `frontend/src/components/ChatInterface.jsx`
- Create: `frontend/src/components/MessageList.jsx`
- Create: `frontend/src/components/InputBox.jsx`
- Create: `frontend/src/services/api.js`
- Create: `frontend/src/hooks/useChat.js`

**Step 1: Create API service**

```javascript
// frontend/src/services/api.js
const API_BASE_URL = 'http://localhost:8000'

export const api = {
  async sendMessage(query) {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query }),
    })

    if (!response.ok) {
      throw new Error('Failed to send message')
    }

    return response.json()
  },

  async checkHealth() {
    const response = await fetch(`${API_BASE_URL}/api/health`)
    return response.json()
  }
}
```

**Step 2: Create chat hook**

```javascript
// frontend/src/hooks/useChat.js
import { useState } from 'react'
import { api } from '../services/api'

export function useChat() {
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const sendMessage = async (query) => {
    if (!query.trim()) return

    // Add user message
    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: query,
      timestamp: new Date()
    }
    setMessages(prev => [...prev, userMessage])

    setLoading(true)
    setError(null)

    try {
      const response = await api.sendMessage(query)

      // Add assistant message
      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response.response,
        queryType: response.query_type,
        sources: response.sources,
        timestamp: new Date(response.timestamp)
      }
      setMessages(prev => [...prev, assistantMessage])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return { messages, loading, error, sendMessage }
}
```

**Step 3: Create MessageList component**

```jsx
// frontend/src/components/MessageList.jsx
import React from 'react'

function MessageList({ messages }) {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
        >
          <div
            className={`max-w-3xl rounded-lg px-4 py-2 ${
              message.role === 'user'
                ? 'bg-blue-600 text-white'
                : 'bg-white border border-gray-200'
            }`}
          >
            <div className="whitespace-pre-wrap">{message.content}</div>
            {message.sources && (
              <div className="mt-2 text-xs opacity-75">
                Sources: {message.sources.join(', ')}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

export default MessageList
```

**Step 4: Create InputBox component**

```jsx
// frontend/src/components/InputBox.jsx
import React, { useState } from 'react'

function InputBox({ onSend, disabled }) {
  const [input, setInput] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (input.trim() && !disabled) {
      onSend(input)
      setInput('')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="border-t border-gray-200 p-4">
      <div className="flex space-x-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about stocks, financial concepts, or market news..."
          disabled={disabled}
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
        />
        <button
          type="submit"
          disabled={disabled || !input.trim()}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
        >
          Send
        </button>
      </div>
    </form>
  )
}

export default InputBox
```

**Step 5: Create ChatInterface component**

```jsx
// frontend/src/components/ChatInterface.jsx
import React from 'react'
import MessageList from './MessageList'
import InputBox from './InputBox'
import { useChat } from '../hooks/useChat'

function ChatInterface() {
  const { messages, loading, error, sendMessage } = useChat()

  return (
    <div className="flex flex-col h-[calc(100vh-200px)] bg-gray-50 rounded-lg shadow-lg">
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          Error: {error}
        </div>
      )}

      <MessageList messages={messages} />

      {loading && (
        <div className="px-4 py-2 text-gray-500 text-sm">
          Thinking...
        </div>
      )}

      <InputBox onSend={sendMessage} disabled={loading} />
    </div>
  )
}

export default ChatInterface
```

**Step 6: Update App to use ChatInterface**

```jsx
// frontend/src/App.jsx
import React from 'react'
import ChatInterface from './components/ChatInterface'

function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4">
          <h1 className="text-3xl font-bold text-gray-900">
            Financial Asset QA System
          </h1>
          <p className="mt-2 text-sm text-gray-600">
            Ask about stock prices, financial concepts, or market news
          </p>
        </div>
      </header>
      <main className="max-w-7xl mx-auto py-6 px-4">
        <ChatInterface />
      </main>
    </div>
  )
}

export default App
```

**Step 7: Test frontend with backend**

Run: `cd frontend && npm run dev` (in one terminal)
Run: `cd backend && uvicorn app.main:app --reload` (in another terminal)
Expected: Chat interface works with backend

**Step 8: Commit chat interface**

```bash
git add frontend/src/
git commit -m "feat: implement chat interface components

- Add ChatInterface with message display
- Add MessageList for rendering messages
- Add InputBox for user input
- Add useChat hook for state management
- Add API service for backend communication

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 9: Docker & Deployment

### Task 14: Create Dockerfiles

**Files:**
- Create: `docker/Dockerfile.backend`
- Create: `docker/Dockerfile.frontend`
- Create: `.dockerignore`

**Step 1: Create backend Dockerfile**

```dockerfile
# docker/Dockerfile.backend
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/app ./app
COPY data ./data
COPY vectorstore ./vectorstore

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Step 2: Create frontend Dockerfile**

```dockerfile
# docker/Dockerfile.frontend
FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY frontend/package*.json ./
RUN npm install

# Copy application
COPY frontend/ .

# Expose port
EXPOSE 5173

# Run development server
CMD ["npm", "run", "dev", "--", "--host"]
```

**Step 3: Create .dockerignore**

```
# .dockerignore
**/__pycache__
**/*.pyc
**/.pytest_cache
**/node_modules
**/.git
**/.env
**/venv
**/.venv
```

**Step 4: Test Docker build**

Run: `docker-compose -f docker/docker-compose.yml up --build`
Expected: All services start successfully

**Step 5: Commit Docker configuration**

```bash
git add docker/Dockerfile.backend docker/Dockerfile.frontend .dockerignore
git commit -m "feat: add Docker configuration for deployment

- Add backend Dockerfile with Python 3.11
- Add frontend Dockerfile with Node 18
- Add .dockerignore for build optimization
- Update docker-compose.yml paths

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 10: Documentation & Testing

### Task 15: Create README and Documentation

**Files:**
- Create: `README.md`
- Create: `docs/ARCHITECTURE.md`
- Create: `docs/API.md`

**Step 1: Create README**

```markdown
# Financial Asset QA System

A production-grade AI system for financial asset Q&A with real-time market data, knowledge retrieval (RAG), and news integration.

## Features

- **Real-time Market Data**: Stock prices, trends, historical analysis
- **Financial Knowledge**: RAG-based Q&A for financial concepts
- **News Integration**: Recent events and market analysis
- **Multi-source Reasoning**: Combines data from multiple sources
- **Streaming Responses**: Real-time response generation

## Architecture

```
Frontend (React + Vite) → API (FastAPI) → Query Router → LangChain Agent
                                                ↓
                                    ┌───────────┼───────────┐
                                    ↓           ↓           ↓
                              Market Data    RAG Tool   Web Search
                              (yfinance)   (ChromaDB)   (Tavily)
```

## Tech Stack

**Backend:**
- Python 3.11+
- FastAPI
- LangChain
- OpenAI GPT-4
- ChromaDB
- Redis

**Frontend:**
- React 18
- Vite
- TailwindCSS

**Infrastructure:**
- Docker Compose
- Redis for caching

## Quick Start

### Prerequisites

- Docker & Docker Compose
- OpenAI API key

### Setup

1. Clone repository:
```bash
git clone <repo-url>
cd Financial_Asset_QA_System
```

2. Create environment file:
```bash
cp backend/.env.example backend/.env
# Edit backend/.env and add your OPENAI_API_KEY
```

3. Start services:
```bash
docker-compose -f docker/docker-compose.yml up --build
```

4. Access application:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Run Tests

```bash
cd backend
pytest
```

## Example Queries

- "阿里巴巴当前股价是多少？"
- "BABA 最近 7 天涨跌情况如何？"
- "什么是市盈率？"
- "特斯拉近期走势如何？"

## Project Structure

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## License

MIT
```

**Step 2: Commit documentation**

```bash
git add README.md docs/
git commit -m "docs: add README and architecture documentation

- Add comprehensive README with setup instructions
- Add example queries
- Add architecture overview
- Add development guide

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Summary

This implementation plan covers:

1. ✅ Project setup with dependencies
2. ✅ Backend models and configuration
3. ✅ Services layer (Market, RAG, WebSearch)
4. ✅ Query router with classification
5. ✅ LangChain tools integration
6. ✅ Agent orchestrator
7. ✅ FastAPI backend with REST + WebSocket
8. ✅ React frontend with chat interface
9. ✅ Docker deployment
10. ✅ Documentation

**Next Steps:**
- Execute this plan task-by-task
- Add evaluation framework
- Integrate Tavily for web search
- Add monitoring and logging
- Deploy to production

---

**Plan Status:** Ready for Execution
**Estimated Time:** 2-3 days for core implementation
**Testing Strategy:** TDD with pytest for backend, manual testing for frontend

