#!/usr/bin/env python3
"""
演示前预热脚本：运行 7 个演示问题，预热 Redis 市场缓存、RAG 模型，并可选生成答案缓存。

用法:
  python -m scripts.warm_demo_cache              # 仅预热（跑一遍 7 个问题）
  python -m scripts.warm_demo_cache --save       # 预热并保存答案到 demo_cache.json
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DEMO_QUERIES = [
    "阿里巴巴当前股价是多少？",
    "BABA 最近 7 天涨跌情况如何？",
    "阿里巴巴最近为何1月15日大涨？",
    "特斯拉近期走势如何？",
    "什么是市盈率？",
    "收入和净利润的区别是什么？",
    "特斯拉最近季度财报摘要是什么？",
]


async def warm_market_cache():
    """预热市场数据缓存（BABA, TSLA 等）"""
    from app.market import MarketDataService
    from app.cache.popular_stocks import get_popular_stocks

    service = MarketDataService()
    stocks = ["BABA", "TSLA", "AAPL"]
    logger.info(f"[1/3] 预热市场缓存: {stocks}")
    for symbol in stocks:
        try:
            await service.get_price(symbol)
            await service.get_history(symbol, days=30)
            await service.get_change(symbol, days=7)
            logger.info(f"  ✓ {symbol}")
        except Exception as e:
            logger.warning(f"  ✗ {symbol}: {e}")


async def warm_rag():
    """预热 RAG 模型（加载 embedding + reranker）"""
    from app.rag.hybrid_pipeline import HybridRAGPipeline

    logger.info("[2/3] 预热 RAG 模型...")
    try:
        pipeline = HybridRAGPipeline()
        if pipeline.collection.count() > 0:
            pipeline._ensure_models()
            # 跑一个简单查询确保模型已加载
            _ = pipeline._search_local_documents("市盈率")
            logger.info("  ✓ RAG 模型已加载")
        else:
            logger.info("  - ChromaDB 为空，跳过向量模型")
    except Exception as e:
        logger.warning(f"  ✗ RAG 预热失败: {e}")


async def run_queries_and_save(save: bool):
    """运行 7 个演示问题，可选保存答案"""
    from app.agent import AgentCore

    logger.info("[3/3] 运行 7 个演示问题...")
    agent = AgentCore()
    cache = {}

    for i, q in enumerate(DEMO_QUERIES, 1):
        logger.info(f"  [{i}/7] {q[:40]}...")
        try:
            blocks = []
            sources = []
            rag_citations = []
            tool_latencies = []
            route = None
            llm_used = False
            text = ""

            async for event in agent.run(q):
                if event.type == "blocks" and event.data:
                    blocks = event.data.get("blocks", [])
                    route = event.data.get("route")
                elif event.type == "done":
                    if event.data:
                        blocks = event.data.get("blocks", blocks)
                        route = event.data.get("route", route)
                        rag_citations = event.data.get("rag_citations", [])
                        tool_latencies = event.data.get("tool_latencies", [])
                        llm_used = event.data.get("llm_used", False)
                    sources = event.sources or []
                elif event.type == "chunk":
                    text += event.text or ""
                elif event.type == "analysis_chunk":
                    text += event.text or ""

            if save:
                cache[q] = {
                    "blocks": blocks,
                    "sources": [{"name": s.name, "timestamp": getattr(s, "timestamp", "")} for s in sources],
                    "rag_citations": rag_citations,
                    "tool_latencies": tool_latencies,
                    "route": route,
                    "llm_used": llm_used,
                    "text": text,
                }
            logger.info(f"      ✓ 完成 ({len(blocks)} blocks)")
        except Exception as e:
            logger.warning(f"      ✗ 失败: {e}")

    if save and cache:
        from app.config import settings
        out_path = Path(__file__).resolve().parents[1] / settings.DEMO_CACHE_PATH
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        logger.info(f"\n已保存 {len(cache)} 条答案到 {out_path}")


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true", help="保存答案到 demo_cache.json")
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("演示缓存预热")
    logger.info("=" * 50)

    await warm_market_cache()
    await warm_rag()
    await run_queries_and_save(save=args.save)

    logger.info("\n预热完成。")


if __name__ == "__main__":
    asyncio.run(main())
