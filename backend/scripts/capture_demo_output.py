#!/usr/bin/env python3
"""
捕获演示问题的完整输出，用于逐字稿撰写。
用法: python -m scripts.capture_demo_output
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx


async def fetch_chat_stream(query: str, base_url: str = "http://localhost:8000"):
    """调用 /api/chat 并解析 SSE 流，记录每步耗时和内容"""
    url = f"{base_url}/api/chat"
    events = []
    start_total = time.perf_counter()
    first_content_time = None
    done_time = None

    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream(
            "POST",
            url,
            json={"query": query},
            headers={"Accept": "text/event-stream"},
        ) as response:
            if response.status_code != 200:
                print(f"Error: {response.status_code} {response.text}")
                return None

            buffer = ""
            event_start = None
            for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]" or data.strip() == "":
                        continue
                    try:
                        obj = json.loads(data)
                        t = time.perf_counter() - start_total
                        events.append({"elapsed_ms": round(t * 1000), "data": obj})

                        # 记录首次可见内容时间
                        if first_content_time is None:
                            if obj.get("type") == "blocks" and obj.get("data", {}).get("blocks"):
                                first_content_time = t
                            elif obj.get("type") == "chunk" and obj.get("text"):
                                first_content_time = t
                            elif obj.get("type") == "analysis_chunk" and obj.get("text"):
                                first_content_time = t
                            elif obj.get("type") == "tool_data":
                                first_content_time = t

                        if obj.get("type") == "done":
                            done_time = t
                    except json.JSONDecodeError:
                        pass

    return {
        "events": events,
        "first_content_sec": first_content_time,
        "done_sec": done_time,
        "total_sec": time.perf_counter() - start_total,
    }


def print_result(query: str, result: dict):
    if not result:
        return
    print("=" * 80)
    print(f"查询: {query}")
    print("=" * 80)

    # Pipeline 步骤（tool_start / tool_data）
    tool_steps = []
    for ev in result["events"]:
        d = ev["data"]
        t = ev["elapsed_ms"]
        if d.get("type") == "tool_start":
            tool_steps.append({"name": d.get("name", ""), "display": d.get("display", ""), "start_ms": t})
        elif d.get("type") == "tool_data":
            # 找到对应的 tool_start，计算耗时（简化：用相邻 tool_data 的 t 作为结束）
            for s in reversed(tool_steps):
                if s.get("name") == d.get("tool") and "end_ms" not in s:
                    s["end_ms"] = t
                    break

    print("\n【Pipeline 步骤与耗时】")
    prev_end = 0
    for s in tool_steps:
        start = s.get("start_ms", 0)
        end = s.get("end_ms", start)
        dur = end - start if s.get("end_ms") else "?"
        print(f"  - {s.get('name', '')} ({s.get('display', '')}): 开始 {start}ms, 耗时 {dur}ms")

    # blocks
    blocks_data = None
    for ev in result["events"]:
        if ev["data"].get("type") == "blocks":
            blocks_data = ev["data"].get("data", {})
            break
    if blocks_data:
        print("\n【数据卡片 blocks】")
        for b in blocks_data.get("blocks", []):
            print(f"  - type={b.get('type')}, title={b.get('title')}")
            if b.get("data"):
                # 简要展示
                d = b["data"]
                if "items" in d and len(str(d["items"])) < 200:
                    print(f"    items: {d['items'][:2]}...")
                elif "rows" in d:
                    print(f"    rows: {len(d['rows'])} 行")

    # chunk / analysis_chunk 文本
    full_text = []
    for ev in result["events"]:
        d = ev["data"]
        if d.get("type") in ("chunk", "analysis_chunk") and d.get("text"):
            full_text.append(d["text"])
    if full_text:
        print("\n【AI 分析 / 回复完整文字】")
        print("".join(full_text))

    # done 中的额外信息
    for ev in result["events"]:
        if ev["data"].get("type") == "done":
            d = ev["data"]
            if d.get("data", {}).get("blocks"):
                print("\n【done 中的 blocks 快照】")
                for b in d["data"]["blocks"]:
                    print(f"  - type={b.get('type')}, title={b.get('title')}")
            break

    # 耗时汇总
    print("\n【耗时汇总】")
    print(f"  首个可见内容: {result.get('first_content_sec') and round(result['first_content_sec']*1000) or 'N/A'} ms")
    print(f"  完整回答完成: {result.get('done_sec') and round(result['done_sec']*1000) or 'N/A'} ms")
    print(f"  总耗时: {round(result.get('total_sec', 0)*1000)} ms")
    print()


async def main():
    base = "http://localhost:8000"
    try:
        r = httpx.get(f"{base}/api/health", timeout=5)
        if r.status_code != 200:
            print("Backend not healthy. Start with: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000")
            return
    except Exception as e:
        print(f"Backend not reachable: {e}")
        print("Start with: cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000")
        return

    # 问题1: 阿里巴巴明天会涨还是跌？
    print("\n" + "#" * 80)
    print("# 问题 1: 阿里巴巴明天会涨还是跌？")
    print("#" * 80)
    r1 = await fetch_chat_stream("阿里巴巴明天会涨还是跌？", base)
    if r1:
        print_result("阿里巴巴明天会涨还是跌？", r1)

    # 问题2: 什么是市盈率？
    print("\n" + "#" * 80)
    print("# 问题 2: 什么是市盈率？")
    print("#" * 80)
    r2 = await fetch_chat_stream("什么是市盈率？", base)
    if r2:
        print_result("什么是市盈率？", r2)
        # 详细 pipeline 步骤
        print("\n【详细 Pipeline 步骤（含每步耗时）】")
        for ev in r2["events"]:
            d = ev["data"]
            t = ev["elapsed_ms"]
            if d.get("type") in ("model_selected", "tool_start", "tool_data", "blocks", "chunk", "analysis_chunk", "done"):
                print(f"  {t:6}ms | {d.get('type', '')} | name={d.get('name','')} tool={d.get('tool','')}")


if __name__ == "__main__":
    asyncio.run(main())
