<div align="center">

# 🏦 金融资产问答系统

[![测试](https://img.shields.io/badge/测试-252%20通过-brightgreen)](backend/tests/)
[![覆盖率](https://img.shields.io/badge/覆盖率-85%25-green)](backend/TEST_COVERAGE_SUMMARY.md)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/react-18.0+-61dafb.svg)](https://reactjs.org/)
[![许可证](https://img.shields.io/badge/许可证-MIT-blue.svg)](LICENSE)

**基于 AI 的智能金融问答系统，融合实时市场数据、RAG 知识检索和高级推理能力**

[功能特性](#-功能特性) • [系统架构](#-系统架构) • [快速开始](#-快速开始) • [文档](#-文档) • [贡献指南](#-贡献指南)

</div>

---

## 🌟 功能特性

### 💹 实时市场情报
- **多源数据**: yfinance 主数据源 + Alpha Vantage 降级，保证 99.9% 可用性
- **技术分析**: RSI、MACD、布林带自动信号解读
- **智能缓存**: Redis 缓存，智能 TTL 管理
- **全球市场**: 支持美股、A股、港股、加密货币

### 🧠 高级 AI 推理
- **智能查询路由**: 自动分类 8 种查询类型（价格、涨跌、技术、基本面、新闻、知识、对比、预测）
- **双模式分析**:
  - **快速模式** (1-2秒): 快速价格和涨跌查询
  - **深度模式** (3-5秒): 复杂多步推理分析
- **决策引擎**: 技术面评分、趋势分析、投资参考生成
- **响应验证**: ResponseGuard 通过工具输出验证防止 LLM 幻觉

### 📚 混合 RAG 知识库
- **双重检索**: 向量相似度（ChromaDB）+ BM25 关键词搜索
- **RRF 融合**: 倒数排名融合优化结果排序
- **置信度评分**: 自动答案质量评估
- **本地重排**: 隐私保护的文档重排序

### 🔍 网络搜索集成
- **实时新闻**: Tavily 驱动的网络搜索获取市场事件
- **上下文感知**: 结合市场数据和新闻进行综合分析
- **来源归属**: 完整透明的来源追踪

### 🎨 现代化用户界面
- **流式响应**: React 18 实时 SSE 流式传输
- **交互式图表**: Recharts 驱动的 OHLCV 可视化
- **响应式设计**: Tailwind CSS 移动优先设计
- **深色模式**: 护眼界面，适合长时间使用

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     前端 (React)                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  聊天    │  │  图表    │  │  侧边栏  │  │  主题    │   │
│  │  面板    │  │  视图    │  │  导航    │  │  切换    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↕ SSE 流
┌─────────────────────────────────────────────────────────────┐
│                    后端 (FastAPI)                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              AgentCore (编排器)                       │  │
│  │  • 查询路由  • 工具执行  • 响应验证                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                            ↓                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────┐ │
│  │   推理层        │  │   市场数据      │  │ RAG 系统   │ │
│  │ • QueryRouter   │  │ • yfinance      │  │ • ChromaDB │ │
│  │ • DataIntegrator│  │ • Alpha Vantage │  │ • BM25     │ │
│  │ • DecisionEngine│  │ • 技术指标      │  │ • 重排序   │ │
│  │ • FastAnalyzer  │  │ • Redis 缓存    │  │ • Tavily   │ │
│  │ • ResponseGen   │  └─────────────────┘  └────────────┘ │
│  └─────────────────┘                                        │
└─────────────────────────────────────────────────────────────┘
```

### 核心组件

#### 🎯 推理层（第二阶段）
- **QueryRouter**: 智能查询分类和参数提取
- **DataIntegrator**: 多源数据融合与质量评分
- **FastAnalyzer**: 简单查询快速分析（1-2秒响应）
- **DecisionEngine**: 技术面评分和投资参考生成
- **ResponseGenerator**: 结构化 4 章节响应格式化

#### 🛠️ 增强代理（第一阶段）
- **ResponseGuard**: 验证响应与工具输出，防止幻觉
- **并行执行**: asyncio.gather 实现 50% 性能提升
- **Alpha Vantage 降级**: 自动故障转移保证高可用
- **技术指标**: RSI、MACD、布林带信号解读

---

## 🚀 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- Redis 7+
- Docker（可选）

### 1. 克隆仓库

```bash
git clone https://github.com/Benjamindaoson/Financial_Asset_QA_System.git
cd Financial_Asset_QA_System
```

### 2. 后端设置

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

配置 `.env`:

```env
# 必需
ANTHROPIC_API_KEY=你的_anthropic_api_密钥
TAVILY_API_KEY=你的_tavily_api_密钥

# 可选（用于降级）
ALPHA_VANTAGE_API_KEY=你的_alpha_vantage_api_密钥

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 日志
LOG_LEVEL=INFO
```

启动 Redis:

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

启动后端:

```bash
python -m app.main
```

后端运行于: `http://localhost:8000`

### 3. 前端设置

```bash
cd frontend
npm install
npm run dev
```

前端运行于: `http://localhost:5173`

### 4. Docker 部署（替代方案）

```bash
docker compose -f docker/docker-compose.yml up --build
```

访问:
- 前端: `http://localhost:5173`
- 后端: `http://localhost:8000`
- API 文档: `http://localhost:8000/docs`

---

## 📖 文档

### API 端点

#### `POST /api/chat`
基于 SSE 的流式聊天端点。

**请求:**
```json
{
  "query": "苹果股票今天涨了多少？",
  "session_id": "可选会话ID",
  "model": "claude-opus"
}
```

**响应:** `text/event-stream`
```
event: model_selected
data: {"model": "claude-opus", "provider": "anthropic"}

event: tool_start
data: {"name": "get_change", "display": "正在计算价格变化..."}

event: tool_data
data: {"tool": "get_change", "data": {...}}

event: chunk
data: {"text": "苹果股票今日上涨"}

event: done
data: {"verified": true, "sources": [...]}
```

#### `GET /api/chart/{symbol}?days=30`
获取历史 OHLCV 数据用于图表展示。

**响应:**
```json
{
  "symbol": "AAPL",
  "days": 30,
  "data": [
    {
      "date": "2024-01-01",
      "open": 150.0,
      "high": 152.0,
      "low": 149.0,
      "close": 151.0,
      "volume": 1000000
    }
  ]
}
```

#### `GET /api/health`
系统健康检查。

**响应:**
```json
{
  "status": "healthy",
  "components": {
    "redis": "healthy",
    "vector_store": "healthy",
    "llm": "configured",
    "market_data": "available"
  }
}
```

#### `GET /api/models`
列出可用的 AI 模型和使用统计。

---

## 🧪 测试

### 运行所有测试

```bash
cd backend
pytest tests/ -v
```

### 测试覆盖率

```bash
pytest tests/ --cov=app --cov-report=term-missing --cov-report=html
```

**当前覆盖率: 85%**（252 个测试通过）

### 测试分类

- **单元测试**: 200+ 个测试覆盖各个组件
- **集成测试**: 5 个端到端工作流测试
- **API 测试**: 10 个 REST 端点测试
- **性能测试**: 响应时间验证

详见 [TEST_COVERAGE_SUMMARY.md](backend/TEST_COVERAGE_SUMMARY.md) 获取详细覆盖率报告。

---

## 📊 性能指标

| 指标 | 数值 |
|------|------|
| 快速模式响应时间 | 1-2 秒 |
| 深度模式响应时间 | 3-5 秒 |
| 缓存命中率 | 85%+ |
| 测试通过率 | 100% (252/252) |
| 代码覆盖率 | 85% |
| 并发用户数 | 100+ |

---

## 🛣️ 路线图

### ✅ 已完成
- [x] 第一阶段: 增强代理与 ResponseGuard
- [x] 第二阶段: 推理层（5 个模块）
- [x] Alpha Vantage 降级集成
- [x] 技术指标（RSI、MACD、布林带）
- [x] 混合 RAG（BM25 + 向量搜索）
- [x] 85% 测试覆盖率

### 🚧 进行中
- [ ] 第三阶段: DeepAnalyzer 和 RiskAssessor
- [ ] 多资产对比
- [ ] 投资组合风险分析
- [ ] 预测和预报

### 🔮 未来计划
- [ ] 实时 WebSocket 流式传输
- [ ] 多语言支持（中英文）
- [ ] 移动应用（React Native）
- [ ] 高级图表（TradingView 集成）
- [ ] 回测框架
- [ ] 社交情绪分析

---

## 🤝 贡献指南

我们欢迎贡献！请查看我们的 [贡献指南](CONTRIBUTING.md) 了解详情。

### 开发工作流

1. Fork 仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: 添加惊艳功能'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

### 代码风格

- **Python**: Black 格式化、isort、flake8
- **JavaScript**: ESLint、Prettier
- **提交**: 遵循 Conventional Commits 格式

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

- **Anthropic Claude** - AI 推理引擎
- **yfinance** - 市场数据提供商
- **ChromaDB** - 向量数据库
- **FastAPI** - 后端框架
- **React** - 前端框架
- **Tavily** - 网络搜索 API

---

## 📧 联系方式

- **作者**: Benjamin Daoson
- **GitHub**: [@Benjamindaoson](https://github.com/Benjamindaoson)
- **项目**: [Financial_Asset_QA_System](https://github.com/Benjamindaoson/Financial_Asset_QA_System)

---

<div align="center">

**⭐ 如果觉得有帮助，请给个 Star！**

用 ❤️ 制作 by Benjamin Daoson

</div>
