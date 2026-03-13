"""Integration tests for the complete system with new components."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.core import PromptManager, LLMClient, ResponseGenerator, ComplianceChecker
from app.routing.hybrid_router import HybridRouter


@pytest.mark.asyncio
async def test_prompt_manager_integration():
    """Test that PromptManager loads prompts correctly."""
    manager = PromptManager()

    # Should load all three prompt types
    assert manager.get_system_prompt("router") is not None
    assert manager.get_system_prompt("generator") is not None
    assert manager.get_system_prompt("compliance") is not None

    # Should render templates
    rendered = manager.render_user_prompt("router", user_question="测试问题")
    assert "测试问题" in rendered


@pytest.mark.asyncio
async def test_llm_client_integration():
    """Test that LLMClient can make API calls."""
    client = LLMClient()

    with patch.object(client.client.chat.completions, 'create', new_callable=AsyncMock) as mock_create:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_create.return_value = mock_response

        response = await client.chat_completion(
            messages=[{"role": "user", "content": "test"}],
            temperature=0.3,
            max_tokens=100
        )

        assert response == "Test response"
        assert mock_create.called


@pytest.mark.asyncio
async def test_hybrid_router_integration():
    """Test that HybridRouter integrates rule and LLM routing."""
    router = HybridRouter()

    # High confidence query should use rule routing
    result = await router.route("AAPL今天价格")

    # HybridRouter returns query_type (from rule router) or question_type (from LLM router)
    assert "query_type" in result or "question_type" in result
    assert "confidence" in result
    assert "route" in result
    assert result["confidence"] >= 0.0


@pytest.mark.asyncio
async def test_response_generator_integration():
    """Test that ResponseGenerator generates structured responses."""
    generator = ResponseGenerator()

    with patch.object(generator.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = """## 测试回答

### 📊 数据摘要
测试数据

### 📝 分析说明
测试分析

---
⚠️ 免责声明：本回答仅供信息参考，不构成投资建议。"""

        response = await generator.generate(
            user_question="测试问题",
            api_data={"price": 150.0},
            rag_context="",
            api_completeness=1.0,
            rag_relevance=0.0
        )

        assert "测试回答" in response
        assert "免责声明" in response


@pytest.mark.asyncio
async def test_compliance_checker_integration():
    """Test that ComplianceChecker validates responses."""
    checker = ComplianceChecker()

    # Compliant content should pass
    result = await checker.check(
        llm_output="AAPL价格为$150.25。⚠️ 免责声明：本回答仅供信息参考，不构成投资建议。",
        user_question="AAPL价格是多少？",
        api_fields_provided=["price"],
        rag_docs_count=0
    )

    assert result["is_compliant"] is True
    assert result["action"] == "pass"


@pytest.mark.asyncio
async def test_end_to_end_query_flow():
    """Test complete query flow: routing -> generation -> compliance."""
    # Step 1: Route the query
    router = HybridRouter()
    route_result = await router.route("AAPL今天涨了多少？")

    assert route_result is not None
    # HybridRouter returns query_type (from rule router) or question_type (from LLM router)
    assert "query_type" in route_result or "question_type" in route_result

    # Step 2: Generate response
    generator = ResponseGenerator()

    with patch.object(generator.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = """## AAPL股价查询

### 📊 数据摘要
当前价格: $150.25
涨跌幅: +2.5%

### 📝 分析说明
苹果股价今日上涨2.5%。

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
        assert "免责声明" in response

    # Step 3: Check compliance
    checker = ComplianceChecker()
    compliance_result = await checker.check(
        llm_output=response,
        user_question="AAPL今天涨了多少？",
        api_fields_provided=["price", "change_percent"],
        rag_docs_count=0
    )

    assert compliance_result["is_compliant"] is True
    assert compliance_result["action"] == "pass"


@pytest.mark.asyncio
async def test_compliance_blocks_investment_advice():
    """Test that compliance checker blocks investment advice in end-to-end flow."""
    generator = ResponseGenerator()

    with patch.object(generator.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_gen:
        # Simulate LLM generating non-compliant content
        mock_gen.return_value = "建议买入AAPL股票，预计将上涨至$200。"

        response = await generator.generate(
            user_question="AAPL值得买吗？",
            api_data={"price": 150.0},
            rag_context="",
            api_completeness=1.0,
            rag_relevance=0.0
        )

    # Check compliance
    checker = ComplianceChecker()
    compliance_result = await checker.check(
        llm_output=response,
        user_question="AAPL值得买吗？",
        api_fields_provided=["price"],
        rag_docs_count=0
    )

    assert compliance_result["is_compliant"] is False
    assert compliance_result["risk_level"] == "high"
    assert compliance_result["action"] == "block"
    assert compliance_result["safe_fallback"] is not None
