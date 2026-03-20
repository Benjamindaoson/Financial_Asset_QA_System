"""Offline evaluation runner for the production route and planning chain."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

from app.agent.route_planner import RoutePlanner
from app.routing import QueryRouter
from app.routing.complexity_analyzer import QueryComplexityAnalyzer


@dataclass(frozen=True)
class EvalCase:
    """Single offline evaluation case."""

    case_id: str
    query: str
    expected_route_type: str
    expected_symbols: List[str] = field(default_factory=list)
    expected_tools: List[str] = field(default_factory=list)
    expected_complexity_level: Optional[str] = None


@dataclass(frozen=True)
class EvalResult:
    """Outcome for a single evaluation case."""

    case_id: str
    passed: bool
    route_type_ok: bool
    symbols_ok: bool
    tools_ok: bool
    complexity_ok: bool
    actual_route_type: str
    actual_symbols: List[str]
    actual_tools: List[str]
    actual_complexity_level: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EvalSummary:
    """Aggregate evaluation summary."""

    total_cases: int
    passed_cases: int
    route_accuracy: float
    symbol_accuracy: float
    tool_plan_accuracy: float
    complexity_accuracy: float
    results: List[EvalResult]

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["results"] = [result.to_dict() for result in self.results]
        return payload


def load_eval_cases(dataset_path: str | Path) -> List[EvalCase]:
    """Load JSONL evaluation cases."""

    path = Path(dataset_path)
    cases: List[EvalCase] = []
    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            cases.append(
                EvalCase(
                    case_id=payload["case_id"],
                    query=payload["query"],
                    expected_route_type=payload["expected_route_type"],
                    expected_symbols=payload.get("expected_symbols", []),
                    expected_tools=payload.get("expected_tools", []),
                    expected_complexity_level=payload.get("expected_complexity_level"),
                )
            )
    return cases


class OfflineEvalRunner:
    """Evaluate the production planner without calling live data providers."""

    def __init__(self, route_planner: Optional[RoutePlanner] = None) -> None:
        self.route_planner = route_planner or RoutePlanner(QueryRouter(), QueryComplexityAnalyzer())

    async def evaluate_case(self, case: EvalCase) -> EvalResult:
        route, complexity = await self.route_planner.analyze(case.query)
        plan = await self.route_planner.build_tool_plan(route, rag_top_k=complexity.rag_top_k)
        actual_tools = [step["name"] for step in plan]

        route_type_ok = route.query_type.value == case.expected_route_type
        symbols_ok = route.symbols == case.expected_symbols
        tools_ok = all(tool in actual_tools for tool in case.expected_tools)
        complexity_ok = (
            complexity.level == case.expected_complexity_level
            if case.expected_complexity_level is not None
            else True
        )

        return EvalResult(
            case_id=case.case_id,
            passed=route_type_ok and symbols_ok and tools_ok and complexity_ok,
            route_type_ok=route_type_ok,
            symbols_ok=symbols_ok,
            tools_ok=tools_ok,
            complexity_ok=complexity_ok,
            actual_route_type=route.query_type.value,
            actual_symbols=route.symbols,
            actual_tools=actual_tools,
            actual_complexity_level=complexity.level,
        )

    async def evaluate_cases(self, cases: List[EvalCase]) -> EvalSummary:
        results: List[EvalResult] = []
        for case in cases:
            results.append(await self.evaluate_case(case))

        total_cases = len(results)
        passed_cases = sum(1 for result in results if result.passed)
        route_hits = sum(1 for result in results if result.route_type_ok)
        symbol_hits = sum(1 for result in results if result.symbols_ok)
        tool_hits = sum(1 for result in results if result.tools_ok)
        complexity_hits = sum(1 for result in results if result.complexity_ok)

        def ratio(hits: int) -> float:
            return round(hits / total_cases, 3) if total_cases else 0.0

        return EvalSummary(
            total_cases=total_cases,
            passed_cases=passed_cases,
            route_accuracy=ratio(route_hits),
            symbol_accuracy=ratio(symbol_hits),
            tool_plan_accuracy=ratio(tool_hits),
            complexity_accuracy=ratio(complexity_hits),
            results=results,
        )
