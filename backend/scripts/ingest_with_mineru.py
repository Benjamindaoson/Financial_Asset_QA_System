"""Ingest raw financial documents into the RAG knowledge base using MinerU."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.rag.mineru_ingestion import MinerUDocumentIngestor  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Use MinerU to parse raw documents into knowledge markdown.")
    parser.add_argument("--raw-dir", type=Path, default=PROJECT_ROOT / "data" / "raw_data")
    parser.add_argument("--knowledge-dir", type=Path, default=PROJECT_ROOT / "data" / "knowledge")
    parser.add_argument("--dealed-dir", type=Path, default=PROJECT_ROOT / "data" / "dealed_data")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    ingestor = MinerUDocumentIngestor(
        raw_root=args.raw_dir,
        knowledge_root=args.knowledge_dir,
        dealed_root=args.dealed_dir,
    )
    files = ingestor.discover_files(limit=args.limit)
    if not files:
        print("[MinerU] 没有找到可解析的原始文件")
        return 0

    print(f"[MinerU] 准备解析 {len(files)} 个文件")
    for file_path in files:
        print(f"  - {file_path}")

    results = ingestor.ingest(files)
    for item in results:
        print(f"[{item.status}] {item.source_file} -> {item.output_file or '-'} | {item.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
