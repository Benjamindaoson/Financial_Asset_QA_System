# 金融资产问答系统 — 设计文档

**日期：** 2026-03-04
**状态：** 已确认

---

## 一、项目概述

基于大模型的全栈金融资产问答系统，核心能力：
1. 资产价格与涨跌分析（调用外部行情 API）
2. 金融知识问答（基于 RAG）
3. 结构化、专业、数据驱动的回答生成

---

## 二、系统架构

```
┌─────────────────────────────────────────────────────┐
│                   React + Vite 前端                   │
│         聊天界面 / 股价图表 / 数据卡片展示             │
└────────────────────┬────────────────────────────────┘
                     │ HTTP / SSE 流式输出
┌────────────────────▼────────────────────────────────┐
│                FastAPI 后端                           │
│                                                       │
│  ┌─────────────┐    ┌──────────────────────────────┐ │
│  │ 意图路由器   │───▶│        Agent 核心             │ │
│  │(LLM分类)    │    │  Claude API + Tool Use        │ │
│  └─────────────┘    └──────┬───────────┬───────────┘ │
│                            │           │              │
│              ┌─────────────▼─┐  ┌──────▼──────────┐  │
│              │  行情工具集    │  │   RAG 模块       │  │
│              │  yfinance      │  │  ChromaDB        │  │
│              │  (价格/涨跌)   │  │  (金融知识库)    │  │
│              └───────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**数据流：**
1. 用户输入 → FastAPI 接收
2. 意图路由器（Claude 分类）判断：MARKET_QUERY / KNOWLEDGE_QA / MIXED
3. 行情类 → Tool Use 调用 yfinance → 结构化数据 → Claude 生成分析
4. 知识类 → ChromaDB 向量检索 → 相关文档 → Claude 生成回答
5. SSE 流式输出返回前端

---

## 三、技术选型

| 层 | 技术 | 说明 |
|----|------|------|
| 后端框架 | FastAPI + uvicorn | 高性能，支持 SSE 流式输出 |
| LLM | Claude API (claude-sonnet-4-6) | Tool Use 能力强，减少 hallucination |
| 行情数据 | yfinance | 免费，支持 A股/美股/加密货币 |
| 向量数据库 | ChromaDB | 本地运行，零配置，Python 原生 |
| Embedding | sentence-transformers | 本地 Embedding，无需额外 API |
| 前端框架 | React + Vite | 轻量，开发体验好 |
| 图表 | Recharts | React 原生图表库 |
| 流式传输 | Server-Sent Events (SSE) | 实现打字机效果 |

---

## 四、核心模块设计

### 4.1 意图路由器

三类意图：
- `MARKET_QUERY`：涉及具体资产的价格、涨跌、走势
- `KNOWLEDGE_QA`：金融概念、术语解释、通用知识
- `MIXED`：既需行情数据又需背景分析（如"某股大涨原因"）

### 4.2 行情工具集（Claude Tool Use）

| 工具名 | 功能 |
|--------|------|
| `get_current_price` | 获取实时/最新价格 |
| `get_price_history` | 获取 N 天历史行情 |
| `calc_price_change` | 计算涨跌幅 |
| `get_stock_info` | 获取公司基本信息 |
| `search_news` | 搜索相关新闻（用于原因分析）|

### 4.3 RAG 模块

```
知识库构建：
  PDF/MD 文档 → 分块 (chunk_size=512, overlap=50)
             → Embedding (sentence-transformers)
             → ChromaDB 存储

查询流程：
  问题 → Embedding → 向量相似检索 (Top-K=3)
       → 拼接上下文 → Claude 生成回答
```

### 4.4 统一回答结构

```
📊 数据摘要      ← 客观数据，标注来源（yfinance / 知识库）
📈 趋势分析      ← 结构化总结（上涨 / 下跌 / 震荡）
🔍 影响因素      ← 基于新闻/事件的分析性描述
⚠️ 免责声明      ← 明确区分数据与分析，不构成投资建议
```

---

## 五、项目结构

```
financial-qa-system/
├── backend/
│   ├── main.py                 # FastAPI 入口
│   ├── routers/
│   │   └── chat.py             # /api/chat 接口（SSE 流式）
│   ├── agent/
│   │   ├── intent_router.py    # 意图分类
│   │   ├── market_tools.py     # yfinance 工具集
│   │   └── agent_core.py       # Claude Tool Use 主循环
│   ├── rag/
│   │   ├── knowledge_base.py   # 文档加载与分块
│   │   ├── embeddings.py       # 向量化
│   │   └── retriever.py        # ChromaDB 检索
│   └── data/
│       └── knowledge/          # 金融知识文档（PDF/MD）
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx  # 对话主界面
│   │   │   ├── MessageBubble.tsx
│   │   │   └── StockChart.tsx  # 价格走势图
│   │   └── App.tsx
│   └── package.json
├── docs/
│   └── plans/
└── README.md
```

---

## 六、Prompt 设计思路

### 系统 Prompt
```
你是一个专业的金融资产分析助手。
规则：
1. 行情数据必须来自工具调用结果，禁止凭记忆生成价格数字
2. 分析性描述必须明确标注"分析"字样与信息来源
3. 回答格式：数据摘要 → 趋势分析 → 影响因素 → 免责声明
4. 若工具调用失败，明确告知用户数据不可用，不得编造
5. 不对未来走势做预测
```

### 意图分类 Prompt
```
判断以下问题属于哪类：
- MARKET_QUERY：涉及具体资产的价格、涨跌、走势
- KNOWLEDGE_QA：金融概念、术语解释、通用知识
- MIXED：既需行情数据又需背景分析
```

---

## 七、错误处理策略

| 场景 | 处理方式 |
|------|----------|
| yfinance 请求失败 | 返回"数据暂时不可用"，不生成假数据 |
| 股票代码识别不到 | 自动尝试别名（BABA → 9988.HK） |
| RAG 检索无结果 | 降级到 Claude 通用知识，明确标注"基于模型知识" |
| API 超时 | 前端显示加载状态，后端 30s 超时保护 |

---

## 八、数据来源说明

- **实时行情**：Yahoo Finance（yfinance），支持美股、A股、港股、加密货币
- **金融知识库**：手动整理的 PDF/Markdown 文档（财务基础知识、常见指标解释等）
- **新闻数据**：yfinance news API（用于事件驱动分析）

---

## 九、优化与扩展方向

1. **多轮对话记忆**：加入对话历史管理，支持追问
2. **更多数据源**：接入 Alpha Vantage、财联社等
3. **实时推送**：WebSocket 支持价格实时更新
4. **用户系统**：收藏股票、历史问答记录
5. **模型切换**：支持 DeepSeek 等低成本模型
