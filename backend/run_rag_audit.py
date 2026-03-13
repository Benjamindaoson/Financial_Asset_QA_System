"""RAG Audit: run retrieval for 3 queries and output full results."""
import asyncio
import sys
import time

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.rag.hybrid_pipeline import HybridRAGPipeline


def run_retrieval(pipeline, query):
    t0 = time.time()
    result = pipeline._search_local_documents(query)
    elapsed = time.time() - t0
    return result, elapsed


def main():
    pipeline = HybridRAGPipeline()
    queries = [
        "什么是市盈率",
        "收入和净利润的区别是什么",
        "什么是可转债的强赎条款",
    ]
    for q in queries:
        sep = "=" * 64
        print(f"\n{sep}")
        print(f"QUERY: {q}")
        print(sep)
        result, elapsed = run_retrieval(pipeline, q)
        # result is KnowledgeResult with .documents list
        docs = result.documents if hasattr(result, "documents") else []
        total = result.total_found if hasattr(result, "total_found") else 0
        print(f"耗时: {elapsed*1000:.0f}ms  | 返回文档数: {len(docs)} / total_found={total}")
        if not docs:
            print(">>> 无结果（零命中）")
        for i, doc in enumerate(docs[:3]):
            # doc is Document model with .content, .source, .score
            print(f"\n--- TOP {i+1} ---")
            print(f"来源文件: {doc.source}")
            print(f"分数    : {doc.score}")
            print("内容（完整）:")
            print(doc.content)
            print()


if __name__ == "__main__":
    main()
