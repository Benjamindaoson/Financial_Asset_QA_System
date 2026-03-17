import pytest
from app.rag.confidence_scorer import ConfidenceScorer
from app.models.schemas import Document

@pytest.fixture
def scorer():
    return ConfidenceScorer()

@pytest.fixture
def high_quality_docs():
    """高质量文档：高分、多文档、有引用"""
    return [
        Document(content="市盈率是股价除以每股收益", source="doc1.md", score=0.9),
        Document(content="PE ratio计算公式为股价/EPS", source="doc2.md", score=0.85),
        Document(content="市盈率用于衡量估值水平", source="doc3.md", score=0.8),
    ]

@pytest.fixture
def low_quality_docs():
    """低质量文档：低分、单文档"""
    return [
        Document(content="一些不太相关的内容", source="doc1.md", score=0.3),
    ]

def test_high_confidence_with_quality_docs(scorer, high_quality_docs):
    """测试高质量文档产生高置信度"""
    answer = "市盈率是股价除以每股收益的比率[文档1]，用于衡量估值[文档3]。"

    confidence = scorer.calculate_confidence(
        answer=answer,
        documents=high_quality_docs,
        query="什么是市盈率？"
    )

    assert confidence >= 0.7  # 高置信度

def test_low_confidence_with_poor_docs(scorer, low_quality_docs):
    """测试低质量文档产生低置信度"""
    answer = "市盈率是一个指标。"

    confidence = scorer.calculate_confidence(
        answer=answer,
        documents=low_quality_docs,
        query="什么是市盈率？"
    )

    assert confidence < 0.5  # 低置信度

def test_confidence_considers_citations(scorer, high_quality_docs):
    """测试置信度考虑引用情况"""
    answer_with_citations = "市盈率是股价除以每股收益[文档1]。"
    answer_without_citations = "市盈率是股价除以每股收益。"

    conf_with = scorer.calculate_confidence(
        answer=answer_with_citations,
        documents=high_quality_docs,
        query="什么是市盈率？"
    )

    conf_without = scorer.calculate_confidence(
        answer=answer_without_citations,
        documents=high_quality_docs,
        query="什么是市盈率？"
    )

    # 有引用的置信度应该更高
    assert conf_with > conf_without

def test_confidence_breakdown(scorer, high_quality_docs):
    """测试置信度分解"""
    answer = "市盈率是股价除以每股收益[文档1]。"

    result = scorer.calculate_confidence_breakdown(
        answer=answer,
        documents=high_quality_docs,
        query="什么是市盈率？"
    )

    assert "overall" in result
    assert "retrieval_quality" in result
    assert "answer_quality" in result
    assert "citation_quality" in result
    assert 0 <= result["overall"] <= 1
