"""RAG package exports with lazy imports to avoid heavy startup side effects."""

from __future__ import annotations

from typing import Any

__all__ = ["RAGPipeline", "HybridRAGPipeline", "MinerUClient", "MinerUDocumentIngestor"]


def __getattr__(name: str) -> Any:
    if name == "RAGPipeline":
        from app.rag.pipeline import RAGPipeline

        return RAGPipeline
    if name == "HybridRAGPipeline":
        from app.rag.hybrid_pipeline import HybridRAGPipeline

        return HybridRAGPipeline
    if name == "MinerUClient":
        from app.rag.mineru_client import MinerUClient

        return MinerUClient
    if name == "MinerUDocumentIngestor":
        from app.rag.mineru_ingestion import MinerUDocumentIngestor

        return MinerUDocumentIngestor
    raise AttributeError(name)
