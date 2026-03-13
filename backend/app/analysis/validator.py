"""Data quality validator for financial analysis."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.models import ToolResult

logger = logging.getLogger(__name__)


class DataValidator:
    """Validate data completeness and determine confidence bands."""

    @staticmethod
    def validate_tool_results(tool_results: List[ToolResult]) -> Dict[str, Any]:
        score = 0
        missing: List[str] = []

        has_price = False
        has_history = False
        has_change = False
        has_info = False
        has_news = False
        has_metrics = False
        has_sec = False
        has_knowledge = False

        for result in tool_results:
            logger.info(f"[DEBUG] Processing result: tool={result.tool}, status={result.status}")
            if result.status != "success":
                continue
            data = result.data
            logger.info(f"[DEBUG] Data type: {type(data)}, keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")

            if result.tool == "get_price":
                if data.get("price") is not None:
                    has_price = True
                    score += 20
                else:
                    missing.append("实时价格")

            elif result.tool == "get_history":
                if len(data.get("data", [])) >= 20:
                    has_history = True
                    score += 20
                else:
                    missing.append("历史行情")

            elif result.tool == "get_change":
                if data.get("change_pct") is not None:
                    has_change = True
                    score += 10
                else:
                    missing.append("涨跌幅")

            elif result.tool == "get_info":
                if data.get("name"):
                    has_info = True
                    score += 10
                else:
                    missing.append("公司资料")

            elif result.tool == "get_metrics":
                if data.get("annualized_volatility") is not None:
                    has_metrics = True
                    score += 20
                else:
                    missing.append("收益风险指标")

            elif result.tool == "search_web":
                if data.get("results"):
                    has_news = True
                    score += 10
                else:
                    missing.append("新闻检索")

            elif result.tool == "search_sec":
                if data.get("results"):
                    has_sec = True
                    score += 10
                else:
                    missing.append("SEC/财报检索")

            elif result.tool == "search_knowledge":
                logger.info(f"[DEBUG] search_knowledge validation:")
                logger.info(f"  data type: {type(data)}")
                logger.info(f"  data keys: {list(data.keys()) if isinstance(data, dict) else 'not a dict'}")
                logger.info(f"  data.get('documents'): {data.get('documents') if isinstance(data, dict) else 'N/A'}")
                logger.info(f"  documents type: {type(data.get('documents')) if isinstance(data, dict) else 'N/A'}")
                if isinstance(data, dict) and data.get("documents"):
                    logger.info(f"  documents length: {len(data.get('documents'))}")
                    logger.info(f"  bool(data.get('documents')): {bool(data.get('documents'))}")

                if data.get("documents"):
                    has_knowledge = True
                    score += 20
                    logger.info(f"  [DEBUG] has_knowledge set to True, score += 20")
                else:
                    missing.append("知识库检索")
                    logger.info(f"  [DEBUG] Missing knowledge, documents is falsy")

        if score >= 75:
            level = "high"
        elif score >= 45:
            level = "medium"
        else:
            level = "low"

        validation_result = {
            "confidence": score,
            "level": level,
            "has_price": has_price,
            "has_history": has_history,
            "has_change": has_change,
            "has_info": has_info,
            "has_metrics": has_metrics,
            "has_news": has_news,
            "has_sec": has_sec,
            "has_knowledge": has_knowledge,
            "missing": sorted(set(missing)),
            "can_analyze": has_price or has_history or has_news or has_sec or has_knowledge,
        }
        logger.info(f"[DEBUG] Final validation result: {validation_result}")
        return validation_result

    @staticmethod
    def should_block_response(validation: Dict[str, Any]) -> bool:
        return not validation.get("can_analyze", False)

    @staticmethod
    def get_fallback_message(validation: Dict[str, Any], symbol: str) -> str:
        missing = "、".join(validation.get("missing") or ["关键数据"])
        return (
            f"当前无法为 {symbol} 生成可靠结论，缺少 {missing}。"
            " 请稍后重试，或改问基础知识/单一行情问题。"
        )
