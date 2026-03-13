"""Hybrid router combining rule-based and LLM routing."""

import re
from typing import Dict, Any, Optional

from app.routing.router import QueryRouter
from app.routing.llm_router import LLMRouter
from app.config import settings


class HybridRouter:
    """Hybrid router that combines rule-based and LLM routing."""

    def __init__(
        self,
        rule_router: QueryRouter = None,
        llm_router: LLMRouter = None,
        confidence_threshold: float = None
    ):
        """Initialize Hybrid Router.

        Args:
            rule_router: QueryRouter instance. If None, creates new one.
            llm_router: LLMRouter instance. If None, creates new one.
            confidence_threshold: Confidence threshold for using rule router.
                If None, uses settings.HYBRID_ROUTING_CONFIDENCE_THRESHOLD
        """
        self.rule_router = rule_router or QueryRouter()
        self.llm_router = llm_router or LLMRouter()
        self.confidence_threshold = confidence_threshold or \
            settings.HYBRID_ROUTING_CONFIDENCE_THRESHOLD

    async def route(self, query: str) -> Dict[str, Any]:
        """Route a query using hybrid approach.

        Strategy:
        1. Use rule router first (fast path)
        2. Calculate confidence score
        3. If confidence > threshold, use rule result
        4. Otherwise, call LLM router for enhancement
        5. If LLM fails, fallback to rule result

        Args:
            query: User query string

        Returns:
            Dict containing routing decision with:
                - route: Routing path (api_direct, rag_retrieval, hybrid)
                - confidence: Confidence score
                - tools: List of tools to call
                - entities: Extracted entities
                - question_type: Type of question (if from LLM)
                - reasoning: Explanation (if from LLM)
        """
        # Check if hybrid routing is enabled
        if not settings.HYBRID_ROUTING_ENABLED:
            return self._convert_rule_result(
                self.rule_router.classify(query),
                query
            )

        # Step 1: Use rule router
        rule_result = self.rule_router.classify(query)
        rule_dict = self._convert_rule_result(rule_result, query)

        # Step 2: Calculate confidence
        confidence = self._calculate_confidence(
            query=query,
            entities=rule_dict.get("entities", {})
        )
        rule_dict["confidence"] = confidence

        # Step 3: High confidence - use rule result
        if confidence > self.confidence_threshold:
            return rule_dict

        # Step 4: Low confidence - call LLM router
        try:
            llm_result = await self.llm_router.route(query)

            # Merge results
            merged = self._merge_results(rule_dict, llm_result)
            return merged

        except Exception as e:
            # Step 5: LLM failed - fallback to rule result
            if settings.HYBRID_ROUTING_FALLBACK_TO_RULE:
                return rule_dict
            else:
                raise

    def _convert_rule_result(
        self,
        rule_result,
        query: str
    ) -> Dict[str, Any]:
        """Convert QueryRoute to dict format.

        Args:
            rule_result: QueryRoute object from rule router
            query: Original query string

        Returns:
            Dict with standardized format
        """
        # Determine route type
        if rule_result.requires_knowledge:
            route = "rag_retrieval"
        elif rule_result.requires_price or rule_result.requires_history:
            route = "api_direct"
        else:
            route = "hybrid"

        # Build tools list
        tools = []
        if rule_result.requires_price:
            tools.append("get_price")
        if rule_result.requires_history:
            tools.append("get_history")
        if rule_result.requires_info:
            tools.append("get_info")
        if rule_result.requires_web:
            tools.append("search_web")
        if rule_result.requires_knowledge:
            tools.append("search_rag")

        # Extract entities
        entities = {
            "ticker": rule_result.symbols[0] if rule_result.symbols else None,
            "company": None,
            "time_range": None
        }

        if rule_result.days:
            entities["time_range"] = f"{rule_result.days} days"
        elif rule_result.range_key:
            entities["time_range"] = rule_result.range_key

        return {
            "route": route,
            "confidence": 0.0,  # Will be calculated
            "tools": tools,
            "entities": entities,
            "query_type": rule_result.query_type.value
        }

    def _calculate_confidence(
        self,
        query: str,
        entities: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for rule-based routing.

        Args:
            query: User query string
            entities: Extracted entities

        Returns:
            Confidence score (0-1)
        """
        # Keyword matching score
        keyword_score = self._keyword_score(query)

        # Entity extraction score
        entity_score = self._entity_score(entities)

        # Complexity score (inverse)
        complexity_score = self._complexity_score(query)

        # Weighted average
        confidence = (
            keyword_score * 0.4 +
            entity_score * 0.3 +
            complexity_score * 0.3
        )

        return confidence

    def _keyword_score(self, query: str) -> float:
        """Calculate keyword matching score."""
        keywords = [
            "价格", "股价", "行情", "涨", "跌", "涨幅", "跌幅",
            "今天", "昨天", "本周", "本月", "历史", "走势"
        ]

        matches = sum(1 for kw in keywords if kw in query)

        if matches >= 3:
            return 1.0
        elif matches == 2:
            return 0.7
        elif matches == 1:
            return 0.5
        else:
            return 0.2

    def _entity_score(self, entities: Dict[str, Any]) -> float:
        """Calculate entity extraction score."""
        has_ticker = entities.get("ticker") is not None
        has_time = entities.get("time_range") is not None

        if has_ticker and has_time:
            return 1.0
        elif has_ticker:
            return 0.7
        elif has_time:
            return 0.5
        else:
            return 0.3

    def _complexity_score(self, query: str) -> float:
        """Calculate query complexity score (inverse)."""
        complexity = 0

        # Check for "why" questions
        if any(word in query for word in ["为什么", "原因", "why"]):
            complexity += 1

        # Check for multiple tickers
        ticker_pattern = r"(?<![A-Za-z])([A-Z]{2,5})(?![A-Za-z])"
        tickers = re.findall(ticker_pattern, query)
        if len(tickers) > 1:
            complexity += 1

        # Check for comparison words
        if any(word in query for word in ["对比", "比较", "vs", "和"]):
            complexity += 1

        # Check for length
        if len(query) > 30:
            complexity += 1

        # Convert to score (higher complexity = lower score)
        if complexity == 0:
            return 1.0
        elif complexity == 1:
            return 0.6
        else:
            return 0.3

    def _merge_results(
        self,
        rule_result: Dict[str, Any],
        llm_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge rule and LLM routing results.

        Args:
            rule_result: Result from rule router
            llm_result: Result from LLM router

        Returns:
            Merged result dict
        """
        # Use LLM's route and confidence
        merged = {
            "route": llm_result["route"],
            "confidence": llm_result["confidence"],
            "question_type": llm_result["question_type"],
            "reasoning": llm_result["reasoning"]
        }

        # Merge entities (LLM takes precedence, but keep rule's ticker if LLM missed it)
        merged_entities = dict(rule_result.get("entities", {}))
        merged_entities.update(llm_result.get("entities", {}))

        # If LLM didn't extract ticker but rule did, keep rule's ticker
        if not merged_entities.get("ticker") and rule_result.get("entities", {}).get("ticker"):
            merged_entities["ticker"] = rule_result["entities"]["ticker"]

        merged["entities"] = merged_entities

        # Keep rule's tools list
        merged["tools"] = rule_result.get("tools", [])

        return merged
