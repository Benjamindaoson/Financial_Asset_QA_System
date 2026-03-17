import pytest
from app.rag.dynamic_topk import DynamicTopKCalculator

@pytest.fixture
def calculator():
    return DynamicTopKCalculator()

def test_simple_query_small_k(calculator):
    """测试简单查询使用较小K值"""
    query = "什么是市盈率？"

    k = calculator.calculate_topk(query)

    assert k <= 5  # 简单定义查询，小K值足够

def test_complex_query_large_k(calculator):
    """测试复杂查询使用较大K值"""
    query = "对比苹果、微软、谷歌三家公司的市盈率、市净率和ROE，分析哪家估值更合理"

    k = calculator.calculate_topk(query)

    assert k >= 8  # 复杂对比查询，需要更多文档

def test_multi_entity_query(calculator):
    """测试多实体查询"""
    query = "苹果、微软、特斯拉的股价"

    k = calculator.calculate_topk(query)

    assert k >= 6  # 3个实体，每个至少2个文档
