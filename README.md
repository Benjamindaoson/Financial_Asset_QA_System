<div align="center">

# 🏦 金融资产问答系统 (Financial Asset QA System)

**基于大模型的全栈金融资产问答系统。融合核心市场价格引擎与实体识别，附带防幻觉知识检索。**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![React 18+](https://img.shields.io/badge/react-18.0+-61dafb.svg)](https://reactjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)](https://fastapi.tiangolo.com/)

---
**🏆 本项目特点：无需配置复杂的数据库容器，只要您有网有环境，填入 API 密钥即可直接体验防幻觉的金融 AI 问答。**
</div>

---

## 🚀 极速本地部署指南 (保姆级教程)

本指南针对**零基础环境**。如果您是一线开发/面试验收人员，请直接按顺序复制命令即可！由于这是一个调用了真实大模型和股价数据的全栈系统，**您必须运行后端和前端两块服务。**

### 第一步：确认基础环境准备
您的电脑必须安装好以下两个基础运行环境。如果没有，请点击链接下载并安装：
1. **Python 环境**: 推荐 `Python 3.11` 及以上。[点击下载 Python](https://www.python.org/downloads/) (注意部分 Windows 安装时务必勾选 `"Add Python to PATH"`)。在命令行输入 `python --version` 必须能输出版本号。
2. **Node.js 环境**: 用于运行网页前端。[点击下载 Node.js 的 LTS 稳定版](https://nodejs.org/)。在命令行输入 `npm --version` 必须能输出版本号。

---

### 第二步：启动 API 后端服务 (提供 AI 思考及爬虫数据)

打开您的终端/命令提示符（Terminal / CMD / PowerShell），**一行一行运行以下命令**：

```bash
# 1. 克隆代码仓库到您的本地 (如果您下载的是 ZIP 文件并解压了，直接进入解压后的文件夹)
git clone https://github.com/Benjamindaoson/Financial_Asset_QA_System.git
cd Financial_Asset_QA_System

# 2. 进入后端文件夹
cd backend

# 3. 创建纯净的独立 Python 运行环境 (这一步非常重要，能防止代码跑不起来)
python -m venv venv

# 4. 激活运行环境 (重点：Windows和Mac/Linux的激活命令不同！)
# 【Windows 系统请复制这行】: 
venv\Scripts\activate
# 【Mac / Linux 系统请复制这行】: 
source venv/bin/activate

# 5. 等待命令行开头出现 (venv) 字样后，安装所有需要的组件 (大概需要等待 1~3 分钟，取决于网速)
pip install -r requirements.txt

# 6. 【最重要的一步：填入 AI 钥匙】如果缺少这一步页面会永远处于"请求失败"状态！
# - 找到 backend 文件夹下的 `.env.example` 文件
# - 将其复制一份并重命名为 `.env` 
# - 用记事本打开 `.env` 文件，在里面填入您的真实大模型 API 密钥。例如替换掉: 
#   ANTHROPIC_API_KEY=您的真实秘钥 
#   (如果没有 Anthropic 也可以填您的 OPENAI 秘钥甚至 DeepSeek，在内部代码中均已做好兼容路由，请参考里面的注释)

# 7. 开启后端服务器引擎！
# ⚠️ 注意：首次启动该命令时，系统会自动下载防幻觉需要的向量大模型 (约 1.5GB)。
# 我们已经在代码中为您配置了中国大陆的清华/官方镜像加速，通常需要 2~5 分钟。请耐心等待它出现 Application startup complete.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

> **成功标志**：当您在终端看到 `Uvicorn running on http://127.0.0.1:8001` 字样时，**不要关闭这个黑框**，把它最小化，您的引擎已经发动了！

---

### 第三步：启动前端可视化网页 (最终交互界面)

**不要关闭刚才运行后端的那个窗口。**我们单独**再新开一个命令提示符/终端窗口**：

```bash
# 1. 确保您在项目的根目录下，如果不在，请先 cd 进去。然后进入前端目录：
cd frontend

# 2. 安装前端网页的所有组件 (大概需要 1 分钟)
npm install

# 3. 立即启动前端本地页面
npm run dev
```

> **成功标志**：当终端打印出绿色的 `➜ Local: http://127.0.0.1:3000/` 或者 `localhost:xxxx` 地址时，大功告成！

---

### 第四步：在浏览器里直接体验！

**网页会自动弹出，如果没有弹出，请手动复制命令提示符里的局域网地址（如 `http://localhost:3000` 或 `http://127.0.0.1:3000` ）粘贴到您的独立浏览器（如 Chrome / Edge）打开。**

你可以向它提问以下例子来验收成果：
1. **测试查询最新股价与走势能力**：输入 `苹果股票今天涨了多少？` （系统会拉取真实市场数据，并在页面左侧直接绘出行情雷达图。绝无大模型自己的胡编乱造）
2. **测试金融词条 RAG 检索能力**：输入 `什么是市盈率？它和市净率有什么区别？`（系统会自动从金融领域知识库中召回专业解答，格式非常严谨）
3. **亮点——体验专业链路可视化**：在任何回答出现前，都会展示 **"💡 分析链路追踪"**，向你毫无保留地证明背后正在进行严谨的数据抓取 (如 Fetching price API)，彻底解决面试官/用户对 "Agent 到底干了什么" 的质疑。

---

## ©️ 疑问排查 FAQ

- **Q: 网页打开一片空白或疯狂报错 `Failed to fetch` 分支失败？**
  - **A:** 99% 的可能是您的第二步后端没有启动成功，或者端口 `8001` 被拦截了。另外，请确认您在启动时是否**耐心等待了 3 分钟的首次向量模型下载**。只有看到绿色的 `Application startup complete` 才算启动成功！请保证你开了两份黑框终端：一个跑着 `python -m uvicorn`，另一个跑着 `npm run dev`，二者缺一不可。
- **Q: 虽然显示出来了，但发送消息后界面报错或者显示无回应？**
  - **A:** 您的 `.env` 配置文件里的秘钥为空或欠费了，导致拦截网络请求。认真检查第二步的第 6 环节！哪怕你乱填一个字符，都比不填要好。

---
🌟 **如果这套严谨落地防幻觉的系统赢得了您的认可，欢迎在右上角点个 Star 鼓励！**
