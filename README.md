<div align="center">

# 🏦 金融资产问答系统

[![测试](https://img.shields.io/badge/测试-252%20通过-brightgreen)](backend/tests/)
[![覆盖率](https://img.shields.io/badge/覆盖率-85%25-green)](backend/TEST_COVERAGE_SUMMARY.md)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React](https://img.shields.io/badge/react-18.0+-61dafb.svg)](https://reactjs.org/)
[![许可证](https://img.shields.io/badge/许可证-MIT-blue.svg)](LICENSE)

**基于 AI 的智能金融问答系统，融合实时市场数据、RAG 知识检索和高级推理能力**

[功能特性](#-功能特性) • [快速开始](#-快速开始一键部署) • [详细安装](#-详细安装步骤) • [使用说明](#-使用说明) • [故障排除](#-故障排除)

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

### 🎨 现代化用户界面
- **流式响应**: React 18 实时 SSE 流式传输
- **交互式图表**: Recharts 驱动的 OHLCV 可视化
- **响应式设计**: Tailwind CSS 移动优先设计
- **深色模式**: 护眼界面，适合长时间使用

---

## 🚀 快速开始（一键部署）

### Windows 用户

```bash
# 1. 克隆项目
git clone https://github.com/Benjamindaoson/Financial_Asset_QA_System.git
cd Financial_Asset_QA_System

# 2. 运行一键安装脚本
.\install.bat
```

### Linux/Mac 用户

```bash
# 1. 克隆项目
git clone https://github.com/Benjamindaoson/Financial_Asset_QA_System.git
cd Financial_Asset_QA_System

# 2. 运行一键安装脚本
chmod +x install.sh
./install.sh
```

安装脚本会自动：
- ✅ 检查并安装 Python 3.11+
- ✅ 检查并安装 Node.js 18+
- ✅ 安装 Redis（Docker）
- ✅ 安装后端依赖
- ✅ 安装前端依赖
- ✅ 配置环境变量
- ✅ 启动所有服务
- ✅ 自动打开浏览器

---

## 📋 详细安装步骤

### 前置要求

#### 必需软件

| 软件 | 版本要求 | 下载地址 | 用途 |
|------|---------|---------|------|
| **Python** | 3.11+ | [python.org](https://www.python.org/downloads/) | 后端运行环境 |
| **Node.js** | 18+ | [nodejs.org](https://nodejs.org/) | 前端运行环境 |
| **Redis** | 7+ | [redis.io](https://redis.io/download) 或 Docker | 缓存服务 |
| **Git** | 最新版 | [git-scm.com](https://git-scm.com/) | 代码管理 |

#### 可选软件

| 软件 | 用途 |
|------|------|
| **Docker** | 简化 Redis 安装 |
| **VS Code** | 推荐的代码编辑器 |

### 第一步：安装 Python 3.11+

#### Windows
1. 访问 https://www.python.org/downloads/
2. 下载 Python 3.11 或更高版本
3. 安装时**勾选** "Add Python to PATH"
4. 验证安装：
```bash
python --version
# 应显示: Python 3.11.x
```

#### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
```

#### Mac
```bash
brew install python@3.11
```

### 第二步：安装 Node.js 18+

#### Windows
1. 访问 https://nodejs.org/
2. 下载 LTS 版本（18.x 或更高）
3. 运行安装程序
4. 验证安装：
```bash
node --version
# 应显示: v18.x.x 或更高

npm --version
# 应显示: 9.x.x 或更高
```

#### Linux (Ubuntu/Debian)
```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs
```

#### Mac
```bash
brew install node@18
```

### 第三步：安装 Redis

#### 方式 1: Docker（推荐）

```bash
# 安装 Docker Desktop
# Windows/Mac: https://www.docker.com/products/docker-desktop
# Linux: https://docs.docker.com/engine/install/

# 启动 Redis
docker run -d --name redis -p 6379:6379 redis:7-alpine

# 验证 Redis 运行
docker ps | grep redis
```

#### 方式 2: 直接安装

**Windows:**
1. 下载 Redis for Windows: https://github.com/tporadowski/redis/releases
2. 解压并运行 `redis-server.exe`

**Linux:**
```bash
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

**Mac:**
```bash
brew install redis
brew services start redis
```

### 第四步：克隆项目

```bash
git clone https://github.com/Benjamindaoson/Financial_Asset_QA_System.git
cd Financial_Asset_QA_System
```

### 第五步：配置后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 复制环境变量模板
cp .env.example .env
```

### 第六步：配置环境变量

编辑 `backend/.env` 文件：

```env
# ============================================
# 必需配置（必须填写）
# ============================================

# Anthropic Claude API Key（必需）
# 获取地址: https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxx

# Tavily 搜索 API Key（必需）
# 获取地址: https://tavily.com/
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxx

# ============================================
# 可选配置（可以使用默认值）
# ============================================

# Alpha Vantage API Key（可选，用于降级）
# 获取地址: https://www.alphavantage.co/support/#api-key
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 缓存 TTL（秒）
CACHE_TTL_PRICE=60
CACHE_TTL_HISTORY=86400
CACHE_TTL_INFO=604800

# 日志级别
LOG_LEVEL=INFO

# RAG 配置
CHROMA_PERSIST_DIR=../vectorstore
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
TOP_K=5
SIMILARITY_THRESHOLD=0.7

# 模型配置
DEFAULT_MODEL=claude-opus
MAX_TOKENS=1500
TEMPERATURE=0.7
```

### 第七步：安装前端依赖

```bash
cd ../frontend
npm install
```

### 第八步：启动服务

#### 启动 Redis（如果还没启动）

```bash
# Docker 方式
docker start redis

# 或直接运行
redis-server
```

#### 启动后端

```bash
cd backend

# 激活虚拟环境（如果还没激活）
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 启动后端服务
python -m app.main
```

后端将运行在: `http://localhost:8000`

#### 启动前端（新终端）

```bash
cd frontend
npm run dev
```

前端将运行在: `http://localhost:5173` 或其他可用端口

### 第九步：访问应用

打开浏览器访问前端显示的地址（通常是 `http://localhost:5173`）

---

## 🎯 使用说明

### 市场查询示例

```
用户: 苹果股票今天涨了多少
系统:
  ✅ 实时获取 AAPL 价格数据
  ✅ 显示涨跌幅和百分比
  ✅ 展示 30 日价格走势图
  ✅ 标注数据来源（yfinance）
```

```
用户: 特斯拉最近走势如何
系统:
  ✅ 分析 TSLA 近期表现
  ✅ 技术指标分析（RSI、MACD）
  ✅ 趋势判断和投资参考
  ✅ 相关新闻整合
```

### 知识问答示例

```
用户: 什么是市盈率
系统:
  ✅ RAG 知识库检索
  ✅ Claude AI 详细解释
  ✅ 公式和计算方法
  ✅ 实际应用案例
```

### 对比分析示例

```
用户: 苹果和特斯拉哪个更值得投资
系统:
  ✅ 获取两只股票数据
  ✅ 多维度对比分析
  ✅ 技术面和基本面评估
  ✅ 风险提示
```

---

## 🔧 故障排除

### 问题 1: 后端启动失败

**错误信息:** `ModuleNotFoundError: No module named 'xxx'`

**解决方案:**
```bash
cd backend
pip install -r requirements.txt --upgrade
```

### 问题 2: Redis 连接失败

**错误信息:** `redis.exceptions.ConnectionError`

**解决方案:**
```bash
# 检查 Redis 是否运行
docker ps | grep redis

# 如果没有运行，启动 Redis
docker start redis

# 或重新创建
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### 问题 3: 前端无法连接后端

**错误信息:** `Failed to fetch` 或 `Network Error`

**解决方案:**
1. 确认后端正在运行: `http://localhost:8000/api/health`
2. 检查 CORS 配置
3. 确认防火墙没有阻止 8000 端口

### 问题 4: API Key 无效

**错误信息:** `401 Unauthorized` 或 `Invalid API Key`

**解决方案:**
1. 检查 `.env` 文件中的 API Key 是否正确
2. 确认 API Key 没有过期
3. 重新获取 API Key:
   - Anthropic: https://console.anthropic.com/
   - Tavily: https://tavily.com/

### 问题 5: 端口被占用

**错误信息:** `Address already in use` 或 `Port 8000 is already in use`

**解决方案:**

**Windows:**
```bash
# 查找占用端口的进程
netstat -ano | findstr :8000

# 结束进程（替换 PID）
taskkill /F /PID <PID>
```

**Linux/Mac:**
```bash
# 查找占用端口的进程
lsof -i :8000

# 结束进程
kill -9 <PID>
```

### 问题 6: 虚拟环境激活失败

**Windows PowerShell 错误:** `无法加载文件，因为在此系统上禁止运行脚本`

**解决方案:**
```powershell
# 以管理员身份运行 PowerShell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

# 然后重新激活虚拟环境
venv\Scripts\activate
```

### 问题 7: npm 安装依赖失败

**错误信息:** `EACCES` 或 `Permission denied`

**解决方案:**
```bash
# 清除 npm 缓存
npm cache clean --force

# 删除 node_modules 和 package-lock.json
rm -rf node_modules package-lock.json

# 重新安装
npm install
```

---

## 📊 系统架构

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

---

## 🧪 运行测试

```bash
cd backend

# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_agent_core.py -v

# 生成覆盖率报告
pytest tests/ --cov=app --cov-report=html

# 查看覆盖率报告
open htmlcov/index.html  # Mac
start htmlcov/index.html  # Windows
```

**当前测试状态:**
- ✅ 252 个测试全部通过
- ✅ 85% 代码覆盖率
- ✅ 单元测试 + 集成测试

---

## 📚 API 文档

启动后端后，访问交互式 API 文档:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### 主要端点

#### `POST /api/chat`
流式聊天接口

**请求:**
```json
{
  "query": "苹果股票今天涨了多少？",
  "session_id": "optional-session-id",
  "model": "claude-opus"
}
```

**响应:** `text/event-stream`

#### `GET /api/chart/{symbol}?days=30`
获取历史价格数据

**响应:**
```json
{
  "symbol": "AAPL",
  "days": 30,
  "data": [...]
}
```

#### `GET /api/health`
系统健康检查

#### `GET /api/models`
列出可用模型

---

## 🔐 安全建议

1. **不要提交 .env 文件到 Git**
   ```bash
   # .env 已在 .gitignore 中
   ```

2. **定期更新依赖**
   ```bash
   pip install --upgrade -r requirements.txt
   npm update
   ```

3. **使用环境变量管理敏感信息**
   - 不要在代码中硬编码 API Key
   - 使用 `.env` 文件管理配置

4. **生产环境建议**
   - 使用 HTTPS
   - 配置防火墙规则
   - 启用 Redis 密码认证
   - 使用反向代理（Nginx）

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

## 🆘 获取帮助

遇到问题？

1. 查看 [故障排除](#-故障排除) 部分
2. 搜索 [GitHub Issues](https://github.com/Benjamindaoson/Financial_Asset_QA_System/issues)
3. 创建新的 Issue 描述问题
4. 加入讨论 [GitHub Discussions](https://github.com/Benjamindaoson/Financial_Asset_QA_System/discussions)

---

<div align="center">

**⭐ 如果觉得有帮助，请给个 Star！**

用 ❤️ 制作 by Benjamin Daoson

</div>
