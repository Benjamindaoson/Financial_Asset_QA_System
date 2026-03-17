import pytest
from app.rag.hybrid_pipeline import HybridRAGPipeline
from app.config import settings


@pytest.fixture
async def pipeline():
    """创建HybridRAGPipeline实例"""
    return HybridRAGPipeline()


@pytest.mark.asyncio
async def test_query_preprocessing_integration(pipeline):
    """测试查询预处理集成到pipeline"""
    # 测试查询清洗和标准化
    query = "  PE  是什么？？  "

    # 验证pipeline有query_processor
    assert hasattr(pipeline, 'query_processor')
    assert pipeline.query_processor is not None

    # 验证query_processor可以处理查询
    processed = pipeline.query_processor.process(query)
    assert processed["cleaned"] == "PE是什么？"
    assert "市盈率" in processed["normalized"]


@pytest.mark.asyncio
async def test_synonym_expansion_improves_recall(pipeline):
    """测试同义词扩展提升召回率"""
    # 原始查询
    query_original = "ROE指标"

    # 处理后的查询应该包含同义词
    processed = pipeline.query_processor.process(query_original)

    # 验证术语标准化
    assert "净资产收益率" in processed["normalized"]

    # 验证同义词扩展（如果启用）
    if settings.QUERY_SYNONYM_EXPANSION:
        assert len(processed["expanded_queries"]) >= 1


@pytest.mark.asyncio
async def test_preprocessing_does_not_break_existing_functionality(pipeline):
    """测试预处理不破坏现有功能"""
    # 简单查询应该正常工作
    query = "苹果公司"

    processed = pipeline.query_processor.process(query)

    # 验证基本处理
    assert processed["original"] == query
    assert processed["cleaned"] == query
    assert processed["normalized"] is not None
    assert len(processed["expanded_queries"]) > 0
