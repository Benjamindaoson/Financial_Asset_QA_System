from unittest.mock import Mock, patch

import pytest

from app.rag.hybrid_pipeline import HybridRAGPipeline


@pytest.mark.asyncio
@patch("app.rag.pipeline.chromadb.PersistentClient")
@patch("app.rag.pipeline.SentenceTransformer")
@patch("app.rag.pipeline.FlagReranker")
async def test_definition_query_prefers_curated_concept_chunks(mock_reranker, mock_transformer, mock_chroma):
    mock_client = Mock()
    mock_collection = Mock()
    mock_collection.count.return_value = 0
    mock_collection.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_chroma.return_value = mock_client

    pipeline = HybridRAGPipeline()
    pipeline.vector_index_synced = False

    result = await pipeline.search("什么是市盈率", use_hybrid=True)

    assert result.documents
    assert result.documents[0].source in {
        "core_finance_metrics.md",
        "valuation_metrics.md",
        "基本面分析.md",
    }
    assert "教材_" not in result.documents[0].source


@pytest.mark.asyncio
@patch("app.rag.pipeline.chromadb.PersistentClient")
@patch("app.rag.pipeline.SentenceTransformer")
@patch("app.rag.pipeline.FlagReranker")
@pytest.mark.parametrize(
    ("query", "expected_section_fragment"),
    [
        ("什么是PS", "市销率 (PS Ratio)"),
        ("什么是EV/EBITDA", "企业价值倍数 (EV/EBITDA)"),
        ("什么是BVPS", "每股净资产 (BVPS)"),
        ("什么是FCF", "自由现金流 (FCF)"),
        ("什么是毛利率", "毛利率"),
        ("什么是净利率", "净利率"),
    ],
)
async def test_new_metric_queries_hit_curated_metric_sections(
    mock_reranker,
    mock_transformer,
    mock_chroma,
    query,
    expected_section_fragment,
):
    mock_client = Mock()
    mock_collection = Mock()
    mock_collection.count.return_value = 0
    mock_collection.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]], "ids": [[]]}
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_chroma.return_value = mock_client

    pipeline = HybridRAGPipeline()
    pipeline.vector_index_synced = False

    result = await pipeline.search(query, use_hybrid=True)

    assert result.documents
    top_doc = result.documents[0]
    assert top_doc.source == "core_finance_metrics.md"
    assert expected_section_fragment in top_doc.section
