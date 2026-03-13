"""End-to-end acceptance tests for the complete system."""

import pytest
import time
from unittest.mock import AsyncMock, patch

from app.core import PromptManager, LLMClient, ResponseGenerator, ComplianceChecker
from app.routing.hybrid_router import HybridRouter


@pytest.mark.asyncio
async def test_1_prompts_yaml_loading():
    """Test 1: Verify prompts.yaml loads successfully."""
    start = time.time()

    prompt_manager = PromptManager()

    # Check all three prompts exist
    router_prompt = prompt_manager.get_system_prompt("router")
    generator_prompt = prompt_manager.get_system_prompt("generator")
    compliance_prompt = prompt_manager.get_system_prompt("compliance")

    assert router_prompt is not None
    assert generator_prompt is not None
    assert compliance_prompt is not None
    assert len(router_prompt) > 100

    duration = (time.time() - start) * 1000
    print(f"\n✅ prompts.yaml loading ({duration:.2f}ms) - All 3 prompts loaded")


@pytest.mark.asyncio
async def test_2_llm_client_initialization():
    """Test 2: Verify LLMClient initializes correctly."""
    start = time.time()

    llm_client = LLMClient()

    assert llm_client.api_key is not None
    assert llm_client.base_url is not None
    assert llm_client.model is not None

    duration = (time.time() - start) * 1000
    print(f"\n✅ LLMClient initialization ({duration:.2f}ms) - Model: {llm_client.model}")


@pytest.mark.asyncio
async def test_3_hybrid_router_simple_query():
    """Test 3: Test hybrid router with simple query (should use rule routing)."""
    start = time.time()

    hybrid_router = HybridRouter()

    result = await hybrid_router.route("AAPL今天价格")

    assert result is not None
    assert "confidence" in result
    assert "route" in result
    assert result["confidence"] > 0.7  # Should have high confidence

    duration = (time.time() - start) * 1000
    print(f"\n✅ Hybrid router - simple query ({duration:.2f}ms) - Confidence: {result['confidence']:.2f}, Route: {result['route']}")

    # Check latency requirement
    if duration > 5:
        print(f"   ⚠️  Warning: Rule routing took {duration:.2f}ms (target: <5ms)")


@pytest.mark.asyncio
async def test_4_hybrid_router_complex_query():
    """Test 4: Test hybrid router with complex query (may use LLM routing)."""
    start = time.time()

    hybrid_router = HybridRouter()
    result = await hybrid_router.route("请解释一下什么是市盈率，以及它在投资决策中的作用")

    assert result is not None
    assert "confidence" in result
    assert "route" in result

    duration = (time.time() - start) * 1000
    print(f"\n✅ Hybrid router - complex query ({duration:.2f}ms) - Confidence: {result['confidence']:.2f}, Route: {result['route']}")

    # Check latency requirement
    if duration > 500:
        print(f"   ⚠️  Warning: LLM routing took {duration:.2f}ms (target: <500ms)")


@pytest.mark.asyncio
async def test_5_response_generator_format():
    """Test 5: Test response generator produces correct format."""
    start = time.time()

    response_generator = ResponseGenerator()

    # Mock LLM response for testing
    with patch.object(response_generator.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
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

        response = await response_generator.generate(
            user_question="AAPL今天涨了多少？",
            api_data={"price": 150.25, "change_percent": 2.5},
            rag_context="",
            api_completeness=1.0,
            rag_relevance=0.0
        )

    # Check format requirements
    assert "##" in response  # Has title
    assert "📊" in response  # Has data summary
    assert "📝" in response  # Has analysis
    assert "免责声明" in response  # Has disclaimer

    duration = (time.time() - start) * 1000
    print(f"\n✅ Response generator format ({duration:.2f}ms) - All required sections present")


@pytest.mark.asyncio
async def test_6_compliance_checker_blocks_advice():
    """Test 6: Test compliance checker blocks investment advice."""
    start = time.time()

    compliance_checker = ComplianceChecker()

    result = await compliance_checker.check(
        llm_output="建议买入AAPL股票，预计将上涨至$200。",
        user_question="AAPL值得买吗？",
        api_fields_provided=["price"],
        rag_docs_count=0
    )

    assert result["is_compliant"] is False
    assert result["risk_level"] == "high"
    assert result["action"] == "block"
    assert result["safe_fallback"] is not None

    duration = (time.time() - start) * 1000
    print(f"\n✅ Compliance checker - blocks advice ({duration:.2f}ms) - Risk: {result['risk_level']}, Action: {result['action']}")

    # Check latency requirement
    if duration > 5:
        print(f"   ⚠️  Warning: Rule-based compliance took {duration:.2f}ms (target: <5ms)")


@pytest.mark.asyncio
async def test_7_compliance_checker_passes_compliant():
    """Test 7: Test compliance checker passes compliant content."""
    start = time.time()

    compliance_checker = ComplianceChecker()
    result = await compliance_checker.check(
        llm_output="AAPL当前价格为$150.25，今日上涨2.5%。⚠️ 免责声明：本回答仅供信息参考，不构成投资建议。",
        user_question="AAPL今天涨了多少？",
        api_fields_provided=["price", "change_percent"],
        rag_docs_count=0
    )

    assert result["is_compliant"] is True
    assert result["action"] == "pass"

    duration = (time.time() - start) * 1000
    print(f"\n✅ Compliance checker - passes compliant ({duration:.2f}ms) - Content approved")


@pytest.mark.asyncio
async def test_8_end_to_end_flow():
    """Test 8: Test complete end-to-end flow."""
    start = time.time()

    hybrid_router = HybridRouter()
    response_generator = ResponseGenerator()
    compliance_checker = ComplianceChecker()

    # Step 1: Route
    route_result = await hybrid_router.route("AAPL今天涨了多少？")

    # Step 2: Generate (mocked)
    with patch.object(response_generator.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = """## AAPL股价查询

### 📊 数据摘要
当前价格: $150.25
涨跌幅: +2.5%

### 📝 分析说明
苹果股价今日上涨2.5%。

---
⚠️ 免责声明：本回答仅供信息参考，不构成投资建议。"""

        response = await response_generator.generate(
            user_question="AAPL今天涨了多少？",
            api_data={"price": 150.25, "change_percent": 2.5},
            rag_context="",
            api_completeness=1.0,
            rag_relevance=0.0
        )

    # Step 3: Compliance check
    compliance_result = await compliance_checker.check(
        llm_output=response,
        user_question="AAPL今天涨了多少？",
        api_fields_provided=["price", "change_percent"],
        rag_docs_count=0
    )

    assert compliance_result["is_compliant"] is True
    assert compliance_result["action"] == "pass"

    duration = (time.time() - start) * 1000
    print(f"\n✅ End-to-end flow ({duration:.2f}ms) - Complete flow successful")

    # Check P95 latency requirement
    if duration > 3000:
        print(f"   ⚠️  Warning: End-to-end took {duration:.2f}ms (target P95: <3000ms)")

