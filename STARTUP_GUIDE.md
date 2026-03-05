# Financial Asset QA System - Startup Guide

## ✅ System Status

Both services are now running successfully!

### Access URLs

- **Frontend UI**: http://localhost:3001
- **Backend API**: http://localhost:8000
- **API Health Check**: http://localhost:8000/api/health

### Current System Health

```json
{
  "status": "degraded",
  "version": "1.0.0",
  "components": {
    "redis": "disconnected",
    "chromadb": "ready",
    "claude_api": "configured",
    "yfinance": "available"
  }
}
```

## 🚀 Quick Start

### Backend (Port 8000)
```bash
cd D:\Financial_Asset_QA_System\backend
.\start.bat
```

### Frontend (Port 3001)
```bash
cd D:\Financial_Asset_QA_System\frontend
npm run dev
```

## ⚙️ Configuration Required

### 1. Anthropic API Key (Required for Chat)

Create `backend/.env` file:
```env
ANTHROPIC_API_KEY=your_api_key_here
```

Get your API key from: https://console.anthropic.com/

### 2. Redis (Optional - for caching)

Install and start Redis for better performance:
- Price data: 60s cache
- Historical data: 24h cache
- Company info: 7d cache

Without Redis, the system will work but without caching.

### 3. Alpha Vantage API (Optional - backup data source)

Add to `backend/.env`:
```env
ALPHA_VANTAGE_API_KEY=your_api_key_here
```

Get free API key from: https://www.alphavantage.co/support/#api-key

## 📊 Knowledge Base

The system includes 24 pre-loaded financial knowledge chunks:
- Valuation metrics (PE, PB, PS, EV/EBITDA)
- Financial statements analysis
- Technical analysis indicators
- Market instruments
- Macroeconomic factors

## 🔧 Troubleshooting

### Proxy Issues

If you encounter connection errors, disable proxy:
```bash
set http_proxy=
set https_proxy=
```

Or use `--noproxy "*"` flag with curl.

### Port Conflicts

- Frontend default: 3000 (auto-switches to 3001 if occupied)
- Backend: 8000 (must be available)

### Model Downloads

All models are cached in: `D:\Financial_Asset_QA_System\models\`
- bge-base-zh-v1.5: ~400MB
- bge-reranker-base: ~200MB

## 📝 Features

### 6 Built-in Tools

1. **get_price** - Real-time stock prices
2. **get_history** - Historical price data with charts
3. **get_change** - Price change analysis
4. **get_info** - Company information
5. **search_knowledge** - RAG-based financial knowledge
6. **search_web** - Web search (stub)

### Example Queries

- "苹果公司的股价是多少？" (What's Apple's stock price?)
- "特斯拉最近一个月的走势" (Tesla's trend in the last month)
- "什么是市盈率？" (What is PE ratio?)
- "比较微软和谷歌的财务状况" (Compare Microsoft and Google)

## 🎯 Next Steps

1. ✅ Services are running
2. ⚠️ Configure ANTHROPIC_API_KEY in backend/.env
3. ⚠️ (Optional) Install and start Redis
4. ⚠️ (Optional) Add ALPHA_VANTAGE_API_KEY
5. 🌐 Open http://localhost:3001 in your browser
6. 💬 Start chatting!

## 📚 Documentation

- Full README: `README.md`
- Deployment Guide: `docs/DEPLOYMENT.md`
- Technical Spec: `docs/plans/financial-qa-tech-spec-v2.md`
- Implementation Plan: `docs/plans/2026-03-04-financial-qa-implementation.md`
