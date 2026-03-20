"""
Semantic chunking for RAG - paragraph-based with structure preservation.
Unified chunking used by ChromaDB, BM25, and Token-Match.
"""
from __future__ import annotations

import re
from typing import List, Dict, Any


def chunk_by_paragraphs(
    text: str,
    chunk_size: int = 600,
    chunk_overlap: int = 120,
) -> List[str]:
    """
    Chunk text by paragraph boundaries, preserving semantic units.
    Similar to StructurePreservingChunker._chunk_text but for raw Markdown/text.

    Args:
        text: Raw document content
        chunk_size: Max characters per chunk
        chunk_overlap: Overlap between consecutive chunks

    Returns:
        List of chunk strings
    """
    if not text or not text.strip():
        return []

    paragraphs = re.split(r"\n\n+", text.strip())
    chunks: List[str] = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            if chunk_overlap > 0:
                overlap_text = current_chunk[-chunk_overlap:]
                current_chunk = overlap_text + "\n\n" + para
            else:
                current_chunk = para
        else:
            current_chunk = current_chunk + "\n\n" + para if current_chunk else para

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def chunk_document(content: str, source: str, doc_key: str | None = None) -> List[Dict[str, Any]]:
    """
    Chunk a single document and return list of chunk dicts with metadata.

    Args:
        content: Document content
        source: Source file name (e.g. "core_finance_metrics.md")
        doc_key: Unique doc key (e.g. "knowledge/core_finance_metrics.md") for chunk_id.
                 If None, uses source (may cause duplicates across dirs).

    Returns:
        List of {"content", "source", "chunk_index", "chunk_id"}
    """
    chunks = chunk_by_paragraphs(content, chunk_size=600, chunk_overlap=120)
    result: List[Dict[str, Any]] = []
    base = (doc_key or source).replace("/", "_").replace("\\", "_")

    for i, chunk_text in enumerate(chunks):
        if not chunk_text or len(chunk_text.strip()) < 20:
            continue
        chunk_id = f"{base}_{i}"
        result.append({
            "content": chunk_text,
            "source": source,
            "chunk_index": i,
            "chunk_id": chunk_id,
        })

    return result
