import pytest
from app.models.schemas import StructuredAnswer

def test_structured_answer_model():
    """测试结构化答案模型"""
    answer = StructuredAnswer(
        answer="市盈率是股价除以每股收益[文档1]。",
        confidence=0.85,
        sources=["doc1.md", "doc2.md"],
        metadata={
            "retrieval_quality": 0.9,
            "answer_quality": 0.8,
            "citation_quality": 0.85,
        }
    )

    assert answer.answer == "市盈率是股价除以每股收益[文档1]。"
    assert answer.confidence == 0.85
    assert len(answer.sources) == 2
    assert "retrieval_quality" in answer.metadata

def test_structured_answer_serialization():
    """测试序列化"""
    answer = StructuredAnswer(
        answer="测试答案",
        confidence=0.75,
        sources=["doc1.md"],
        metadata={"key": "value"}
    )

    data = answer.model_dump()

    assert data["answer"] == "测试答案"
    assert data["confidence"] == 0.75
    assert data["sources"] == ["doc1.md"]
    assert data["metadata"]["key"] == "value"
