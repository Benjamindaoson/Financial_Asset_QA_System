# 高级功能集成指南
# Advanced Features Integration Guide

## 概述

所有6个高级功能已完全集成到系统中，可通过统一的API接口访问。

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     API Layer (routes.py)                    │
│  /api/v1/enhanced/chat - 增强版聊天（集成所有功能）          │
│  /api/v1/enhanced/price - 多数据源验证价格查询               │
│  /api/v1/enhanced/change - 深度涨跌分析                      │
│  /api/v1/enhanced/knowledge - 意图识别知识检索               │
│  /api/v1/enhanced/route - 查询分类与置信度评估               │
│  /api/v1/enhanced/format - 智能格式化                        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              EnhancedAgentCore (enhanced_core.py)            │
│  - 统一入口：run_enhanced()                                  │
│  - 流程编排：路由→处理→格式化→错误处理                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────┬──────────────────┬──────────────────────┐
│ EnhancedMarket   │ EnhancedRAG      │ EnhancedRouter       │
│ DataService      │ Pipeline         │                      │
│ - 多源验证       │ - 意图识别       │ - 置信度评估         │
│ - 深度涨跌分析   │ - 自适应回答     │ - 混合查询拆解       │
└──────────────────┴──────────────────┴──────────────────────┘
                              ↓
┌──────────────────┬──────────────────────────────────────────┐
│ SmartFormatter   │ FriendlyErrorHandler                     │
│ - 6种数据类型    │ - 友好错误提示                           │
│ - 自动格式选择   │ - 智能降级                               │
└──────────────────┴──────────────────────────────────────────┘
```

## 使用方式

### 方式1: 使用增强版聊天接口（推荐）

这是最简单的方式，自动集成所有高级功能。

```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AAPL最新价格是多少？最近7天涨跌情况如何？",
    "enable_validation": true,
    "enable_intent_recognition": true
  }'
```

**功能特性**:
- ✅ 自动识别查询类型（置信度评估）
- ✅ 混合查询自动拆解
- ✅ 多数据源交叉验证
- ✅ 深度涨跌分析
- ✅ 意图识别和自适应回答
- ✅ 智能格式化
- ✅ 友好错误处理

**响应格式** (SSE流式):
```json
data: {"type": "status", "text": "🔍 智能分析查询意图..."}
data: {"type": "route_decision", "data": {"route": "price", "confidence": 0.95}}
data: {"type": "tool_start", "data": {"name": "get_price_validated", "symbol": "AAPL"}}
data: {"type": "tool_data", "data": {"price": 178.50, "consistency": "high"}}
data: {"type": "chunk", "text": "📊 AAPL 当前价格：178.50 USD"}
data: {"type": "done", "data": {"formatted": {...}}}
data: [DONE]
```

### 方式2: 使用独立功能接口

如果只需要特定功能，可以直接调用对应接口。

#### 2.1 多数据源验证价格查询

```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/price?symbol=AAPL&validate=true"
```

**响应**:
```json
{
  "price": 178.50,
  "currency": "USD",
  "consistency": "high",
  "confidence": "high",
  "validated": true,
  "details": {
    "message": "数据一致性良好，3个数据源偏差 ≤ 1%",
    "individual_prices": [
      {"source": "yfinance", "price": 178.52},
      {"source": "alpha_vantage", "price": 178.48},
      {"source": "finnhub", "price": 178.51}
    ],
    "median": 178.51,
    "mean": 178.50,
    "std_dev": 0.02
  }
}
```

#### 2.2 深度涨跌分析

```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/change?symbol=AAPL&days=7"
```

**响应**:
```json
{
  "price_change": {
    "change_percent": 5.2,
    "change_amount": 8.75,
    "trend": "上涨"
  },
  "volume_analysis": {
    "pattern": "放量上涨",
    "interpretation": "✅ 量价配合良好，上涨趋势健康",
    "volume_change_percent": 15.3
  },
  "relative_strength": {
    "performance": "跑赢大盘",
    "vs_market": 3.5,
    "interpretation": "✅ 强于大盘 3.5%"
  },
  "key_events": [],
  "conclusion": "该股票呈现强势上涨态势，放量上涨。相对大盘表现为跑赢大盘。整体表现强劲，趋势健康。"
}
```

#### 2.3 意图识别知识检索

```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/knowledge" \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是市盈率"}'
```

**响应**:
```json
{
  "intent": "definition",
  "user_level": "beginner",
  "answer": {
    "main_answer": "💡 简单来说：\n\n市盈率是股价除以每股收益...",
    "confidence": "high",
    "related_topics": ["市净率", "估值方法", "财务指标"]
  },
  "documents": [...]
}
```

#### 2.4 查询分类与置信度评估

```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/route" \
  -H "Content-Type: application/json" \
  -d '{"query": "特斯拉"}'
```

**响应（高置信度）**:
```json
{
  "route": "price",
  "confidence": 0.85,
  "entities": {
    "symbols": ["TSLA"]
  }
}
```

**响应（低置信度 - 需要澄清）**:
```json
{
  "route": "clarification_needed",
  "confidence": 0.65,
  "original_route": "price",
  "clarification": {
    "message": "我不太确定您的问题类型，请选择：",
    "options": [
      {"type": "price", "label": "查询 TSLA 的当前价格"},
      {"type": "change", "label": "查询 TSLA 的涨跌情况"},
      {"type": "knowledge", "label": "了解相关金融知识"}
    ]
  }
}
```

#### 2.5 智能格式化

```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/format" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "AAPL和TSLA对比",
    "data": {
      "AAPL": {"price": 178.50, "change": 2.5},
      "TSLA": {"price": 245.30, "change": -1.2}
    }
  }'
```

**响应**:
```json
{
  "type": "table",
  "data": {
    "headers": ["股票", "价格", "涨跌幅"],
    "rows": [
      ["AAPL", "178.50", "+2.5%"],
      ["TSLA", "245.30", "-1.2%"]
    ]
  },
  "caption": "对比数据"
}
```

## 配置选项

### 环境变量

在 `.env` 文件中配置：

```bash
# 启用/禁用高级功能
ENABLE_MULTI_SOURCE_VALIDATION=true
ENABLE_INTENT_RECOGNITION=true
ENABLE_SMART_FORMATTING=true
ENABLE_FRIENDLY_ERRORS=true

# 置信度阈值
CONFIDENCE_THRESHOLD=0.8

# 数据源配置
ALPHA_VANTAGE_API_KEY=your_key
FINNHUB_API_KEY=your_key
```

### 代码配置

```python
from app.agent.enhanced_core import EnhancedAgentCore

agent = EnhancedAgentCore()

# 运行增强版查询
async for event in agent.run_enhanced(
    query="AAPL最新价格",
    enable_validation=True,        # 启用多数据源验证
    enable_intent_recognition=True # 启用意图识别
):
    print(event)
```

## 性能优化

### 1. 并行处理

混合查询自动并行处理：

```python
# 查询: "AAPL价格多少？TSLA涨跌如何？"
# 自动拆解为2个子查询并并行执行
sub_queries = [
    {"query": "AAPL价格多少", "type": "price"},
    {"query": "TSLA涨跌如何", "type": "change"}
]
results = await asyncio.gather(*[process(q) for q in sub_queries])
```

### 2. 缓存策略

多数据源验证结果自动缓存：

```python
# 第一次查询：调用3个数据源
result1 = await service.get_price_with_validation("AAPL")  # ~500ms

# 5分钟内再次查询：使用缓存
result2 = await service.get_price_with_validation("AAPL")  # ~10ms
```

### 3. 降级策略

当部分功能不可用时自动降级：

```python
# LLM不可用 → 使用模板回答
# API限流 → 使用缓存数据
# 部分数据源失败 → 使用可用数据源
```

## 错误处理

所有接口都提供友好的错误信息：

```json
{
  "error": "symbol_not_found",
  "message": "未找到股票：苹果公司",
  "suggestions": [
    {
      "symbol": "AAPL",
      "name": "苹果",
      "confidence": "high",
      "reason": "精确匹配"
    }
  ],
  "help": {
    "title": "您可以尝试：",
    "options": [
      "使用标准股票代码（如 AAPL、TSLA）",
      "使用中文名称（如 苹果、特斯拉）",
      "检查拼写是否正确"
    ]
  },
  "examples": [
    "AAPL最新价格",
    "特斯拉股价",
    "600519.SS涨跌情况"
  ]
}
```

## 测试示例

### 测试1: 简单价格查询

```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "AAPL最新价格"}'
```

**预期结果**:
- 路由类型: price
- 置信度: > 0.8
- 数据验证: 3个数据源
- 一致性: high

### 测试2: 混合查询

```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "AAPL现在多少钱？最近7天涨了多少？市盈率是什么？"}'
```

**预期结果**:
- 检测到3个子查询
- 并行处理
- 整合答案（价格 + 涨跌 + 知识）

### 测试3: 低置信度查询

```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "特斯拉"}'
```

**预期结果**:
- 置信度 < 0.8
- 返回澄清选项
- 用户选择后继续

### 测试4: 错误处理

```bash
curl -X POST "http://localhost:8000/api/v1/enhanced/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "苹果公司股价"}'
```

**预期结果**:
- 识别"苹果公司"
- 建议使用"AAPL"
- 提供示例查询

## 监控和日志

所有增强功能的调用都会记录到监控系统：

```bash
# 查看性能指标
curl "http://localhost:8000/api/monitoring/metrics"

# 查看响应时间统计
curl "http://localhost:8000/api/monitoring/response-times"
```

## 总结

所有6个高级功能已完全集成：

1. ✅ **多数据源交叉验证** - `EnhancedMarketDataService`
2. ✅ **深度涨跌分析** - `EnhancedMarketDataService`
3. ✅ **意图识别和自适应回答** - `EnhancedRAGPipeline`
4. ✅ **混合查询处理** - `EnhancedQueryRouter`
5. ✅ **智能格式化** - `SmartFormatter`
6. ✅ **友好错误处理** - `FriendlyErrorHandler`

统一入口：`EnhancedAgentCore.run_enhanced()`

API接口：`/api/v1/enhanced/*`

可独立使用，也可组合使用，提供灵活的集成方式。
