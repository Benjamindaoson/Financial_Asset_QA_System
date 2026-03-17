import pytest
from pathlib import Path


def test_grounded_prompt_has_few_shot_examples():
    """测试RAG生成器提示词包含Few-Shot示例"""
    # Read grounded_pipeline.py to check the prompt template
    grounded_pipeline_path = Path(__file__).parent.parent / "app" / "rag" / "grounded_pipeline.py"
    with open(grounded_pipeline_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 应该包含示例标记
    assert "【示例1" in content
    assert "【示例2" in content
    assert "【示例3" in content
    assert "查询:" in content
    assert "回答:" in content


def test_grounded_prompt_has_citation_requirement():
    """测试RAG提示词要求引用来源"""
    # Read grounded_pipeline.py to check the prompt template
    grounded_pipeline_path = Path(__file__).parent.parent / "app" / "rag" / "grounded_pipeline.py"
    with open(grounded_pipeline_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 应该明确要求引用
    assert "[文档" in content
    assert "引用来源" in content or "标注来源" in content
