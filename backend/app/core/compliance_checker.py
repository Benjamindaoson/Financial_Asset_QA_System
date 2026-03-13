"""Compliance checker for LLM outputs."""

import json
import re
from typing import Dict, Any, List

from app.core.prompt_manager import PromptManager
from app.core.llm_client import LLMClient
from app.config import settings


class ComplianceChecker:
    """Check LLM outputs for compliance violations."""

    # Investment advice keywords
    ADVICE_KEYWORDS = [
        "建议买入", "建议卖出", "建议持有", "推荐买入", "推荐卖出",
        "值得投资", "建议配置", "推荐购买", "应该买", "应该卖",
        "预计上涨", "预计下跌", "将上涨", "将下跌", "目标价"
    ]

    # Disclaimer patterns
    DISCLAIMER_PATTERNS = [
        r"免责声明",
        r"不构成投资建议",
        r"仅供.*参考"
    ]

    def __init__(
        self,
        prompt_manager: PromptManager = None,
        llm_client: LLMClient = None
    ):
        """Initialize Compliance Checker.

        Args:
            prompt_manager: PromptManager instance. If None, creates new one.
            llm_client: LLMClient instance. If None, creates new one.
        """
        self.prompt_manager = prompt_manager or PromptManager()
        self.llm_client = llm_client or LLMClient()

    async def check(
        self,
        llm_output: str,
        user_question: str,
        api_fields_provided: List[str],
        rag_docs_count: int
    ) -> Dict[str, Any]:
        """Check LLM output for compliance.

        Args:
            llm_output: Generated output to check
            user_question: Original user question
            api_fields_provided: List of API fields that were provided
            rag_docs_count: Number of RAG documents retrieved

        Returns:
            Dict containing:
                - is_compliant: bool
                - risk_level: "low" | "medium" | "high"
                - violations: List of violation dicts
                - action: "pass" | "block" | "replace"
                - safe_fallback: Optional safe replacement text
        """
        # Check if compliance checking is disabled
        if not settings.COMPLIANCE_RULE_CHECK_ENABLED and \
           not settings.COMPLIANCE_LLM_CHECK_ENABLED:
            return self._pass_result()

        # Step 1: Rule-based check (fast)
        rule_result = self._rule_check(llm_output)

        # If rule check finds high risk, block immediately
        if rule_result["risk_level"] == "high":
            return rule_result

        # Step 2: LLM check (if enabled and rule check passed or found medium risk)
        if settings.COMPLIANCE_LLM_CHECK_ENABLED:
            try:
                llm_result = await self._llm_check(
                    llm_output,
                    user_question,
                    api_fields_provided,
                    rag_docs_count
                )

                # Merge results (take stricter one)
                return self._merge_results(rule_result, llm_result)

            except Exception:
                # LLM check failed, use rule result
                return rule_result

        return rule_result

    def _rule_check(self, llm_output: str) -> Dict[str, Any]:
        """Perform rule-based compliance check.

        Args:
            llm_output: Output to check

        Returns:
            Compliance result dict
        """
        if not settings.COMPLIANCE_RULE_CHECK_ENABLED:
            return self._pass_result()

        violations = []

        # Rule 1: Check for investment advice
        for keyword in self.ADVICE_KEYWORDS:
            if keyword in llm_output:
                violations.append({
                    "rule_id": "rule_1",
                    "violation_detail": f"包含投资建议关键词：{keyword}",
                    "suggested_action": "remove"
                })
                break

        # Rule 4: Check for disclaimer (if content has data/analysis)
        has_data = any(char.isdigit() for char in llm_output)
        has_disclaimer = any(
            re.search(pattern, llm_output)
            for pattern in self.DISCLAIMER_PATTERNS
        )

        if has_data and not has_disclaimer:
            violations.append({
                "rule_id": "rule_4",
                "violation_detail": "缺少免责声明",
                "suggested_action": "add_disclaimer"
            })

        # Determine risk level and action
        if violations:
            # Check if any violation is high risk
            has_advice = any(v["rule_id"] == "rule_1" for v in violations)

            if has_advice:
                risk_level = "high"
                action = "block"
                safe_fallback = "抱歉，本系统仅提供历史数据与客观分析，无法提供投资建议或价格预测。"
            else:
                risk_level = "medium"
                action = "replace"
                safe_fallback = None

            return {
                "is_compliant": False,
                "risk_level": risk_level,
                "violations": violations,
                "action": action,
                "safe_fallback": safe_fallback
            }

        return self._pass_result()

    async def _llm_check(
        self,
        llm_output: str,
        user_question: str,
        api_fields_provided: List[str],
        rag_docs_count: int
    ) -> Dict[str, Any]:
        """Perform LLM-based compliance check.

        Args:
            llm_output: Output to check
            user_question: Original question
            api_fields_provided: API fields provided
            rag_docs_count: Number of RAG docs

        Returns:
            Compliance result dict
        """
        # Get system prompt and user prompt
        system_prompt = self.prompt_manager.get_system_prompt("compliance")
        user_prompt = self.prompt_manager.render_user_prompt(
            "compliance",
            llm_output=llm_output,
            user_question=user_question,
            api_fields_provided=", ".join(api_fields_provided) if api_fields_provided else "无",
            rag_docs_count=rag_docs_count
        )

        # Get temperature and max_tokens from config
        temperature = self.prompt_manager.get_temperature("compliance")
        max_tokens = self.prompt_manager.get_max_tokens("compliance")

        # Call LLM with JSON mode
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        response = await self.llm_client.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=settings.LLM_COMPLIANCE_TIMEOUT,
            response_format={"type": "json_object"}
        )

        # Parse JSON response
        result = json.loads(response)

        return result

    def _merge_results(
        self,
        rule_result: Dict[str, Any],
        llm_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge rule and LLM check results (take stricter).

        Args:
            rule_result: Result from rule check
            llm_result: Result from LLM check

        Returns:
            Merged result
        """
        # If either says non-compliant, it's non-compliant
        is_compliant = rule_result["is_compliant"] and llm_result["is_compliant"]

        if not is_compliant:
            # Take higher risk level
            risk_levels = {"low": 0, "medium": 1, "high": 2}
            rule_risk = risk_levels.get(rule_result["risk_level"], 0)
            llm_risk = risk_levels.get(llm_result["risk_level"], 0)

            if rule_risk >= llm_risk:
                return rule_result
            else:
                return llm_result

        return self._pass_result()

    def _pass_result(self) -> Dict[str, Any]:
        """Return a passing compliance result.

        Returns:
            Passing result dict
        """
        return {
            "is_compliant": True,
            "risk_level": "low",
            "violations": [],
            "action": "pass",
            "safe_fallback": None
        }
