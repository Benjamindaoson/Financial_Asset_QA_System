"""
FastAPI Main Application
"""
import asyncio
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(name)s - %(message)s'
)

# Set HuggingFace mirror for users in restricted network environments BEFORE any model imports
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import router
from app.config import settings
from app.cache.warmer import CacheWarmer
from app.market import MarketDataService


# Global cache warmer instance
cache_warmer: CacheWarmer = None
_logger = logging.getLogger(__name__)


def _warmup_rag_models() -> None:
    """Preload RAG embedding + reranker models in background to avoid first-request latency."""
    try:
        from app.rag.hybrid_pipeline import HybridRAGPipeline
        pipeline = HybridRAGPipeline()
        if pipeline.collection.count() > 0:
            pipeline._ensure_models()
            _logger.info("[RAG] Embedding + reranker models warmed up")
        else:
            _logger.info("[RAG] ChromaDB empty, skipping model warmup")
    except Exception as e:
        _logger.warning(f"[RAG] Warmup skipped: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    global cache_warmer

    if settings.CACHE_WARM_ENABLED:
        market_service = MarketDataService()
        cache_warmer = CacheWarmer(
            market_service=market_service,
            interval_seconds=settings.CACHE_WARM_INTERVAL_SECONDS,
            limit=settings.CACHE_WARM_LIMIT,
            concurrency=settings.CACHE_WARM_CONCURRENCY,
        )
        await cache_warmer.start_background_warming()

    # Warm up RAG models in background (embedding + reranker) to avoid 5–15s first-request delay
    asyncio.create_task(asyncio.to_thread(_warmup_rag_models))

    yield

    # Shutdown: Stop cache warmer
    if cache_warmer:
        await cache_warmer.stop()


app = FastAPI(
    title="Financial Asset QA System",
    description="AI-powered financial asset question answering system",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Financial Asset QA System",
        "version": "1.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )
