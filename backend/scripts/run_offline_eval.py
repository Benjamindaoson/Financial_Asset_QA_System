"""Run the production offline evaluation suite."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.evaluation import OfflineEvalRunner, load_eval_cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run offline evaluation against the production planner.")
    parser.add_argument(
        "--dataset",
        default=str(PROJECT_ROOT / "evals" / "production_queries.jsonl"),
        help="Path to the JSONL evaluation dataset.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON summary.",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    cases = load_eval_cases(args.dataset)
    runner = OfflineEvalRunner()
    summary = await runner.evaluate_cases(cases)
    if args.pretty:
        print(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(summary.to_dict(), ensure_ascii=False))
    return 0 if summary.passed_cases == summary.total_cases else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
