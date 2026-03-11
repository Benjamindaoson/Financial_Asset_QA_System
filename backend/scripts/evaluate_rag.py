"""Evaluate local RAG retrieval quality and write a Markdown regression report."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Dict, List


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.rag.hybrid_pipeline import HybridRAGPipeline  # noqa: E402


DEFAULT_DATASET_PATH = BACKEND_ROOT / "tests" / "datasets" / "rag_regression_dataset.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "docs" / "RAG_REGRESSION_REPORT.md"


def _load_dataset(dataset_path: Path) -> List[Dict[str, Any]]:
    if not dataset_path.exists():
        raise FileNotFoundError(f"未找到评测数据集: {dataset_path}")
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(dataset, list) or not dataset:
        raise ValueError("评测数据集为空或格式不正确")
    return dataset


def _keyword_coverage(documents: List[Dict[str, Any]], expected_keywords: List[str]) -> float:
    if not expected_keywords:
        return 1.0
    combined = " ".join(
        f"{doc.get('title', '')} {doc.get('section', '')} {doc.get('content', '')}".lower()
        for doc in documents
    )
    hit = sum(1 for keyword in expected_keywords if keyword.lower() in combined)
    return hit / len(expected_keywords)


def _render_report(
    dataset_path: Path,
    report_path: Path,
    status: Dict[str, Any],
    metrics: Dict[str, Any],
    rows: List[Dict[str, Any]],
) -> str:
    report_lines = [
        "# RAG 回归评测报告",
        "",
        f"- 评测时间: {metrics['generated_at']}",
        f"- 数据集: `{dataset_path.relative_to(PROJECT_ROOT)}`",
        f"- 样本数: `{metrics['cases']}`",
        f"- Top1 准确率: `{metrics['top1_accuracy']:.2%}`",
        f"- Recall@3: `{metrics['recall_at_3']:.2%}`",
        f"- 召回命中率: `{metrics['retrieval_hit_rate']:.2%}`",
        f"- 关键词覆盖率: `{metrics['keyword_coverage']:.2%}`",
        "",
        "## 索引状态",
        "",
        f"- 知识源数: `{status['sources']}`",
        f"- Chunk 数: `{status['chunks']}`",
        f"- 向量索引条数: `{status['vector_index_count']}`",
        f"- BM25 就绪: `{status['bm25_ready']}`",
        f"- Embedding 后端: `{status['embedding_backend']}`",
        "",
        "## 样本明细",
        "",
        "| 用例 | 问题 | Top1 | Top3 是否命中 | 关键词覆盖率 |",
        "| --- | --- | --- | --- | --- |",
    ]

    for row in rows:
        report_lines.append(
            f"| {row['id']} | {row['query']} | {row['top1_source'] or '无'} | "
            f"{'是' if row['hit_at_3'] else '否'} | {row['keyword_coverage']:.0%} |"
        )

    report_lines.extend(
        [
            "",
            "## 备注",
            "",
            "- 评测只检查检索质量，不评估最终 LLM 生成措辞。",
            "- `Top1 准确率` 使用 `expected_top1_source` 判定；`Recall@3` 使用 `expected_sources` 判定。",
            "- 若 `embedding_backend=local-hash`，说明当前环境未启用正式向量模型，但向量索引仍可工作。",
            "",
        ]
    )
    markdown = "\n".join(report_lines)
    report_path.write_text(markdown, encoding="utf-8")
    return markdown


async def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval quality.")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()

    dataset = _load_dataset(args.dataset)
    pipeline = HybridRAGPipeline()
    status = pipeline.get_status()
    if status["vector_index_count"] == 0 and status["chunks"] > 0:
        pipeline.index_local_knowledge(force=False)
        status = pipeline.get_status()

    rows: List[Dict[str, Any]] = []
    top1_correct = 0
    hit_at_3 = 0
    hit_any = 0
    keyword_coverage_sum = 0.0

    for item in dataset:
        result = await pipeline.search(item["query"], use_hybrid=True)
        documents = [doc.model_dump() for doc in result.documents]
        top_sources = [doc["source"] for doc in documents[:3]]
        top1_source = top_sources[0] if top_sources else None
        expected_sources = item.get("expected_sources", [])
        expected_top1_source = item.get("expected_top1_source")
        keyword_coverage = _keyword_coverage(documents[:3], item.get("expected_keywords", []))

        row = {
            "id": item["id"],
            "query": item["query"],
            "top1_source": top1_source,
            "top3_sources": top_sources,
            "expected_sources": expected_sources,
            "expected_top1_source": expected_top1_source,
            "hit_any": any(source in expected_sources for source in [doc["source"] for doc in documents]),
            "hit_at_3": any(source in expected_sources for source in top_sources),
            "top1_correct": top1_source == expected_top1_source if expected_top1_source else False,
            "keyword_coverage": keyword_coverage,
        }
        rows.append(row)

        top1_correct += int(row["top1_correct"])
        hit_at_3 += int(row["hit_at_3"])
        hit_any += int(row["hit_any"])
        keyword_coverage_sum += keyword_coverage

    total = len(rows)
    metrics = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "cases": total,
        "top1_accuracy": top1_correct / total,
        "recall_at_3": hit_at_3 / total,
        "retrieval_hit_rate": hit_any / total,
        "keyword_coverage": keyword_coverage_sum / total,
    }

    report_markdown = _render_report(args.dataset, args.report, status, metrics, rows)
    print("[RAG] 评测完成")
    print(
        json.dumps(
            {
                "dataset": str(args.dataset),
                "report": str(args.report),
                "status": status,
                "metrics": metrics,
                "samples": rows[:10],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print(report_markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
