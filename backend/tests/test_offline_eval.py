"""Tests for the offline evaluation runner."""

from pathlib import Path

import pytest

from app.evaluation import OfflineEvalRunner, load_eval_cases


def test_load_eval_cases_reads_jsonl_dataset():
    dataset = Path(__file__).resolve().parents[1] / "evals" / "production_queries.jsonl"

    cases = load_eval_cases(dataset)

    assert len(cases) >= 10
    assert cases[0].case_id
    assert cases[0].query


@pytest.mark.asyncio
async def test_offline_eval_runner_scores_dataset():
    dataset = Path(__file__).resolve().parents[1] / "evals" / "production_queries.jsonl"
    cases = load_eval_cases(dataset)
    runner = OfflineEvalRunner()

    summary = await runner.evaluate_cases(cases)

    assert summary.total_cases == len(cases)
    assert 0.0 <= summary.route_accuracy <= 1.0
    assert 0.0 <= summary.tool_plan_accuracy <= 1.0
    assert summary.route_accuracy >= 0.95
    assert summary.tool_plan_accuracy >= 0.95
    assert summary.complexity_accuracy >= 0.95
    assert summary.passed_cases >= len(cases) - 1
