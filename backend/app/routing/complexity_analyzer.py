"""Query complexity analyzer for adaptive routing."""

from dataclasses import dataclass

from app.routing.router import QueryRoute, QueryType


@dataclass
class ComplexityScore:
    """Query complexity assessment."""

    level: str
    score: float
    recommended_model: str
    rag_top_k: int
    timeout_multiplier: float
    reasoning: str


class QueryComplexityAnalyzer:
    """Analyze query complexity and recommend execution parameters."""

    SIMPLE_THRESHOLD = 0.3
    COMPLEX_THRESHOLD = 0.6

    def analyze(self, query: str, route: QueryRoute) -> ComplexityScore:
        entity_score = self._score_entities(route)
        time_score = self._score_time_span(route)
        tool_score = self._score_tools(route)
        type_score = self._score_query_type(route)
        bonus_score = self._score_execution_shape(route)

        total_score = min(
            1.0,
            entity_score * 0.3
            + time_score * 0.2
            + tool_score * 0.3
            + type_score * 0.2
            + bonus_score,
        )

        if total_score < self.SIMPLE_THRESHOLD:
            level = "simple"
            model = "deepseek-chat"
            top_k = 3
            timeout_mult = 1.0
        elif total_score < self.COMPLEX_THRESHOLD:
            level = "medium"
            model = "deepseek-chat"
            top_k = 5
            timeout_mult = 1.5
        else:
            level = "complex"
            model = "deepseek-chat"
            top_k = 10
            timeout_mult = 2.0

        return ComplexityScore(
            level=level,
            score=round(total_score, 3),
            recommended_model=model,
            rag_top_k=top_k,
            timeout_multiplier=timeout_mult,
            reasoning=self._build_reasoning(route, entity_score, time_score, tool_score, type_score, bonus_score),
        )

    def _score_entities(self, route: QueryRoute) -> float:
        num_symbols = len(route.symbols)
        if num_symbols == 0:
            return 0.0
        if num_symbols == 1:
            return 0.2
        if num_symbols <= 3:
            return 0.5
        return 1.0

    def _score_time_span(self, route: QueryRoute) -> float:
        if route.range_key:
            range_scores = {
                "1m": 0.3,
                "3m": 0.5,
                "6m": 0.6,
                "1y": 0.6,
                "ytd": 0.6,
                "5y": 0.8,
            }
            return range_scores.get(route.range_key, 0.5)

        if route.days is None:
            return 0.0
        if route.days < 30:
            return 0.2
        if route.days < 180:
            return 0.5
        return 0.8

    def _score_tools(self, route: QueryRoute) -> float:
        tool_count = sum(
            [
                route.requires_price,
                route.requires_history,
                route.requires_change,
                route.requires_info,
                route.requires_metrics,
                route.requires_comparison,
                route.requires_knowledge,
                route.requires_web,
                route.requires_sec,
            ]
        )

        if tool_count <= 1:
            return 0.1
        if tool_count <= 3:
            return 0.4
        if tool_count <= 5:
            return 0.7
        return 1.0

    def _score_query_type(self, route: QueryRoute) -> float:
        type_scores = {
            QueryType.MARKET: 0.2,
            QueryType.KNOWLEDGE: 0.3,
            QueryType.NEWS: 0.5,
            QueryType.HYBRID: 0.9,
        }
        return type_scores.get(route.query_type, 0.5)

    def _score_execution_shape(self, route: QueryRoute) -> float:
        bonus = 0.0

        if route.requires_history and (route.days is not None or route.range_key is not None):
            bonus += 0.08
        if route.requires_metrics:
            bonus += 0.08
        if route.requires_comparison:
            bonus += 0.2
        if len(route.symbols) >= 2:
            bonus += 0.05
        if route.query_type == QueryType.HYBRID:
            bonus += 0.2
        if route.requires_web and route.symbols:
            bonus += 0.05
        if route.requires_sec:
            bonus += 0.08
        if route.requires_web and route.requires_knowledge:
            bonus += 0.05

        return bonus

    def _build_reasoning(
        self,
        route: QueryRoute,
        entity_score: float,
        time_score: float,
        tool_score: float,
        type_score: float,
        bonus_score: float,
    ) -> str:
        parts = []

        if len(route.symbols) >= 2 or entity_score >= 0.5:
            parts.append("multiple entities")
        if route.range_key or route.days:
            parts.append("explicit time window")
        if route.requires_comparison:
            parts.append("cross-asset comparison")
        if route.requires_metrics:
            parts.append("risk metric computation")
        if route.query_type == QueryType.HYBRID or type_score >= 0.9:
            parts.append("cross-source retrieval")
        if route.requires_sec:
            parts.append("SEC filing retrieval")
        if tool_score >= 0.7:
            parts.append("multi-tool orchestration")
        if bonus_score >= 0.2 and "cross-source retrieval" not in parts and route.requires_web:
            parts.append("mixed execution path")

        if not parts:
            return "Simple query with minimal requirements"
        return f"Complex query: {', '.join(parts)}"
