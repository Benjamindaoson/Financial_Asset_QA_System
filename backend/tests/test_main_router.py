import pytest

from app.routing.router import QueryRouter, QueryType


@pytest.fixture
def router():
    return QueryRouter()


def test_report_query_routes_to_knowledge_and_sec(router):
    route = router.classify("阿里巴巴最近财报")

    assert route.query_type in {QueryType.NEWS, QueryType.HYBRID}
    assert route.report_focus is True
    assert route.prefer_recent is True
    assert route.requires_knowledge is True
    assert route.requires_sec is True
    assert route.requires_web is True
    assert any(symbol in {"BABA", "9988.HK"} for symbol in route.symbols)


def test_recent_knowledge_query_enables_web_fallback(router):
    route = router.classify("最近什么是市盈率")

    assert route.query_type == QueryType.KNOWLEDGE
    assert route.requires_knowledge is True
    assert route.requires_web is True


def test_plain_knowledge_query_stays_internal(router):
    route = router.classify("什么是市盈率")

    assert route.query_type == QueryType.KNOWLEDGE
    assert route.requires_knowledge is True
    assert route.requires_web is False
    assert route.requires_sec is False


@pytest.mark.parametrize(
    "query",
    [
        "什么是EPS",
        "什么是PEG",
        "什么是ROE",
        "什么是PS",
        "什么是BVPS",
        "什么是FCF",
        "什么是EV/EBITDA",
        "EPS的定义是什么",
        "PS的定义是什么",
        "FCF怎么计算",
    ],
)
def test_metric_abbreviations_route_to_knowledge_not_market(router, query):
    route = router.classify(query)

    assert route.query_type == QueryType.KNOWLEDGE
    assert route.requires_knowledge is True
    assert route.requires_price is False
    assert route.symbols == []
