<div align="center">

# 🏦 金融资产问答系统
### Financial Asset QA System

**基于大模型的全栈金融资产问答系统**

融合实时市场数据、AI智能分析与防幻觉知识检索

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 18+](https://img.shields.io/badge/react-18.0+-61dafb.svg)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [常见问题](#-常见问题) • [技术架构](#-技术架构)

</div>

---

## 🎯 功能特性

### 💹 实时股票查询
- 支持全球主要股票市场实时数据
- 自动生成价格走势图表
- 涨跌幅分析和历史数据对比

### 🤖 AI智能分析
- 多模型支持（Claude、GPT、DeepSeek）
- 流式响应，实时展示分析过程
- 透明化AI推理链路追踪

### 📚 防幻觉知识问答
- RAG增强的知识检索系统
- 自动来源标注和引用
- 向量数据库支持精准匹配

### 🎨 现代化UI
- 响应式设计，支持移动端
- 实时图表可视化
- 暗色主题，护眼舒适

---

## 🚀 快速开始

### 📋 前置要求

在开始之前，请确保已安装：

| 软件 | 版本要求 | 下载链接 | 安装提示 |
|------|---------|---------|---------|
| **Python** | 3.11+ | [官网下载](https://www.python.org/downloads/) | Windows用户必须勾选 `Add Python to PATH` |
| **Node.js** | 18+ | [官网下载](https://nodejs.org/) | 选择LTS版本 |
| **Git** | 最新版 | [官网下载](https://git-scm.com/) | 可选，也可直接下载ZIP |

**验证安装**：
```bash
python --version  # 应显示 Python 3.11.x
node --version    # 应显示 v18.x.x 或更高
npm --version     # 应显示 10.x.x 或更高
```

---

### 📥 第一步：下载代码

**方法1：使用Git（推荐）**
```bash
git clone https://github.com/Benjamindaoson/Financial_Asset_QA_System.git
cd Financial_Asset_QA_System
```

**方法2：下载ZIP**
1. 点击页面上的绿色 `<> Code` 按钮
2. 选择 `Download ZIP`
3. 解压到任意目录并进入该目录

---

### 🔑 第二步：配置API密钥

1. 进入 `backend` 目录
2. 复制 `.env.example` 为 `.env`：
   ```bash
   # Windows
   copy backend\.env.example backend\.env

   # macOS/Linux
   cp backend/.env.example backend/.env
   ```

3. 编辑 `backend/.env` 文件，**至少配置一个AI模型的API密钥**：

```env
# 推荐：Claude API（效果最好）
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
ANTHROPIC_BASE_URL=https://api.anthropic.com

# 或者：DeepSeek API（性价比高）
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxx

# 或者：OpenAI API
OPENAI_API_KEY=sk-xxxxxxxxxxxxx

# 可选：金融数据API（不配置也能用Yahoo Finance）
ALPHA_VANTAGE_API_KEY=your_key_here
FINNHUB_API_KEY=your_key_here
```

> 💡 **获取API密钥**：
> - Claude: [console.anthropic.com](https://console.anthropic.com/)
> - DeepSeek: [platform.deepseek.com](https://platform.deepseek.com/)
> - OpenAI: [platform.openai.com](https://platform.openai.com/)

---

### 🎬 第三步：启动系统

#### 🪟 Windows用户（一键启动）

**启动后端**：
双击运行项目根目录下的 `启动后端.bat`

**启动前端**：
双击运行项目根目录下的 `启动前端.bat`

#### 🐧 macOS/Linux用户（命令行启动）

**启动后端**（终端1）：
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

**启动前端**（终端2）：
```bash
cd frontend
npm install
npm run dev
```

---

### ✅ 第四步：验证运行

#### 1. 检查后端
浏览器访问：http://127.0.0.1:8001/api/health

应该看到JSON格式的健康状态：
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "redis": "connected",
    "chromadb": "ready",
    "claude_api": "configured"
  }
}
```

#### 2. 访问前端
浏览器访问：http://127.0.0.1:5173

应该看到"金融资产智能问答"页面

#### 3. 测试功能
输入以下测试问题：
- `苹果股票今天涨了多少` - 测试股票查询
- `什么是市盈率` - 测试知识问答
- `特斯拉最近走势` - 测试图表展示

**成功标志**：
- ✅ AI开始流式回复
- ✅ 显示"💡 分析链路追踪"面板
- ✅ 股票问题显示价格图表

---

## 🔍 常见问题

<details>
<summary><b>❌ 后端启动失败：ChromaDB错误</b></summary>

**错误信息**：`sqlite3.OperationalError: no such column: collections.topic`

**原因**：旧版本数据库与新代码不兼容

**解决方案**：
```bash
# 删除旧数据库
rm -rf vectorstore/chroma
# Windows: rmdir /s /q vectorstore\chroma

# 重新启动后端，会自动创建新数据库
```
</details>

<details>
<summary><b>❌ 前端显示"请求失败"</b></summary>

**检查清单**：
1. ✅ 后端是否启动成功（看到 `Application startup complete.`）
2. ✅ 后端端口是否为 **8001**（不是8000）
3. ✅ 前端访问地址是否为 http://127.0.0.1:5173
4. ✅ 按F12查看浏览器控制台是否有错误

**快速修复**：
```bash
# 1. 关闭所有Python和Node进程
taskkill /F /IM python.exe /T
taskkill /F /IM node.exe /T

# 2. 重新启动后端和前端
```
</details>

<details>
<summary><b>❌ 端口被占用</b></summary>

**查找占用端口的进程**：
```bash
# Windows
netstat -ano | findstr "8001"
netstat -ano | findstr "5173"
taskkill /F /PID <进程ID>

# macOS/Linux
lsof -ti:8001 | xargs kill -9
lsof -ti:5173 | xargs kill -9
```
</details>

<details>
<summary><b>⏱️ 首次启动很慢</b></summary>

**原因**：首次启动会自动下载约1.5GB的BGE嵌入模型

**解决**：耐心等待下载完成（2-5分钟），后续启动会很快

**进度查看**：后端终端会显示下载进度
</details>

<details>
<summary><b>🔑 API密钥无效</b></summary>

**检查清单**：
1. ✅ `.env` 文件是否在 `backend` 目录下
2. ✅ API密钥是否正确复制（无多余空格）
3. ✅ API密钥是否有效且有余额
4. ✅ 文件名是 `.env` 不是 `.env.txt`

**验证方法**：
```bash
# 查看环境变量是否加载
cd backend
python -c "from app.config import settings; print(settings.ANTHROPIC_API_KEY)"
```
</details>

<details>
<summary><b>🌐 网络问题：模型下载失败</b></summary>

**错误信息**：`ReadTimeoutError` 或 `Connection timeout`

**解决方案**：
1. 检查网络连接
2. 使用国内镜像（已自动配置HuggingFace镜像）
3. 如果仍然失败，可以手动下载模型后放入 `models` 目录
</details>

---

## 🏗️ 技术架构

### 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                         用户浏览器                            │
│                   http://127.0.0.1:5173                      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    前端 (Vite + React)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  聊天界面     │  │  图表展示     │  │  链路追踪     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────────┬────────────────────────────────────┘
                         │ Vite Proxy: /api → :8001
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    后端 (FastAPI)                            │
│                   http://127.0.0.1:8001                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              API路由层 (SSE流式响应)                   │  │
│  └────────┬─────────────────────────────────────────────┘  │
│           │                                                  │
│  ┌────────▼──────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │   AgentCore       │  │ MarketData   │  │ RAG Pipeline│ │
│  │  (AI推理引擎)      │  │  Service     │  │ (知识检索)   │ │
│  │                   │  │              │  │             │ │
│  │ • 多模型支持       │  │ • Yahoo      │  │ • ChromaDB  │ │
│  │ • 工具调用         │  │ • Alpha      │  │ • BGE嵌入   │ │
│  │ • 流式输出         │  │ • Finnhub    │  │ • 重排序    │ │
│  └───────────────────┘  └──────────────┘  └─────────────┘ │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Redis缓存     │  │ 向量数据库     │  │ 日志系统      │     │
│  │ (可选)        │  │ (ChromaDB)    │  │ (JSONL)      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 技术栈

#### 后端
- **框架**: FastAPI 0.109+
- **AI模型**: Anthropic Claude / OpenAI GPT / DeepSeek
- **向量数据库**: ChromaDB 0.4.24
- **嵌入模型**: BAAI/bge-base-zh-v1.5
- **缓存**: Redis (可选)
- **市场数据**: yfinance, Alpha Vantage, Finnhub

#### 前端
- **框架**: React 18.2
- **构建工具**: Vite 5.0
- **图表库**: Recharts 2.10
- **样式**: TailwindCSS 3.4
- **HTTP**: Fetch API (SSE流式响应)

### 项目结构

```
Financial_Asset_QA_System/
├── backend/                      # 后端服务
│   ├── app/
│   │   ├── agent/               # AI Agent核心
│   │   │   ├── core.py         # Agent主逻辑
│   │   │   └── tools.py        # 工具函数集
│   │   ├── api/                # API路由
│   │   │   └── routes.py       # 端点定义
│   │   ├── models/             # 数据模型
│   │   │   ├── schemas.py      # Pydantic模型
│   │   │   └── multi_model.py  # 多模型管理
│   │   ├── rag/                # RAG检索系统
│   │   │   ├── pipeline.py     # 检索管道
│   │   │   └── hybrid_pipeline.py
│   │   ├── market/             # 市场数据服务
│   │   │   └── service.py      # 数据获取
│   │   ├── cache/              # 缓存系统
│   │   ├── config.py           # 配置管理
│   │   └── main.py             # 应用入口
│   ├── requirements.txt        # Python依赖
│   ├── .env.example            # 环境变量模板
│   └── .env                    # 环境变量（需创建）
│
├── frontend/                    # 前端应用
│   ├── src/
│   │   ├── components/         # React组件
│   │   │   ├── Chat/          # 聊天组件
│   │   │   ├── Chart.jsx      # 图表组件
│   │   │   └── UI/            # UI组件
│   │   ├── services/          # API服务
│   │   │   └── api.js         # API调用
│   │   ├── App.jsx            # 主应用
│   │   └── main.jsx           # 入口文件
│   ├── vite.config.ts         # Vite配置
│   ├── package.json           # Node依赖
│   └── tailwind.config.js     # Tailwind配置
│
├── vectorstore/                # 向量数据库
│   └── chroma/                # ChromaDB数据
│
├── models/                     # 模型缓存
│   ├── huggingface/           # HF模型
│   └── transformers/          # Transformers缓存
│
├── logs/                       # 日志文件
│   └── tool_calls.jsonl       # 工具调用日志
│
├── 启动后端.bat                 # Windows启动脚本
├── 启动前端.bat                 # Windows启动脚本
└── README.md                   # 本文档
```

---

## 📊 性能优化

### 缓存策略
| 数据类型 | 缓存时长 | 说明 |
|---------|---------|------|
| 实时价格 | 60秒 | 减少API调用 |
| 历史数据 | 24小时 | 历史数据不常变 |
| 公司信息 | 7天 | 基本信息稳定 |

### 智能预热
- 热门股票（AAPL, TSLA, MSFT等）自动预热
- 后台定期更新缓存
- 减少首次查询延迟

### 并发处理
- 异步IO处理所有网络请求
- 流式响应提升用户体验
- 连接池复用减少开销

---

## 🔒 安全说明

### 环境变量保护
- ⚠️ **永远不要**将 `.env` 文件提交到Git
- ✅ 使用 `.env.example` 作为模板
- ✅ `.gitignore` 已配置忽略 `.env`

### CORS配置
```python
# 开发环境：允许所有来源
allow_origins=["*"]

# 生产环境：限制特定域名
allow_origins=["https://yourdomain.com"]
```

### API密钥安全
- 定期轮换API密钥
- 监控API使用量
- 设置速率限制

### 数据验证
- 所有用户输入经过Pydantic验证
- SQL注入防护
- XSS攻击防护

---

## 🎨 功能演示

### 股票查询示例
```
用户: 苹果股票今天涨了多少

AI: 正在查询苹果(AAPL)的最新行情...

💡 分析链路追踪
🧠 Using claude-opus-4 (Complexity: fast)
🔧 查询股票价格: AAPL
📊 获取历史数据: 30天

根据最新数据，苹果公司(AAPL)今日表现如下：
• 当前价格: $178.52
• 涨跌幅: +2.34% (+$4.08)
• 今日最高: $179.23
• 今日最低: $176.45

[显示30天价格走势图]
```

### 知识问答示例
```
用户: 什么是市盈率

AI: 正在检索相关知识...

💡 分析链路追踪
🧠 Using claude-sonnet-4 (Complexity: medium)
🔍 知识检索: 市盈率定义

市盈率(P/E Ratio)是衡量股票估值的重要指标：

定义：市盈率 = 股价 / 每股收益(EPS)

意义：
• 反映投资者愿意为每1元盈利支付的价格
• 高市盈率：市场预期增长快，但可能高估
• 低市盈率：可能被低估，或增长预期低

应用：
• 同行业比较
• 历史市盈率对比
• 结合其他指标综合判断

📚 来源：金融知识库
```

---

## 🛠️ 开发指南

### 本地开发

#### 后端开发
```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate

# 开发模式（自动重载）
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001

# 运行测试
pytest tests/

# 代码格式化
black app/
isort app/
```

#### 前端开发
```bash
cd frontend

# 开发模式
npm run dev

# 构建生产版本
npm run build

# 预览生产版本
npm run preview
```

### 添加新功能

#### 1. 添加新的工具函数
```python
# backend/app/agent/tools.py

@tool
def your_new_tool(param: str) -> dict:
    """
    工具描述

    Args:
        param: 参数说明

    Returns:
        返回值说明
    """
    # 实现逻辑
    return {"result": "data"}
```

#### 2. 注册工具到Agent
```python
# backend/app/agent/core.py

self.tools = [
    get_stock_price,
    search_knowledge,
    your_new_tool,  # 添加新工具
]
```

#### 3. 前端调用
前端无需修改，Agent会自动选择合适的工具调用

---

## 📈 路线图

### v1.1 (计划中)
- [ ] 支持更多金融数据源
- [ ] 添加技术指标分析
- [ ] 支持多语言界面
- [ ] 移动端优化

### v1.2 (计划中)
- [ ] 用户账户系统
- [ ] 自选股票列表
- [ ] 价格提醒功能
- [ ] 历史对话记录

### v2.0 (规划中)
- [ ] 投资组合分析
- [ ] 风险评估工具
- [ ] 回测系统
- [ ] API开放平台

---

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

### 如何贡献

1. **Fork本仓库**
2. **创建特性分支** (`git checkout -b feature/AmazingFeature`)
3. **提交更改** (`git commit -m 'Add some AmazingFeature'`)
4. **推送到分支** (`git push origin feature/AmazingFeature`)
5. **开启Pull Request**

### 代码规范

- Python: 遵循PEP 8
- JavaScript: 遵循Airbnb风格指南
- 提交信息: 使用约定式提交

### 报告问题

提交Issue时请包含：
- 问题描述
- 复现步骤
- 预期行为
- 实际行为
- 系统环境（OS、Python版本、Node版本）
- 错误日志

---

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 致谢

### 技术支持
- [Anthropic](https://www.anthropic.com/) - Claude AI模型
- [OpenAI](https://openai.com/) - GPT模型
- [DeepSeek](https://www.deepseek.com/) - DeepSeek模型

### 数据来源
- [Yahoo Finance](https://finance.yahoo.com/) - 免费市场数据
- [Alpha Vantage](https://www.alphavantage.co/) - 金融数据API
- [Finnhub](https://finnhub.io/) - 实时股票数据

### 开源项目
- [FastAPI](https://fastapi.tiangolo.com/) - 现代Python Web框架
- [React](https://reactjs.org/) - 用户界面库
- [ChromaDB](https://www.trychroma.com/) - 向量数据库
- [Recharts](https://recharts.org/) - React图表库

---

## 📞 联系方式

- **GitHub Issues**: [提交问题](https://github.com/Benjamindaoson/Financial_Asset_QA_System/issues)
- **Email**: benjamindaoson@example.com
- **项目主页**: [GitHub](https://github.com/Benjamindaoson/Financial_Asset_QA_System)

---

## ⭐ Star历史

如果这个项目对您有帮助，请给个Star支持一下！

[![Star History Chart](https://api.star-history.com/svg?repos=Benjamindaoson/Financial_Asset_QA_System&type=Date)](https://star-history.com/#Benjamindaoson/Financial_Asset_QA_System&Date)

---

<div align="center">

**🎉 感谢使用金融资产问答系统！**

Made with ❤️ by [Benjamin Daoson](https://github.com/Benjamindaoson)

[⬆ 回到顶部](#-金融资产问答系统)

</div>
