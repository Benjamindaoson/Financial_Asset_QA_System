"""
测试查询增强器
"""
import pytest
from app.enricher.enricher import QueryEnricher


class TestQueryEnricher:
    """测试QueryEnricher类"""

    def test_enricher_initialization(self):
        """测试增强器初始化"""
        enricher = QueryEnricher()
        assert enricher is not None

    def test_enrich_simple_query(self):
        """测试增强简单查询"""
        enricher = QueryEnricher()

        query = "苹果股价"
        enriched = enricher.enrich(query)

        assert isinstance(enriched, str)
        assert len(enriched) >= len(query)

    def test_enrich_with_symbol(self):
        """测试增强包含股票代码的查询"""
        enricher = QueryEnricher()

        query = "AAPL price"
        enriched = enricher.enrich(query)

        assert isinstance(enriched, str)
        assert "AAPL" in enriched

    def test_enrich_empty_query(self):
        """测试增强空查询"""
        enricher = QueryEnricher()

        query = ""
        enriched = enricher.enrich(query)

        assert isinstance(enriched, str)

    def test_enrich_chinese_query(self):
        """测试增强中文查询"""
        enricher = QueryEnricher()

        queries = [
            "茅台股价",
            "比亚迪涨了多少",
            "什么是市盈率"
        ]

        for query in queries:
            enriched = enricher.enrich(query)
            assert isinstance(enriched, str)
            assert len(enriched) > 0

    def test_enrich_english_query(self):
        """测试增强英文查询"""
        enricher = QueryEnricher()

        queries = [
            "Tesla stock price",
            "What is P/E ratio",
            "Apple vs Microsoft"
        ]

        for query in queries:
            enriched = enricher.enrich(query)
            assert isinstance(enriched, str)
            assert len(enriched) > 0

    def test_enrich_mixed_query(self):
        """测试增强中英文混合查询"""
        enricher = QueryEnricher()

        query = "AAPL苹果公司的股价"
        enriched = enricher.enrich(query)

        assert isinstance(enriched, str)
        assert "AAPL" in enriched or "苹果" in enriched

    def test_enrich_long_query(self):
        """测试增强长查询"""
        enricher = QueryEnricher()

        query = "请详细分析一下苹果公司最近一个季度的财务状况，包括营收、利润、市盈率等指标"
        enriched = enricher.enrich(query)

        assert isinstance(enriched, str)
        assert len(enriched) >= len(query)

    def test_enrich_special_characters(self):
        """测试增强包含特殊字符的查询"""
        enricher = QueryEnricher()

        queries = [
            "AAPL价格？",
            "特斯拉涨了吗！",
            "市盈率是什么？？？"
        ]

        for query in queries:
            enriched = enricher.enrich(query)
            assert isinstance(enriched, str)

    def test_enrich_numbers(self):
        """测试增强包含数字的查询"""
        enricher = QueryEnricher()

        queries = [
            "苹果股价150美元",
            "涨了10%",
            "市值3万亿"
        ]

        for query in queries:
            enriched = enricher.enrich(query)
            assert isinstance(enriched, str)

    def test_enrich_consistency(self):
        """测试增强的一致性"""
        enricher = QueryEnricher()

        query = "苹果股价"
        enriched1 = enricher.enrich(query)
        enriched2 = enricher.enrich(query)

        # 相同查询应该得到相同结果
        assert enriched1 == enriched2


class TestQueryEnricherEdgeCases:
    """测试查询增强器边界情况"""

    def test_enrich_very_long_query(self):
        """测试非常长的查询"""
        enricher = QueryEnricher()

        query = "请详细分析" * 100
        enriched = enricher.enrich(query)

        assert isinstance(enriched, str)

    def test_enrich_only_numbers(self):
        """测试纯数字查询"""
        enricher = QueryEnricher()

        query = "123456"
        enriched = enricher.enrich(query)

        assert isinstance(enriched, str)

    def test_enrich_only_symbols(self):
        """测试纯符号查询"""
        enricher = QueryEnricher()

        query = "!@#$%^&*()"
        enriched = enricher.enrich(query)

        assert isinstance(enriched, str)

    def test_enrich_whitespace_query(self):
        """测试空白字符查询"""
        enricher = QueryEnricher()

        query = "   \t\n   "
        enriched = enricher.enrich(query)

        assert isinstance(enriched, str)


class TestQueryEnricherAdvanced:
    """测试查询增强器高级功能"""

    def test_enrich_multiple_symbols(self):
        """测试多个股票代码"""
        enricher = QueryEnricher()
        
        query = "比较AAPL和TSLA的表现"
        enriched = enricher.enrich(query)
        
        assert isinstance(enriched, str)
        assert len(enriched) > 0

    def test_enrich_with_dates(self):
        """测试包含日期的查询"""
        enricher = QueryEnricher()
        
        query = "2024年3月5日的股价"
        enriched = enricher.enrich(query)
        
        assert isinstance(enriched, str)

    def test_enrich_question_format(self):
        """测试问题格式"""
        enricher = QueryEnricher()
        
        queries = [
            "什么是市盈率？",
            "如何计算市净率？",
            "为什么股价下跌？"
        ]
        
        for query in queries:
            enriched = enricher.enrich(query)
            assert isinstance(enriched, str)
            assert len(enriched) > 0
