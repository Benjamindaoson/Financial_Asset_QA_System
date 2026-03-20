"""Tests for the production QueryRouter hardening rules."""

from app.routing import QueryRouter, QueryType


def test_price_today_query_stays_market():
    router = QueryRouter()

    route = router.classify("AAPL price today")

    assert route.query_type == QueryType.MARKET
    assert route.symbols == ["AAPL"]
    assert route.requires_web is False


def test_sector_query_does_not_trigger_sec_filing_search():
    router = QueryRouter()

    route = router.classify("NVDA company profile and sector")

    assert route.query_type == QueryType.MARKET
    assert route.requires_sec is False
    assert route.requires_info is True


def test_valuation_terms_are_not_treated_as_tickers():
    router = QueryRouter()

    route = router.classify("Difference between PE and PB")

    assert route.query_type == QueryType.KNOWLEDGE
    assert route.symbols == []


def test_price_to_earnings_definition_stays_knowledge():
    router = QueryRouter()

    route = router.classify("What is price-to-earnings ratio")

    assert route.query_type == QueryType.KNOWLEDGE
    assert route.requires_knowledge is True
    assert route.requires_price is False
