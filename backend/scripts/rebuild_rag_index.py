"""Rebuild the local RAG vector index from Markdown knowledge files."""

from __future__ import annotations

import json
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.rag.hybrid_pipeline import HybridRAGPipeline  # noqa: E402


def main() -> int:
    pipeline = HybridRAGPipeline()
    print("[RAG] 当前索引状态：")
    print(json.dumps(pipeline.get_status(), ensure_ascii=False, indent=2))

    try:
        result = pipeline.index_local_knowledge(force=True)
    except Exception as exc:
        print(f"[RAG] 重建失败: {exc}")
        return 1

    print("[RAG] 重建完成：")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("[RAG] 最新状态：")
    print(json.dumps(pipeline.get_status(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
