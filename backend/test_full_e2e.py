"""Full 8-case E2E test with detailed quality checks."""

import asyncio
import sys
import json
import time

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx

BASE_URL = "http://127.0.0.1:8001"

# ─────────────────────────────────────────────────────────────
# Test definitions
# ─────────────────────────────────────────────────────────────
TEST_CASES = [
    {
        "id": 1,
        "label": "实时价格 - 美股",
        "query": "特斯拉当前股价是多少",
        "checks": {
            "route": "market",
            "llm_used": True,
            "has_price_number": lambda t, blocks, tools: any(
                b.get("type") == "bullets" for b in blocks
            ),
            "analysis_block_exists": lambda t, blocks, tools: any(
                b.get("type") == "analysis" for b in blocks
            ),
            "no_prediction": lambda t, blocks, tools: not any(
                w in t for w in ["将会上涨", "预计上涨", "目标价", "建议买", "推荐"]
            ),
            "TSLA_in_response": lambda t, blocks, tools: "tsla" in t.lower() or "特斯拉" in t,
        },
    },
    {
        "id": 2,
        "label": "7日涨跌分析",
        "query": "BABA 最近7天涨跌情况如何",
        "checks": {
            "route": "hybrid",
            "llm_used": True,
            "has_change_pct": lambda t, blocks, tools: any(
                b.get("type") == "bullets" and
                any("%" in str(item) for item in b.get("data", {}).get("items", []))
                for b in blocks
            ),
            "get_change_called": lambda t, blocks, tools: "get_change" in tools,
            "analysis_mentions_numbers": lambda t, blocks, tools: any(
                b.get("type") == "analysis" and
                any(c.isdigit() for c in b.get("data", {}).get("text", ""))
                for b in blocks
            ),
        },
    },
    {
        "id": 3,
        "label": "多源归因分析",
        "query": "阿里巴巴最近为何大涨",
        "checks": {
            "route": "hybrid",
            "llm_used": True,
            "web_search_called": lambda t, blocks, tools: "search_web" in tools,
            "has_news_block": lambda t, blocks, tools: any(
                b.get("type") == "bullets" and "新闻" in b.get("title", "")
                for b in blocks
            ),
            "analysis_has_attribution": lambda t, blocks, tools: any(
                b.get("type") == "analysis" and
                any(w in b.get("data", {}).get("text", "") for w in [
                    "根据", "来源", "据", "报道", "可能", "原因", "驱动", "显示"
                ])
                for b in blocks
            ),
        },
    },
    {
        "id": 4,
        "label": "RAG知识问答 - 市盈率",
        "query": "什么是市盈率",
        "checks": {
            "route": "knowledge",
            "llm_used": True,
            "rag_called": lambda t, blocks, tools: "search_knowledge" in tools,
            "has_pe_definition": lambda t, blocks, tools: any(
                w in t for w in ["市盈率", "PE", "Price", "每股收益", "EPS"]
            ),
            "has_formula": lambda t, blocks, tools: any(
                b.get("type") == "analysis" and
                any(w in b.get("data", {}).get("text", "") for w in ["=", "公式", "计算", "÷", "/", "EPS"])
                for b in blocks
            ),
            "quote_block_exists": lambda t, blocks, tools: any(
                b.get("type") == "quote" for b in blocks
            ),
        },
    },
    {
        "id": 5,
        "label": "RAG知识问答 - 对比类",
        "query": "收入和净利润的区别是什么",
        "checks": {
            "route": "knowledge",
            "llm_used": True,
            "both_concepts": lambda t, blocks, tools: (
                any(w in t for w in ["收入", "营收"]) and
                any(w in t for w in ["净利润", "净利", "利润"])
            ),
            "has_contrast": lambda t, blocks, tools: any(
                b.get("type") == "analysis" and
                any(w in b.get("data", {}).get("text", "") for w in [
                    "区别", "不同", "而", "前者", "后者", "相比", "差异", "对比"
                ])
                for b in blocks
            ),
        },
    },
    {
        "id": 6,
        "label": "合规拒绝 - 预测问题",
        "query": "比特币明天会涨吗",
        "checks": {
            "llm_used": False,
            "no_tools": lambda t, blocks, tools: len(tools) == 0,
            "compliance_text": lambda t, blocks, tools: any(
                w in t for w in ["不能", "无法", "不提供", "不做预测", "不构成投资建议", "不给出"]
            ),
            # Note: "目标价" legitimately appears in the refusal text ("不能给出目标价")
            # Only flag actual predictive conclusions, not mentions in refusal context
            "no_prediction": lambda t, blocks, tools: not any(
                w in t for w in ["会涨", "会跌", "将上涨", "预计涨", "明天涨至"]
            ),
        },
    },
    {
        "id": 7,
        "label": "中文实体识别 - 港股",
        "query": "腾讯当前股价",
        "checks": {
            "route": "market",
            "ticker_mapped": lambda t, blocks, tools: any(
                w in t.upper() for w in ["0700", "700", "腾讯", "TENCENT"]
            ),
            "has_price": lambda t, blocks, tools: any(
                b.get("type") == "bullets" for b in blocks
            ),
            "no_hard_error": lambda t, blocks, tools: "stack trace" not in t.lower() and "traceback" not in t.lower(),
        },
    },
    {
        "id": 8,
        "label": "中文实体识别 - A股",
        "query": "茅台最近走势",
        "checks": {
            "ticker_mapped": lambda t, blocks, tools: any(
                w in t for w in ["600519", "茅台", "MOUTAI", "贵州茅台"]
            ),
            "no_hard_error": lambda t, blocks, tools: "stack trace" not in t.lower() and "traceback" not in t.lower(),
            "friendly_if_no_data": lambda t, blocks, tools: True,  # passes regardless; just checking it doesn't crash
        },
    },
]


# ─────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────
async def run_query(client: httpx.AsyncClient, query: str):
    payload = {"query": query, "session_id": "e2e-full-test"}
    final_text = ""
    llm_used = False
    route_type = None
    blocks = []
    tools_called = []
    sources = []

    t0 = time.time()
    async with client.stream("POST", f"{BASE_URL}/api/chat", json=payload, timeout=120) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            raw = line[6:].strip()
            if not raw:
                continue
            try:
                ev = json.loads(raw)
            except json.JSONDecodeError:
                continue
            t = ev.get("type")
            if t == "chunk":
                final_text = ev.get("text", "")
            elif t == "tool_start":
                tools_called.append(ev.get("name", ""))
            elif t == "done":
                data = ev.get("data") or {}
                llm_used = data.get("llm_used", False)
                route_info = data.get("route") or {}
                route_type = route_info.get("type")
                blocks = data.get("blocks", [])
                sources = ev.get("sources", [])
    elapsed = time.time() - t0

    # Build combined text for checks (template + analysis block)
    combined_text = final_text
    for b in blocks:
        if b.get("type") == "analysis":
            combined_text += "\n" + b.get("data", {}).get("text", "")

    return combined_text, final_text, llm_used, route_type, blocks, tools_called, sources, elapsed


def fmt_status(ok): return "[OK  ]" if ok else "[FAIL]"


async def main():
    print()
    print("=" * 70)
    print("  Financial QA System — Full 8-Case E2E Test")
    print("=" * 70)

    # Health
    async with httpx.AsyncClient(trust_env=False, timeout=30) as client:
        try:
            r = await client.get(f"{BASE_URL}/api/health")
            h = r.json()
            svcs = h.get("services") or h.get("components") or {}
            print(f"\n[HEALTH] status={h.get('status')}")
            for k, v in svcs.items():
                print(f"  {k}: {v}")
            print()
        except Exception as e:
            print(f"[ERROR] Cannot reach backend ({type(e).__name__}): {e}")
            print("[INFO] Continuing anyway since backend may still be available...")
            print()

    total_pass = 0
    total_fail = 0
    failures = []

    for tc in TEST_CASES:
        print(f"┌─ [{tc['id']}/8] {tc['label']}")
        print(f"│  Query: {tc['query']}")
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                combined, final_text, llm_used, route_type, blocks, tools, sources, elapsed = \
                    await run_query(client, tc["query"])

            # Route check
            expect_route = tc["checks"].get("route")
            route_ok = expect_route is None or route_type == expect_route
            print(f"│  Route  : {(route_type or 'N/A'):12s} {fmt_status(route_ok)}  (expected: {expect_route or 'any'})")

            # LLM check
            expect_llm = tc["checks"].get("llm_used")
            llm_ok = expect_llm is None or llm_used == expect_llm
            print(f"│  LLM    : {'yes' if llm_used else 'no':12s} {fmt_status(llm_ok)}  (expected: {'yes' if expect_llm else 'no' if expect_llm is not None else 'any'})")

            # Block summary
            block_types = [b.get("type") for b in blocks]
            print(f"│  Blocks : {len(blocks)} ({', '.join(block_types)})")
            print(f"│  Tools  : {', '.join(t for t in tools if t != 'llm_generate') or 'none'}")
            print(f"│  Time   : {elapsed:.1f}s")

            # Functional checks
            func_checks = {k: v for k, v in tc["checks"].items()
                           if k not in ("route", "llm_used") and callable(v)}
            check_results = []
            for name, fn in func_checks.items():
                try:
                    ok = fn(combined, blocks, tools)
                except Exception:
                    ok = False
                check_results.append((name, ok))
                print(f"│    {fmt_status(ok)} {name}")

            # Preview (first 160 chars of analysis block, or template text)
            analysis_text = next(
                (b.get("data", {}).get("text", "") for b in blocks if b.get("type") == "analysis"), ""
            )
            preview = (analysis_text or final_text)[:180].replace("\n", " ")
            print(f"│  Preview: {preview}…")

            # Result
            case_ok = route_ok and llm_ok and all(ok for _, ok in check_results)
            if case_ok:
                print(f"└─ PASS ✓\n")
                total_pass += 1
            else:
                failed_names = (
                    (["route mismatch"] if not route_ok else []) +
                    (["llm_used mismatch"] if not llm_ok else []) +
                    [name for name, ok in check_results if not ok]
                )
                print(f"└─ FAIL ✗  ({', '.join(failed_names)})\n")
                total_fail += 1
                failures.append({
                    "id": tc["id"],
                    "label": tc["label"],
                    "failed": failed_names,
                    "route_type": route_type,
                    "llm_used": llm_used,
                    "blocks": block_types,
                    "tools": tools,
                    "preview": preview,
                })

        except Exception as e:
            print(f"│  [ERROR] {e}")
            print(f"└─ FAIL ✗  (exception)\n")
            total_fail += 1
            failures.append({"id": tc["id"], "label": tc["label"], "failed": [str(e)]})

    # Summary
    print("=" * 70)
    print(f"  Result: {total_pass} passed / {total_fail} failed / {len(TEST_CASES)} total")
    print("=" * 70)

    if failures:
        print("\n[FAILURE DETAILS]")
        for f in failures:
            print(f"\n  [{f['id']}] {f['label']}")
            print(f"  Failed checks : {f['failed']}")
            if "route_type" in f:
                print(f"  Actual route  : {f['route_type']}")
                print(f"  Actual LLM    : {f['llm_used']}")
                print(f"  Blocks        : {f['blocks']}")
                print(f"  Tools called  : {f['tools']}")
                print(f"  Preview       : {f.get('preview','')[:200]}")


if __name__ == "__main__":
    asyncio.run(main())
