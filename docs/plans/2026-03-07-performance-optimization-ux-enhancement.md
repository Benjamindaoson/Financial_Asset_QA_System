# 金融问答系统性能优化与用户体验提升实施计划
# Performance Optimization & UX Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将系统响应延迟从3.7s降低到0.3s（热门股票），提升用户体验到"即时反馈"级别

**Architecture:** 采用分层响应策略（缓存预热+并行执行+流式响应+乐观UI），核心数据优先返回，次要数据异步加载，通过渐进式呈现消除用户等待感

**Tech Stack:** Redis缓存预热、asyncio并行、SSE流式、React乐观更新、HNSW近似搜索、Prometheus监控

**Performance Targets:**
- 热门股票查询: 3.7s → 0.3s (12x提升)
- 首字节时间: 2.0s → 0.2s (10x提升)
- P95延迟: 5.0s → 2.0s (2.5x提升)

---

## Phase 1: 核心性能优化 (Week 1-2)

### Task 1: 智能缓存预热系统

**Files:**
- Create: `backend/app/cache/warmer.py`
- Create: `backend/app/cache/popular_stocks.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_cache_warmer.py`

**Step 1: 编写缓存预热测试**

Create `backend/tests/test_cache_warmer.py`:

```python
import pytest
from app.cache.warmer import CacheWarmer
from app.market import MarketDataService

@pytest.mark.asyncio
async def test_cache_warmer_preloads_popular_stocks():
    """Test that cache warmer preloads TOP stocks."""
    warmer = CacheWarmer(market_service=MarketDataService())

    # Warm cache for top 3 stocks
    await warmer.warm_popular_stocks(limit=3)

    # Verify cache hit
    service = MarketDataService()
    result = await service.get_price("AAPL")

    assert result.cache_hit is True
    assert result.latency_ms < 100  # Should be fast from cache
```

**Step 2: 运行测试确认失败**

```bash
cd backend
pytest tests/test_cache_warmer.py::test_cache_warmer_preloads_popular_stocks -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'app.cache.warmer'"

**Step 3: 实现热门股票列表**

Create `backend/app/cache/popular_stocks.py`:

```python
"""Popular stocks configuration for cache warming."""

# TOP 100 most queried stocks (US + China markets)
POPULAR_STOCKS = [
    # US Tech Giants
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",

    # US Finance
    "JPM", "BAC", "WFC", "GS", "MS",

    # China ADRs
    "BABA", "JD", "PDD", "BIDU", "NIO",

    # A-shares (top 20)
    "600519.SS",  # 贵州茅台
    "000858.SZ",  # 五粮液
    "601318.SS",  # 中国平安
    "600036.SS",  # 招商银行
    "000333.SZ",  # 美的集团
    # ... (继续添加到100个)
]

def get_popular_stocks(limit: int = 100) -> list[str]:
    """Get top N popular stocks."""
    return POPULAR_STOCKS[:limit]
```

**Step 4: 实现缓存预热器**

Create `backend/app/cache/warmer.py`:

```python
"""Cache warmer for preloading popular stock data."""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from app.cache.popular_stocks import get_popular_stocks
from app.market import MarketDataService

logger = logging.getLogger(__name__)


class CacheWarmer:
    """Preloads popular stock data into Redis cache."""

    def __init__(
        self,
        market_service: MarketDataService,
        interval_seconds: int = 30,
    ):
        self.market_service = market_service
        self.interval_seconds = interval_seconds
        self._task: Optional[asyncio.Task] = None

    async def warm_popular_stocks(self, limit: int = 100):
        """Warm cache for top N popular stocks."""
        stocks = get_popular_stocks(limit)

        logger.info(f"[CacheWarmer] Warming {len(stocks)} popular stocks...")
        start_time = datetime.now()

        # Parallel fetch with concurrency limit
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests

        async def fetch_with_limit(symbol: str):
            async with semaphore:
                try:
                    await self.market_service.get_price(symbol)
                    await self.market_service.get_history(symbol, days=30)
                except Exception as e:
                    logger.warning(f"[CacheWarmer] Failed to warm {symbol}: {e}")

        await asyncio.gather(*[fetch_with_limit(s) for s in stocks])

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"[CacheWarmer] Completed in {elapsed:.2f}s")

    async def start_background_warming(self):
        """Start background task that warms cache periodically."""
        async def warming_loop():
            while True:
                try:
                    await self.warm_popular_stocks()
                    await asyncio.sleep(self.interval_seconds)
                except Exception as e:
                    logger.error(f"[CacheWarmer] Error in warming loop: {e}")
                    await asyncio.sleep(60)  # Retry after 1 minute

        self._task = asyncio.create_task(warming_loop())
        logger.info(f"[CacheWarmer] Background warming started (interval={self.interval_seconds}s)")

    async def stop(self):
        """Stop background warming task."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
```

**Step 5: 集成到FastAPI启动**

Modify `backend/app/main.py`:

```python
from app.cache.warmer import CacheWarmer
from app.market import MarketDataService

# Global cache warmer instance
cache_warmer: Optional[CacheWarmer] = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    global cache_warmer

    # Initialize cache warmer
    market_service = MarketDataService()
    cache_warmer = CacheWarmer(market_service, interval_seconds=30)

    # Start background warming
    await cache_warmer.start_background_warming()

    print("[Startup] Cache warmer initialized")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    if cache_warmer:
        await cache_warmer.stop()
    print("[Shutdown] Cache warmer stopped")
```

**Step 6: 运行测试验证**

```bash
pytest tests/test_cache_warmer.py -v
```

Expected: PASS

**Step 7: 手动验证缓存预热效果**

```bash
# 启动服务
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

# 等待30秒让预热完成，然后测试
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "AAPL股价"}' \
  --no-buffer
```

Expected: 响应时间 < 500ms，日志显示 cache_hit=True

**Step 8: 提交**

```bash
git add backend/app/cache/ backend/app/main.py backend/tests/test_cache_warmer.py
git commit -m "feat(cache): add intelligent cache warming for popular stocks

- Preload TOP 100 stocks every 30 seconds
- Parallel fetching with concurrency limit
- Background task with error recovery
- Target: 3.7s -> 0.3s for popular stocks"
```

---

### Task 2: 并行工具调用优化

**Files:**
- Modify: `backend/app/agent/core.py:282-318`
- Test: `backend/tests/test_parallel_execution.py`

**Step 1: 编写并行执行测试**

Create `backend/tests/test_parallel_execution.py`:

```python
import pytest
import time
from app.agent.core import AgentCore

@pytest.mark.asyncio
async def test_parallel_tool_execution():
    """Test that tools execute in parallel, not sequentially."""
    agent = AgentCore()

    start_time = time.time()

    # Query that requires multiple tools
    query = "分析苹果股票的价格、历史走势和最新新闻"

    async for event in agent.run(query):
        if event.type == "done":
            break

    elapsed = time.time() - start_time

    # If sequential: ~3s (1s + 0.8s + 1.2s)
    # If parallel: ~1.2s (max of all)
    assert elapsed < 2.0, f"Expected parallel execution < 2s, got {elapsed:.2f}s"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_parallel_execution.py::test_parallel_tool_execution -v
```

Expected: FAIL with "AssertionError: Expected parallel execution < 2s, got 3.1s"

**Step 3: 重构工具调用为并行执行**

Modify `backend/app/agent/core.py`:

```python
async def _execute_tools_parallel(
    self, tool_plan: List[Dict[str, Any]]
) -> List[ToolResult]:
    """Execute multiple tools in parallel."""

    async def execute_single_tool(tool_spec: Dict[str, Any]) -> ToolResult:
        tool_name = tool_spec["name"]
        tool_input = tool_spec["input"]

        start_time = time.time()

        try:
            if tool_name == "get_price":
                result = await self.market_service.get_price(tool_input["symbol"])
            elif tool_name == "get_history":
                result = await self.market_service.get_history(
                    tool_input["symbol"], tool_input.get("days", 30)
                )
            elif tool_name == "search_knowledge":
                result = await self.rag_pipeline.search(tool_input["query"])
            elif tool_name == "search_web":
                result = await self.search_service.search(tool_input["query"])
            else:
                raise ValueError(f"Unknown tool: {tool_name}")

            latency_ms = int((time.time() - start_time) * 1000)

            return ToolResult(
                tool=tool_name,
                data=result.model_dump() if hasattr(result, "model_dump") else result,
                latency_ms=latency_ms,
                status="success",
            )
        except Exception as e:
            return ToolResult(
                tool=tool_name,
                data={},
                latency_ms=int((time.time() - start_time) * 1000),
                status="error",
                error_message=str(e),
            )

    # Execute all tools in parallel
    results = await asyncio.gather(*[execute_single_tool(spec) for spec in tool_plan])

    return results
```

**Step 4: 更新主执行流程使用并行调用**

Modify `backend/app/agent/core.py` in the `run()` method:

```python
async def run(self, query: str, model_name: str = None) -> AsyncGenerator[SSEEvent, None]:
    """Execute agent workflow with parallel tool execution."""

    # Step 1: Build tool plan
    tool_plan = await self._build_tool_plan(query)

    yield SSEEvent(type="plan", tools=[t["name"] for t in tool_plan])

    # Step 2: Execute tools in parallel (NEW)
    tool_results = await self._execute_tools_parallel(tool_plan)

    # Step 3: Yield tool results
    for result in tool_results:
        yield SSEEvent(
            type="tool_data",
            tool=result.tool,
            data=result.data,
            latency_ms=result.latency_ms,
        )

    # Step 4: Generate response
    async for event in self._generate_response(query, tool_results, model_name):
        yield event
```

**Step 5: 运行测试验证**

```bash
pytest tests/test_parallel_execution.py -v
```

Expected: PASS (elapsed < 2.0s)

**Step 6: 提交**

```bash
git add backend/app/agent/core.py backend/tests/test_parallel_execution.py
git commit -m "perf(agent): execute tools in parallel instead of sequentially

- Use asyncio.gather for concurrent tool execution
- Reduce multi-tool queries from 3s to 1.2s (60% faster)
- Maintain error handling per tool"
```

---

### Task 3: 流式响应首字节优化

**Files:**
- Modify: `backend/app/agent/core.py:370-450`
- Test: `backend/tests/test_streaming_performance.py`

**Step 1: 编写首字节延迟测试**

Create `backend/tests/test_streaming_performance.py`:

```python
import pytest
import time
from app.agent.core import AgentCore

@pytest.mark.asyncio
async def test_first_byte_latency():
    """Test that first response chunk arrives quickly."""
    agent = AgentCore()
    query = "AAPL股价"

    start_time = time.time()
    first_chunk_time = None

    async for event in agent.run(query):
        if event.type == "chunk" and event.text and first_chunk_time is None:
            first_chunk_time = time.time() - start_time
            break

    assert first_chunk_time is not None
    assert first_chunk_time < 0.5, f"First byte took {first_chunk_time:.2f}s, expected < 0.5s"
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_streaming_performance.py::test_first_byte_latency -v
```

Expected: FAIL with "AssertionError: First byte took 2.1s, expected < 0.5s"

**Step 3: 实现数据摘要优先返回**

Modify `backend/app/agent/core.py`:

```python
async def _generate_response(
    self, query: str, tool_results: List[ToolResult], model_name: str = None
) -> AsyncGenerator[SSEEvent, None]:
    """Generate response with immediate data summary."""

    # OPTIMIZATION: Immediately yield data summary (before LLM)
    data_summary = self._build_data_summary(tool_results)
    if data_summary:
        yield SSEEvent(type="chunk", text=data_summary + "\n\n")

    # Then stream LLM analysis
    messages = self._build_grounded_messages(query, tool_results)
    system_prompt = self._build_system_prompt()

    # ... rest of LLM streaming code
```

**Step 4: 实现数据摘要生成器**

Add to `backend/app/agent/core.py`:

```python
def _build_data_summary(self, tool_results: List[ToolResult]) -> str:
    """Build immediate data summary from tool results."""
    summary_parts = []

    for result in tool_results:
        if result.status != "success":
            continue

        if result.tool == "get_price":
            data = result.data
            symbol = data.get("symbol", "")
            price = data.get("price")
            change_pct = data.get("change_percent")

            if price and change_pct is not None:
                direction = "📈" if change_pct > 0 else "📉"
                summary_parts.append(
                    f"{direction} **{symbol}** 当前价格: ${price:.2f} ({change_pct:+.2f}%)"
                )

        elif result.tool == "get_history":
            data = result.data
            if data.get("data_points"):
                count = len(data["data_points"])
                summary_parts.append(f"📊 已获取 {count} 天历史数据")

    return "\n".join(summary_parts) if summary_parts else ""
```

**Step 5: 运行测试验证**

```bash
pytest tests/test_streaming_performance.py -v
```

Expected: PASS (first_chunk_time < 0.5s)

**Step 6: 提交**

```bash
git add backend/app/agent/core.py backend/tests/test_streaming_performance.py
git commit -m "perf(streaming): return data summary before LLM generation

- Immediately yield structured data summary
- First byte latency: 2.0s -> 0.2s (10x faster)
- User sees price/data while AI analysis generates"
```

---

### Task 4: 前端乐观更新

**Files:**
- Modify: `frontend/src/components/ChatInterface.tsx`
- Create: `frontend/src/hooks/useOptimisticChat.ts`

**Step 1: 创建乐观更新Hook**

Create `frontend/src/hooks/useOptimisticChat.ts`:

```typescript
import { useState, useCallback } from 'react';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  loading?: boolean;
  timestamp: number;
}

export function useOptimisticChat() {
  const [messages, setMessages] = useState<Message[]>([]);

  const addUserMessage = useCallback((content: string) => {
    const userMsg: Message = {
      id: `user_${Date.now()}`,
      role: 'user',
      content,
      timestamp: Date.now(),
    };

    const loadingMsg: Message = {
      id: `assistant_${Date.now()}`,
      role: 'assistant',
      content: '正在查询...',
      loading: true,
      timestamp: Date.now(),
    };

    // Optimistic update: immediately show both messages
    setMessages(prev => [...prev, userMsg, loadingMsg]);

    return loadingMsg.id;
  }, []);

  const updateAssistantMessage = useCallback((id: string, content: string, loading = false) => {
    setMessages(prev =>
      prev.map(msg =>
        msg.id === id
          ? { ...msg, content, loading }
          : msg
      )
    );
  }, []);

  return {
    messages,
    addUserMessage,
    updateAssistantMessage,
  };
}
```

**Step 2: 更新ChatInterface使用乐观更新**

Modify `frontend/src/components/ChatInterface.tsx`:

```typescript
import { useOptimisticChat } from '../hooks/useOptimisticChat';

export function ChatInterface() {
  const { messages, addUserMessage, updateAssistantMessage } = useOptimisticChat();
  const [input, setInput] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    // Step 1: Optimistic update (0ms perceived latency)
    const assistantMsgId = addUserMessage(input);
    setInput('');

    // Step 2: Fetch real response
    try {
      const response = await fetch('http://localhost:8001/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: input }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let accumulatedText = '';

      while (true) {
        const { done, value } = await reader!.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'chunk' && data.text) {
              accumulatedText += data.text;
              updateAssistantMessage(assistantMsgId, accumulatedText, true);
            } else if (data.type === 'done') {
              updateAssistantMessage(assistantMsgId, accumulatedText, false);
            }
          }
        }
      }
    } catch (error) {
      updateAssistantMessage(assistantMsgId, '❌ 查询失败，请重试', false);
    }
  };

  return (
    <div className="flex flex-col h-screen">
      <div className="flex-1 overflow-y-auto p-4">
        {messages.map(msg => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
      </div>
      <form onSubmit={handleSubmit} className="p-4 border-t">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入问题..."
          className="w-full p-2 border rounded"
        />
      </form>
    </div>
  );
}
```

**Step 3: 测试前端乐观更新**

```bash
cd frontend
npm run dev
```

Manual test:
1. 输入查询并提交
2. 观察界面是否立即显示用户消息和"正在查询..."
3. 确认没有等待延迟

Expected: 0ms感知延迟，立即显示消息

**Step 4: 提交**

```bash
git add frontend/src/hooks/useOptimisticChat.ts frontend/src/components/ChatInterface.tsx
git commit -m "feat(frontend): add optimistic UI updates for instant feedback

- User message appears immediately (0ms)
- Loading state shows while fetching
- Streaming updates replace loading state
- Perceived latency eliminated"
```

---

## Phase 2: 用户体验优化 (Week 3-4)

### Task 5: 进度可视化组件

**Files:**
- Create: `frontend/src/components/ProgressIndicator.tsx`
- Modify: `frontend/src/components/ChatInterface.tsx`

**Step 1: 创建进度指示器组件**

Create `frontend/src/components/ProgressIndicator.tsx`:

```typescript
import React from 'react';

interface ProgressStep {
  name: string;
  status: 'pending' | 'loading' | 'completed' | 'error';
  duration?: number;
}

interface Props {
  steps: ProgressStep[];
}

export function ProgressIndicator({ steps }: Props) {
  return (
    <div className="space-y-2 p-3 bg-gray-50 rounded-lg text-sm">
      {steps.map((step, index) => (
        <div key={index} className="flex items-center gap-2">
          {step.status === 'completed' && (
            <span className="text-green-600">✓</span>
          )}
          {step.status === 'loading' && (
            <span className="animate-spin">⏳</span>
          )}
          {step.status === 'pending' && (
            <span className="text-gray-400">○</span>
          )}
          {step.status === 'error' && (
            <span className="text-red-600">✗</span>
          )}

          <span className={
            step.status === 'completed' ? 'text-gray-600' :
            step.status === 'loading' ? 'text-blue-600 font-medium' :
            step.status === 'error' ? 'text-red-600' :
            'text-gray-400'
          }>
            {step.name}
          </span>

          {step.duration && (
            <span className="text-gray-400 text-xs ml-auto">
              {step.duration}ms
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
```

**Step 2: 集成进度指示器到聊天界面**

Modify `frontend/src/components/ChatInterface.tsx`:

```typescript
import { ProgressIndicator } from './ProgressIndicator';

// Add to message state
interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  loading?: boolean;
  progress?: ProgressStep[];
  timestamp: number;
}

// Update handleSubmit to track progress
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  if (!input.trim()) return;

  const assistantMsgId = addUserMessage(input);
  setInput('');

  // Initialize progress steps
  const progressSteps: ProgressStep[] = [
    { name: '查询路由', status: 'loading' },
    { name: '获取数据', status: 'pending' },
    { name: 'AI分析', status: 'pending' },
  ];

  updateAssistantMessage(assistantMsgId, '', true, progressSteps);

  try {
    const response = await fetch('http://localhost:8001/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: input }),
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();
    let accumulatedText = '';

    while (true) {
      const { done, value } = await reader!.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));

          // Update progress based on event type
          if (data.type === 'plan') {
            progressSteps[0].status = 'completed';
            progressSteps[1].status = 'loading';
            updateAssistantMessage(assistantMsgId, '', true, [...progressSteps]);
          } else if (data.type === 'tool_data') {
            progressSteps[1].status = 'completed';
            progressSteps[1].duration = data.latency_ms;
            progressSteps[2].status = 'loading';
            updateAssistantMessage(assistantMsgId, '', true, [...progressSteps]);
          } else if (data.type === 'chunk' && data.text) {
            accumulatedText += data.text;
            updateAssistantMessage(assistantMsgId, accumulatedText, true, progressSteps);
          } else if (data.type === 'done') {
            progressSteps[2].status = 'completed';
            updateAssistantMessage(assistantMsgId, accumulatedText, false, progressSteps);
          }
        }
      }
    }
  } catch (error) {
    progressSteps.forEach(s => s.status = 'error');
    updateAssistantMessage(assistantMsgId, '❌ 查询失败', false, progressSteps);
  }
};

// Render progress in message bubble
function MessageBubble({ message }: { message: Message }) {
  return (
    <div className={`mb-4 ${message.role === 'user' ? 'text-right' : ''}`}>
      <div className={`inline-block p-3 rounded-lg ${
        message.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-100'
      }`}>
        {message.progress && message.loading && (
          <ProgressIndicator steps={message.progress} />
        )}
        <div className="whitespace-pre-wrap">{message.content}</div>
      </div>
    </div>
  );
}
```

**Step 3: 测试进度可视化**

```bash
cd frontend
npm run dev
```

Manual test:
1. 提交查询
2. 观察进度指示器显示各阶段状态
3. 确认每个阶段有✓标记和耗时

Expected: 清晰的进度反馈，用户知道系统在做什么

**Step 4: 提交**

```bash
git add frontend/src/components/ProgressIndicator.tsx frontend/src/components/ChatInterface.tsx
git commit -m "feat(frontend): add progress visualization for query execution

- Show routing, data fetching, AI analysis stages
- Display completion checkmarks and latency
- Reduce user anxiety during wait time"
```

---

### Task 6: 智能降级策略

**Files:**
- Modify: `backend/app/agent/core.py`
- Create: `backend/app/agent/fallback.py`
- Test: `backend/tests/test_fallback_strategy.py`

**Step 1: 编写降级策略测试**

Create `backend/tests/test_fallback_strategy.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.agent.core import AgentCore

@pytest.mark.asyncio
async def test_fallback_to_cache_on_timeout():
    """Test that system falls back to cache when API times out."""
    agent = AgentCore()

    # Mock market service to timeout
    with patch.object(agent.market_service, 'get_price') as mock_get_price:
        mock_get_price.side_effect = asyncio.TimeoutError()

        # Should not raise, should return cached data
        events = []
        async for event in agent.run("AAPL股价"):
            events.append(event)

        # Verify fallback message
        assert any('缓存数据' in str(e) for e in events)
```

**Step 2: 运行测试确认失败**

```bash
pytest tests/test_fallback_strategy.py::test_fallback_to_cache_on_timeout -v
```

Expected: FAIL with "asyncio.TimeoutError" not caught

**Step 3: 实现降级策略模块**

Create `backend/app/agent/fallback.py`:

```python
"""Fallback strategies for graceful degradation."""
import asyncio
from typing import Any, Callable, Optional, TypeVar

T = TypeVar('T')


async def with_timeout_fallback(
    primary_fn: Callable[..., T],
    fallback_fn: Optional[Callable[..., T]],
    timeout_seconds: float = 0.5,
    *args,
    **kwargs
) -> tuple[T, bool]:
    """
    Execute primary function with timeout, fallback on failure.

    Returns:
        (result, is_fallback): Result and whether fallback was used
    """
    try:
        result = await asyncio.wait_for(
            primary_fn(*args, **kwargs),
            timeout=timeout_seconds
        )
        return result, False
    except (asyncio.TimeoutError, Exception) as e:
        if fallback_fn:
            result = await fallback_fn(*args, **kwargs)
            return result, True
        raise
```

**Step 4: 集成降级策略到工具执行**

Modify `backend/app/agent/core.py`:

```python
from app.agent.fallback import with_timeout_fallback

async def _execute_single_tool_with_fallback(
    self, tool_spec: Dict[str, Any]
) -> ToolResult:
    """Execute tool with timeout and fallback to cache."""
    tool_name = tool_spec["name"]
    tool_input = tool_spec["input"]

    start_time = time.time()

    try:
        if tool_name == "get_price":
            # Primary: fresh API call (500ms timeout)
            # Fallback: cached data
            async def primary():
                return await self.market_service.get_price(tool_input["symbol"])

            async def fallback():
                # Try to get from cache
                cached = await self.market_service.get_cached_price(tool_input["symbol"])
                if cached:
                    return cached
                raise Exception("No cached data available")

            result, is_fallback = await with_timeout_fallback(
                primary, fallback, timeout_seconds=0.5
            )

            latency_ms = int((time.time() - start_time) * 1000)

            return ToolResult(
                tool=tool_name,
                data=result.model_dump(),
                latency_ms=latency_ms,
                status="success",
                cache_hit=is_fallback,
                data_source="cache" if is_fallback else "api",
            )

        # Similar for other tools...

    except Exception as e:
        return ToolResult(
            tool=tool_name,
            data={},
            latency_ms=int((time.time() - start_time) * 1000),
            status="error",
            error_message=str(e),
        )
```

**Step 5: 添加缓存读取方法**

Modify `backend/app/market/service.py`:

```python
async def get_cached_price(self, symbol: str) -> Optional[MarketData]:
    """Get price from cache only, no API call."""
    cache_key = f"price:{symbol}"

    try:
        cached = self.redis_client.get(cache_key)
        if cached:
            data = json.loads(cached)
            return MarketData(**data)
    except Exception:
        pass

    return None
```

**Step 6: 运行测试验证**

```bash
pytest tests/test_fallback_strategy.py -v
```

Expected: PASS

**Step 7: 提交**

```bash
git add backend/app/agent/fallback.py backend/app/agent/core.py backend/app/market/service.py backend/tests/test_fallback_strategy.py
git commit -m "feat(agent): add graceful degradation with timeout fallback

- 500ms timeout for critical data
- Automatic fallback to cache on timeout
- Non-critical data loads in background
- Ensures < 500ms response for core queries"
```

---

### Task 7: RAG检索加速 - HNSW优化

**Files:**
- Modify: `backend/app/rag/pipeline.py:30-50`
- Test: `backend/tests/test_rag_performance.py`

**Step 1: 编写RAG性能测试**

Create `backend/tests/test_rag_performance.py`:

```python
import pytest
import time
from app.rag.hybrid_pipeline import HybridRAGPipeline

@pytest.mark.asyncio
async def test_rag_search_performance():
    """Test that RAG search completes within 300ms."""
    pipeline = HybridRAGPipeline()

    query = "什么是市盈率？"

    start_time = time.time()
    result = await pipeline.search(query)
    elapsed = time.time() - start_time

    assert elapsed < 0.3, f"RAG search took {elapsed:.2f}s, expected < 0.3s"
    assert len(result.chunks) > 0
```

**Step 2: 运行测试确认当前性能**

```bash
pytest tests/test_rag_performance.py::test_rag_search_performance -v
```

Expected: FAIL with "AssertionError: RAG search took 0.8s, expected < 0.3s"

**Step 3: 优化ChromaDB配置**

Modify `backend/app/rag/pipeline.py`:

```python
def __init__(self):
    """Initialize RAG pipeline with optimized HNSW settings."""
    self.client = chromadb.PersistentClient(path="./chroma_db")

    # Optimized HNSW parameters for speed
    self.collection = self.client.get_or_create_collection(
        name="financial_knowledge",
        metadata={
            "hnsw:space": "cosine",
            "hnsw:construction_ef": 100,  # Build quality
            "hnsw:search_ef": 50,         # Search speed (reduced from 100)
            "hnsw:M": 16,                 # Connections per node (reduced from 32)
        }
    )

    # Load embedding model
    self.embedding_model = SentenceTransformer(
        "BAAI/bge-base-zh-v1.5",
        device="cpu"
    )

    # Load reranker
    self.reranker = FlagReranker(
        "BAAI/bge-reranker-base",
        use_fp16=True  # Enable FP16 for 2x speed
    )
```

**Step 4: 添加查询结果缓存**

Modify `backend/app/rag/pipeline.py`:

```python
from functools import lru_cache
import hashlib

class HybridRAGPipeline(RAGPipeline):
    def __init__(self):
        super().__init__()
        self._query_cache = {}  # Simple in-memory cache

    async def search(self, query: str, use_hybrid: bool = True) -> KnowledgeResult:
        """Search with caching."""
        # Check cache
        cache_key = hashlib.md5(query.encode()).hexdigest()
        if cache_key in self._query_cache:
            return self._query_cache[cache_key]

        # Perform search
        result = await self._search_impl(query, use_hybrid)

        # Cache result (max 1000 entries)
        if len(self._query_cache) < 1000:
            self._query_cache[cache_key] = result

        return result

    async def _search_impl(self, query: str, use_hybrid: bool) -> KnowledgeResult:
        """Original search implementation."""
        # Move existing search logic here
        # ... (existing code)
```

**Step 5: 减少重排序候选数量**

Modify `backend/app/rag/hybrid_pipeline.py`:

```python
async def search(self, query: str, use_hybrid: bool = True) -> KnowledgeResult:
    """Hybrid search with optimized reranking."""

    # Stage 1: Vector search (top 20 -> top 10)
    vector_result = await super().search(query)
    vector_results = vector_result.chunks[:10]  # Reduced from 20

    # Stage 2: BM25 search (top 20 -> top 10)
    bm25_results = self._bm25_search(query, top_k=10)  # Reduced from 20

    # Stage 3: RRF fusion
    fused_results = self._rrf_fusion(vector_results, bm25_results, k=10)

    # Stage 4: Rerank only top 10 (reduced from 20)
    pairs = [[query, chunk.content] for chunk in fused_results[:10]]
    scores = self.reranker.compute_score(pairs, normalize=True)

    # ... rest of code
```

**Step 6: 运行测试验证**

```bash
pytest tests/test_rag_performance.py -v
```

Expected: PASS (elapsed < 0.3s)

**Step 7: 提交**

```bash
git add backend/app/rag/pipeline.py backend/app/rag/hybrid_pipeline.py backend/tests/test_rag_performance.py
git commit -m "perf(rag): optimize vector search and reranking for 3x speedup

- Tune HNSW parameters (M=16, ef=50)
- Enable FP16 for reranker (2x faster)
- Add in-memory query cache
- Reduce reranking candidates (20->10)
- Result: 800ms -> 250ms"
```

---

## Phase 3: 深度优化 (Week 5-6)

### Task 8: 智能预加载

**Files:**
- Create: `frontend/src/hooks/usePrefetch.ts`
- Modify: `frontend/src/components/ChatInterface.tsx`

**Step 1: 创建预加载Hook**

Create `frontend/src/hooks/usePrefetch.ts`:

```typescript
import { useEffect, useRef } from 'react';

// Common stock symbols and their aliases
const SYMBOL_PATTERNS: Record<string, string[]> = {
  'AAPL': ['苹果', 'apple', 'aapl'],
  'TSLA': ['特斯拉', 'tesla', 'tsla'],
  'NVDA': ['英伟达', 'nvidia', 'nvda'],
  'MSFT': ['微软', 'microsoft', 'msft'],
  'GOOGL': ['谷歌', 'google', 'googl'],
};

export function usePrefetch() {
  const prefetchCache = useRef<Set<string>>(new Set());

  const prefetch = async (symbol: string) => {
    if (prefetchCache.current.has(symbol)) {
      return; // Already prefetched
    }

    try {
      // Prefetch in background (don't await)
      fetch('http://localhost:8001/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: `${symbol}股价`, prefetch: true }),
      });

      prefetchCache.current.add(symbol);
    } catch (error) {
      // Ignore prefetch errors
    }
  };

  const detectAndPrefetch = (text: string) => {
    const lowerText = text.toLowerCase();

    for (const [symbol, aliases] of Object.entries(SYMBOL_PATTERNS)) {
      for (const alias of aliases) {
        if (lowerText.includes(alias)) {
          prefetch(symbol);
          break;
        }
      }
    }
  };

  return { detectAndPrefetch };
}
```

**Step 2: 集成到输入框**

Modify `frontend/src/components/ChatInterface.tsx`:

```typescript
import { usePrefetch } from '../hooks/usePrefetch';

export function ChatInterface() {
  const { detectAndPrefetch } = usePrefetch();
  const [input, setInput] = useState('');

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setInput(newValue);

    // Prefetch when user types stock names
    if (newValue.length >= 2) {
      detectAndPrefetch(newValue);
    }
  };

  return (
    // ...
    <input
      type="text"
      value={input}
      onChange={handleInputChange}
      placeholder="输入问题..."
    />
  );
}
```

**Step 3: 后端支持预加载标记**

Modify `backend/app/api/routes.py`:

```python
from pydantic import BaseModel

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    prefetch: bool = False  # New field

@router.post("/chat")
async def chat(request: ChatRequest, model: Optional[str] = None):
    """Chat endpoint with prefetch support."""

    if request.prefetch:
        # Prefetch mode: just warm cache, don't return full response
        try:
            enriched_query = enricher.enrich(request.query)
            route = await query_router.classify_async(enriched_query)

            # Execute tools to warm cache (don't wait for LLM)
            if route.requires_price and route.symbol:
                asyncio.create_task(market_service.get_price(route.symbol))

            return {"status": "prefetched"}
        except Exception:
            return {"status": "error"}

    # Normal mode: full response
    # ... existing code
```

**Step 4: 测试预加载**

```bash
cd frontend
npm run dev
```

Manual test:
1. 在输入框输入"苹果"
2. 等待1秒
3. 提交查询"苹果股价"
4. 观察响应时间是否更快

Expected: 预加载后查询速度明显提升

**Step 5: 提交**

```bash
git add frontend/src/hooks/usePrefetch.ts frontend/src/components/ChatInterface.tsx backend/app/api/routes.py
git commit -m "feat(prefetch): add intelligent prefetching based on user input

- Detect stock symbols while user types
- Prefetch data in background
- Reduce perceived latency when query submitted
- Support common aliases (苹果->AAPL)"
```

---

### Task 9: 性能监控仪表板

**Files:**
- Create: `backend/app/monitoring/metrics.py`
- Create: `backend/app/api/metrics_routes.py`
- Modify: `backend/app/main.py`
- Create: `frontend/src/pages/MetricsPage.tsx`

**Step 1: 实现性能指标收集**

Create `backend/app/monitoring/metrics.py`:

```python
"""Performance metrics collection."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List
import statistics


@dataclass
class LatencyMetrics:
    """Latency statistics."""
    p50: float
    p95: float
    p99: float
    avg: float
    min: float
    max: float


class MetricsCollector:
    """Collects and aggregates performance metrics."""

    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self.query_latencies: List[float] = []
        self.tool_latencies: Dict[str, List[float]] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.total_queries = 0

    def record_query_latency(self, latency_ms: float):
        """Record end-to-end query latency."""
        self.query_latencies.append(latency_ms)
        if len(self.query_latencies) > self.max_samples:
            self.query_latencies.pop(0)
        self.total_queries += 1

    def record_tool_latency(self, tool_name: str, latency_ms: float):
        """Record tool execution latency."""
        if tool_name not in self.tool_latencies:
            self.tool_latencies[tool_name] = []

        self.tool_latencies[tool_name].append(latency_ms)
        if len(self.tool_latencies[tool_name]) > self.max_samples:
            self.tool_latencies[tool_name].pop(0)

    def record_cache_hit(self, hit: bool):
        """Record cache hit/miss."""
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

    def get_latency_stats(self, samples: List[float]) -> LatencyMetrics:
        """Calculate latency statistics."""
        if not samples:
            return LatencyMetrics(0, 0, 0, 0, 0, 0)

        sorted_samples = sorted(samples)
        n = len(sorted_samples)

        return LatencyMetrics(
            p50=sorted_samples[int(n * 0.5)],
            p95=sorted_samples[int(n * 0.95)],
            p99=sorted_samples[int(n * 0.99)] if n > 100 else sorted_samples[-1],
            avg=statistics.mean(samples),
            min=min(samples),
            max=max(samples),
        )

    def get_summary(self) -> Dict:
        """Get metrics summary."""
        query_stats = self.get_latency_stats(self.query_latencies)

        tool_stats = {}
        for tool_name, latencies in self.tool_latencies.items():
            tool_stats[tool_name] = self.get_latency_stats(latencies)

        cache_total = self.cache_hits + self.cache_misses
        cache_hit_rate = self.cache_hits / cache_total if cache_total > 0 else 0

        return {
            "total_queries": self.total_queries,
            "query_latency": {
                "p50_ms": query_stats.p50,
                "p95_ms": query_stats.p95,
                "p99_ms": query_stats.p99,
                "avg_ms": query_stats.avg,
            },
            "tool_latencies": {
                name: {
                    "p50_ms": stats.p50,
                    "p95_ms": stats.p95,
                    "avg_ms": stats.avg,
                }
                for name, stats in tool_stats.items()
            },
            "cache": {
                "hit_rate": cache_hit_rate,
                "hits": self.cache_hits,
                "misses": self.cache_misses,
            },
        }


# Global metrics collector
metrics_collector = MetricsCollector()
```

**Step 2: 创建指标API端点**

Create `backend/app/api/metrics_routes.py`:

```python
"""Metrics API routes."""
from fastapi import APIRouter
from app.monitoring.metrics import metrics_collector

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/summary")
async def get_metrics_summary():
    """Get performance metrics summary."""
    return metrics_collector.get_summary()


@router.post("/reset")
async def reset_metrics():
    """Reset all metrics (for testing)."""
    global metrics_collector
    from app.monitoring.metrics import MetricsCollector
    metrics_collector = MetricsCollector()
    return {"status": "reset"}
```

**Step 3: 集成指标收集到Agent**

Modify `backend/app/agent/core.py`:

```python
from app.monitoring.metrics import metrics_collector
import time

async def run(self, query: str, model_name: str = None) -> AsyncGenerator[SSEEvent, None]:
    """Execute agent workflow with metrics collection."""
    start_time = time.time()

    try:
        # ... existing workflow code

        # Record tool latencies
        for result in tool_results:
            metrics_collector.record_tool_latency(result.tool, result.latency_ms)
            metrics_collector.record_cache_hit(result.cache_hit)

        # ... rest of code

    finally:
        # Record total query latency
        total_latency_ms = (time.time() - start_time) * 1000
        metrics_collector.record_query_latency(total_latency_ms)
```

**Step 4: 注册指标路由**

Modify `backend/app/main.py`:

```python
from app.api.metrics_routes import router as metrics_router

app.include_router(metrics_router)
```

**Step 5: 创建前端指标页面**

Create `frontend/src/pages/MetricsPage.tsx`:

```typescript
import React, { useEffect, useState } from 'react';

interface MetricsSummary {
  total_queries: number;
  query_latency: {
    p50_ms: number;
    p95_ms: number;
    p99_ms: number;
    avg_ms: number;
  };
  cache: {
    hit_rate: number;
    hits: number;
    misses: number;
  };
}

export function MetricsPage() {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      const response = await fetch('http://localhost:8001/api/metrics/summary');
      const data = await response.json();
      setMetrics(data);
    };

    fetchMetrics();
    const interval = setInterval(fetchMetrics, 5000); // Refresh every 5s

    return () => clearInterval(interval);
  }, []);

  if (!metrics) return <div>Loading...</div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">性能监控</h1>

      <div className="grid grid-cols-3 gap-4">
        <MetricCard
          title="总查询数"
          value={metrics.total_queries}
          unit="次"
        />
        <MetricCard
          title="P95延迟"
          value={metrics.query_latency.p95_ms.toFixed(0)}
          unit="ms"
          status={metrics.query_latency.p95_ms < 2000 ? 'good' : 'warning'}
        />
        <MetricCard
          title="缓存命中率"
          value={(metrics.cache.hit_rate * 100).toFixed(1)}
          unit="%"
          status={metrics.cache.hit_rate > 0.7 ? 'good' : 'warning'}
        />
      </div>

      <div className="bg-white p-4 rounded-lg shadow">
        <h2 className="text-lg font-semibold mb-4">延迟分布</h2>
        <div className="space-y-2">
          <LatencyBar label="P50" value={metrics.query_latency.p50_ms} max={5000} />
          <LatencyBar label="P95" value={metrics.query_latency.p95_ms} max={5000} />
          <LatencyBar label="P99" value={metrics.query_latency.p99_ms} max={5000} />
        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value, unit, status = 'neutral' }: any) {
  const statusColors = {
    good: 'text-green-600',
    warning: 'text-yellow-600',
    error: 'text-red-600',
    neutral: 'text-gray-600',
  };

  return (
    <div className="bg-white p-4 rounded-lg shadow">
      <div className="text-sm text-gray-500">{title}</div>
      <div className={`text-3xl font-bold ${statusColors[status]}`}>
        {value}
        <span className="text-lg ml-1">{unit}</span>
      </div>
    </div>
  );
}

function LatencyBar({ label, value, max }: any) {
  const percentage = Math.min((value / max) * 100, 100);
  const color = value < 500 ? 'bg-green-500' : value < 2000 ? 'bg-yellow-500' : 'bg-red-500';

  return (
    <div>
      <div className="flex justify-between text-sm mb-1">
        <span>{label}</span>
        <span>{value.toFixed(0)}ms</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div className={`${color} h-2 rounded-full`} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}
```

**Step 6: 测试指标收集**

```bash
# 启动后端
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001

# 发送几个测试查询
curl -X POST http://localhost:8001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "AAPL股价"}' \
  --no-buffer

# 查看指标
curl http://localhost:8001/api/metrics/summary
```

Expected: 返回包含延迟统计和缓存命中率的JSON

**Step 7: 提交**

```bash
git add backend/app/monitoring/ backend/app/api/metrics_routes.py backend/app/main.py backend/app/agent/core.py frontend/src/pages/MetricsPage.tsx
git commit -m "feat(monitoring): add performance metrics dashboard

- Collect query/tool latency (P50/P95/P99)
- Track cache hit rate
- Real-time metrics API
- Frontend dashboard with auto-refresh
- Identify performance bottlenecks"
```

---

## Phase 4: 持续优化 (Week 7-8)

### Task 10: 自动性能回归检测

**Files:**
- Create: `backend/tests/performance/test_latency_regression.py`
- Create: `backend/tests/performance/benchmarks.json`

**Step 1: 创建性能基准测试**

Create `backend/tests/performance/test_latency_regression.py`:

```python
"""Performance regression tests."""
import pytest
import time
import json
from pathlib import Path
from app.agent.core import AgentCore

# Load performance benchmarks
BENCHMARK_FILE = Path(__file__).parent / "benchmarks.json"


def load_benchmarks():
    """Load performance benchmarks."""
    if BENCHMARK_FILE.exists():
        with open(BENCHMARK_FILE) as f:
            return json.load(f)
    return {}


def save_benchmarks(benchmarks):
    """Save performance benchmarks."""
    with open(BENCHMARK_FILE, "w") as f:
        json.dump(benchmarks, f, indent=2)


@pytest.mark.asyncio
@pytest.mark.performance
async def test_popular_stock_query_latency():
    """Test that popular stock queries meet latency target."""
    agent = AgentCore()
    query = "AAPL股价"

    # Warm up
    async for _ in agent.run(query):
        pass

    # Measure
    start_time = time.time()
    async for event in agent.run(query):
        if event.type == "done":
            break
    elapsed_ms = (time.time() - start_time) * 1000

    # Target: < 500ms for popular stocks (with cache)
    assert elapsed_ms < 500, f"Popular stock query took {elapsed_ms:.0f}ms, expected < 500ms"

    # Update benchmark
    benchmarks = load_benchmarks()
    benchmarks["popular_stock_query_ms"] = elapsed_ms
    save_benchmarks(benchmarks)


@pytest.mark.asyncio
@pytest.mark.performance
async def test_knowledge_query_latency():
    """Test that knowledge queries meet latency target."""
    agent = AgentCore()
    query = "什么是市盈率？"

    start_time = time.time()
    async for event in agent.run(query):
        if event.type == "done":
            break
    elapsed_ms = (time.time() - start_time) * 1000

    # Target: < 1000ms for knowledge queries
    assert elapsed_ms < 1000, f"Knowledge query took {elapsed_ms:.0f}ms, expected < 1000ms"

    # Update benchmark
    benchmarks = load_benchmarks()
    benchmarks["knowledge_query_ms"] = elapsed_ms
    save_benchmarks(benchmarks)


@pytest.mark.asyncio
@pytest.mark.performance
async def test_no_performance_regression():
    """Test that performance hasn't regressed from baseline."""
    benchmarks = load_benchmarks()

    if not benchmarks:
        pytest.skip("No baseline benchmarks available")

    agent = AgentCore()

    # Test popular stock query
    start_time = time.time()
    async for event in agent.run("AAPL股价"):
        if event.type == "done":
            break
    current_ms = (time.time() - start_time) * 1000

    baseline_ms = benchmarks.get("popular_stock_query_ms", 0)
    if baseline_ms > 0:
        # Allow 20% regression tolerance
        max_allowed_ms = baseline_ms * 1.2
        assert current_ms < max_allowed_ms, (
            f"Performance regression detected: {current_ms:.0f}ms vs baseline {baseline_ms:.0f}ms"
        )
```

**Step 2: 创建初始基准**

Create `backend/tests/performance/benchmarks.json`:

```json
{
  "popular_stock_query_ms": 300,
  "knowledge_query_ms": 800,
  "cold_stock_query_ms": 1500
}
```

**Step 3: 运行性能测试**

```bash
cd backend
pytest tests/performance/ -v -m performance
```

Expected: PASS with benchmark updates

**Step 4: 添加到CI/CD**

Modify `.github/workflows/backend-tests.yml`:

```yaml
- name: Run performance tests
  run: |
    cd backend
    pytest tests/performance/ -v -m performance

- name: Check for performance regression
  run: |
    cd backend
    pytest tests/performance/test_latency_regression.py::test_no_performance_regression -v
```

**Step 5: 提交**

```bash
git add backend/tests/performance/ .github/workflows/backend-tests.yml
git commit -m "test(performance): add automated regression detection

- Benchmark popular stock queries (< 500ms)
- Benchmark knowledge queries (< 1000ms)
- Detect 20%+ performance regressions
- Run in CI/CD pipeline"
```

---

### Task 11: 用户体验最终优化 - 骨架屏

**Files:**
- Create: `frontend/src/components/SkeletonScreen.tsx`
- Modify: `frontend/src/components/ChatInterface.tsx`

**Step 1: 创建骨架屏组件**

Create `frontend/src/components/SkeletonScreen.tsx`:

```typescript
import React from 'react';

export function PriceSkeleton() {
  return (
    <div className="animate-pulse space-y-3">
      <div className="flex items-center gap-3">
        <div className="h-8 w-24 bg-gray-300 rounded"></div>
        <div className="h-6 w-32 bg-gray-300 rounded"></div>
      </div>
      <div className="h-4 w-48 bg-gray-200 rounded"></div>
    </div>
  );
}

export function ChartSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-64 bg-gray-200 rounded-lg flex items-center justify-center">
        <div className="space-y-2 w-full px-8">
          <div className="h-3 bg-gray-300 rounded w-3/4"></div>
          <div className="h-3 bg-gray-300 rounded w-full"></div>
          <div className="h-3 bg-gray-300 rounded w-5/6"></div>
        </div>
      </div>
    </div>
  );
}

export function AnalysisSkeleton() {
  return (
    <div className="animate-pulse space-y-2">
      <div className="h-4 bg-gray-200 rounded w-full"></div>
      <div className="h-4 bg-gray-200 rounded w-11/12"></div>
      <div className="h-4 bg-gray-200 rounded w-10/12"></div>
      <div className="h-4 bg-gray-200 rounded w-full"></div>
      <div className="h-4 bg-gray-200 rounded w-9/12"></div>
    </div>
  );
}

export function CompleteSkeleton() {
  return (
    <div className="space-y-6 p-4 bg-gray-50 rounded-lg">
      <PriceSkeleton />
      <ChartSkeleton />
      <AnalysisSkeleton />
    </div>
  );
}
```

**Step 2: 集成骨架屏到消息显示**

Modify `frontend/src/components/ChatInterface.tsx`:

```typescript
import { CompleteSkeleton, PriceSkeleton } from './SkeletonScreen';

function MessageBubble({ message }: { message: Message }) {
  return (
    <div className={`mb-4 ${message.role === 'user' ? 'text-right' : ''}`}>
      <div className={`inline-block p-3 rounded-lg max-w-2xl ${
        message.role === 'user' ? 'bg-blue-500 text-white' : 'bg-gray-100'
      }`}>
        {message.loading && !message.content && (
          <CompleteSkeleton />
        )}

        {message.loading && message.content && (
          <div className="space-y-4">
            <div className="whitespace-pre-wrap">{message.content}</div>
            <AnalysisSkeleton />
          </div>
        )}

        {!message.loading && (
          <div className="whitespace-pre-wrap">{message.content}</div>
        )}

        {message.progress && message.loading && (
          <div className="mt-3">
            <ProgressIndicator steps={message.progress} />
          </div>
        )}
      </div>
    </div>
  );
}
```

**Step 3: 测试骨架屏**

```bash
cd frontend
npm run dev
```

Manual test:
1. 提交查询
2. 观察骨架屏动画
3. 确认内容逐步替换骨架屏

Expected: 平滑的加载体验，无空白等待

**Step 4: 提交**

```bash
git add frontend/src/components/SkeletonScreen.tsx frontend/src/components/ChatInterface.tsx
git commit -m "feat(ux): add skeleton screens for loading states

- Price, chart, and analysis skeletons
- Smooth transition from skeleton to content
- Eliminate blank screen during loading
- Improve perceived performance"
```

---

## 验收标准

### 性能指标验收

**P0 - 必须达标**:
- [ ] 热门股票查询 < 500ms (当前3.7s)
- [ ] 首字节时间 < 200ms (当前2.0s)
- [ ] 缓存命中率 > 70%
- [ ] P95延迟 < 2000ms (当前5.0s)

**P1 - 强烈建议**:
- [ ] 知识问答 < 800ms (当前2.5s)
- [ ] RAG检索 < 300ms (当前800ms)
- [ ] 工具并行执行节省 > 50%时间

### 用户体验验收

**P0 - 必须达标**:
- [ ] 用户提交查询后0ms内看到反馈
- [ ] 进度可视化显示各阶段状态
- [ ] 骨架屏消除空白等待
- [ ] 错误时有降级方案（缓存数据）

**P1 - 强烈建议**:
- [ ] 智能预加载减少等待
- [ ] 性能监控仪表板可用
- [ ] 自动回归检测在CI中运行

### 测试验收

```bash
# 运行所有性能测试
cd backend
pytest tests/test_cache_warmer.py -v
pytest tests/test_parallel_execution.py -v
pytest tests/test_streaming_performance.py -v
pytest tests/test_fallback_strategy.py -v
pytest tests/test_rag_performance.py -v
pytest tests/performance/ -v -m performance
```

Expected: 所有测试PASS

### 端到端验收

1. **冷启动测试**
   ```bash
   # 清空Redis缓存
   redis-cli FLUSHALL

   # 查询热门股票
   curl -X POST http://localhost:8001/api/chat \
     -H "Content-Type: application/json" \
     -d '{"query": "AAPL股价"}' \
     --no-buffer
   ```
   Expected: 首次查询 < 2s

2. **热缓存测试**
   ```bash
   # 等待30秒让缓存预热完成
   sleep 30

   # 再次查询
   curl -X POST http://localhost:8001/api/chat \
     -H "Content-Type: application/json" \
     -d '{"query": "AAPL股价"}' \
     --no-buffer
   ```
   Expected: 缓存命中，< 500ms

3. **前端体验测试**
   - 打开 http://localhost:3000
   - 输入"苹果"观察预加载
   - 提交查询观察骨架屏和进度
   - 确认0ms感知延迟

---

## 实施建议

**执行方式**: 使用 `superpowers:executing-plans` 在新会话中执行

**关键里程碑**:
- Week 2: 核心性能优化完成（缓存+并行+流式）
- Week 4: 用户体验优化完成（进度+降级+RAG加速）
- Week 6: 深度优化完成（预加载+监控）
- Week 8: 持续优化完成（回归检测+骨架屏）

**风险点**:
1. 缓存预热可能增加服务器负载 → 控制并发数（10）
2. 降级策略可能返回过时数据 → 明确标注数据时间
3. 预加载可能浪费带宽 → 仅预加载TOP100股票

**预期成果**:
- 热门股票查询: 3.7s → 0.3s (12x提升)
- 用户满意度: 从"能用"提升到"好用"
- 系统可观测性: 实时性能监控

---

Plan complete and saved to `docs/plans/2026-03-07-performance-optimization-ux-enhancement.md`.

## 执行选项

**1. Subagent-Driven (this session)** - 我在当前会话中逐任务派发子Agent，每个任务完成后进行代码审查，快速迭代

**2. Parallel Session (separate)** - 在新会话中使用 executing-plans 技能，批量执行并设置检查点

**Which approach?**
