<div align="center">

# 🏦 金融资产问答系统 (Financial Asset QA System)

**基于大模型的全栈金融资产问答系统。融合核心市场价格引擎与实体识别，附带防幻觉知识检索。**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 18+](https://img.shields.io/badge/react-18.0+-61dafb.svg)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)

</div>

---

## 🌟 核心能力概览

本项目是一整套达到企业级生产标准的金融 AI 应用，针对金融领域严格的"拒绝对外幻觉"等红线需求，采取了**确定义数据管线 + 强制工具校验**的最优方案：

- 📈 **资产价格与走势问答 (核心)**: 原生集成 Yahoo Finance 实时引擎，能够精准回答 "阿里巴巴当前股价是多少？" 或 "特斯拉最近的走势如何？" 并由大模型结合客观数据生成走势分析。
- 📚 **金融知识问答 (RAG)**: 支持纯双路检索 (ChromaDB 向量 + BM25 稀疏) 融合架构。安全回答 "什么是市盈率？" 等专业百科术语。
- 🛡️ **抗幻觉拦截 (ResponseGuard)**: 自带极强的数字校验层。引擎在对外发包前强制核对大模型输出的所有数字，确认其完全来自于 API 获取的历史真实财报数组中，强力杜绝“编造股价”。
- 🚦 **透明链路追踪 (Trace View)**: 前端应用能在毫秒级响应展示当前触发的 LLM 型号、分析复杂度和背后调用的工具（如 `get_price` 或 `search_knowledge`）。

---

## 🚀 极速一键部署 (本地双端联动运行)

本项目的架构已彻底做到前后解耦。按照以下步骤，您可以立刻将它运行在您的电脑上！

### 🔧 环境要求
- **Python**: `3.11` 或更高版本。
- **Node.js**: `v18.x` 或更高版本。
- **Redis** *(可选但强烈推荐)*: 用于缓存市场行情 API 数据以防封禁。

### 📌 步骤 1: 准备后端引擎 (FastAPI & AgentCore)

1. 打开您的终端（如果是 Windows 推荐使用 PowerShell 或 CMD）：
2. 进入后端根目录：
   ```bash
   cd backend
   ```
3. 创建并激活虚拟环境 (强烈建议)：
   ```bash
   python -m venv venv
   # Windows 激活方式:
   venv\Scripts\activate
   # Mac/Linux 激活方式:
   source venv/bin/activate
   ```
4. 安装核心依赖包：
   ```bash
   pip install -r requirements.txt
   ```
5. 配置大模型 API 密钥：
   - 将后端文件夹里的 `.env.example` 复制并重命名为 `.env`。
   - 打开 `.env`，**填入您的真实模型 API Keys**（支持 `ANTHROPIC_API_KEY`, 或配置 `OPENAI_API_KEY` 等）。
6. **启动后端服务器**：
   ```bash
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
   ```
*(注：如果运行遭遇 502/端口占用，请确保杀掉所有残存的僵尸 Python 进程，或更改监听端口并在前端文件中对应同步 URL。)*

---

### 📌 步骤 2: 准备前端交互界面 (Vite & React)

1. 新开一个终端窗口，进入前端目录：
   ```bash
   cd frontend
   ```
2. 安装 NPM 依赖：
   ```bash
   npm install
   ```
3. （如修改过后端端口）打开 `src/services/api.js`：
   确保首行的 `API_BASE` 指向您的真实后端端口，例如：`const API_BASE = "http://127.0.0.1:8001/api";`
4. **启动前端开发服务器**：
   ```bash
   npm run dev
   ```

### 🎈 完成！

打开您的浏览器，输入刚才控制台提示的地址（例如 `http://127.0.0.1:3000` 或 `http://localhost:5173`），深色模式极客风的金融助手将展现在您面前！

您可以尝试询问：
- `"苹果股票今天表现如何？"`
- `"特斯拉近30天走势"`
- `"什么是市净率（PB）？"`

---

## ©️ 代码结构简析

- `/backend/app/agent/core.py` -> 包含核心决策工作流。
- `/backend/app/routing/` -> 包含由大模型意图加持的异步混合路由 (LLM Semantic Router + Regex)。
- `/backend/app/rag/hybrid_pipeline.py` -> 高级混合召回链路引擎。
- `/frontend/src/App.jsx` -> 核心前端应用聚合展示区。
- `/frontend/src/components/` -> 高度分离的 Chat UI, 图表 (Chart) 和渲染套件。
