import pytest
from app.rag.query_processor import QueryProcessor

@pytest.fixture
def processor():
    return QueryProcessor()

def test_query_cleaning(processor):
    """测试查询清洗"""
    query = "  苹果公司  的  市盈率   是多少？？  "
    cleaned = processor.clean_query(query)
    assert cleaned == "苹果公司的市盈率是多少？"
    assert "  " not in cleaned

def test_synonym_expansion(processor):
    """测试同义词扩展"""
    query = "PE是什么"
    expanded = processor.expand_synonyms(query)
    assert "市盈率" in expanded or "price-to-earnings" in expanded.lower()

def test_financial_term_normalization(processor):
    """测试金融术语标准化"""
    query = "ROE指标"
    normalized = processor.normalize_financial_terms(query)
    assert "净资产收益率" in normalized or "ROE" in normalized
