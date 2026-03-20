"""Tests for RAG chunking module."""

import pytest

from app.rag.chunking import chunk_by_paragraphs, chunk_document


def test_chunk_by_paragraphs_empty():
    assert chunk_by_paragraphs("") == []
    assert chunk_by_paragraphs("   ") == []


def test_chunk_by_paragraphs_single_short():
    text = "Short text."
    result = chunk_by_paragraphs(text)
    assert len(result) == 1
    assert result[0] == "Short text."


def test_chunk_by_paragraphs_respects_boundaries():
    text = "Para one.\n\nPara two.\n\nPara three."
    result = chunk_by_paragraphs(text, chunk_size=50, chunk_overlap=10)
    assert len(result) >= 1
    assert "Para one" in result[0]


def test_chunk_document_returns_metadata():
    content = "First paragraph with enough text.\n\nSecond paragraph with more content for the chunk."
    result = chunk_document(content, "test.md", "knowledge/test.md")
    assert len(result) >= 1
    for ch in result:
        assert "content" in ch
        assert "source" in ch
        assert "chunk_index" in ch
        assert "chunk_id" in ch
        assert ch["source"] == "test.md"
        assert "knowledge_test" in ch["chunk_id"] or "test" in ch["chunk_id"]


def test_chunk_document_unique_ids_across_dirs():
    content = "Some content here that is long enough to pass the minimum length filter."
    r1 = chunk_document(content, "file.md", "knowledge/file.md")
    r2 = chunk_document(content, "file.md", "raw_data/file.md")
    assert len(r1) >= 1 and len(r2) >= 1
    assert r1[0]["chunk_id"] != r2[0]["chunk_id"]
    assert "knowledge" in r1[0]["chunk_id"]
    assert "raw_data" in r2[0]["chunk_id"]
