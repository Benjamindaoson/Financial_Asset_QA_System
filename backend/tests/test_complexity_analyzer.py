"""Tests for the production query complexity analyzer."""

from app.routing.complexity_analyzer import QueryComplexityAnalyzer
from app.routing.router import QueryRoute, QueryType


class TestQueryComplexityAnalyzer:
    def setup_method(self):
        self.analyzer = QueryComplexityAnalyzer()

    def test_simple_query_single_symbol(self):
        route = QueryRoute(
            query_type=QueryType.MARKET,
            cleaned_query="AAPL latest price",
            symbols=["AAPL"],
            requires_price=True,
        )

        result = self.analyzer.analyze("AAPL latest price", route)

        assert result.level == "simple"
        assert result.score < 0.3
        assert result.recommended_model == "deepseek-chat"
        assert result.rag_top_k == 3
        assert result.timeout_multiplier == 1.0

    def test_market_history_query_is_medium(self):
        route = QueryRoute(
            query_type=QueryType.MARKET,
            cleaned_query="NFLX chart over 3m",
            symbols=["NFLX"],
            range_key="3m",
            requires_history=True,
        )

        result = self.analyzer.analyze("NFLX chart over 3m", route)

        assert result.level == "medium"
        assert result.score >= 0.3

    def test_compare_query_is_complex(self):
        route = QueryRoute(
            query_type=QueryType.MARKET,
            cleaned_query="Compare AAPL vs MSFT performance",
            symbols=["AAPL", "MSFT"],
            requires_price=True,
            requires_history=True,
            requires_metrics=True,
            requires_comparison=True,
        )

        result = self.analyzer.analyze("Compare AAPL vs MSFT performance", route)

        assert result.level == "complex"
        assert result.score >= 0.6
        assert result.rag_top_k == 10

    def test_complex_query_hybrid(self):
        route = QueryRoute(
            query_type=QueryType.HYBRID,
            cleaned_query="Why is AMZN down today",
            symbols=["AMZN"],
            requires_price=True,
            requires_change=True,
            requires_web=True,
        )

        result = self.analyzer.analyze("Why is AMZN down today", route)

        assert result.level == "complex"
        assert result.score >= 0.6
        assert result.timeout_multiplier == 2.0

    def test_knowledge_query(self):
        route = QueryRoute(
            query_type=QueryType.KNOWLEDGE,
            cleaned_query="What is PE ratio",
            requires_knowledge=True,
        )

        result = self.analyzer.analyze("What is PE ratio", route)

        assert result.level == "simple"
        assert result.score < 0.4

    def test_entity_scoring(self):
        assert self.analyzer._score_entities(QueryRoute(query_type=QueryType.KNOWLEDGE, cleaned_query="", symbols=[])) == 0.0
        assert self.analyzer._score_entities(QueryRoute(query_type=QueryType.MARKET, cleaned_query="", symbols=["AAPL"])) == 0.2
        assert (
            self.analyzer._score_entities(
                QueryRoute(query_type=QueryType.MARKET, cleaned_query="", symbols=["AAPL", "MSFT", "GOOGL"])
            )
            == 0.5
        )
        assert (
            self.analyzer._score_entities(
                QueryRoute(query_type=QueryType.MARKET, cleaned_query="", symbols=["A", "B", "C", "D", "E"])
            )
            == 1.0
        )

    def test_time_span_scoring(self):
        route = QueryRoute(query_type=QueryType.MARKET, cleaned_query="")
        assert self.analyzer._score_time_span(route) == 0.0

        route.days = 7
        assert self.analyzer._score_time_span(route) == 0.2

        route.days = 90
        assert self.analyzer._score_time_span(route) == 0.5

        route.days = 365
        assert self.analyzer._score_time_span(route) == 0.8

        route.days = None
        route.range_key = "5y"
        assert self.analyzer._score_time_span(route) == 0.8

    def test_tool_count_scoring(self):
        route = QueryRoute(query_type=QueryType.MARKET, cleaned_query="")

        route.requires_price = True
        assert self.analyzer._score_tools(route) == 0.1

        route.requires_history = True
        route.requires_change = True
        assert self.analyzer._score_tools(route) == 0.4

        route.requires_info = True
        route.requires_metrics = True
        route.requires_knowledge = True
        assert self.analyzer._score_tools(route) == 1.0

    def test_query_type_scoring(self):
        assert self.analyzer._score_query_type(QueryRoute(query_type=QueryType.MARKET, cleaned_query="")) == 0.2
        assert self.analyzer._score_query_type(QueryRoute(query_type=QueryType.KNOWLEDGE, cleaned_query="")) == 0.3
        assert self.analyzer._score_query_type(QueryRoute(query_type=QueryType.NEWS, cleaned_query="")) == 0.5
        assert self.analyzer._score_query_type(QueryRoute(query_type=QueryType.HYBRID, cleaned_query="")) == 0.9
