"""Document and query domain classification helpers for multi-domain RAG."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Iterable, List, Sequence, Tuple

from app.rag.domain_router import DOMAINS


@dataclass(frozen=True)
class DomainClassification:
    """Structured classification result."""

    domain: str
    confidence: float
    scores: Dict[str, float]
    matched_terms: Dict[str, List[str]]


_DOMAIN_TERMS: Dict[str, Dict[str, Sequence[str]]] = {
    "equity": {
        "filename": (
            "股票", "权益", "估值", "pe", "pb", "roe", "eps", "etf", "财报",
            "基本面", "技术分析", "technical", "valuation", "equity", "stock",
            "industry", "股东", "分红", "回购",
        ),
        "heading": (
            "股票", "权益", "估值", "财务报表", "财报", "basic analysis",
            "technical analysis", "equity", "stock", "etf",
        ),
        "content": (
            "股票", "权益", "市盈率", "市净率", "市销率", "roe", "roa", "eps",
            "ebitda", "分红", "回购", "股东", "上市公司", "a股", "港股", "美股",
            "财报", "估值", "k线", "macd", "rsi", "etf", "equity", "stock",
            "share", "earnings", "valuation", "dividend",
        ),
    },
    "macro": {
        "filename": (
            "宏观", "经济", "货币政策", "cpi", "ppi", "gdp", "利率", "inflation",
            "macro", "federal", "fed", "rate",
        ),
        "heading": (
            "宏观", "经济", "货币政策", "财政政策", "利率", "通胀", "macro",
            "inflation", "gdp", "federal reserve",
        ),
        "content": (
            "宏观", "经济", "gdp", "cpi", "ppi", "通胀", "就业", "失业率", "美联储",
            "联储", "央行", "利率", "降息", "加息", "qe", "货币政策", "财政政策",
            "汇率", "贸易", "macro", "inflation", "recession", "federal reserve",
            "interest rate", "monetary policy", "fiscal",
        ),
    },
    "fixed_income": {
        "filename": (
            "债券", "固收", "固定收益", "信用利差", "久期", "bond", "yield",
            "duration", "credit", "fixed_income",
        ),
        "heading": (
            "债券", "固定收益", "信用利差", "久期", "收益率", "bond", "yield",
            "fixed income", "credit spread",
        ),
        "content": (
            "债券", "国债", "企业债", "信用债", "可转债", "票息", "久期", "凸性",
            "收益率", "到期收益率", "利差", "信用评级", "违约", "固收", "bond",
            "yield", "duration", "coupon", "treasury", "spread", "credit",
        ),
    },
    "risk": {
        "filename": (
            "风险", "回撤", "波动率", "var", "sharpe", "beta", "alpha", "risk",
            "drawdown", "volatility", "hedge",
        ),
        "heading": (
            "风险", "风控", "回撤", "波动率", "var", "夏普", "risk", "drawdown",
            "volatility", "hedge",
        ),
        "content": (
            "风险", "风控", "风险预算", "波动率", "回撤", "最大回撤", "var", "夏普",
            "索提诺", "beta", "alpha", "相关性", "对冲", "止损", "黑天鹅", "hedge",
            "risk", "volatility", "drawdown", "sharpe", "correlation",
        ),
    },
}

_GENERAL_FILENAME_TERMS = (
    "基金", "期权", "期货", "资产配置", "投资策略", "市场术语", "量化", "衍生",
    "greeks", "option", "future", "futures", "allocation", "strategy",
)

_TERM_WEIGHTS = {
    "filename": 4.0,
    "heading": 2.5,
    "content": 1.0,
}


def get_domain_documents_path(persist_dir: Path, domain: str) -> Path:
    return persist_dir / f"documents.{domain}.json"


def get_domain_chunks_path(persist_dir: Path, domain: str) -> Path:
    return persist_dir / f"chunks.{domain}.json"


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _extract_headings(content: str) -> List[str]:
    headings: List[str] = []
    for line in (content or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            headings.append(stripped.lstrip("#").strip())
        elif len(headings) < 3:
            headings.append(stripped)
        if len(headings) >= 6:
            break
    return headings


def _score_terms(text: str, terms: Iterable[str]) -> Tuple[float, List[str]]:
    matched: List[str] = []
    score = 0.0
    for term in terms:
        normalized = term.lower()
        if normalized and normalized in text:
            matched.append(term)
            score += 1.0
    return score, matched


def classify_document(source: str, content: str, doc_key: str | None = None) -> DomainClassification:
    """Classify a document into one of the supported knowledge domains."""

    normalized_source = _normalize(f"{source} {doc_key or ''}")
    normalized_headings = _normalize(" ".join(_extract_headings(content)))
    normalized_content = _normalize(content[:12000])

    scores: Dict[str, float] = {domain: 0.0 for domain in DOMAINS}
    matched_terms: Dict[str, List[str]] = {domain: [] for domain in DOMAINS}

    for domain, term_groups in _DOMAIN_TERMS.items():
        for bucket, terms in term_groups.items():
            if bucket == "filename":
                text = normalized_source
            elif bucket == "heading":
                text = normalized_headings
            else:
                text = normalized_content
            raw_score, matched = _score_terms(text, terms)
            if raw_score:
                scores[domain] += raw_score * _TERM_WEIGHTS[bucket]
                matched_terms[domain].extend(matched)

    general_bonus, general_matched = _score_terms(normalized_source, _GENERAL_FILENAME_TERMS)
    if general_bonus:
        scores["general"] += general_bonus * _TERM_WEIGHTS["filename"]
        matched_terms["general"].extend(general_matched)

    best_domain = max(scores, key=scores.get)
    best_score = scores[best_domain]
    runner_up = max((score for domain, score in scores.items() if domain != best_domain), default=0.0)

    if best_score <= 0:
        return DomainClassification(
            domain="general",
            confidence=0.0,
            scores=scores,
            matched_terms=matched_terms,
        )

    if best_domain != "general" and best_score < 3.0:
        best_domain = "general"

    margin = max(best_score - runner_up, 0.0)
    confidence = min(1.0, 0.45 + (best_score / 12.0) + (margin / 20.0))

    return DomainClassification(
        domain=best_domain,
        confidence=round(confidence, 4),
        scores=scores,
        matched_terms=matched_terms,
    )
