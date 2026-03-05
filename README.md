# 金融资产问答系统 (Financial Asset QA System)

一个基于 Claude Sonnet 4.6 和 RAG 技术的智能金融问答系统，支持实时行情查询、知识库问答、新闻搜索和流式对话。

## 功能特性

- **智能问答**：基于 Claude Sonnet 4.6 的自然语言理解和生成能力
- **实时行情**：集成 yfinance 获取股票实时价格和历史数据
- **知识库检索**：使用 ChromaDB + bge-base-zh-v1.5 实现语义检索
- **新闻搜索**：集成 Tavily API 获取最新金融资讯
- **流式对话**：支持 SSE 流式响应，提升用户体验
- **智能路由**：自动识别查询类型并调用相应工具
- **缓存优化**：Redis 缓存提升响应速度

## 技术栈

### 后端
- **框架**：FastAPI + Uvicorn
- **AI 模型**：Claude Sonnet 4.6 (Anthropic)
- **嵌入模型**：bge-base-zh-v1.5 (BAAI)
- **重排序模型**：bge-reranker-base (BAAI)
- **向量数据库**：ChromaDB
- **缓存**：Redis
- **数据源**：yfinance, Tavily API

### 前端
- **框架**：React 18 + Vite
- **样式**：TailwindCSS
- **图表**：Recharts
- **语言**：TypeScript

## 目录结构

```
Financial_Asset_QA_System/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── agent/          # Agent 核心逻辑
│   │   ├── api/            # API 路由
│   │   ├── enricher/       # 响应增强器
│   │   ├── market/         # 行情服务
│   │   ├── rag/            # RAG 检索管道
│   │   ├── search/         # 网络搜索服务
│   │   ├── config.py       # 配置管理
│   │   ├── models.py       # 数据模型
│   │   └── main.py         # 应用入口
│   ├── .env.example        # 环境变量示例
│   ├── requirements.txt    # Python 依赖
│   └── start.bat           # Windows 启动脚本
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── components/     # React 组件
│   │   ├── App.jsx         # 主应用
│   │   └── main.jsx        # 入口文件
│   └── package.json        # Node.js 依赖
├── data/                   # 知识库数据
├── vectorstore/            # 向量数据库存储
├── models/                 # 模型缓存目录
├── logs/                   # 日志文件
├── docker/                 # Docker 配置
│   └── docker-compose.yml
└── docs/                   # 文档
    └── DEPLOYMENT.md       # 部署指南
```

## 环境要求

- **Python**：3.11+
- **Node.js**：18+
- **Redis**：7.0+
- **操作系统**：Windows/Linux/macOS
- **内存**：建议 8GB+（模型加载需要）
- **磁盘空间**：约 5GB（模型文件）

## 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd Financial_Asset_QA_System
```

### 2. 后端配置

#### 2.1 创建虚拟环境

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

#### 2.2 安装依赖

```bash
pip install -r requirements.txt
```

#### 2.3 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 必需配置
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# 可选配置（用于新闻搜索）
TAVILY_API_KEY=your_tavily_api_key_here

# 可选配置（用于 Alpha Vantage 数据源）
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# 日志级别
LOG_LEVEL=INFO
```

#### 2.4 启动 Redis

```bash
# Windows (使用 Docker)
docker run -d -p 6379:6379 redis:7-alpine

# Linux/macOS
redis-server
```

#### 2.5 初始化知识库（可选）

如果需要使用知识库问答功能，请将文档放入 `data/` 目录，系统会自动加载。

### 3. 前端配置

#### 3.1 安装依赖

```bash
cd frontend
npm install
```

### 4. 启动应用

#### 4.1 启动后端

```bash
# Windows
cd backend
start.bat

# Linux/macOS
cd backend
export PYTHONPATH=.
export HF_HOME=../models/huggingface
export TRANSFORMERS_CACHE=../models/transformers
export HF_HUB_CACHE=../models/huggingface/hub
python -m app.main
```

后端服务将在 `http://localhost:8000` 启动

#### 4.2 启动前端

```bash
cd frontend
npm run dev
```

前端应用将在 `http://localhost:5173` 启动

### 5. 访问应用

打开浏览器访问：`http://localhost:5173`

## API 密钥获取

### ANTHROPIC_API_KEY（必需）

1. 访问 [Anthropic Console](https://console.anthropic.com/)
2. 注册/登录账号
3. 进入 API Keys 页面
4. 创建新的 API Key
5. 复制密钥到 `.env` 文件

### TAVILY_API_KEY（可选）

1. 访问 [Tavily](https://tavily.com/)
2. 注册账号
3. 获取 API Key
4. 复制密钥到 `.env` 文件

注意：如果不配置 TAVILY_API_KEY，新闻搜索功能将不可用，但不影响其他功能。

## 使用示例

### 行情查询

```
用户：特斯拉股票现在多少钱？
系统：[返回 TSLA 实时价格和趋势图]
```

### 知识问答

```
用户：什么是市盈率？
系统：[基于知识库返回详细解释]
```

### 新闻搜索

```
用户：最近有什么关于苹果公司的新闻？
系统：[返回最新相关新闻]
```

### 综合查询

```
用户：分析一下微软的投资价值
系统：[结合行情、知识库和新闻进行综合分析]
```

## Docker 部署

使用 Docker Compose 一键部署：

```bash
cd docker
docker-compose up -d
```

详细部署说明请参考 [部署文档](docs/DEPLOYMENT.md)

## 常见问题

### 1. 模型下载慢或失败

**问题**：首次启动时下载 bge 模型速度慢

**解决方案**：
- 使用国内镜像源：设置环境变量 `HF_ENDPOINT=https://hf-mirror.com`
- 手动下载模型到 `models/` 目录

### 2. Redis 连接失败

**问题**：`ConnectionError: Error connecting to Redis`

**解决方案**：
- 确认 Redis 服务已启动：`redis-cli ping`
- 检查 `.env` 中的 Redis 配置
- Windows 用户建议使用 Docker 运行 Redis

### 3. API Key 无效

**问题**：`AuthenticationError: Invalid API Key`

**解决方案**：
- 检查 `.env` 文件中的 API Key 是否正确
- 确认 API Key 有足够的配额
- 重启后端服务使配置生效

### 4. 前端无法连接后端

**问题**：前端显示网络错误

**解决方案**：
- 确认后端服务已启动（访问 `http://localhost:8000/docs`）
- 检查防火墙设置
- 确认端口 8000 和 5173 未被占用

### 5. 内存不足

**问题**：模型加载时内存溢出

**解决方案**：
- 关闭其他占用内存的应用
- 考虑使用更小的嵌入模型
- 增加系统虚拟内存

## 性能优化建议

1. **Redis 缓存**：合理设置缓存过期时间
2. **模型预加载**：首次启动会较慢，后续启动会快很多
3. **批量查询**：使用批量接口减少请求次数
4. **CDN 加速**：生产环境建议使用 CDN 加速前端资源

## 开发计划

- [ ] 支持更多数据源（如东方财富、同花顺）
- [ ] 添加用户认证和权限管理
- [ ] 实现对话历史持久化
- [ ] 支持多语言（英文、日文等）
- [ ] 添加更多可视化图表
- [ ] 实现移动端适配

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。

---

**注意**：本系统仅供学习和研究使用，不构成任何投资建议。投资有风险，决策需谨慎。
