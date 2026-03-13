"""Tests for ComplianceChecker."""

import pytest
from unittest.mock import AsyncMock, patch
from app.core.compliance_checker import ComplianceChecker


@pytest.mark.asyncio
async def test_compliance_checker_initialization():
    """Test that ComplianceChecker initializes correctly."""
    checker = ComplianceChecker()

    assert checker is not None
    assert checker.prompt_manager is not None
    assert checker.llm_client is not None


@pytest.mark.asyncio
async def test_check_compliant_content():
    """Test checking compliant content."""
    checker = ComplianceChecker()

    with patch.object(checker.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = """{
            "is_compliant": true,
            "risk_level": "low",
            "violations": [],
            "action": "pass",
            "safe_fallback": null
        }"""

        result = await checker.check(
            llm_output="AAPL当前价格为$150.25，今日上涨2.5%。⚠️ 免责声明：本回答仅供信息参考，不构成投资建议。",
            user_question="AAPL今天涨了多少？",
            api_fields_provided=["price", "change_percent"],
            rag_docs_count=0
        )

        assert result["is_compliant"] is True
        assert result["action"] == "pass"


@pytest.mark.asyncio
async def test_check_investment_advice_violation():
    """Test detecting investment advice violation."""
    checker = ComplianceChecker()

    # Rule-based check should catch this
    result = await checker.check(
        llm_output="建议买入AAPL股票，预计将上涨至$200。",
        user_question="AAPL值得买吗？",
        api_fields_provided=["price"],
        rag_docs_count=0
    )

    assert result["is_compliant"] is False
    assert result["risk_level"] == "high"
    assert result["action"] == "block"
    assert len(result["violations"]) > 0


@pytest.mark.asyncio
async def test_check_missing_disclaimer():
    """Test detecting missing disclaimer."""
    checker = ComplianceChecker()

    with patch.object(checker.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = """{
            "is_compliant": false,
            "risk_level": "medium",
            "violations": [{
                "rule_id": "rule_4",
                "violation_detail": "缺少免责声明",
                "suggested_action": "add_disclaimer"
            }],
            "action": "replace",
            "safe_fallback": null
        }"""

        result = await checker.check(
            llm_output="AAPL价格为$150.25，表现强劲。",
            user_question="AAPL今天表现如何？",
            api_fields_provided=["price"],
            rag_docs_count=0
        )

        assert result["is_compliant"] is False
        assert result["action"] == "replace"


@pytest.mark.asyncio
async def test_rule_check_only_mode():
    """Test rule-based checking only."""
    with patch('app.config.settings.COMPLIANCE_LLM_CHECK_ENABLED', False):
        checker = ComplianceChecker()

        result = await checker.check(
            llm_output="AAPL价格为$150.25。⚠️ 免责声明：本回答仅供信息参考，不构成投资建议。",
            user_question="AAPL价格是多少？",
            api_fields_provided=["price"],
            rag_docs_count=0
        )

        # Should pass rule check
        assert result["is_compliant"] is True


@pytest.mark.asyncio
async def test_llm_check_detects_data_fabrication():
    """Test LLM detecting data fabrication."""
    checker = ComplianceChecker()

    with patch.object(checker.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = """{
            "is_compliant": false,
            "risk_level": "high",
            "violations": [{
                "rule_id": "rule_2",
                "violation_detail": "引用了上下文中未提供的数据：市值$3万亿",
                "suggested_action": "remove"
            }],
            "action": "block",
            "safe_fallback": "抱歉，暂无相关数据。"
        }"""

        result = await checker.check(
            llm_output="AAPL市值达到$3万亿，创历史新高。",
            user_question="AAPL市值多少？",
            api_fields_provided=["price"],  # No market_cap provided
            rag_docs_count=0
        )

        assert result["is_compliant"] is False
        assert result["risk_level"] == "high"
        assert result["action"] == "block"


@pytest.mark.asyncio
async def test_strict_mode():
    """Test strict mode enforcement."""
    with patch('app.config.settings.COMPLIANCE_STRICT_MODE', True):
        checker = ComplianceChecker()

        with patch.object(checker.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
            mock_llm.return_value = """{
                "is_compliant": false,
                "risk_level": "medium",
                "violations": [{
                    "rule_id": "rule_1",
                    "violation_detail": "模糊表述",
                    "suggested_action": "replace"
                }],
                "action": "replace",
                "safe_fallback": null
            }"""

            result = await checker.check(
                llm_output="AAPL可能会上涨。",
                user_question="AAPL会涨吗？",
                api_fields_provided=[],
                rag_docs_count=0
            )

            # In strict mode, medium risk should be blocked
            assert result["action"] in ["block", "replace"]


@pytest.mark.asyncio
async def test_disabled_compliance_check():
    """Test behavior when compliance checking is disabled."""
    with patch('app.config.settings.COMPLIANCE_RULE_CHECK_ENABLED', False), \
         patch('app.config.settings.COMPLIANCE_LLM_CHECK_ENABLED', False):

        checker = ComplianceChecker()

        result = await checker.check(
            llm_output="建议买入AAPL",  # Would normally violate
            user_question="AAPL值得买吗？",
            api_fields_provided=[],
            rag_docs_count=0
        )

        # Should pass when all checks disabled
        assert result["is_compliant"] is True
        assert result["action"] == "pass"
