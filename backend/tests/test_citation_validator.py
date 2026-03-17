import pytest
from app.rag.citation_validator import CitationValidator

@pytest.fixture
def validator():
    return CitationValidator()

def test_detect_valid_citations(validator):
    """测试检测有效引用"""
    answer = "市盈率是股价除以每股收益[文档1]。"
    num_docs = 3

    result = validator.validate(answer, num_docs)
    assert result["is_valid"] is True
    assert len(result["citations"]) == 1
    assert 1 in result["citations"]

def test_detect_invalid_citations(validator):
    """测试检测无效引用"""
    answer = "市盈率是股价除以每股收益[文档5]。"
    num_docs = 3

    result = validator.validate(answer, num_docs)
    assert result["is_valid"] is False
    assert 5 in result["invalid_citations"]

def test_detect_missing_citations(validator):
    """测试检测缺失引用"""
    answer = "市盈率是股价除以每股收益。"
    num_docs = 3

    result = validator.validate(answer, num_docs)
    assert result["has_citations"] is False

def test_fix_invalid_citations(validator):
    """测试修复无效引用"""
    answer = "市盈率[文档5]是重要指标[文档10]。"
    num_docs = 3

    fixed = validator.fix_citations(answer, num_docs)
    assert "[文档5]" not in fixed
    assert "[文档10]" not in fixed
