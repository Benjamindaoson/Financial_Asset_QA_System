"""Tests for internal agent service layers."""

import asyncio
from unittest.mock import Mock

from app.agent.answer_assembler import AnswerAssembler
from app.agent.tool_executor import ToolExecutor
from app.models import StructuredBlock, ToolResult
from app.routing import QueryRoute, QueryType
from app.routing.complexity_analyzer import ComplexityScore


def test_tool_executor_returns_empty_knowledge_payload_when_rag_unavailable():
    executor = ToolExecutor(
        market_service=Mock(),
        search_service=Mock(),
        sec_service=Mock(),
        rag_pipeline=None,
        confidence_scorer=Mock(),
    )

    result = asyncio.run(executor.search_knowledge("what is pe ratio", top_k=3))

    assert result["documents"] == []
    assert result["method_used"] == "unavailable"
    assert result["confidence_level"] == "low"


def test_answer_assembler_orders_blocks_for_frontend_contract():
    assembler = AnswerAssembler(answer_confidence_scorer=Mock(), citation_validator=Mock())
    route = QueryRoute(query_type=QueryType.HYBRID, cleaned_query="AAPL earnings", symbols=["AAPL"])
    blocks = [
        StructuredBlock(type="news", title="News", data={}),
        StructuredBlock(type="analysis", title="Analysis", data={}),
        StructuredBlock(type="chart", title="Chart", data={}),
        StructuredBlock(type="quote", title="Quote", data={}),
        StructuredBlock(type="warning", title="Warning", data={}),
        StructuredBlock(type="table", title="Table", data={}),
        StructuredBlock(type="key_metrics", title="Metrics", data={}),
    ]

    ordered = assembler.order_blocks(blocks, route)

    assert [block.type for block in ordered] == [
        "chart",
        "key_metrics",
        "table",
        "analysis",
        "quote",
        "news",
        "warning",
    ]


def test_answer_assembler_builds_done_data_contract():
    confidence_scorer = Mock()
    confidence_scorer.calculate_confidence_breakdown.return_value = {"overall": 0.78}
    citation_validator = Mock()
    citation_validator.validate.return_value = {"valid": True}
    assembler = AnswerAssembler(confidence_scorer, citation_validator)

    route = QueryRoute(query_type=QueryType.KNOWLEDGE, cleaned_query="what is pe ratio")
    complexity = ComplexityScore(
        level="medium",
        score=0.45,
        recommended_model="deepseek-chat",
        rag_top_k=5,
        timeout_multiplier=1.5,
        reasoning="knowledge retrieval",
    )
    tool_results = [
        ToolResult(
            tool="search_knowledge",
            data={
                "documents": [
                    {"content": "---\ntitle: test\n---\nPE ratio compares price to earnings", "source": "kb.md", "score": 0.91}
                ],
                "method_used": "hybrid_vector",
            },
            latency_ms=18,
            status="success",
            data_source="kb",
            cache_hit=False,
            error_message=None,
        )
    ]
    blocks = [StructuredBlock(type="quote", title="Quote", data={"items": []})]

    done_data = assembler.build_done_data(
        query="what is pe ratio",
        route=route,
        tool_results=tool_results,
        blocks=blocks,
        validation={"level": "high", "confidence": 88},
        llm_used=False,
        final_answer_text="PE ratio compares price to earnings.",
        complexity_score=complexity,
        disclaimer="test disclaimer",
    )

    assert done_data["route"]["type"] == "knowledge"
    assert done_data["rag_citations"][0]["source"] == "kb.md"
    assert done_data["tool_latencies"][0]["latency_ms"] == 18
    assert done_data["confidence_breakdown"] == {"overall": 0.78}
    assert done_data["citation_validation"] == {"valid": True}
