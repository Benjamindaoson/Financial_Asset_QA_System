# -*- coding: utf-8 -*-
"""
End-to-end test script.
Usage: python test_e2e.py  (run from backend/ directory, backend must be running on port 8001)
"""
import asyncio
import json
import sys
import time
import httpx

# Force UTF-8 output on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_URL = "http://127.0.0.1:8001"

TEST_CASES = [
    {
        "id": 1,
        "desc": "行情类: 单股实时价格",
        "query": "特斯拉当前股价是多少",
        "expect_route": "market",
        "expect_llm": True,
    },
    {
        "id": 2,
        "desc": "行情+新闻混合: 7日涨跌 (含'最近'触发hybrid)",
        "query": "BABA 最近7天涨跌情况如何",
        "expect_route": "hybrid",
        "expect_llm": True,
    },
    {
        "id": 3,
        "desc": "混合类: 归因分析",
        "query": "阿里巴巴最近为何大涨",
        "expect_route": "hybrid",
        "expect_llm": True,
    },
    {
        "id": 4,
        "desc": "知识类: RAG检索",
        "query": "什么是市盈率",
        "expect_route": "knowledge",
        "expect_llm": True,
    },
    {
        "id": 5,
        "desc": "合规拒绝: 预测性问题",
        "query": "比特币明天会涨吗",
        "expect_route": None,
        "expect_llm": False,
    },
]


async def send_chat(client: httpx.AsyncClient, query: str) -> dict:
    """Send SSE request, collect all events, return summary."""
    events = []
    async with client.stream(
        "POST",
        f"{BASE_URL}/api/chat",
        json={"query": query},
        timeout=90.0,
    ) as response:
        response.raise_for_status()
        buffer = ""
        async for chunk in response.aiter_text():
            buffer += chunk
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line.startswith("data: "):
                    raw = line[6:].strip()
                    if raw:
                        try:
                            events.append(json.loads(raw))
                        except json.JSONDecodeError:
                            pass

    result = {
        "events": events,
        "text": "",
        "route": None,
        "llm_used": False,
        "blocks": [],
        "tools_called": [],
    }
    for ev in events:
        t = ev.get("type")
        if t == "chunk":
            result["text"] += ev.get("text", "")
        elif t == "tool_start":
            result["tools_called"].append(ev.get("name", ""))
        elif t == "done":
            data = ev.get("data") or {}
            result["route"] = (data.get("route") or {}).get("type")
            result["llm_used"] = data.get("llm_used", False)
            result["blocks"] = data.get("blocks", [])
        elif t == "error":
            result["error"] = ev.get("message", "unknown error")
    return result


async def run_tests():
    print()
    print("=" * 65)
    print("  Financial QA System - End-to-End Tests")
    print("=" * 65)
    print()

    # trust_env=False bypasses system proxy (e.g. 127.0.0.1:10808 → localhost 502)
    # Health check
    async with httpx.AsyncClient(trust_env=False) as client:
        try:
            r = await client.get(f"{BASE_URL}/api/health", timeout=5)
            if r.status_code == 200:
                health = r.json()
                print(f"[HEALTH] status={health.get('status', '?')}")
                comps = health.get("components", {})
                for k, v in comps.items():
                    print(f"  {k}: {v}")
                print()
                llm_active = comps.get("deepseek_api") == "configured"
                if not llm_active:
                    print("[WARN] DEEPSEEK_API_KEY not configured -> llm_used will always be False")
                    print("       Fill in DEEPSEEK_API_KEY in backend/.env to enable LLM generation")
                    print()
            else:
                print(f"[WARN] /api/health returned HTTP {r.status_code}")
                print()
        except Exception as e:
            print(f"[FAIL] Backend not reachable: {e}")
            print("Start backend first: cd backend && uvicorn app.main:app --port 8001")
            return

    passed = 0
    failed = 0

    async with httpx.AsyncClient(trust_env=False) as client:
        for tc in TEST_CASES:
            print(f"[{tc['id']}] {tc['desc']}")
            print(f"    Query : {tc['query']}")
            t0 = time.time()
            try:
                result = await send_chat(client, tc["query"])
                elapsed = time.time() - t0

                if "error" in result:
                    print(f"    [FAIL] Service error: {result['error']}")
                    failed += 1
                    print()
                    continue

                # Route check
                route_ok = (tc["expect_route"] is None) or (result["route"] == tc["expect_route"])
                # LLM check
                llm_ok = result["llm_used"] == tc["expect_llm"]
                # Has text
                has_text = len(result["text"].strip()) > 0

                route_tag = "OK  " if route_ok else "FAIL"
                llm_tag   = "OK  " if llm_ok   else "WARN"
                text_tag  = "OK  " if has_text  else "FAIL"

                block_types = ", ".join(b["type"] for b in result["blocks"][:5]) or "none"
                tools_str   = ", ".join(result["tools_called"]) or "none"

                print(f"    Route : {str(result['route']):12s} [{route_tag}]  (expected: {tc['expect_route']})")
                print(f"    LLM   : {'yes' if result['llm_used'] else 'no':4s}         [{llm_tag}]  (expected: {'yes' if tc['expect_llm'] else 'no'})")
                print(f"    Text  : {'yes' if has_text else 'no':4s}         [{text_tag}]")
                print(f"    Blocks: {len(result['blocks'])} ({block_types})")
                print(f"    Tools : {tools_str}")
                print(f"    Time  : {elapsed:.1f}s")

                if has_text:
                    preview = result["text"].replace("\n", " ")[:150]
                    print(f"    Preview: {preview}")

                if route_ok and has_text:
                    passed += 1
                else:
                    failed += 1

            except Exception as e:
                elapsed = time.time() - t0
                print(f"    [FAIL] Exception ({elapsed:.1f}s): {e}")
                import traceback
                traceback.print_exc()
                failed += 1

            print()

    print("=" * 65)
    print(f"  Result: {passed} passed / {failed} failed / {len(TEST_CASES)} total")
    print("=" * 65)
    print()

    if failed == 0:
        print("All tests passed. Ready for demo recording.")
    else:
        print("Some tests failed. Check output above for details.")


if __name__ == "__main__":
    asyncio.run(run_tests())
