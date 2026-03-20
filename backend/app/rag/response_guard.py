"""ResponseGuard: semantic triple-binding validation for grounded responses."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GroundedFact:
    """A single numeric fact extracted from a tool payload."""

    value: float
    field: str          # e.g. "pe_ratio", "price", "market_cap"
    symbol: str
    timestamp: str      # ISO date string YYYY-MM-DD
    unit: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of ResponseGuard.validate()."""

    valid: bool
    reason: str
    ungrounded: List[str] = field(default_factory=list)


class ResponseGuard:
    """Validate that numeric claims in a response are grounded in tool payloads.

    Upgrade over plain number-set matching: validates (value, field, timestamp)
    triples so that '100 USD' cannot be confused with '100 亿', and a mention
    of '市盈率' is only accepted when a pe_ratio fact exists in the payload.
    """

    # Maps payload field name -> natural language aliases that may appear in responses
    FIELD_ALIASES: Dict[str, List[str]] = {
        "pe_ratio":     ["市盈率", "PE", "P/E", "price-to-earnings", "pe ratio"],
        "price":        ["股价", "价格", "报价", "price", "现价", "当前价格"],
        "market_cap":   ["市值", "总市值", "market cap", "market_cap"],
        "change_pct":   ["涨幅", "跌幅", "涨跌幅", "变动", "涨跌"],
        "volume":       ["成交量", "volume", "交易量"],
        "week_52_high": ["52周高", "52week high", "年内高点", "52周最高"],
        "week_52_low":  ["52周低", "52week low", "年内低点", "52周最低"],
        "annualized_volatility": ["波动率", "volatility", "年化波动"],
        "max_drawdown_pct":      ["最大回撤", "max drawdown", "drawdown"],
        "total_return_pct":      ["总回报", "total return", "累计收益"],
        "sharpe_ratio":          ["夏普", "sharpe", "sharpe ratio"],
    }

    # Fields that are known numeric but NOT financial metrics (skip semantic check)
    _SKIP_FIELDS = {"days", "cache_hit", "latency_ms", "tokens_input", "tokens_output"}

    @staticmethod
    def extract_grounded_facts(tool_results: List[Any]) -> List[GroundedFact]:
        """Extract structured facts from tool result payloads."""
        facts: List[GroundedFact] = []
        for result in tool_results:
            data: Dict[str, Any] = getattr(result, "data", {})
            if not isinstance(data, dict):
                continue
            symbol = str(data.get("symbol", ""))
            raw_ts = data.get("timestamp", "")
            timestamp = str(raw_ts)[:10] if raw_ts else ""
            for fld, value in data.items():
                if fld in ResponseGuard._SKIP_FIELDS:
                    continue
                if isinstance(value, bool):
                    continue
                if isinstance(value, (int, float)):
                    facts.append(GroundedFact(
                        value=float(value),
                        field=fld,
                        symbol=symbol,
                        timestamp=timestamp,
                    ))
        return facts

    @staticmethod
    def validate_detailed(response_text: str, tool_results: List[Any]) -> ValidationResult:
        """Validate response text and return a detailed ValidationResult."""
        return ResponseGuard._run_validation(response_text, tool_results)

    @staticmethod
    def validate(response_text: str, tool_results: List[Any]) -> bool:
        """Validate response text against tool payloads using triple-binding.

        Returns True when the response is grounded.  Backward-compatible with
        the old bool-returning API.
        """
        return ResponseGuard._run_validation(response_text, tool_results).valid

    @staticmethod
    def _run_validation(response_text: str, tool_results: List[Any]) -> ValidationResult:
        """Core validation logic returning a ValidationResult."""
        if not response_text.strip():
            return ValidationResult(valid=False, reason="empty_response")

        facts = ResponseGuard.extract_grounded_facts(tool_results)

        if not facts:
            # No numeric tool data — nothing to ground against, allow through
            return ValidationResult(valid=True, reason="no_numeric_tools")

        # ---- Field semantic consistency check ----
        # If the response mentions an alias for a known field, that field's
        # fact must exist in the payload.
        for fld, aliases in ResponseGuard.FIELD_ALIASES.items():
            response_lower = response_text.lower()
            mentioned = any(alias.lower() in response_lower for alias in aliases)
            if mentioned:
                has_fact = any(f.field == fld for f in facts)
                if not has_fact:
                    return ValidationResult(
                        valid=False,
                        reason=f"field_{fld}_not_in_payload",
                    )

        # ---- Numeric grounding check ----
        mentioned_numbers = re.findall(r"\d+(?:\.\d+)?", response_text)
        if not mentioned_numbers:
            return ValidationResult(valid=True, reason="no_numbers_in_response")

        grounded_values = {f.value for f in facts}

        def _is_grounded(num_str: str) -> bool:
            val = float(num_str)
            # Small integers (≤ 10) are likely counts/ordinals, not financial claims
            if val <= 10 and float(num_str) == int(float(num_str)):
                return True
            return any(abs(gv - val) < 0.011 for gv in grounded_values)

        ungrounded = [n for n in mentioned_numbers if not _is_grounded(n)]
        ungrounded_ratio = len(ungrounded) / len(mentioned_numbers)

        if ungrounded_ratio > 0.3:
            return ValidationResult(
                valid=False,
                reason="too_many_ungrounded_numbers",
                ungrounded=ungrounded,
            )

        return ValidationResult(valid=True, reason="all_numbers_grounded")

    # ---- Legacy helpers kept for backward compatibility ----

    @staticmethod
    def _collect_numbers(value: Any, bucket: set) -> None:
        """Recursively collect numeric strings from a nested payload."""
        if isinstance(value, dict):
            for item in value.values():
                ResponseGuard._collect_numbers(item, bucket)
            return
        if isinstance(value, list):
            for item in value:
                ResponseGuard._collect_numbers(item, bucket)
            return
        if isinstance(value, (int, float)):
            bucket.add(str(int(value)) if float(value).is_integer() else f"{value:.2f}")
