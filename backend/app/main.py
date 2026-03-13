"""
FastAPI Main Application
"""
import os
import logging

# Configure logging FIRST
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
from app.middleware import PerformanceMonitoringMiddleware


# Global cache warmer instance
cache_warmer: CacheWarmer = None


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

# Performance monitoring middleware
app.add_middleware(PerformanceMonitoringMiddleware)

# Include API routes
app.include_router(router, prefix="/api")

# Include optimized RAG routes
from app.api.routes.rag_optimized import router as rag_optimized_router
app.include_router(rag_optimized_router)

try:
    from app.api.enhanced_routes import router as enhanced_router
except Exception:
    enhanced_router = None

if enhanced_router:
    app.include_router(enhanced_router)


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
