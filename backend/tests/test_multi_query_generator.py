import pytest
from app.rag.multi_query_generator import MultiQueryGenerator

@pytest.fixture
def generator():
    return MultiQueryGenerator()

def test_generate_perspective_queries(generator):
    """测试生成不同视角的查询"""
    query = "苹果公司的市盈率是多少？"

    queries = generator.generate_queries(query, num_queries=3)

    assert len(queries) >= 2  # 至少包含原查询+1个变体
    assert query in queries  # 包含原查询
    # 变体应该包含同义词或不同表达
    assert any("PE" in q or "估值" in q for q in queries)

def test_generate_decomposed_queries(generator):
    """测试复杂查询分解"""
    query = "对比苹果和微软的市盈率和市净率"

    queries = generator.generate_queries(query, num_queries=4)

    # 应该分解为子查询
    assert len(queries) >= 3
    # 可能包含单独的查询
    assert any("苹果" in q and "市盈率" in q for q in queries)

def test_financial_term_expansion(generator):
    """测试金融术语扩展"""
    query = "什么是PE？"

    queries = generator.generate_queries(query, num_queries=2)

    # 应该扩展缩写
    assert any("市盈率" in q for q in queries)
