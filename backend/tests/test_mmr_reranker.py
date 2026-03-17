import pytest
import numpy as np
from app.rag.mmr_reranker import MMRReranker
from app.models.schemas import Document

@pytest.fixture
def reranker():
    return MMRReranker(lambda_param=0.7)

@pytest.fixture
def sample_documents():
    """创建测试文档（包含相似和不同的文档）"""
    return [
        Document(content="市盈率是股价除以每股收益", source="doc1.md", score=0.9),
        Document(content="PE ratio是股价除以每股收益的比率", source="doc2.md", score=0.85),  # 与doc1相似
        Document(content="市净率是股价除以每股净资产", source="doc3.md", score=0.8),  # 不同主题
        Document(content="市盈率用于衡量股票估值水平", source="doc4.md", score=0.75),  # 与doc1相似
        Document(content="波动率反映价格变化幅度", source="doc5.md", score=0.7),  # 不同主题
    ]

def test_mmr_increases_diversity(reranker, sample_documents):
    """测试MMR提升结果多样性"""
    # 提供简单的相似度函数（基于内容长度差异）
    def similarity_fn(doc1, doc2):
        # 简化：基于共同字符数
        common = set(doc1.content) & set(doc2.content)
        return len(common) / max(len(doc1.content), len(doc2.content))

    reranked = reranker.rerank(sample_documents, top_n=3, similarity_fn=similarity_fn)

    # MMR应该选择多样化的文档
    assert len(reranked) == 3
    # 第一个应该是最高分
    assert reranked[0].source == "doc1.md"
    # 后续应该包含不同主题的文档
    sources = [doc.source for doc in reranked]
    # 应该包含至少一个不同主题的文档（doc3或doc5）
    assert "doc3.md" in sources or "doc5.md" in sources

def test_mmr_with_high_lambda_prefers_relevance(reranker, sample_documents):
    """测试高lambda值偏向相关性"""
    high_lambda_reranker = MMRReranker(lambda_param=0.9)

    def similarity_fn(doc1, doc2):
        common = set(doc1.content) & set(doc2.content)
        return len(common) / max(len(doc1.content), len(doc2.content))

    reranked = high_lambda_reranker.rerank(sample_documents, top_n=3, similarity_fn=similarity_fn)

    # 高lambda应该更偏向高分文档
    assert reranked[0].score >= reranked[1].score
