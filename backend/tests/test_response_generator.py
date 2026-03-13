"""Tests for ResponseGenerator."""

import pytest
from unittest.mock import AsyncMock, patch
from app.core.response_generator import ResponseGenerator


@pytest.mark.asyncio
async def test_response_generator_initialization():
    """Test that ResponseGenerator initializes correctly."""
    generator = ResponseGenerator()

    assert generator is not None
    assert generator.prompt_manager is not None
    assert generator.llm_client is not None


@pytest.mark.asyncio
async def test_generate_basic_response():
    """Test generating a basic response."""
    generator = ResponseGenerator()

    with patch.object(generator.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = """## AAPL股价查询

### 📊 数据摘要
当前价格: $150.25
涨跌幅: +2.5%
数据来源：Yahoo Finance | 时间：2026-03-12 10:00:00

### 📝 分析说明
苹果股价今日上涨2.5%，表现强劲。

### 📎 参考来源
- Yahoo Finance | 数据时间：2026-03-12 10:00:00

### 💡 相关问题
- AAPL的历史走势如何？
- AAPL与MSFT的对比如何？

---
⚠️ 免责声明：本回答仅供信息参考，不构成投资建议。"""

        response = await generator.generate(
            user_question="AAPL今天涨了多少？",
            api_data={"price": 150.25, "change_percent": 2.5},
            rag_context="",
            api_completeness=1.0,
            rag_relevance=0.0
        )

        assert "AAPL" in response
        assert "150.25" in response
        assert "免责声明" in response


@pytest.mark.asyncio
async def test_generate_with_rag_context():
    """Test generating response with RAG context."""
    generator = ResponseGenerator()

    with patch.object(generator.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = """## 市盈率解释

### 📊 数据摘要
市盈率（P/E Ratio）是股票价格与每股收益的比率。

### 📝 分析说明
市盈率是衡量股票估值的重要指标。

### 📎 参考来源
- 金融知识库 | 发布日期：2026-01-01

### 💡 相关问题
- 如何计算市盈率？
- 市盈率多少算合理？

---
⚠️ 免责声明：本回答仅供信息参考，不构成投资建议。"""

        response = await generator.generate(
            user_question="什么是市盈率？",
            api_data={},
            rag_context="市盈率是股票价格与每股收益的比率...",
            api_completeness=0.0,
            rag_relevance=0.95
        )

        assert "市盈率" in response
        assert "免责声明" in response


@pytest.mark.asyncio
async def test_generate_uses_correct_temperature():
    """Test that generator uses correct temperature from config."""
    generator = ResponseGenerator()

    with patch.object(generator.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Test response"

        await generator.generate(
            user_question="Test",
            api_data={},
            rag_context="",
            api_completeness=0.0,
            rag_relevance=0.0
        )

        call_kwargs = mock_llm.call_args[1]
        assert call_kwargs['temperature'] == 0.3  # Generator should use 0.3


@pytest.mark.asyncio
async def test_generate_formats_api_data():
    """Test that API data is properly formatted."""
    generator = ResponseGenerator()

    with patch.object(generator.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Test response"

        await generator.generate(
            user_question="Test",
            api_data={"price": 150.25, "volume": 1000000},
            rag_context="",
            api_completeness=1.0,
            rag_relevance=0.0
        )

        # Check that API data was formatted in the prompt
        call_args = mock_llm.call_args
        messages = call_args[1]["messages"]
        user_message = messages[1]["content"]
        assert "price" in user_message or "150.25" in user_message


@pytest.mark.asyncio
async def test_generate_handles_empty_data():
    """Test handling of empty API and RAG data."""
    generator = ResponseGenerator()

    with patch.object(generator.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = """## 查询结果

### 📊 数据摘要
暂无相关数据

### 📝 分析说明
抱歉，未能获取到相关数据。

---
⚠️ 免责声明：本回答仅供信息参考，不构成投资建议。"""

        response = await generator.generate(
            user_question="Test",
            api_data={},
            rag_context="",
            api_completeness=0.0,
            rag_relevance=0.0
        )

        assert "暂无" in response or "未能" in response
