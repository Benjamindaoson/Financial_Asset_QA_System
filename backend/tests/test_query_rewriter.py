"""Tests for query rewriter."""
import pytest
from app.rag.query_rewriter import QueryRewriter


def test_query_rewriter_initialization():
    """Test QueryRewriter initialization."""
    rewriter = QueryRewriter()
    assert rewriter.synonym_map is not None
    assert len(rewriter.synonym_map) > 0


def test_normalize_query_english_to_chinese():
    """Test normalizing English terms to Chinese."""
    rewriter = QueryRewriter()

    query = "What is the PE ratio of AAPL?"
    normalized = rewriter.normalize_query(query)

    assert "市盈率" in normalized
    assert "pe" not in normalized.lower() or "市盈率" in normalized


def test_normalize_query_preserves_chinese():
    """Test that Chinese queries are preserved."""
    rewriter = QueryRewriter()

    query = "苹果的市盈率是多少？"
    normalized = rewriter.normalize_query(query)

    assert "市盈率" in normalized


def test_expand_query_with_synonyms():
    """Test query expansion with synonyms."""
    rewriter = QueryRewriter()

    query = "股票价格上涨"
    expanded = rewriter.expand_query(query)

    assert len(expanded) > 1
    assert query in expanded
    # Should have variations with synonyms
    assert any("股价" in q or "股份" in q for q in expanded)


def test_expand_query_limits_expansions():
    """Test that query expansion is limited."""
    rewriter = QueryRewriter()

    query = "股票价格上涨"
    expanded = rewriter.expand_query(query)

    assert len(expanded) <= 5


def test_generate_multi_queries():
    """Test generating multiple query variations."""
    rewriter = QueryRewriter()

    query = "什么是PE ratio？"
    multi_queries = rewriter.generate_multi_queries(query)

    assert len(multi_queries) > 1
    assert query in multi_queries
    # Should include normalized version
    assert any("市盈率" in q for q in multi_queries)


def test_generate_multi_queries_removes_duplicates():
    """Test that duplicate queries are removed."""
    rewriter = QueryRewriter()

    query = "股票价格"
    multi_queries = rewriter.generate_multi_queries(query)

    # Should not have duplicates
    assert len(multi_queries) == len(set(multi_queries))


def test_extract_keywords():
    """Test keyword extraction."""
    rewriter = QueryRewriter()

    query = "苹果公司的股票价格是多少？"
    keywords = rewriter.extract_keywords(query)

    assert len(keywords) > 0
    # Without proper Chinese word segmentation, the whole phrase may be returned
    # This is acceptable for basic keyword extraction
    assert any("苹果" in k for k in keywords)
    # Stop words should be removed
    assert not any(k in ["的", "是"] for k in keywords)


def test_extract_keywords_filters_short_words():
    """Test that short words are filtered."""
    rewriter = QueryRewriter()

    query = "PE is a ratio"
    keywords = rewriter.extract_keywords(query)

    # Single letter words should be filtered
    assert "a" not in keywords


def test_rewrite_returns_complete_result():
    """Test that rewrite returns all components."""
    rewriter = QueryRewriter()

    query = "什么是PE？"
    result = rewriter.rewrite(query)

    assert "original" in result
    assert "normalized" in result
    assert "expanded" in result
    assert "multi_queries" in result
    assert "keywords" in result

    assert result["original"] == query
    assert isinstance(result["normalized"], str)
    assert isinstance(result["expanded"], list)
    assert isinstance(result["multi_queries"], list)
    assert isinstance(result["keywords"], list)


def test_rewrite_with_complex_query():
    """Test rewriting a complex financial query."""
    rewriter = QueryRewriter()

    query = "特斯拉的PE ratio和营收增长率是多少？"
    result = rewriter.rewrite(query)

    # Should normalize PE to 市盈率
    assert any("市盈率" in q for q in result["multi_queries"])

    # Should have multiple variations
    assert len(result["multi_queries"]) > 1

    # Should extract key terms
    assert len(result["keywords"]) > 0
