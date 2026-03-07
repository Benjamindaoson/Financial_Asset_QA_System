"""Popular stocks configuration for cache warming."""

# TOP 100 most queried stocks (US + China markets)
POPULAR_STOCKS = [
    # US Tech Giants
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "NFLX", "ADBE", "CRM", "ORCL", "INTC", "AMD", "QCOM",

    # US Finance
    "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW",

    # US Consumer
    "WMT", "HD", "DIS", "NKE", "SBUX", "MCD", "PG", "KO", "PEP",

    # US Healthcare
    "JNJ", "UNH", "PFE", "ABBV", "TMO", "MRK", "LLY",

    # China ADRs
    "BABA", "JD", "PDD", "BIDU", "NIO", "XPEV", "LI", "BILI",

    # A-shares (Shanghai)
    "600519.SS",  # 贵州茅台
    "601318.SS",  # 中国平安
    "600036.SS",  # 招商银行
    "600276.SS",  # 恒瑞医药
    "600887.SS",  # 伊利股份
    "601888.SS",  # 中国中免
    "600900.SS",  # 长江电力
    "601012.SS",  # 隆基绿能
    "600809.SS",  # 山西汾酒
    "601166.SS",  # 兴业银行

    # A-shares (Shenzhen)
    "000858.SZ",  # 五粮液
    "000333.SZ",  # 美的集团
    "002594.SZ",  # 比亚迪
    "000651.SZ",  # 格力电器
    "002475.SZ",  # 立讯精密
    "300750.SZ",  # 宁德时代
    "000568.SZ",  # 泸州老窖
    "002415.SZ",  # 海康威视
    "002714.SZ",  # 牧原股份
    "000001.SZ",  # 平安银行

    # Hong Kong
    "0700.HK",    # 腾讯控股
    "9988.HK",    # 阿里巴巴-SW
    "1810.HK",    # 小米集团-W
    "9618.HK",    # 京东集团-SW
    "2318.HK",    # 中国平安
    "0941.HK",    # 中国移动
    "1398.HK",    # 工商银行
    "3690.HK",    # 美团-W

    # Crypto
    "BTC-USD", "ETH-USD",

    # Additional US stocks
    "V", "MA", "PYPL", "COST", "AVGO", "CSCO", "TXN",
    "IBM", "UBER", "LYFT", "SNAP", "TWTR", "SQ", "SHOP"
]


def get_popular_stocks(limit: int = 100) -> list[str]:
    """Get top N popular stocks."""
    return POPULAR_STOCKS[:limit]
