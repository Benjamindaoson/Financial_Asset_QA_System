"""
FastAPI Main Application
"""
import os

# Set HuggingFace mirror for users in restricted network environments BEFORE any model imports
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import router
from app.config import settings

app = FastAPI(
    title="Financial Asset QA System",
    description="""
    ## AI-powered Financial Asset Question Answering System

    This API provides intelligent financial analysis and question answering capabilities:

    * **Chat Interface**: Natural language queries about stocks, funds, and financial concepts
    * **Market Data**: Real-time stock prices and historical charts
    * **RAG Pipeline**: Retrieval-augmented generation for accurate financial knowledge
    * **Agent System**: Multi-step reasoning with tool use for complex queries

    ### Features
    - Real-time market data integration
    - Financial knowledge base with 10,000+ entries
    - Multi-turn conversation support
    - Source attribution and confidence scoring
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "chat",
            "description": "Chat and question answering endpoints"
        },
        {
            "name": "market",
            "description": "Market data and chart endpoints"
        },
        {
            "name": "health",
            "description": "Health check and system status"
        }
    ]
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
        port=8000,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )
