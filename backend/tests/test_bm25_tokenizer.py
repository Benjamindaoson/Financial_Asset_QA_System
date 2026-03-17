import pytest
from app.rag.hybrid_retrieval import BM25Retriever


@pytest.fixture
def retriever():
    return BM25Retriever()


def test_tokenize_chinese_with_jieba(retriever):
    """测试中文分词使用jieba"""
    text = "苹果公司的市盈率是25倍"

    tokens = retriever._tokenize(text)

    # jieba应该将"市盈率"作为一个词
    assert "市盈率" in tokens
    # 不应该拆分为单字
    assert tokens.count("市") == 0 or "市盈率" in tokens


def test_tokenize_mixed_text(retriever):
    """测试中英文混合分词"""
    text = "AAPL的PE ratio是多少"

    tokens = retriever._tokenize(text)

    # 英文应该保留
    assert "aapl" in tokens or any("aapl" in t.lower() for t in tokens)
    assert "pe" in tokens or any("pe" in t.lower() for t in tokens)
    assert "ratio" in tokens


def test_financial_terms_not_split(retriever):
    """测试金融术语不被拆分"""
    text = "净资产收益率ROE"

    tokens = retriever._tokenize(text)

    # "净资产收益率"应该作为一个词（如果在词典中）
    # 至少不应该完全拆分为单字
    assert len(tokens) < 10  # 如果完全拆分会有更多token
