# Financial Asset QA System

Financial Asset QA System is a full-stack financial question answering demo that combines:

- real market data tools for asset questions
- a local RAG pipeline for financial knowledge questions
- web search for event-driven market questions
- streaming responses in a React frontend

## What the system does

### Asset Q&A

- current price lookup
- recent change analysis such as 7-day or 30-day performance
- historical chart retrieval
- event-oriented questions that combine price movement and news

### Knowledge Q&A

- financial concept explanation
- accounting concept comparison
- knowledge-base-backed answers with retrieval and reranking

## Current architecture

### Backend

- FastAPI + Uvicorn
- deterministic query router for `MARKET`, `KNOWLEDGE`, `NEWS`, and `HYBRID`
- market data service backed by `yfinance`
- Alpha Vantage fallback for price, history, and profile requests when configured
- hybrid RAG pipeline backed by ChromaDB and local reranking
- Tavily-based web search wrapper
- SSE streaming API

### Frontend

- React 18 + Vite
- JavaScript JSX implementation
- Tailwind CSS
- Recharts for chart rendering

## Repository layout

```text
Financial_Asset_QA_System/
  backend/
    app/
      agent/
      api/
      enricher/
      market/
      rag/
      routing/
      search/
      models/
      main.py
    requirements.txt
    .env.example
  frontend/
    src/
    package.json
  data/
  vectorstore/
  docker/
    docker-compose.yml
    Dockerfile.backend
    Dockerfile.frontend
```

## Local setup

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Required environment variables:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
LOG_LEVEL=INFO
```

Start Redis:

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

Start backend:

```bash
cd backend
python -m app.main
```

Backend URL: `http://localhost:8000`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL: `http://localhost:5173`

## Docker

```bash
docker compose -f docker/docker-compose.yml up --build
```

The compose file now uses placeholder environment values by default. Export real API keys in your shell before starting Docker if you want live external services.

## API endpoints

### `POST /api/chat`

- accepts a JSON body with `query` and optional `session_id`
- returns `text/event-stream`
- emits `model_selected`, `tool_start`, `tool_data`, `chunk`, `done`, and `error`

### `GET /api/chart/{symbol}`

- returns historical OHLCV data for chart rendering

### `GET /api/health`

- returns component health for Redis, vector retrieval, LLM configuration, and market data library availability

### `GET /api/models`

- returns available configured models and usage counters

## Key implementation notes

- asset questions are routed to market tools instead of being answered from free-form model output
- generic knowledge questions are routed to retrieval
- market requests fall back to Alpha Vantage when the primary source fails and a fallback key is configured
- streaming answer text is appended from SSE chunks without stale React state
- the sidebar no longer shows synthetic real-time prices

## Verification status

The following checks were run after the current fixes:

```bash
cd backend
pytest tests/test_agent_core.py tests/test_api_routes.py tests/test_market_service.py tests/test_rag_pipeline.py tests/test_hybrid_pipeline.py tests/test_model_adapter.py tests/test_multi_model.py -q

cd frontend
npm run build
```

## Known gaps

- the health endpoint is still configuration-oriented rather than a full live dependency probe
- the vector knowledge base is small and not yet rich enough for company-quarter-specific reporting
- the frontend bundle is larger than ideal and still needs code splitting
