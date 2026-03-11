"""Popular stocks configuration for cache warming with smart prioritization."""

# Priority tiers for intelligent cache warming
# Tier 1: Most frequently queried (warm every 30 min)
TIER_1_STOCKS = [
    # US Tech Giants
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",

    # China ADRs
    "BABA", "JD", "PDD", "BIDU",

    # A-shares Top
    "600519.SS",  # 贵州茅台
    "000858.SZ",  # 五粮液
    "002594.SZ",  # 比亚迪
    "300750.SZ",  # 宁德时代

    # Hong Kong
    "0700.HK",    # 腾讯控股
    "9988.HK",    # 阿里巴巴-SW

    # Crypto
    "BTC-USD", "ETH-USD",
]

# Tier 2: Frequently queried (warm every 2 hours)
TIER_2_STOCKS = [
    # US Tech
    "NFLX", "ADBE", "CRM", "ORCL", "INTC", "AMD", "QCOM",

    # US Finance
    "JPM", "BAC", "WFC", "GS", "MS",

    # US Consumer
    "WMT", "HD", "DIS", "NKE", "SBUX", "MCD",

    # China
    "NIO", "XPEV", "LI", "BILI",
    "601318.SS", "600036.SS", "000333.SZ", "000651.SZ",
    "1810.HK", "9618.HK", "3690.HK",
]

# Tier 3: Occasionally queried (warm every 6 hours)
TIER_3_STOCKS = [
    "PG", "KO", "PEP", "JNJ", "UNH", "PFE", "ABBV",
    "V", "MA", "PYPL", "COST", "AVGO", "CSCO",
    "600276.SS", "600887.SS", "601888.SS", "002475.SZ",
    "2318.HK", "0941.HK", "1398.HK",
]

# Legacy full list for backward compatibility
POPULAR_STOCKS = TIER_1_STOCKS + TIER_2_STOCKS + TIER_3_STOCKS


def get_popular_stocks(limit: int = 100) -> list[str]:
    """Get top N popular stocks."""
    return POPULAR_STOCKS[:limit]


def get_tier_1_stocks() -> list[str]:
    """Get highest priority stocks for frequent warming."""
    return TIER_1_STOCKS


def get_tier_2_stocks() -> list[str]:
    """Get medium priority stocks."""
    return TIER_2_STOCKS


def get_tier_3_stocks() -> list[str]:
    """Get lower priority stocks."""
    return TIER_3_STOCKS
