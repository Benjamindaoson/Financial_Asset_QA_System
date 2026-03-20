#!/usr/bin/env python3
"""
直接调用 AgentCore 运行演示问题，无需启动 HTTP 服务。
用法: cd backend && python -m scripts.run_demo_queries
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent import AgentCore
from app.enricher import QueryEnricher


async def run_query(query: str):
    """直接调用 AgentCore.run() 并收集所有事件"""
    enricher = QueryEnricher()
    agent = AgentCore()
    enriched = enricher.enrich(query)

    events = []
    start = time.perf_counter()

    async for ev in agent.run(enriched):
        t_ms = round((time.perf_counter() - start) * 1000)
        d = ev.model_dump(exclude_none=True)
        events.append({"elapsed_ms": t_ms, **d})

    return events


def main():
    print("=" * 80)
    print("问题 1: 阿里巴巴明天会涨还是跌？")
    print("=" * 80)

    events1 = asyncio.run(run_query("阿里巴巴明天会涨还是跌？"))

    # Pipeline 步骤
    print("\n【Pipeline 步骤】")
    for e in events1:
        t = e.get("elapsed_ms", 0)
        typ = e.get("type", "")
        if typ == "tool_start":
            print(f"  {t}ms | tool_start: {e.get('name')} - {e.get('display')}")
        elif typ == "tool_data":
            print(f"  {t}ms | tool_data: {e.get('tool')}")
        elif typ == "model_selected":
            print(f"  {t}ms | model_selected: {e.get('model')}")
        elif typ == "chunk":
            print(f"  {t}ms | chunk (文本): {e.get('text', '')[:80]}...")
        elif typ == "blocks":
            blocks = e.get("data", {}).get("blocks", [])
            print(f"  {t}ms | blocks: {len(blocks)} 个")
            for b in blocks:
                print(f"       - {b.get('type')}: {b.get('title')}")
        elif typ == "done":
            print(f"  {t}ms | done")
            d = e.get("data", {})
            if d.get("blocks"):
                print("  done.blocks:")
                for b in d["blocks"]:
                    print(f"       - {b.get('type')}: {b.get('title')}")

    # 完整回复文本
    texts = [e.get("text", "") for e in events1 if e.get("type") in ("chunk", "analysis_chunk") and e.get("text")]
    print("\n【完整回复文本】")
    print("".join(texts))

    # 首个内容时间
    first = next((e["elapsed_ms"] for e in events1 if e.get("type") in ("blocks", "chunk", "analysis_chunk", "tool_data") and (e.get("data") or e.get("text"))), None)
    done = next((e["elapsed_ms"] for e in events1 if e.get("type") == "done"), None)
    print(f"\n【耗时】首个内容: {first}ms, 完成: {done}ms")

    print("\n" + "#" * 80)
    print("问题 2: 什么是市盈率？")
    print("#" * 80)

    events2 = asyncio.run(run_query("什么是市盈率？"))

    print("\n【Pipeline 步骤与耗时】")
    for e in events2:
        t = e.get("elapsed_ms", 0)
        typ = e.get("type", "")
        if typ == "model_selected":
            print(f"  {t:5}ms | model_selected")
        elif typ == "tool_start":
            print(f"  {t:5}ms | tool_start: {e.get('name')}")
        elif typ == "tool_data":
            lat = e.get("data", {}).get("latency_ms") if isinstance(e.get("data"), dict) else None
            print(f"  {t:5}ms | tool_data: {e.get('tool')} (tool latency: {lat}ms)")
        elif typ == "blocks":
            print(f"  {t:5}ms | blocks")
        elif typ == "chunk":
            print(f"  {t:5}ms | chunk")
        elif typ == "analysis_chunk":
            print(f"  {t:5}ms | analysis_chunk")
        elif typ == "done":
            print(f"  {t:5}ms | done")

    texts2 = [e.get("text", "") for e in events2 if e.get("type") in ("chunk", "analysis_chunk") and e.get("text")]
    print("\n【完整回复文本（前 500 字）】")
    full = "".join(texts2)
    print(full[:500] + ("..." if len(full) > 500 else ""))

    first2 = next((e["elapsed_ms"] for e in events2 if e.get("type") in ("blocks", "chunk", "analysis_chunk", "tool_data") and (e.get("data") or e.get("text"))), None)
    done2 = next((e["elapsed_ms"] for e in events2 if e.get("type") == "done"), None)
    print(f"\n【耗时】首个可见内容: {first2}ms, 完整回答完成: {done2}ms")


if __name__ == "__main__":
    main()
