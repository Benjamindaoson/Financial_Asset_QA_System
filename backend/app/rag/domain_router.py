"""Domain router: classify a query into a knowledge domain using keyword rules."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

# Canonical domain names
DOMAINS: List[str] = ["equity", "macro", "fixed_income", "risk", "general"]


class DomainRouter:
    """Route a query to a knowledge domain.

    Uses keyword scoring on the query text (and optionally a HyDE hypothesis
    text).  HyDE text tends to use document-level language rather than user
    vernacular, so it produces more reliable domain signals when available.
    """

    DOMAIN_KEYWORDS: Dict[str, Set[str]] = {
        "equity": {
            "股票", "A股", "港股", "美股", "沪深", "纳斯达克", "标普",
            "市盈率", "PE", "P/E", "市净率", "PB", "市销率", "PS",
            "股价", "上市公司", "分红", "配股", "增发", "IPO",
            "equity", "stock", "share", "dividend", "earnings",
            "EPS", "ROE", "ROA", "EBITDA",
        },
        "macro": {
            "宏观", "GDP", "通胀", "CPI", "PPI", "央行", "利率", "货币政策",
            "财政政策", "联储", "美联储", "加息", "降息", "量化宽松", "QE",
            "经济周期", "景气", "就业", "失业率", "贸易",
            "macro", "inflation", "federal reserve", "interest rate",
            "monetary policy", "fiscal", "recession", "gdp",
        },
        "fixed_income": {
            "债券", "国债", "企业债", "信用债", "可转债", "票息", "久期",
            "信用评级", "违约", "收益率", "利差", "固收", "利息",
            "bond", "yield", "duration", "credit", "coupon",
            "fixed income", "treasury", "spread",
        },
        "risk": {
            "风险", "VaR", "回撤", "最大回撤", "波动率", "对冲", "夏普",
            "Sharpe", "贝塔", "Beta", "阿尔法", "Alpha", "相关性",
            "风险管理", "止损", "风控", "黑天鹅",
            "risk", "volatility", "drawdown", "hedge", "var",
            "sharpe ratio", "beta", "correlation",
        },
    }

    def route(self, query: str, hyde_text: Optional[str] = None) -> str:
        """Return the best-matching domain name.

        Falls back to 'general' when no domain keyword matches.
        """
        # Prefer HyDE text (document-language) over raw user query
        text_to_score = (hyde_text or "") + " " + query

        scores: Dict[str, int] = {domain: 0 for domain in self.DOMAIN_KEYWORDS}
        text_lower = text_to_score.lower()

        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    scores[domain] += 1

        best_domain = max(scores, key=lambda d: scores[d])
        if scores[best_domain] == 0:
            return "general"
        return best_domain
