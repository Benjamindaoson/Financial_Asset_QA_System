# 金融资产问答系统全面升级实施计划
# Comprehensive System Upgrade Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 解决技术审计报告中的所有问题（P0-P3），将系统从 7.2/10 提升到 9.0/10，实现企业级金融 AI 问答系统

**Architecture:**
- P0: 扩充 RAG 知识库至 10,000+ 条目，重构前端为多页面应用（Zustand + React Router）
- P1: 实现真正的 Agent 模式（ReAct 循环），接入实时行情 API，添加 OpenAPI 文档
- P2: 增强 ResponseGuard，实现查询改写，添加多轮对话，集成认证系统
- P3: 配置 CI/CD，集成监控日志，优化性能

**Tech Stack:**
- Backend: FastAPI, Anthropic SDK, ChromaDB, Redis, BeautifulSoup4
- Frontend: React 18, Zustand, React Router, Recharts, Lightweight-Charts
- DevOps: GitHub Actions, Sentry, Prometheus
- Testing: pytest, pytest-asyncio, React Testing Library

---

## Phase 1: P0 阻断性问题修复（1-2 周）

### Task 1: 扩充 RAG 知识库 - 数据爬取基础设施

**Files:**
- Create: `backend/scripts/crawlers/__init__.py`
- Create: `backend/scripts/crawlers/base_crawler.py`
- Create: `backend/scripts/crawlers/eastmoney_crawler.py`
- Create: `backend/requirements-dev.txt`
- Test: `backend/tests/test_crawlers.py`

**Step 1: 安装爬虫依赖**

```bash
cd backend
echo "beautifulsoup4==4.12.3
lxml==5.1.0
aiohttp==3.9.3
fake-useragent==1.4.0" >> requirements-dev.txt
pip install -r requirements-dev.txt
```

**Step 2: 创建基础爬虫类**

Create `backend/scripts/crawlers/base_crawler.py`:

```python
"""Base crawler with rate limiting and error handling."""
import asyncio
import aiohttp
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from fake_useragent import UserAgent


class BaseCrawler(ABC):
    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit
        self.ua = UserAgent()
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={"User-Agent": self.ua.random}
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    @abstractmethod
    async def crawl(self) -> List[Dict[str, Any]]:
        """Implement crawling logic."""
        pass

    async def _fetch(self, url: str) -> str:
        await asyncio.sleep(self.rate_limit)
        async with self.session.get(url, timeout=30) as response:
            return await response.text()
```

**Step 3: 实现东方财富爬虫**

Create `backend/scripts/crawlers/eastmoney_crawler.py`:

```python
"""东方财富财经术语爬虫."""
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from .base_crawler import BaseCrawler


class EastMoneyCrawler(BaseCrawler):
    BASE_URL = "https://baike.eastmoney.com"

    async def crawl(self) -> List[Dict[str, Any]]:
        """爬取金融术语."""
        terms = []
        # 爬取常见金融术语分类页面
        categories = [
            "/wiki/股票术语",
            "/wiki/基金术语",
            "/wiki/债券术语",
            "/wiki/期货术语"
        ]

        for category in categories:
            url = f"{self.BASE_URL}{category}"
            try:
                html = await self._fetch(url)
                soup = BeautifulSoup(html, 'lxml')

                # 提取术语列表
                for item in soup.select('.term-item'):
                    term = {
                        'title': item.select_one('.term-title').text.strip(),
                        'content': item.select_one('.term-content').text.strip(),
                        'category': category.split('/')[-1],
                        'source': 'eastmoney'
                    }
                    terms.append(term)
            except Exception as e:
                print(f"Error crawling {url}: {e}")

        return terms
```

**Step 4: 编写爬虫测试**

Create `backend/tests/test_crawlers.py`:

```python
import pytest
from scripts.crawlers.eastmoney_crawler import EastMoneyCrawler


@pytest.mark.asyncio
async def test_eastmoney_crawler():
    async with EastMoneyCrawler(rate_limit=2.0) as crawler:
        terms = await crawler.crawl()
        assert len(terms) > 0
        assert 'title' in terms[0]
        assert 'content' in terms[0]
        assert terms[0]['source'] == 'eastmoney'
```

**Step 5: 运行测试验证**

```bash
cd backend
pytest tests/test_crawlers.py -v
```

Expected: PASS (may take 30-60s due to rate limiting)

**Step 6: 提交基础设施**

```bash
git add backend/scripts/crawlers/ backend/requirements-dev.txt backend/tests/test_crawlers.py
git commit -m "feat(rag): add web crawler infrastructure for knowledge base expansion"
```

---

### Task 2: 扩充 RAG 知识库 - 批量数据采集

**Files:**
- Create: `backend/scripts/build_knowledge_base.py`
- Create: `data/knowledge/raw/`
- Modify: `backend/app/rag/pipeline.py`

**Step 1: 创建知识库构建脚本**

Create `backend/scripts/build_knowledge_base.py`:

```python
"""Build comprehensive financial knowledge base."""
import asyncio
import json
from pathlib import Path
from crawlers.eastmoney_crawler import EastMoneyCrawler


async def main():
    output_dir = Path("../data/knowledge/raw")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 爬取东方财富术语
    print("Crawling EastMoney terms...")
    async with EastMoneyCrawler(rate_limit=1.0) as crawler:
        terms = await crawler.crawl()
        with open(output_dir / "eastmoney_terms.json", "w", encoding="utf-8") as f:
            json.dump(terms, f, ensure_ascii=False, indent=2)
        print(f"Collected {len(terms)} terms from EastMoney")

    # 2. 生成结构化 markdown
    print("Generating structured markdown...")
    generate_markdown(terms, output_dir)

    print("Knowledge base build complete!")


def generate_markdown(terms, output_dir):
    """Convert JSON to structured markdown."""
    categories = {}
    for term in terms:
        cat = term['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(term)

    for category, items in categories.items():
        md_content = f"# {category}\n\n"
        for item in items:
            md_content += f"## {item['title']}\n\n"
            md_content += f"{item['content']}\n\n"
            md_content += f"**来源**: {item['source']}\n\n---\n\n"

        filename = f"{category.replace('术语', '_terms')}.md"
        with open(output_dir / filename, "w", encoding="utf-8") as f:
            f.write(md_content)


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 2: 运行数据采集**

```bash
cd backend/scripts
python build_knowledge_base.py
```

Expected: Creates JSON and markdown files in `data/knowledge/raw/`

**Step 3: 验证数据质量**

```bash
wc -l ../data/knowledge/raw/*.md
```

Expected: Total lines > 5000 (vs original 692)

**Step 4: 提交知识库数据**

```bash
git add backend/scripts/build_knowledge_base.py data/knowledge/raw/
git commit -m "feat(rag): expand knowledge base with 1000+ financial terms"
```

---

### Task 3: 更新 RAG 管道以加载新知识库

**Files:**
- Create: `backend/scripts/index_knowledge_base.py`
- Modify: `backend/app/rag/pipeline.py:109-127`

**Step 1: 创建索引脚本**

Create `backend/scripts/index_knowledge_base.py`:

```python
"""Index knowledge base into ChromaDB."""
import sys
sys.path.append('..')

from pathlib import Path
from app.rag.pipeline import RAGPipeline
from app.rag.hybrid_pipeline import HybridRAGPipeline


def load_documents():
    """Load all markdown documents."""
    docs = []
    metadatas = []
    ids = []

    knowledge_dir = Path("../data/knowledge")

    # Load original docs
    for md_file in knowledge_dir.glob("*.md"):
        content = md_file.read_text(encoding='utf-8')
        # Split by ## headers
        sections = content.split('\n## ')
        for i, section in enumerate(sections[1:], 1):
            docs.append(f"## {section}")
            metadatas.append({'source': md_file.stem, 'section': i})
            ids.append(f"{md_file.stem}_{i}")

    # Load new crawled docs
    raw_dir = knowledge_dir / "raw"
    if raw_dir.exists():
        for md_file in raw_dir.glob("*.md"):
            content = md_file.read_text(encoding='utf-8')
            sections = content.split('\n## ')
            for i, section in enumerate(sections[1:], 1):
                docs.append(f"## {section}")
                metadatas.append({'source': f"raw/{md_file.stem}", 'section': i})
                ids.append(f"raw_{md_file.stem}_{i}")

    return docs, metadatas, ids


def main():
    print("Loading documents...")
    docs, metadatas, ids = load_documents()
    print(f"Loaded {len(docs)} document chunks")

    print("Initializing RAG pipeline...")
    pipeline = HybridRAGPipeline()

    print("Adding documents to vector store...")
    pipeline.add_documents(docs, metadatas, ids)

    print("Building BM25 index...")
    pipeline.build_bm25_index(docs, ids)

    count = pipeline.get_collection_count()
    print(f"Indexing complete! Total documents: {count}")


if __name__ == "__main__":
    main()
```

**Step 2: 运行索引**

```bash
cd backend/scripts
python index_knowledge_base.py
```

Expected: "Indexing complete! Total documents: 1000+" (vs original ~50)

**Step 3: 测试检索质量**

```bash
cd backend
pytest tests/test_rag_pipeline.py -v
```

Expected: All tests PASS with improved recall

**Step 4: 提交索引脚本**

```bash
git add backend/scripts/index_knowledge_base.py
git commit -m "feat(rag): add indexing script for expanded knowledge base"
```

---

### Task 4: 前端状态管理 - 引入 Zustand

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/store/chatStore.ts`
- Create: `frontend/src/store/index.ts`

**Step 1: 安装 Zustand**

```bash
cd frontend
npm install zustand@4.5.0
```

**Step 2: 创建聊天状态管理**

Create `frontend/src/store/chatStore.ts`:

```typescript
import { create } from 'zustand';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  sources?: Array<{ name: string; timestamp: string }>;
  verified?: boolean;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

interface ChatState {
  sessions: ChatSession[];
  currentSessionId: string | null;
  isLoading: boolean;

  // Actions
  createSession: () => void;
  addMessage: (sessionId: string, message: Omit<Message, 'id' | 'timestamp'>) => void;
  deleteSession: (sessionId: string) => void;
  setCurrentSession: (sessionId: string) => void;
  setLoading: (loading: boolean) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  sessions: [],
  currentSessionId: null,
  isLoading: false,

  createSession: () => {
    const newSession: ChatSession = {
      id: `session_${Date.now()}`,
      title: '新对话',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    set((state) => ({
      sessions: [newSession, ...state.sessions],
      currentSessionId: newSession.id,
    }));
  },

  addMessage: (sessionId, message) => {
    const newMessage: Message = {
      ...message,
      id: `msg_${Date.now()}`,
      timestamp: Date.now(),
    };
    set((state) => ({
      sessions: state.sessions.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              messages: [...session.messages, newMessage],
              updatedAt: Date.now(),
              title: session.messages.length === 0 ? message.content.slice(0, 30) : session.title,
            }
          : session
      ),
    }));
  },

  deleteSession: (sessionId) => {
    set((state) => ({
      sessions: state.sessions.filter((s) => s.id !== sessionId),
      currentSessionId: state.currentSessionId === sessionId ? null : state.currentSessionId,
    }));
  },

  setCurrentSession: (sessionId) => {
    set({ currentSessionId: sessionId });
  },

  setLoading: (loading) => {
    set({ isLoading: loading });
  },
}));
```

**Step 3: 创建 store 入口**

Create `frontend/src/store/index.ts`:

```typescript
export { useChatStore } from './chatStore';
export type { Message, ChatSession } from './chatStore';
```

**Step 4: 提交状态管理**

```bash
git add frontend/package.json frontend/src/store/
git commit -m "feat(frontend): add Zustand state management for chat sessions"
```

---

### Task 5: 前端路由 - 引入 React Router

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/pages/ChatPage.tsx`
- Create: `frontend/src/pages/HistoryPage.tsx`
- Create: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: 安装 React Router**

```bash
cd frontend
npm install react-router-dom@6.22.0
```

**Step 2: 创建聊天页面**

Create `frontend/src/pages/ChatPage.tsx`:

```typescript
import React, { useState } from 'react';
import { useChatStore } from '../store';

export const ChatPage: React.FC = () => {
  const [input, setInput] = useState('');
  const { currentSessionId, addMessage, isLoading, setLoading } = useChatStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !currentSessionId) return;

    addMessage(currentSessionId, { role: 'user', content: input });
    setInput('');
    setLoading(true);

    try {
      const response = await fetch('http://localhost:8001/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: input }),
      });

      const reader = response.body?.getReader();
      let assistantMessage = '';

      while (true) {
        const { done, value } = await reader!.read();
        if (done) break;
        const text = new TextDecoder().decode(value);
        assistantMessage += text;
      }

      addMessage(currentSessionId, { role: 'assistant', content: assistantMessage });
    } catch (error) {
      console.error('Chat error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen">
      <div className="flex-1 overflow-y-auto p-4">
        {/* Messages will be rendered here */}
      </div>
      <form onSubmit={handleSubmit} className="p-4 border-t">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isLoading}
          className="w-full p-2 border rounded"
          placeholder="输入问题..."
        />
      </form>
    </div>
  );
};
```

**Step 3: 创建历史记录页面**

Create `frontend/src/pages/HistoryPage.tsx`:

```typescript
import React from 'react';
import { useChatStore } from '../store';
import { useNavigate } from 'react-router-dom';

export const HistoryPage: React.FC = () => {
  const { sessions, setCurrentSession, deleteSession } = useChatStore();
  const navigate = useNavigate();

  const handleSessionClick = (sessionId: string) => {
    setCurrentSession(sessionId);
    navigate('/chat');
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">对话历史</h1>
      <div className="space-y-2">
        {sessions.map((session) => (
          <div
            key={session.id}
            className="p-4 border rounded hover:bg-gray-50 cursor-pointer flex justify-between"
            onClick={() => handleSessionClick(session.id)}
          >
            <div>
              <h3 className="font-medium">{session.title}</h3>
              <p className="text-sm text-gray-500">
                {new Date(session.updatedAt).toLocaleString()}
              </p>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                deleteSession(session.id);
              }}
              className="text-red-500 hover:text-red-700"
            >
              删除
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};
```

**Step 4: 创建数据看板页面**

Create `frontend/src/pages/DashboardPage.tsx`:

```typescript
import React, { useEffect, useState } from 'react';

interface SystemHealth {
  status: string;
  components: Record<string, string>;
}

export const DashboardPage: React.FC = () => {
  const [health, setHealth] = useState<SystemHealth | null>(null);

  useEffect(() => {
    fetch('http://localhost:8001/api/health')
      .then((res) => res.json())
      .then(setHealth);
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-4">系统状态</h1>
      {health && (
        <div className="grid grid-cols-2 gap-4">
          <div className="p-4 border rounded">
            <h3 className="font-medium">整体状态</h3>
            <p className={health.status === 'healthy' ? 'text-green-600' : 'text-yellow-600'}>
              {health.status}
            </p>
          </div>
          {Object.entries(health.components).map(([key, value]) => (
            <div key={key} className="p-4 border rounded">
              <h3 className="font-medium">{key}</h3>
              <p>{value}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
```

**Step 5: 更新 App.tsx 使用路由**

Modify `frontend/src/App.tsx`:

```typescript
import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ChatPage } from './pages/ChatPage';
import { HistoryPage } from './pages/HistoryPage';
import { DashboardPage } from './pages/DashboardPage';
import { useChatStore } from './store';

function App() {
  const { createSession, currentSessionId } = useChatStore();

  useEffect(() => {
    if (!currentSessionId) {
      createSession();
    }
  }, []);

  return (
    <BrowserRouter>
      <div className="flex h-screen">
        <nav className="w-64 bg-gray-800 text-white p-4">
          <h2 className="text-xl font-bold mb-4">金融问答系统</h2>
          <ul className="space-y-2">
            <li><a href="/chat" className="block p-2 hover:bg-gray-700 rounded">对话</a></li>
            <li><a href="/history" className="block p-2 hover:bg-gray-700 rounded">历史</a></li>
            <li><a href="/dashboard" className="block p-2 hover:bg-gray-700 rounded">状态</a></li>
          </ul>
        </nav>
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Navigate to="/chat" />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
```

**Step 6: 测试路由**

```bash
cd frontend
npm run dev
```

Expected: Navigate between /chat, /history, /dashboard

**Step 7: 提交前端路由**

```bash
git add frontend/src/pages/ frontend/src/App.tsx frontend/package.json
git commit -m "feat(frontend): add multi-page routing with React Router"
```

---

### Task 6: 增强图表 - K 线图集成

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/components/CandlestickChart.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`

**Step 1: 安装 lightweight-charts**

```bash
cd frontend
npm install lightweight-charts@4.1.3
```

**Step 2: 创建 K 线图组件**

Create `frontend/src/components/CandlestickChart.tsx`:

```typescript
import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi } from 'lightweight-charts';

interface CandlestickData {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

interface Props {
  data: CandlestickData[];
  symbol: string;
}

export const CandlestickChart: React.FC<Props> = ({ data, symbol }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 400,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#e1e1e1' },
        horzLines: { color: '#e1e1e1' },
      },
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });

    candlestickSeries.setData(data);
    chart.timeScale().fitContent();

    chartRef.current = chart;

    return () => {
      chart.remove();
    };
  }, [data]);

  return (
    <div className="border rounded p-4">
      <h3 className="font-medium mb-2">{symbol} K线图</h3>
      <div ref={chartContainerRef} />
    </div>
  );
};
```

**Step 3: 提交图表组件**

```bash
git add frontend/package.json frontend/src/components/CandlestickChart.tsx
git commit -m "feat(frontend): add candlestick chart with lightweight-charts"
```

---

### Task 7: 添加 OpenAPI 文档

**Files:**
- Modify: `backend/app/main.py:14-18`

**Step 1: 启用 FastAPI 自动文档**

Modify `backend/app/main.py`:

```python
app = FastAPI(
    title="Financial Asset QA System",
    description="AI-powered financial asset question answering system with real-time market data",
    version="2.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
)
```

**Step 2: 测试文档端点**

```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Visit: http://localhost:8001/docs

Expected: Interactive API documentation

**Step 3: 提交文档配置**

```bash
git add backend/app/main.py
git commit -m "feat(api): enable OpenAPI documentation at /docs and /redoc"
```

---

## Phase 2: P1 严重问题修复（2-4 周）

### Task 8: 实现真正的 Agent 模式 - ReAct 循环

**Files:**
- Create: `backend/app/agent/react_agent.py`
- Create: `backend/app/agent/agent_mode.py`
- Modify: `backend/app/api/routes.py:24-58`
- Test: `backend/tests/test_react_agent.py`

**Step 1: 编写 ReAct Agent 测试**

Create `backend/tests/test_react_agent.py`:

```python
import pytest
from app.agent.react_agent import ReActAgent


@pytest.mark.asyncio
async def test_react_agent_initialization():
    agent = ReActAgent()
    assert agent is not None
    assert agent.max_iterations == 5


@pytest.mark.asyncio
async def test_react_agent_tool_calling():
    agent = ReActAgent()
    query = "苹果股票今天价格是多少？"

    result = await agent.run(query)

    assert result is not None
    assert 'thought' in result or 'action' in result
```

**Step 2: 运行测试确认失败**

```bash
cd backend
pytest tests/test_react_agent.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'app.agent.react_agent'"

**Step 3: 实现 ReAct Agent**

Create `backend/app/agent/react_agent.py`:

```python
"""ReAct Agent with autonomous tool calling."""
import json
import re
from typing import AsyncGenerator, Dict, List, Any, Optional
from app.models import SSEEvent, ToolResult
from app.models.model_adapter import ModelAdapterFactory
from app.models.multi_model import model_manager
from app.market import MarketDataService
from app.rag.hybrid_pipeline import HybridRAGPipeline
from app.search import WebSearchService


class ReActAgent:
    """
    ReAct (Reasoning + Acting) Agent.

    Loop:
    1. Thought: LLM reasons about what to do next
    2. Action: LLM decides which tool to call
    3. Observation: Execute tool and observe result
    4. Repeat until answer is ready
    """

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.model_manager = model_manager
        self.market_service = MarketDataService()
        self.rag_pipeline = HybridRAGPipeline()
        self.search_service = WebSearchService()
        self.tools = self._build_tools()

    def _build_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "get_price",
                "description": "Get current market price for a stock symbol",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            },
            {
                "name": "get_history",
                "description": "Get historical price data",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "days": {"type": "integer", "default": 30},
                    },
                    "required": ["symbol"],
                },
            },
            {
                "name": "search_knowledge",
                "description": "Search financial knowledge base",
                "input_schema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        ]

    async def _execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return result."""
        if tool_name == "get_price":
            result = await self.market_service.get_price(tool_input["symbol"])
            return result.model_dump()
        elif tool_name == "get_history":
            result = await self.market_service.get_history(
                tool_input["symbol"], tool_input.get("days", 30)
            )
            return result.model_dump()
        elif tool_name == "search_knowledge":
            result = await self.rag_pipeline.search(tool_input["query"])
            return result.model_dump()
        else:
            return {"error": f"Unknown tool: {tool_name}"}

    async def run(self, query: str) -> AsyncGenerator[SSEEvent, None]:
        """Run ReAct loop."""
        model_name = self.model_manager.select_model(complexity=None)
        config = self.model_manager.models[model_name]
        adapter = ModelAdapterFactory.create_adapter(config)

        conversation_history = []
        observations = []

        for iteration in range(self.max_iterations):
            # Build prompt with history
            system_prompt = self._build_system_prompt()
            user_message = self._build_user_message(query, observations)

            # LLM decides next action
            stream = adapter.create_message_stream(
                messages=[{"role": "user", "content": user_message}],
                system=system_prompt,
                tools=self.tools,
                max_tokens=1000,
            )

            tool_calls = []
            async for event in stream:
                if isinstance(event, dict) and "final_message" in event:
                    fm = event["final_message"]
                    if hasattr(fm, "content"):
                        for block in fm.content:
                            if getattr(block, "type", None) == "tool_use":
                                tool_calls.append({
                                    "name": block.name,
                                    "input": block.input,
                                })

            # If no tool calls, LLM has final answer
            if not tool_calls:
                yield SSEEvent(type="chunk", text="Final answer ready")
                break

            # Execute tools
            for tool_call in tool_calls:
                yield SSEEvent(
                    type="tool_start",
                    name=tool_call["name"],
                    display=f"Calling {tool_call['name']}...",
                )

                result = await self._execute_tool(tool_call["name"], tool_call["input"])
                observations.append({
                    "tool": tool_call["name"],
                    "input": tool_call["input"],
                    "output": result,
                })

                yield SSEEvent(type="tool_data", tool=tool_call["name"], data=result)

        yield SSEEvent(type="done", verified=True)

    def _build_system_prompt(self) -> str:
        return (
            "You are a financial analyst with access to real-time market data and knowledge base.\n"
            "Use the ReAct framework:\n"
            "1. Thought: Reason about what information you need\n"
            "2. Action: Call appropriate tools\n"
            "3. Observation: Analyze tool results\n"
            "4. Repeat until you have enough information to answer\n\n"
            "When you have gathered sufficient information, provide a final answer without calling more tools."
        )

    def _build_user_message(self, query: str, observations: List[Dict]) -> str:
        message = f"User question: {query}\n\n"

        if observations:
            message += "Previous observations:\n"
            for obs in observations:
                message += f"- {obs['tool']}: {json.dumps(obs['output'], ensure_ascii=False)}\n"

        return message
```

**Step 4: 运行测试验证实现**

```bash
pytest tests/test_react_agent.py -v
```

Expected: PASS

**Step 5: 提交 ReAct Agent**

```bash
git add backend/app/agent/react_agent.py backend/tests/test_react_agent.py
git commit -m "feat(agent): implement ReAct agent with autonomous tool calling"
```

### Task 9: 添加 Agent 模式切换

**Files:**
- Create: `backend/app/agent/agent_mode.py`
- Modify: `backend/app/api/routes.py:24-58`

**Step 1: 创建模式管理器**

Create `backend/app/agent/agent_mode.py`:

```python
"""Agent mode manager - switch between deterministic and ReAct modes."""
from enum import Enum
from typing import AsyncGenerator
from app.agent.core import AgentCore
from app.agent.react_agent import ReActAgent
from app.models import SSEEvent


class AgentMode(str, Enum):
    DETERMINISTIC = "deterministic"  # Fast, rule-based
    REACT = "react"  # Autonomous, LLM-driven


class AgentModeManager:
    """Manages agent mode selection."""

    def __init__(self):
        self.deterministic_agent = AgentCore()
        self.react_agent = ReActAgent()

    async def run(
        self, query: str, mode: AgentMode = AgentMode.DETERMINISTIC, model_name: str = None
    ) -> AsyncGenerator[SSEEvent, None]:
        """Run agent in specified mode."""
        if mode == AgentMode.DETERMINISTIC:
            async for event in self.deterministic_agent.run(query, model_name):
                yield event
        elif mode == AgentMode.REACT:
            async for event in self.react_agent.run(query):
                yield event
        else:
            yield SSEEvent(type="error", message=f"Unknown mode: {mode}", code="INVALID_MODE")
```

**Step 2: 更新 API 路由支持模式选择**

Modify `backend/app/api/routes.py`:

```python
from app.agent.agent_mode import AgentModeManager, AgentMode

# Replace agent initialization
agent_manager = AgentModeManager()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    model: Optional[str] = None,
    mode: AgentMode = AgentMode.DETERMINISTIC,
):
    """
    Chat endpoint with SSE streaming

    Args:
        request: Chat request with query
        model: Optional model name
        mode: Agent mode (deterministic or react)

    Returns: text/event-stream
    """
    enriched_query = enricher.enrich(request.query)

    async def event_generator():
        try:
            async for event in agent_manager.run(enriched_query, mode=mode, model_name=model):
                event_data = event.model_dump(exclude_none=True)
                yield {"event": "message", "data": json.dumps(event_data, ensure_ascii=False)}
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": str(e), "code": "STREAM_ERROR"}),
            }

    return EventSourceResponse(event_generator())
```

**Step 3: 测试模式切换**

```bash
# Test deterministic mode
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "苹果股票价格"}' \
  --no-buffer

# Test ReAct mode
curl -X POST "http://localhost:8001/api/chat?mode=react" \
  -H "Content-Type: application/json" \
  -d '{"query": "分析苹果股票最近表现"}' \
  --no-buffer
```

Expected: Both modes work, ReAct shows autonomous tool calling

**Step 4: 提交模式管理**

```bash
git add backend/app/agent/agent_mode.py backend/app/api/routes.py
git commit -m "feat(agent): add agent mode switching (deterministic vs ReAct)"
```

---

### Task 10: 收紧 ResponseGuard 验证逻辑

**Files:**
- Modify: `backend/app/agent/core.py:103-111`
- Test: `backend/tests/test_response_guard.py`

**Step 1: 编写严格验证测试**

Modify `backend/tests/test_response_guard.py`:

```python
def test_validate_rejects_small_ungrounded_numbers():
    """Small numbers (<=5) should also be validated."""
    tool_results = [
        ToolResult(
            tool="get_price",
            data={"price": 150.0},
            latency_ms=100,
            status="success",
            data_source="yfinance",
            cache_hit=False,
            error_message=None,
        )
    ]

    # Response with ungrounded small number
    response = "The stock has 3 major competitors."

    result = ResponseGuard.validate(response, tool_results)
    assert result is False, "Should reject ungrounded small numbers"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_response_guard.py::test_validate_rejects_small_ungrounded_numbers -v
```

Expected: FAIL (current implementation allows small numbers)

**Step 3: 收紧验证逻辑**

Modify `backend/app/agent/core.py`:

```python
@staticmethod
def _is_ignorable_number(token: str) -> bool:
    """Check if number can be ignored in validation."""
    try:
        value = float(token)
        if not value.is_integer():
            return False
        # Remove exception for small numbers - validate ALL numbers
        return False  # Changed from: return int(value) <= 5
    except ValueError:
        return False
```

**Step 4: 运行测试验证修复**

```bash
pytest tests/test_response_guard.py -v
```

Expected: All tests PASS

**Step 5: 提交验证增强**

```bash
git add backend/app/agent/core.py backend/tests/test_response_guard.py
git commit -m "fix(agent): tighten ResponseGuard to validate all numbers"
```

---

### Task 11: 实现查询改写（Query Rewriting）

**Files:**
- Create: `backend/app/rag/query_rewriter.py`
- Modify: `backend/app/rag/hybrid_pipeline.py:151-165`
- Test: `backend/tests/test_query_rewriter.py`

**Step 1: 编写查询改写测试**

Create `backend/tests/test_query_rewriter.py`:

```python
import pytest
from app.rag.query_rewriter import QueryRewriter


@pytest.mark.asyncio
async def test_query_rewriter_expands_colloquial():
    rewriter = QueryRewriter()

    original = "PE是啥？"
    rewritten = await rewriter.rewrite(original)

    assert "市盈率" in rewritten or "Price-to-Earnings" in rewritten
    assert len(rewritten) > len(original)


@pytest.mark.asyncio
async def test_query_rewriter_adds_context():
    rewriter = QueryRewriter()

    original = "怎么算？"
    rewritten = await rewriter.rewrite(original)

    # Should add context or expand abbreviation
    assert len(rewritten) >= len(original)
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_query_rewriter.py -v
```

Expected: FAIL with "ModuleNotFoundError"

**Step 3: 实现查询改写**

Create `backend/app/rag/query_rewriter.py`:

```python
"""Query rewriter for improving RAG recall."""
from typing import List
from app.models.model_adapter import ModelAdapterFactory
from app.models.multi_model import model_manager


class QueryRewriter:
    """
    Rewrites user queries to improve RAG retrieval.

    Techniques:
    1. Expand abbreviations (PE -> 市盈率)
    2. Add context for ambiguous queries
    3. Generate multiple query variations
    """

    def __init__(self):
        self.model_manager = model_manager

    async def rewrite(self, query: str) -> str:
        """Rewrite query for better retrieval."""
        # Use fastest model for rewriting
        model_name = self.model_manager.select_model(complexity=None)
        config = self.model_manager.models[model_name]
        adapter = ModelAdapterFactory.create_adapter(config)

        system_prompt = (
            "You are a query rewriter for a financial knowledge base.\n"
            "Rewrite the user's query to be more specific and searchable.\n"
            "Expand abbreviations, add context, and clarify ambiguous terms.\n"
            "Output only the rewritten query, no explanation."
        )

        messages = [{"role": "user", "content": f"Rewrite this query: {query}"}]

        stream = adapter.create_message_stream(
            messages=messages, system=system_prompt, tools=[], max_tokens=200
        )

        rewritten = ""
        async for event in stream:
            if isinstance(event, dict) and "final_message" in event:
                fm = event["final_message"]
                if hasattr(fm, "content"):
                    for block in fm.content:
                        if getattr(block, "type", None) == "text":
                            rewritten += block.text
            elif getattr(event, "type", None) == "content_block_delta":
                if getattr(event.delta, "type", None) == "text_delta":
                    rewritten += event.delta.text

        return rewritten.strip() if rewritten else query

    async def generate_variations(self, query: str, num_variations: int = 3) -> List[str]:
        """Generate multiple query variations for multi-query retrieval."""
        variations = [query]  # Include original

        model_name = self.model_manager.select_model(complexity=None)
        config = self.model_manager.models[model_name]
        adapter = ModelAdapterFactory.create_adapter(config)

        system_prompt = (
            f"Generate {num_variations} different ways to ask the same question.\n"
            "Each variation should use different wording but seek the same information.\n"
            "Output one variation per line, no numbering."
        )

        messages = [{"role": "user", "content": query}]

        stream = adapter.create_message_stream(
            messages=messages, system=system_prompt, tools=[], max_tokens=300
        )

        text = ""
        async for event in stream:
            if isinstance(event, dict) and "final_message" in event:
                fm = event["final_message"]
                if hasattr(fm, "content"):
                    for block in fm.content:
                        if getattr(block, "type", None) == "text":
                            text += block.text

        for line in text.strip().split("\n"):
            if line.strip():
                variations.append(line.strip())

        return variations[:num_variations + 1]
```

**Step 4: 集成到 RAG 管道**

Modify `backend/app/rag/hybrid_pipeline.py`:

```python
from app.rag.query_rewriter import QueryRewriter


class HybridRAGPipeline(RAGPipeline):
    def __init__(self):
        super().__init__()
        self.query_rewriter = QueryRewriter()
        # ... existing code ...

    async def search(self, query: str, use_hybrid: bool = True, use_rewrite: bool = True) -> KnowledgeResult:
        """Hybrid search with optional query rewriting."""

        # Rewrite query if enabled
        search_query = query
        if use_rewrite:
            search_query = await self.query_rewriter.rewrite(query)
            print(f"[QueryRewriter] Original: {query}")
            print(f"[QueryRewriter] Rewritten: {search_query}")

        # Continue with existing search logic using search_query
        vector_result = await super().search(search_query)
        # ... rest of existing code ...
```

**Step 5: 运行测试验证**

```bash
pytest tests/test_query_rewriter.py -v
```

Expected: PASS

**Step 6: 提交查询改写**

```bash
git add backend/app/rag/query_rewriter.py backend/app/rag/hybrid_pipeline.py backend/tests/test_query_rewriter.py
git commit -m "feat(rag): add query rewriting for improved retrieval"
```

---

## Phase 3: P2 中等问题修复（4-6 周）

### Task 12: 实现多轮对话支持

**Files:**
- Create: `backend/app/session/manager.py`
- Create: `backend/app/session/context.py`
- Modify: `backend/app/api/routes.py`
- Test: `backend/tests/test_session_manager.py`

**Step 1: 编写会话管理测试**

Create `backend/tests/test_session_manager.py`:

```python
import pytest
from app.session.manager import SessionManager


def test_create_session():
    manager = SessionManager()
    session_id = manager.create_session()

    assert session_id is not None
    assert manager.get_session(session_id) is not None


def test_add_message_to_session():
    manager = SessionManager()
    session_id = manager.create_session()

    manager.add_message(session_id, role="user", content="Hello")
    session = manager.get_session(session_id)

    assert len(session.messages) == 1
    assert session.messages[0]["role"] == "user"
```

**Step 2: 实现会话管理器**

Create `backend/app/session/manager.py`:

```python
"""Session manager for multi-turn conversations."""
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class ChatSession:
    id: str
    messages: List[Dict[str, str]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict = field(default_factory=dict)


class SessionManager:
    """Manages chat sessions with TTL."""

    def __init__(self, ttl_hours: int = 24):
        self.sessions: Dict[str, ChatSession] = {}
        self.ttl = timedelta(hours=ttl_hours)

    def create_session(self) -> str:
        """Create new session."""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = ChatSession(id=session_id)
        return session_id

    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get session by ID."""
        session = self.sessions.get(session_id)
        if session:
            # Check TTL
            if datetime.utcnow() - session.last_active > self.ttl:
                del self.sessions[session_id]
                return None
            session.last_active = datetime.utcnow()
        return session

    def add_message(self, session_id: str, role: str, content: str):
        """Add message to session."""
        session = self.get_session(session_id)
        if session:
            session.messages.append({"role": role, "content": content})

    def get_context(self, session_id: str, max_messages: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation context."""
        session = self.get_session(session_id)
        if not session:
            return []
        return session.messages[-max_messages:]

    def delete_session(self, session_id: str):
        """Delete session."""
        if session_id in self.sessions:
            del self.sessions[session_id]

    def cleanup_expired(self):
        """Remove expired sessions."""
        now = datetime.utcnow()
        expired = [
            sid for sid, session in self.sessions.items()
            if now - session.last_active > self.ttl
        ]
        for sid in expired:
            del self.sessions[sid]
```

**Step 3: 创建上下文处理器**

Create `backend/app/session/context.py`:

```python
"""Context processor for multi-turn conversations."""
from typing import List, Dict


class ContextProcessor:
    """Processes conversation context for better understanding."""

    @staticmethod
    def resolve_references(query: str, context: List[Dict[str, str]]) -> str:
        """Resolve pronouns and references using context."""
        if not context:
            return query

        # Simple reference resolution
        query_lower = query.lower()

        # "它" -> last mentioned entity
        if "它" in query_lower or "这个" in query_lower:
            for msg in reversed(context):
                if msg["role"] == "user":
                    # Extract potential entity (简化版)
                    words = msg["content"].split()
                    for word in words:
                        if len(word) >= 2 and word not in ["什么", "怎么", "为什么"]:
                            query = query.replace("它", word).replace("这个", word)
                            break
                    break

        return query

    @staticmethod
    def build_context_prompt(query: str, context: List[Dict[str, str]]) -> str:
        """Build prompt with conversation context."""
        if not context:
            return query

        prompt = "Previous conversation:\n"
        for msg in context[-5:]:  # Last 5 messages
            role = "User" if msg["role"] == "user" else "Assistant"
            prompt += f"{role}: {msg['content']}\n"

        prompt += f"\nCurrent question: {query}"
        return prompt
```

**Step 4: 更新 API 支持会话**

Modify `backend/app/api/routes.py`:

```python
from app.session.manager import SessionManager
from app.session.context import ContextProcessor

# Initialize session manager
session_manager = SessionManager()
context_processor = ContextProcessor()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    model: Optional[str] = None,
    mode: AgentMode = AgentMode.DETERMINISTIC,
):
    """Chat with session support."""
    # Get or create session
    session_id = request.session_id
    if not session_id:
        session_id = session_manager.create_session()

    # Get conversation context
    context = session_manager.get_context(session_id)

    # Resolve references
    resolved_query = context_processor.resolve_references(request.query, context)

    # Add context to query
    enriched_query = context_processor.build_context_prompt(resolved_query, context)

    # Add user message to session
    session_manager.add_message(session_id, "user", request.query)

    async def event_generator():
        assistant_response = ""
        try:
            async for event in agent_manager.run(enriched_query, mode=mode, model_name=model):
                if event.type == "chunk" and event.text:
                    assistant_response += event.text
                event_data = event.model_dump(exclude_none=True)
                yield {"event": "message", "data": json.dumps(event_data, ensure_ascii=False)}

            # Add assistant response to session
            session_manager.add_message(session_id, "assistant", assistant_response)

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"type": "error", "message": str(e)}),
            }

    return EventSourceResponse(event_generator())
```

**Step 5: 运行测试**

```bash
pytest tests/test_session_manager.py -v
```

Expected: PASS

**Step 6: 提交多轮对话**

```bash
git add backend/app/session/ backend/app/api/routes.py backend/tests/test_session_manager.py
git commit -m "feat(session): add multi-turn conversation support with context"
```

### Task 13: 添加 API 认证机制

**Files:**
- Create: `backend/app/auth/api_key.py`
- Create: `backend/app/auth/middleware.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_auth.py`

**Step 1: 编写认证测试**

Create `backend/tests/test_auth.py`:

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app


def test_api_requires_key():
    client = TestClient(app)
    response = client.post("/api/chat", json={"query": "test"})
    assert response.status_code == 401


def test_api_accepts_valid_key():
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={"query": "test"},
        headers={"X-API-Key": "test_key_123"}
    )
    assert response.status_code in [200, 422]  # 422 if validation fails, but auth passed
```

**Step 2: 实现 API Key 验证**

Create `backend/app/auth/api_key.py`:

```python
"""API Key authentication."""
from typing import Optional
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> str:
    """Verify API key."""
    if not settings.REQUIRE_API_KEY:
        return "anonymous"

    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")

    if api_key not in settings.VALID_API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key
```

**Step 3: 添加配置**

Modify `backend/app/config.py`:

```python
class Settings(BaseSettings):
    # ... existing fields ...

    # Authentication
    REQUIRE_API_KEY: bool = False
    VALID_API_KEYS: str = ""  # Comma-separated keys

    @property
    def api_keys_list(self) -> list[str]:
        if not self.VALID_API_KEYS:
            return []
        return [k.strip() for k in self.VALID_API_KEYS.split(",")]

    # ... rest of config ...
```

**Step 4: 应用认证到路由**

Modify `backend/app/api/routes.py`:

```python
from app.auth.api_key import verify_api_key


@router.post("/chat")
async def chat(
    request: ChatRequest,
    api_key: str = Depends(verify_api_key),
    model: Optional[str] = None,
    mode: AgentMode = AgentMode.DETERMINISTIC,
):
    """Chat endpoint with API key authentication."""
    # ... existing code ...
```

**Step 5: 更新 .env.example**

```bash
echo "REQUIRE_API_KEY=false
VALID_API_KEYS=your_api_key_1,your_api_key_2" >> backend/.env.example
```

**Step 6: 运行测试**

```bash
cd backend
export REQUIRE_API_KEY=true
export VALID_API_KEYS=test_key_123
pytest tests/test_auth.py -v
```

Expected: PASS

**Step 7: 提交认证系统**

```bash
git add backend/app/auth/ backend/app/config.py backend/app/api/routes.py backend/.env.example backend/tests/test_auth.py
git commit -m "feat(auth): add API key authentication with configurable enforcement"
```

---

## Phase 4: P3 轻微问题修复（持续优化）

### Task 14: 配置 CI/CD - GitHub Actions

**Files:**
- Create: `.github/workflows/backend-tests.yml`
- Create: `.github/workflows/frontend-build.yml`

**Step 1: 创建后端测试工作流**

Create `.github/workflows/backend-tests.yml`:

```yaml
name: Backend Tests

on:
  push:
    branches: [master, main]
    paths:
      - 'backend/**'
  pull_request:
    branches: [master, main]
    paths:
      - 'backend/**'

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('backend/requirements.txt') }}

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov

      - name: Run tests
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          REDIS_HOST: localhost
        run: |
          cd backend
          pytest tests/ -v --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: ./backend/coverage.xml
          flags: backend
```

**Step 2: 创建前端构建工作流**

Create `.github/workflows/frontend-build.yml`:

```yaml
name: Frontend Build

on:
  push:
    branches: [master, main]
    paths:
      - 'frontend/**'
  pull_request:
    branches: [master, main]
    paths:
      - 'frontend/**'

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'

      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: frontend/node_modules
          key: ${{ runner.os }}-node-${{ hashFiles('frontend/package-lock.json') }}

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Build
        run: |
          cd frontend
          npm run build

      - name: Upload build artifacts
        uses: actions/upload-artifact@v4
        with:
          name: frontend-build
          path: frontend/dist/
```

**Step 3: 提交 CI/CD 配置**

```bash
git add .github/workflows/
git commit -m "ci: add GitHub Actions for automated testing and building"
```

---

### Task 15: 集成监控 - Sentry 错误追踪

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/app/main.py`
- Modify: `backend/app/config.py`

**Step 1: 安装 Sentry SDK**

```bash
cd backend
echo "sentry-sdk[fastapi]==1.40.0" >> requirements.txt
pip install sentry-sdk[fastapi]
```

**Step 2: 添加 Sentry 配置**

Modify `backend/app/config.py`:

```python
class Settings(BaseSettings):
    # ... existing fields ...

    # Monitoring
    SENTRY_DSN: Optional[str] = None
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
```

**Step 3: 初始化 Sentry**

Modify `backend/app/main.py`:

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.redis import RedisIntegration

# Initialize Sentry
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[
            FastApiIntegration(),
            RedisIntegration(),
        ],
    )
    print(f"[Sentry] Initialized for environment: {settings.SENTRY_ENVIRONMENT}")
```

**Step 4: 测试错误追踪**

```python
# Add test endpoint
@app.get("/debug/sentry")
async def test_sentry():
    """Test Sentry error tracking."""
    raise Exception("Test Sentry integration")
```

Visit: http://localhost:8001/debug/sentry

Expected: Error appears in Sentry dashboard

**Step 5: 提交监控集成**

```bash
git add backend/requirements.txt backend/app/main.py backend/app/config.py
git commit -m "feat(monitoring): integrate Sentry for error tracking"
```

---

### Task 16: 添加代码格式化工具

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.pre-commit-config.yaml`
- Create: `.editorconfig`

**Step 1: 安装格式化工具**

```bash
cd backend
pip install black==24.1.1 ruff==0.2.0 pre-commit==3.6.0
```

**Step 2: 配置 Black 和 Ruff**

Create `backend/pyproject.toml`:

```toml
[tool.black]
line-length = 120
target-version = ['py311']
include = '\.pyi?$'
exclude = '''
/(
    \.git
  | \.venv
  | venv
  | build
  | dist
)/
'''

[tool.ruff]
line-length = 120
target-version = "py311"
select = [
    "E",   # pycodestyle errors
    "W",   # pycodestyle warnings
    "F",   # pyflakes
    "I",   # isort
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
]
ignore = [
    "E501",  # line too long (handled by black)
    "B008",  # do not perform function calls in argument defaults
]

[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]  # unused imports
```

**Step 3: 配置 pre-commit hooks**

Create `backend/.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.2.0
    hooks:
      - id: ruff
        args: [--fix]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
```

**Step 4: 安装 pre-commit hooks**

```bash
cd backend
pre-commit install
```

**Step 5: 格式化现有代码**

```bash
black app/ tests/
ruff check app/ tests/ --fix
```

**Step 6: 提交格式化配置**

```bash
git add backend/pyproject.toml backend/.pre-commit-config.yaml
git commit -m "chore: add code formatting with black and ruff"
```

---

### Task 17: 性能优化 - 向量检索加速

**Files:**
- Modify: `backend/app/rag/pipeline.py`
- Create: `backend/app/rag/cache.py`

**Step 1: 实现查询缓存**

Create `backend/app/rag/cache.py`:

```python
"""Query result caching for RAG."""
import hashlib
import json
from typing import Optional
import redis
from app.config import settings
from app.models import KnowledgeResult


class RAGCache:
    """Cache RAG query results."""

    def __init__(self, ttl: int = 3600):
        self.redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )
        self.ttl = ttl

    def _make_key(self, query: str) -> str:
        """Generate cache key from query."""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"rag:query:{query_hash}"

    def get(self, query: str) -> Optional[KnowledgeResult]:
        """Get cached result."""
        try:
            key = self._make_key(query)
            data = self.redis_client.get(key)
            if data:
                return KnowledgeResult(**json.loads(data))
        except Exception:
            pass
        return None

    def set(self, query: str, result: KnowledgeResult):
        """Cache result."""
        try:
            key = self._make_key(query)
            data = result.model_dump_json()
            self.redis_client.setex(key, self.ttl, data)
        except Exception:
            pass
```

**Step 2: 集成缓存到 RAG 管道**

Modify `backend/app/rag/pipeline.py`:

```python
from app.rag.cache import RAGCache


class RAGPipeline:
    def __init__(self):
        # ... existing code ...
        self.cache = RAGCache(ttl=3600)

    async def search(self, query: str) -> KnowledgeResult:
        """Search with caching."""
        # Check cache
        cached = self.cache.get(query)
        if cached:
            print(f"[RAGCache] Hit for query: {query[:50]}")
            return cached

        # Perform search
        result = await self._search_impl(query)

        # Cache result
        self.cache.set(query, result)

        return result

    async def _search_impl(self, query: str) -> KnowledgeResult:
        """Original search implementation."""
        # Move existing search logic here
        query_embedding = self._embed_query(query)
        # ... rest of existing code ...
```

**Step 3: 测试缓存性能**

```bash
cd backend
pytest tests/test_rag_pipeline.py -v --durations=10
```

Expected: Second query much faster (cache hit)

**Step 4: 提交性能优化**

```bash
git add backend/app/rag/cache.py backend/app/rag/pipeline.py
git commit -m "perf(rag): add Redis caching for query results"
```

---

## 总结与验收

### Task 18: 端到端测试

**Files:**
- Create: `backend/tests/integration/test_e2e.py`

**Step 1: 创建端到端测试**

Create `backend/tests/integration/test_e2e.py`:

```python
"""End-to-end integration tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    """Test health endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_chat_deterministic_mode(client):
    """Test chat in deterministic mode."""
    response = client.post(
        "/api/chat",
        json={"query": "苹果股票价格"},
        stream=True
    )
    assert response.status_code == 200


def test_chat_react_mode(client):
    """Test chat in ReAct mode."""
    response = client.post(
        "/api/chat?mode=react",
        json={"query": "分析苹果股票"},
        stream=True
    )
    assert response.status_code == 200


def test_models_endpoint(client):
    """Test models listing."""
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert "usage" in data
```

**Step 2: 运行完整测试套件**

```bash
cd backend
pytest tests/ -v --cov=app --cov-report=html
```

Expected: All tests PASS, coverage > 90%

**Step 3: 验证前端**

```bash
cd frontend
npm run build
npm run preview
```

Expected: All pages work, navigation smooth

**Step 4: 最终提交**

```bash
git add backend/tests/integration/test_e2e.py
git commit -m "test: add end-to-end integration tests"
git tag v2.0.0
git push origin master --tags
```

---

## 验收标准

### P0 问题解决验证

- [ ] RAG 知识库文档数 > 1000（原 50）
- [ ] 前端支持多页面路由（Chat/History/Dashboard）
- [ ] 前端使用 Zustand 状态管理
- [ ] K 线图正常显示
- [ ] OpenAPI 文档可访问 (/docs)

### P1 问题解决验证

- [ ] ReAct Agent 模式可用
- [ ] 模式切换正常（deterministic vs react）
- [ ] ResponseGuard 验证所有数字
- [ ] 查询改写提升召回率

### P2 问题解决验证

- [ ] 多轮对话支持上下文
- [ ] API Key 认证可配置
- [ ] 会话管理正常

### P3 问题解决验证

- [ ] GitHub Actions CI/CD 运行
- [ ] Sentry 错误追踪集成
- [ ] 代码格式化工具配置
- [ ] RAG 查询缓存生效

### 性能指标

- [ ] 测试覆盖率 > 90%
- [ ] API 响应时间 < 2s (P95)
- [ ] RAG 召回率 > 80%
- [ ] 前端首屏加载 < 3s

---

## 执行建议

**预计总工时**: 6-8 周（1 人全职）

**关键里程碑**:
- Week 2: P0 完成（知识库 + 前端基础）
- Week 4: P1 完成（Agent + 实时数据）
- Week 6: P2 完成（多轮对话 + 认证）
- Week 8: P3 完成（CI/CD + 监控）

**风险点**:
1. 数据爬取可能遇到反爬虫（备选：购买数据集）
2. ReAct Agent 可能不稳定（保留确定性模式作为降级）
3. 实时行情 API 成本较高（可选功能）

---

Plan complete and saved to `docs/plans/2026-03-07-comprehensive-system-upgrade.md`.

## 执行选项

**1. Subagent-Driven (this session)** - 我在当前会话中逐任务派发子 Agent，每个任务完成后进行代码审查，快速迭代

**2. Parallel Session (separate)** - 在新会话中使用 executing-plans 技能，批量执行并设置检查点

**Which approach?**
