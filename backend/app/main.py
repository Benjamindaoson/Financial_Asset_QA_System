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

    # Start background index building (non-blocking)
    logger = logging.getLogger(__name__)
    logger.info("Checking knowledge index...")

    from pathlib import Path
    import asyncio
    chroma_dir = Path(__file__).parent.parent / "data" / "chroma_db"

    # Check if index exists and has content
    needs_build = True
    if chroma_dir.exists():
        chroma_files = list(chroma_dir.rglob("*"))
        if len(chroma_files) > 5:  # Has some content
            needs_build = False
            logger.info(f"Knowledge index exists with {len(chroma_files)} files")

    if needs_build:
        logger.info("Starting background knowledge index build...")
        # Run index building in background thread to avoid blocking startup
        async def build_index_async():
            try:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    loop = asyncio.get_event_loop()
                    from scripts.build_knowledge_index import build_index
                    success = await loop.run_in_executor(executor, build_index)
                    if success:
                        logger.info("Background knowledge index build completed successfully")
                    else:
                        logger.warning("Background knowledge index build returned False")
            except Exception as e:
                logger.error(f"Background knowledge index build failed: {e}", exc_info=True)

        # Start the task but don't wait for it
        asyncio.create_task(build_index_async())
        logger.info("Knowledge index build started in background")

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
