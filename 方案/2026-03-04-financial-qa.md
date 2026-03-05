# Financial QA System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a full-stack financial asset Q&A system with real-time market data, RAG-based knowledge retrieval, and Claude-powered structured analysis.

**Architecture:** FastAPI backend with Claude Tool Use for market queries (yfinance) and ChromaDB RAG for financial knowledge. Intent router classifies queries before dispatch. React + Vite frontend with SSE streaming.

**Tech Stack:** Python 3.11+, FastAPI, Anthropic SDK, yfinance, ChromaDB, sentence-transformers, React 18, Vite, Recharts, TypeScript

---

## Task 1: Project Structure & Dependencies

**Files:**
- Create: `financial-qa-system/backend/requirements.txt`
- Create: `financial-qa-system/frontend/` (via Vite scaffold)
- Create: `financial-qa-system/.env.example`
- Create: `financial-qa-system/.gitignore`

**Step 1: Create root project directory**

```bash
mkdir financial-qa-system
cd financial-qa-system
git init
```

**Step 2: Create backend requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
anthropic==0.40.0
yfinance==0.2.50
chromadb==0.5.0
sentence-transformers==3.0.0
python-dotenv==1.0.0
httpx==0.27.0
pydantic==2.9.0
```

Save to `backend/requirements.txt`.

**Step 3: Create .env.example**

```
ANTHROPIC_API_KEY=your_key_here
```

Save to `.env.example`. Copy to `.env` and fill in your key.

**Step 4: Create .gitignore**

```
.env
__pycache__/
*.pyc
.chroma/
node_modules/
dist/
.venv/
```

**Step 5: Install backend dependencies**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Step 6: Scaffold frontend**

```bash
cd ..
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install recharts axios
npm install -D @types/recharts
```

**Step 7: Commit**

```bash
git add .
git commit -m "feat: project structure and dependencies"
```

---

## Task 2: FastAPI Backend Foundation

**Files:**
- Create: `backend/main.py`
- Create: `backend/routers/__init__.py`
- Create: `backend/routers/chat.py`
- Create: `backend/tests/test_main.py`

**Step 1: Write failing test**

Create `backend/tests/test_main.py`:

```python
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

**Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_main.py::test_health -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'main'`

**Step 3: Create main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import chat

app = FastAPI(title="Financial QA System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")

@app.get("/health")
def health():
    return {"status": "ok"}
```

**Step 4: Create routers/__init__.py** (empty file)

**Step 5: Create routers/chat.py** (stub)

```python
from fastapi import APIRouter

router = APIRouter()

@router.post("/chat")
async def chat(body: dict):
    return {"reply": "stub"}
```

**Step 6: Run test to verify it passes**

```bash
pytest tests/test_main.py::test_health -v
```
Expected: PASS

**Step 7: Verify server starts**

```bash
uvicorn main:app --reload --port 8000
```
Visit `http://localhost:8000/health` — should return `{"status":"ok"}`

**Step 8: Commit**

```bash
git add backend/
git commit -m "feat: fastapi foundation with health endpoint"
```

---

## Task 3: Market Tools Module (yfinance)

**Files:**
- Create: `backend/agent/market_tools.py`
- Create: `backend/agent/__init__.py`
- Create: `backend/tests/test_market_tools.py`

**Step 1: Write failing tests**

Create `backend/tests/test_market_tools.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.market_tools import get_current_price, get_price_history, calc_price_change, get_stock_info

def test_get_current_price_returns_dict():
    result = get_current_price("AAPL")
    assert isinstance(result, dict)
    assert "symbol" in result
    assert "price" in result
    assert "currency" in result

def test_get_price_history_returns_list():
    result = get_price_history("AAPL", days=7)
    assert isinstance(result, list)
    assert len(result) > 0
    assert "date" in result[0]
    assert "close" in result[0]

def test_calc_price_change_returns_dict():
    result = calc_price_change("AAPL", days=7)
    assert isinstance(result, dict)
    assert "change_pct" in result
    assert "trend" in result  # "上涨" / "下跌" / "震荡"

def test_unknown_symbol_returns_error():
    result = get_current_price("INVALID_TICKER_XYZ")
    assert result.get("error") is not None
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_market_tools.py -v
```
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Create agent/__init__.py** (empty)

**Step 4: Create agent/market_tools.py**

```python
import yfinance as yf
from datetime import datetime, timedelta

def get_current_price(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is None:
            hist = ticker.history(period="1d")
            if hist.empty:
                return {"error": f"无法获取 {symbol} 的价格数据"}
            price = float(hist["Close"].iloc[-1])
        return {
            "symbol": symbol,
            "price": round(float(price), 2),
            "currency": info.get("currency", "USD"),
            "name": info.get("longName") or info.get("shortName", symbol),
        }
    except Exception as e:
        return {"error": str(e)}


def get_price_history(symbol: str, days: int = 30) -> list:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=f"{days}d")
        if hist.empty:
            return [{"error": f"无法获取 {symbol} 的历史数据"}]
        result = []
        for date, row in hist.iterrows():
            result.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return result
    except Exception as e:
        return [{"error": str(e)}]


def calc_price_change(symbol: str, days: int = 7) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=f"{days + 5}d")
        if len(hist) < 2:
            return {"error": "数据不足以计算涨跌幅"}
        hist = hist.tail(days)
        start_price = float(hist["Close"].iloc[0])
        end_price = float(hist["Close"].iloc[-1])
        change_pct = round((end_price - start_price) / start_price * 100, 2)
        if change_pct > 2:
            trend = "上涨"
        elif change_pct < -2:
            trend = "下跌"
        else:
            trend = "震荡"
        return {
            "symbol": symbol,
            "days": days,
            "start_price": round(start_price, 2),
            "end_price": round(end_price, 2),
            "change_pct": change_pct,
            "trend": trend,
        }
    except Exception as e:
        return {"error": str(e)}


def get_stock_info(symbol: str) -> dict:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return {
            "symbol": symbol,
            "name": info.get("longName") or info.get("shortName", symbol),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE"),
            "52w_high": info.get("fiftyTwoWeekHigh"),
            "52w_low": info.get("fiftyTwoWeekLow"),
            "description": (info.get("longBusinessSummary") or "")[:300],
        }
    except Exception as e:
        return {"error": str(e)}


def get_news(symbol: str, limit: int = 5) -> list:
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news or []
        return [
            {
                "title": item.get("content", {}).get("title") or item.get("title", ""),
                "summary": (item.get("content", {}).get("summary") or item.get("summary", ""))[:200],
                "published": item.get("content", {}).get("pubDate") or item.get("providerPublishTime", ""),
            }
            for item in news[:limit]
        ]
    except Exception as e:
        return [{"error": str(e)}]
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/test_market_tools.py -v
```
Expected: PASS (requires network access to Yahoo Finance)

**Step 6: Commit**

```bash
git add backend/agent/
git add backend/tests/test_market_tools.py
git commit -m "feat: yfinance market tools module"
```

---

## Task 4: Claude Tool Definitions

**Files:**
- Create: `backend/agent/tool_definitions.py`
- Create: `backend/tests/test_tool_definitions.py`

**Step 1: Write failing test**

Create `backend/tests/test_tool_definitions.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.tool_definitions import TOOLS

def test_tools_is_list():
    assert isinstance(TOOLS, list)
    assert len(TOOLS) >= 4

def test_each_tool_has_required_fields():
    for tool in TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_tool_definitions.py -v
```

**Step 3: Create agent/tool_definitions.py**

```python
TOOLS = [
    {
        "name": "get_current_price",
        "description": "获取股票/加密货币的当前价格。使用标准代码如 AAPL, BABA, BTC-USD, 0700.HK",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "股票代码，如 AAPL, BABA, 600519.SS"}
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_price_history",
        "description": "获取股票 N 天的历史价格数据（每日开高低收成交量）",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "股票代码"},
                "days": {"type": "integer", "description": "天数，默认30", "default": 30},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "calc_price_change",
        "description": "计算股票在指定天数内的涨跌幅，并判断趋势（上涨/下跌/震荡）",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "股票代码"},
                "days": {"type": "integer", "description": "统计天数，如 7, 30", "default": 7},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_stock_info",
        "description": "获取公司基本信息：行业、市值、市盈率、52周高低等",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "股票代码"},
            },
            "required": ["symbol"],
        },
    },
    {
        "name": "get_news",
        "description": "获取与股票相关的最新新闻，用于分析涨跌原因",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "股票代码"},
                "limit": {"type": "integer", "description": "新闻条数，默认5", "default": 5},
            },
            "required": ["symbol"],
        },
    },
]
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_tool_definitions.py -v
```

**Step 5: Commit**

```bash
git add backend/agent/tool_definitions.py backend/tests/test_tool_definitions.py
git commit -m "feat: claude tool definitions for market data"
```

---

## Task 5: Intent Router

**Files:**
- Create: `backend/agent/intent_router.py`
- Create: `backend/tests/test_intent_router.py`

**Step 1: Write failing tests**

Create `backend/tests/test_intent_router.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.intent_router import classify_intent, IntentType

def test_market_query_price():
    result = classify_intent("阿里巴巴当前股价是多少？")
    assert result == IntentType.MARKET_QUERY

def test_knowledge_query():
    result = classify_intent("什么是市盈率？")
    assert result == IntentType.KNOWLEDGE_QA

def test_mixed_query():
    result = classify_intent("阿里巴巴1月15日为何大涨？")
    assert result in (IntentType.MIXED, IntentType.MARKET_QUERY)

def test_returns_valid_intent_type():
    result = classify_intent("特斯拉近期走势如何？")
    assert isinstance(result, IntentType)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_intent_router.py -v
```

**Step 3: Create agent/intent_router.py**

```python
import os
import anthropic
from enum import Enum
from dotenv import load_dotenv

load_dotenv()


class IntentType(str, Enum):
    MARKET_QUERY = "MARKET_QUERY"
    KNOWLEDGE_QA = "KNOWLEDGE_QA"
    MIXED = "MIXED"


_client = None

def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


CLASSIFY_PROMPT = """判断以下用户问题属于哪类意图，只回答分类标签，不要解释。

分类规则：
- MARKET_QUERY：涉及具体资产的当前价格、涨跌幅、历史走势、基本行情数据
- KNOWLEDGE_QA：金融概念解释、财务术语、通用金融知识、财报分析方法
- MIXED：既需要实时行情数据，又需要背景分析（如"某股为何大涨"、"某股财报与走势"）

只回答：MARKET_QUERY 或 KNOWLEDGE_QA 或 MIXED

用户问题：{question}"""


def classify_intent(question: str) -> IntentType:
    client = _get_client()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
        messages=[{"role": "user", "content": CLASSIFY_PROMPT.format(question=question)}],
    )
    text = response.content[0].text.strip().upper()
    if "MARKET" in text:
        return IntentType.MARKET_QUERY
    elif "KNOWLEDGE" in text:
        return IntentType.KNOWLEDGE_QA
    elif "MIXED" in text:
        return IntentType.MIXED
    return IntentType.MARKET_QUERY  # default
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_intent_router.py -v
```
Expected: PASS (requires ANTHROPIC_API_KEY in .env)

**Step 5: Commit**

```bash
git add backend/agent/intent_router.py backend/tests/test_intent_router.py
git commit -m "feat: claude-based intent router"
```

---

## Task 6: Agent Core (Claude Tool Use)

**Files:**
- Create: `backend/agent/agent_core.py`
- Create: `backend/tests/test_agent_core.py`

**Step 1: Write failing test**

Create `backend/tests/test_agent_core.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from agent.agent_core import run_market_agent

def test_market_agent_returns_string():
    result = run_market_agent("苹果公司当前股价是多少？")
    assert isinstance(result, str)
    assert len(result) > 50

def test_market_agent_contains_data():
    result = run_market_agent("AAPL 最近7天涨跌幅？")
    assert any(char.isdigit() for char in result)
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_agent_core.py -v
```

**Step 3: Create agent/agent_core.py**

```python
import os
import json
import anthropic
from dotenv import load_dotenv
from agent.tool_definitions import TOOLS
from agent import market_tools

load_dotenv()

SYSTEM_PROMPT = """你是一个专业的金融资产分析助手。

规则（必须严格遵守）：
1. 所有价格数字必须来自工具调用结果，严禁凭记忆生成任何价格或涨跌幅数据
2. 使用工具获取数据后，用以下结构组织回答：
   📊 **数据摘要**（客观数据，标注数据来源）
   📈 **趋势分析**（上涨/下跌/震荡，附简要说明）
   🔍 **影响因素**（基于新闻/事件，明确标注"分析"）
   ⚠️ **风险提示**（本内容不构成投资建议）
3. 若工具返回 error 字段，告知用户数据不可用，不得编造
4. 不对未来走势做预测
5. 回答使用中文"""


def _dispatch_tool(tool_name: str, tool_input: dict):
    fn_map = {
        "get_current_price": market_tools.get_current_price,
        "get_price_history": market_tools.get_price_history,
        "calc_price_change": market_tools.calc_price_change,
        "get_stock_info": market_tools.get_stock_info,
        "get_news": market_tools.get_news,
    }
    fn = fn_map.get(tool_name)
    if fn is None:
        return {"error": f"未知工具: {tool_name}"}
    return fn(**tool_input)


def run_market_agent(question: str) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    messages = [{"role": "user", "content": question}]

    for _ in range(5):  # max 5 tool call rounds
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return "无法生成回答"

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = _dispatch_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
            messages.append({"role": "user", "content": tool_results})

    return "工具调用超出限制，请重试"


async def stream_market_agent(question: str):
    """Async generator for SSE streaming."""
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    messages = [{"role": "user", "content": question}]

    for _ in range(5):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    yield block.text
            return

        if response.stop_reason == "tool_use":
            yield "[TOOL_CALLING]"
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = _dispatch_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
            messages.append({"role": "user", "content": tool_results})
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_agent_core.py -v
```
Expected: PASS (requires API key and network)

**Step 5: Commit**

```bash
git add backend/agent/agent_core.py backend/tests/test_agent_core.py
git commit -m "feat: claude tool-use agent core with streaming support"
```

---

## Task 7: RAG - Knowledge Base & Embeddings

**Files:**
- Create: `backend/rag/__init__.py`
- Create: `backend/rag/knowledge_base.py`
- Create: `backend/rag/embeddings.py`
- Create: `backend/data/knowledge/financial_basics.md`
- Create: `backend/tests/test_rag.py`

**Step 1: Create financial knowledge document**

Create `backend/data/knowledge/financial_basics.md`:

```markdown
# 金融基础知识库

## 市盈率（PE Ratio / Price-to-Earnings Ratio）
市盈率是股票价格与每股收益的比率，公式为：市盈率 = 股价 / 每股收益（EPS）。
市盈率反映投资者愿意为每元利润支付多少价格。
- 市盈率越低，通常表示股票估值较低（但需结合行业比较）
- 成长型公司市盈率通常较高，价值型公司较低
- 市盈率为负表示公司亏损

## 收入与净利润的区别
- **收入（Revenue）**：公司通过销售产品或服务获得的总金额，也称营业收入或营收。是损益表的第一行（"顶线"）。
- **净利润（Net Income/Net Profit）**：收入减去所有成本（包括运营成本、税费、利息等）后的剩余金额，是损益表的最后一行（"底线"）。
- **毛利润（Gross Profit）**：收入减去直接生产成本（COGS）后的金额。
- 公式：净利润 = 收入 - 成本 - 费用 - 利息 - 税费

## 市净率（P/B Ratio）
市净率 = 股价 / 每股净资产（账面价值）。
反映市场对公司资产的估值倍数。市净率 < 1 可能意味着股票被低估，但也可能反映公司经营问题。

## EPS（每股收益）
EPS = 净利润 / 总股本。衡量公司每股创造的利润，是评估盈利能力的重要指标。

## ROE（净资产收益率）
ROE = 净利润 / 股东权益。衡量公司利用股东资金创造利润的效率，ROE > 15% 通常被视为优秀。

## 财报季度与类型
- **季报（10-Q）**：美股上市公司每季度披露，包含财务报表和经营讨论。
- **年报（10-K）**：每年披露，更详细的财务数据和风险因素。
- **A股**：中报（半年报）、年报、一季报、三季报。

## 股息与分红
股息是公司将部分利润分配给股东的形式。
- **股息率**：年股息 / 股价，反映持股的现金回报率。
- **派息比例（Payout Ratio）**：股息 / 净利润，反映公司分红意愿。

## 技术分析基础
- **支撑位**：价格反复触及但未跌破的低点，买盘聚集处。
- **阻力位**：价格反复触及但未突破的高点，卖盘聚集处。
- **均线（MA）**：过去 N 日收盘价的平均值，如 MA5、MA20、MA200。
- **成交量**：衡量市场活跃度，量价配合是重要信号。
```

**Step 2: Write failing test**

Create `backend/tests/test_rag.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from rag.knowledge_base import load_and_chunk_documents
from rag.embeddings import get_embedder

def test_load_and_chunk_returns_list():
    docs = load_and_chunk_documents("data/knowledge")
    assert isinstance(docs, list)
    assert len(docs) > 0

def test_chunk_has_required_fields():
    docs = load_and_chunk_documents("data/knowledge")
    for doc in docs:
        assert "text" in doc
        assert "source" in doc

def test_embedder_returns_vector():
    embedder = get_embedder()
    vector = embedder.encode("什么是市盈率？")
    assert len(vector) > 0
```

**Step 3: Run tests to verify they fail**

```bash
pytest tests/test_rag.py -v
```

**Step 4: Create rag/__init__.py** (empty)

**Step 5: Create rag/knowledge_base.py**

```python
import os
from pathlib import Path

def load_and_chunk_documents(data_dir: str, chunk_size: int = 512, overlap: int = 50) -> list[dict]:
    docs = []
    data_path = Path(data_dir)
    for file_path in data_path.rglob("*.md"):
        text = file_path.read_text(encoding="utf-8")
        chunks = _chunk_text(text, chunk_size, overlap)
        for i, chunk in enumerate(chunks):
            docs.append({
                "text": chunk,
                "source": str(file_path),
                "chunk_id": i,
            })
    return docs


def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    # Split by double newline (paragraphs) first
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) <= chunk_size:
            current += ("\n\n" if current else "") + para
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks
```

**Step 6: Create rag/embeddings.py**

```python
from sentence_transformers import SentenceTransformer

_model = None

def get_embedder(model_name: str = "BAAI/bge-small-zh-v1.5"):
    global _model
    if _model is None:
        _model = SentenceTransformer(model_name)
    return _model
```

Note: `BAAI/bge-small-zh-v1.5` is a lightweight Chinese embedding model. It will be downloaded on first run (~90MB).

**Step 7: Run tests to verify they pass**

```bash
pytest tests/test_rag.py -v
```
Expected: PASS (first run downloads embedding model)

**Step 8: Commit**

```bash
git add backend/rag/ backend/data/ backend/tests/test_rag.py
git commit -m "feat: rag knowledge base and embedding module"
```

---

## Task 8: RAG - ChromaDB Retriever

**Files:**
- Create: `backend/rag/retriever.py`
- Modify: `backend/tests/test_rag.py`

**Step 1: Add retriever test**

Append to `backend/tests/test_rag.py`:

```python
from rag.retriever import RAGRetriever

def test_retriever_indexes_and_searches():
    retriever = RAGRetriever(collection_name="test_collection")
    retriever.index_documents("data/knowledge")
    results = retriever.search("什么是市盈率？", top_k=2)
    assert isinstance(results, list)
    assert len(results) > 0
    assert "text" in results[0]
    assert "score" in results[0]
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_rag.py::test_retriever_indexes_and_searches -v
```

**Step 3: Create rag/retriever.py**

```python
import chromadb
from chromadb.config import Settings
from rag.knowledge_base import load_and_chunk_documents
from rag.embeddings import get_embedder


class RAGRetriever:
    def __init__(self, collection_name: str = "financial_knowledge", persist_dir: str = ".chroma"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self.embedder = get_embedder()

    def index_documents(self, data_dir: str, force_reindex: bool = False):
        if self.collection.count() > 0 and not force_reindex:
            return  # already indexed
        docs = load_and_chunk_documents(data_dir)
        if not docs:
            return
        texts = [d["text"] for d in docs]
        embeddings = self.embedder.encode(texts).tolist()
        self.collection.upsert(
            ids=[f"{d['source']}_{d['chunk_id']}" for d in docs],
            embeddings=embeddings,
            documents=texts,
            metadatas=[{"source": d["source"]} for d in docs],
        )

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        query_embedding = self.embedder.encode([query]).tolist()
        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=min(top_k, self.collection.count() or 1),
        )
        output = []
        for i, doc in enumerate(results["documents"][0]):
            output.append({
                "text": doc,
                "source": results["metadatas"][0][i].get("source", ""),
                "score": 1 - results["distances"][0][i],  # cosine similarity
            })
        return output
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_rag.py -v
```
Expected: All PASS

**Step 5: Commit**

```bash
git add backend/rag/retriever.py backend/tests/test_rag.py
git commit -m "feat: chromadb vector retriever with persistent storage"
```

---

## Task 9: RAG Agent & Chat API Endpoint

**Files:**
- Create: `backend/agent/rag_agent.py`
- Modify: `backend/routers/chat.py`
- Create: `backend/tests/test_chat_api.py`

**Step 1: Create rag_agent.py**

```python
import os
import anthropic
from dotenv import load_dotenv
from rag.retriever import RAGRetriever

load_dotenv()

RAG_SYSTEM_PROMPT = """你是一个专业的金融知识助手。

规则：
1. 基于提供的参考资料回答问题
2. 如果参考资料中有相关内容，优先使用并标注"来源：知识库"
3. 如果参考资料不足，可以补充通用知识，但需标注"来源：模型知识"
4. 回答要结构清晰、专业准确
5. 回答使用中文"""

_retriever = None

def get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever()
        _retriever.index_documents("data/knowledge")
    return _retriever


def run_rag_agent(question: str) -> str:
    retriever = get_retriever()
    results = retriever.search(question, top_k=3)
    context = "\n\n".join([f"[参考{i+1}] {r['text']}" for i, r in enumerate(results)])
    prompt = f"""参考资料：
{context}

用户问题：{question}

请基于以上参考资料回答问题。"""

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=RAG_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
```

**Step 2: Write failing API test**

Create `backend/tests/test_chat_api.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_chat_endpoint_exists():
    response = client.post("/api/chat", json={"message": "什么是市盈率？"})
    assert response.status_code == 200

def test_chat_response_has_reply():
    response = client.post("/api/chat", json={"message": "什么是市盈率？"})
    data = response.json()
    assert "reply" in data
    assert len(data["reply"]) > 10
```

**Step 3: Run test to verify it fails (stub returns minimal reply)**

```bash
pytest tests/test_chat_api.py::test_chat_response_has_reply -v
```

**Step 4: Update routers/chat.py with full logic**

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
from agent.intent_router import classify_intent, IntentType
from agent.agent_core import run_market_agent, stream_market_agent
from agent.rag_agent import run_rag_agent

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
async def chat(body: ChatRequest):
    intent = classify_intent(body.message)
    if intent == IntentType.KNOWLEDGE_QA:
        reply = run_rag_agent(body.message)
    else:
        reply = run_market_agent(body.message)
    return {"reply": reply, "intent": intent.value}


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest):
    intent = classify_intent(body.message)

    async def event_generator():
        yield f"data: {json.dumps({'type': 'intent', 'value': intent.value}, ensure_ascii=False)}\n\n"
        if intent == IntentType.KNOWLEDGE_QA:
            reply = run_rag_agent(body.message)
            yield f"data: {json.dumps({'type': 'chunk', 'value': reply}, ensure_ascii=False)}\n\n"
        else:
            async for chunk in stream_market_agent(body.message):
                yield f"data: {json.dumps({'type': 'chunk', 'value': chunk}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/test_chat_api.py -v
```
Expected: PASS

**Step 6: Commit**

```bash
git add backend/agent/rag_agent.py backend/routers/chat.py backend/tests/test_chat_api.py
git commit -m "feat: rag agent and full chat api endpoint with streaming"
```

---

## Task 10: Frontend - Chat Interface

**Files:**
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api/chat.ts`
- Create: `frontend/src/components/ChatWindow.tsx`
- Create: `frontend/src/components/MessageBubble.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/index.css`

**Step 1: Create types.ts**

```typescript
// frontend/src/types.ts
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  intent?: 'MARKET_QUERY' | 'KNOWLEDGE_QA' | 'MIXED';
  loading?: boolean;
}
```

**Step 2: Create api/chat.ts**

```typescript
// frontend/src/api/chat.ts
const API_BASE = 'http://localhost:8000/api';

export async function sendMessage(message: string): Promise<{ reply: string; intent: string }> {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) throw new Error('API error');
  return res.json();
}
```

**Step 3: Create components/MessageBubble.tsx**

```tsx
// frontend/src/components/MessageBubble.tsx
import { Message } from '../types';

const INTENT_BADGE: Record<string, string> = {
  MARKET_QUERY: '📊 行情查询',
  KNOWLEDGE_QA: '📚 知识问答',
  MIXED: '🔍 综合分析',
};

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user';
  return (
    <div style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start', marginBottom: 12 }}>
      <div style={{
        maxWidth: '75%',
        padding: '10px 14px',
        borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
        background: isUser ? '#1677ff' : '#f0f0f0',
        color: isUser ? '#fff' : '#000',
      }}>
        {!isUser && message.intent && (
          <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>
            {INTENT_BADGE[message.intent]}
          </div>
        )}
        {message.loading ? (
          <span>分析中...</span>
        ) : (
          <pre style={{ margin: 0, fontFamily: 'inherit', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {message.content}
          </pre>
        )}
      </div>
    </div>
  );
}
```

**Step 4: Create components/ChatWindow.tsx**

```tsx
// frontend/src/components/ChatWindow.tsx
import { useState, useRef, useEffect } from 'react';
import { Message } from '../types';
import { MessageBubble } from './MessageBubble';
import { sendMessage } from '../api/chat';

const SUGGESTIONS = [
  '阿里巴巴当前股价是多少？',
  'AAPL 最近7天涨跌情况如何？',
  '什么是市盈率？',
  '特斯拉近期走势如何？',
];

export function ChatWindow() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (text?: string) => {
    const question = text || input.trim();
    if (!question || loading) return;
    setInput('');
    const userMsg: Message = { id: Date.now().toString(), role: 'user', content: question };
    const loadingMsg: Message = { id: Date.now().toString() + '_ai', role: 'assistant', content: '', loading: true };
    setMessages(prev => [...prev, userMsg, loadingMsg]);
    setLoading(true);
    try {
      const { reply, intent } = await sendMessage(question);
      setMessages(prev => prev.map(m =>
        m.id === loadingMsg.id ? { ...m, content: reply, intent: intent as any, loading: false } : m
      ));
    } catch {
      setMessages(prev => prev.map(m =>
        m.id === loadingMsg.id ? { ...m, content: '请求失败，请检查后端服务是否启动。', loading: false } : m
      ));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', maxWidth: 800, margin: '0 auto' }}>
      <div style={{ padding: '16px 20px', borderBottom: '1px solid #eee', background: '#fff' }}>
        <h2 style={{ margin: 0 }}>📈 金融资产问答系统</h2>
        <p style={{ margin: '4px 0 0', color: '#888', fontSize: 13 }}>基于 Claude AI · 实时行情 · RAG 知识库</p>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 20, background: '#fafafa' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', paddingTop: 60 }}>
            <p style={{ color: '#888', marginBottom: 16 }}>你可以问我：</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
              {SUGGESTIONS.map(s => (
                <button key={s} onClick={() => handleSend(s)}
                  style={{ padding: '6px 12px', borderRadius: 20, border: '1px solid #1677ff', background: '#fff', color: '#1677ff', cursor: 'pointer', fontSize: 13 }}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map(m => <MessageBubble key={m.id} message={m} />)}
        <div ref={bottomRef} />
      </div>

      <div style={{ padding: '12px 16px', borderTop: '1px solid #eee', background: '#fff', display: 'flex', gap: 8 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder="输入股票名称或金融问题..."
          style={{ flex: 1, padding: '10px 14px', borderRadius: 24, border: '1px solid #ddd', fontSize: 14, outline: 'none' }}
          disabled={loading}
        />
        <button onClick={() => handleSend()}
          disabled={loading || !input.trim()}
          style={{ padding: '10px 20px', borderRadius: 24, background: '#1677ff', color: '#fff', border: 'none', cursor: 'pointer', fontSize: 14 }}>
          发送
        </button>
      </div>
    </div>
  );
}
```

**Step 5: Update App.tsx**

```tsx
// frontend/src/App.tsx
import { ChatWindow } from './components/ChatWindow';

function App() {
  return <ChatWindow />;
}

export default App;
```

**Step 6: Update index.css** (reset styles)

```css
* { box-sizing: border-box; }
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
```

**Step 7: Start both servers and verify manually**

Backend:
```bash
cd backend && uvicorn main:app --reload --port 8000
```

Frontend:
```bash
cd frontend && npm run dev
```

Visit `http://localhost:5173`, send a test message.

**Step 8: Commit**

```bash
git add frontend/src/
git commit -m "feat: react chat interface with message bubbles and suggestions"
```

---

## Task 11: Stock Chart Component

**Files:**
- Create: `frontend/src/components/StockChart.tsx`
- Modify: `frontend/src/api/chat.ts`
- Modify: `frontend/src/types.ts`

**Step 1: Add chart data type to types.ts**

Append to `frontend/src/types.ts`:

```typescript
export interface PricePoint {
  date: string;
  close: number;
  open: number;
  high: number;
  low: number;
}
```

**Step 2: Add chart data endpoint to backend**

Append to `backend/routers/chat.py`:

```python
@router.get("/chart/{symbol}")
async def get_chart_data(symbol: str, days: int = 30):
    from agent.market_tools import get_price_history
    data = get_price_history(symbol, days=days)
    return {"symbol": symbol, "data": data}
```

**Step 3: Create StockChart.tsx**

```tsx
// frontend/src/components/StockChart.tsx
import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { PricePoint } from '../types';

interface Props { symbol: string; }

export function StockChart({ symbol }: Props) {
  const [data, setData] = useState<PricePoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`http://localhost:8000/api/chart/${symbol}?days=30`)
      .then(r => r.json())
      .then(d => { setData(d.data || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [symbol]);

  if (loading) return <div style={{ textAlign: 'center', padding: 20 }}>加载图表中...</div>;
  if (!data.length) return null;

  const isUp = data[data.length - 1]?.close >= data[0]?.close;
  const color = isUp ? '#f04' : '#0a0';  // red up, green down (A-share convention)

  return (
    <div style={{ marginTop: 12, padding: 16, background: '#fff', borderRadius: 8, border: '1px solid #eee' }}>
      <div style={{ fontSize: 13, color: '#888', marginBottom: 8 }}>{symbol} · 近30日走势</div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={d => d.slice(5)} />
          <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v: number) => v.toFixed(2)} />
          <Line type="monotone" dataKey="close" stroke={color} dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

**Step 4: Add chart to MessageBubble for market queries**

In `MessageBubble.tsx`, add after the pre tag:

```tsx
import { StockChart } from './StockChart';

// Inside the component, extract symbol from message if intent is market query:
const symbolMatch = message.content.match(/\b([A-Z]{1,5}(?:\.[A-Z]{2})?|-USD|\d{6}\.[A-Z]{2})\b/);
const symbol = !isUser && message.intent === 'MARKET_QUERY' && symbolMatch ? symbolMatch[0] : null;

// Then after </pre>:
{symbol && <StockChart symbol={symbol} />}
```

**Step 5: Test chart manually**

Visit `http://localhost:8000/api/chart/AAPL` — should return price data.
Ask "苹果当前股价" in the chat — chart should appear below the response.

**Step 6: Commit**

```bash
git add frontend/src/components/StockChart.tsx frontend/src/
git add backend/routers/chat.py
git commit -m "feat: stock price chart with recharts"
```

---

## Task 12: README & Final Polish

**Files:**
- Create: `README.md`
- Create: `backend/data/knowledge/` (ensure at least 2 documents)

**Step 1: Add a second knowledge document**

Create `backend/data/knowledge/financial_reports.md` with content about reading earnings reports, key metrics, etc. (at least 500 words covering quarterly reports, EPS beats/misses, guidance, etc.)

**Step 2: Re-index knowledge base**

```bash
cd backend
python -c "from rag.retriever import RAGRetriever; r = RAGRetriever(); r.index_documents('data/knowledge', force_reindex=True); print('Indexed', r.collection.count(), 'chunks')"
```

**Step 3: Create README.md**

Create `README.md` in project root with:
- Project title and description
- Architecture diagram (ASCII)
- Tech stack table
- Setup instructions (backend + frontend)
- Prompt design explanation
- Data sources
- Example questions
- Optimization ideas

**Step 4: Run all backend tests**

```bash
cd backend
pytest tests/ -v
```
Expected: All tests PASS

**Step 5: Final manual E2E test**

Test these 4 questions:
1. "阿里巴巴当前股价是多少？" → should call tools, show price
2. "BABA 最近7天涨跌情况如何？" → should show trend analysis
3. "什么是市盈率？" → should use RAG, show knowledge base answer
4. "收入和净利润的区别是什么？" → should use RAG

**Step 6: Final commit**

```bash
git add README.md backend/data/knowledge/
git commit -m "docs: readme, knowledge base, project complete"
```

---

## Summary

| Task | Component | Key Tech |
|------|-----------|----------|
| 1 | Project Setup | Python venv, Vite |
| 2 | FastAPI Foundation | FastAPI, pytest |
| 3 | Market Tools | yfinance |
| 4 | Tool Definitions | Anthropic Tool Use spec |
| 5 | Intent Router | Claude Haiku |
| 6 | Agent Core | Claude Sonnet + Tool Use loop |
| 7 | Knowledge Base + Embeddings | sentence-transformers, BAAI/bge |
| 8 | ChromaDB Retriever | ChromaDB |
| 9 | RAG Agent + Chat API | FastAPI SSE |
| 10 | Chat Frontend | React, TypeScript |
| 11 | Stock Chart | Recharts |
| 12 | Docs + Polish | README, E2E tests |
