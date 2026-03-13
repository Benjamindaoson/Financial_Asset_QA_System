"""Prompt quality test - verifies LLM output matches prompt constraints."""

import asyncio
import sys
import json

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import httpx

BASE_URL = "http://127.0.0.1:8001"

TEST_CASES = [
    {
        "id": 1,
        "label": "MARKET: 行情查询（简洁数据型）",
        "query": "特斯拉股价",
        "expect_route": "market",
        "expect_llm": True,
        "quality_checks": [
            ("包含价格数字", lambda t: any(c.isdigit() for c in t)),
            ("不含预测词", lambda t: not any(w in t for w in ["将会", "预计", "目标价", "会涨", "会跌"])),
            ("不含建议词", lambda t: not any(w in t for w in ["建议买", "推荐", "值得投资", "应该买"])),
            ("回答较简短(<300字)", lambda t: len(t) < 300),
        ],
    },
    {
        "id": 2,
        "label": "HYBRID: 归因分析（需引用新闻）",
        "query": "阿里巴巴为什么最近涨了",
        "expect_route": "hybrid",
        "expect_llm": True,
        "quality_checks": [
            ("包含价格/涨跌数字", lambda t: any(c.isdigit() for c in t)),
            ("不含预测词", lambda t: not any(w in t for w in ["将会", "预计", "目标价"])),
            ("不含建议词", lambda t: not any(w in t for w in ["建议买", "推荐", "值得投资"])),
            ("有归因分析语气词", lambda t: any(w in t for w in ["根据", "可能", "来看", "显示", "来源", "据", "由于", "受"])),
        ],
    },
    {
        "id": 3,
        "label": "KNOWLEDGE: 金融概念解释（扩展型）",
        "query": "什么是自由现金流",
        "expect_route": "knowledge",
        "expect_llm": True,
        "quality_checks": [
            ("包含定义说明", lambda t: any(w in t for w in ["是指", "是企业", "指", "定义", "FCF", "现金流"])),
            ("包含公式或计算", lambda t: any(w in t for w in ["公式", "=", "计算", "减去", "减", "CapEx", "经营"])),
            ("不含行情数据", lambda t: not any(w in t for w in ["当前价格", "涨跌幅", "USD", "最新价"])),
            ("不含预测词", lambda t: not any(w in t for w in ["将会", "预计", "目标价"])),
            ("回答有一定深度(>100字)", lambda t: len(t) > 100),
        ],
    },
    {
        "id": 4,
        "label": "COMPLIANCE: 预测性问题（应被拒绝）",
        "query": "比特币明天会涨吗",
        "expect_route": None,
        "expect_llm": False,
        "quality_checks": [
            ("包含拒绝预测的说明", lambda t: any(w in t for w in ["不能", "无法", "不提供", "不做", "不预测", "不建议"])),
            ("不含价格预测", lambda t: not any(w in t for w in ["会涨", "会跌", "将上涨", "预计"])),
        ],
    },
]


async def run_query(client: httpx.AsyncClient, query: str):
    """Run a single chat query and collect the full response."""
    payload = {"query": query, "session_id": "test-prompt-quality"}
    final_text = ""
    llm_used = False
    route_type = None
    blocks = []

    async with client.stream("POST", f"{BASE_URL}/api/chat", json=payload, timeout=90) as resp:
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
            elif t == "done":
                data = ev.get("data") or {}
                llm_used = data.get("llm_used", False)
                route_info = data.get("route") or {}
                route_type = route_info.get("type")
                blocks = data.get("blocks", [])

    # If LLM used, prefer the analysis block text for quality checks
    analysis_text = ""
    for b in blocks:
        if b.get("type") == "analysis":
            analysis_text = b.get("data", {}).get("text", "")
            break
    check_text = analysis_text if analysis_text else final_text
    return check_text, llm_used, route_type, final_text, blocks


async def main():
    print()
    print("=" * 65)
    print("  Prompt Quality Verification")
    print("=" * 65)

    # Health check
    async with httpx.AsyncClient(trust_env=False, timeout=10) as client:
        try:
            r = await client.get(f"{BASE_URL}/api/health")
            health = r.json()
            deepseek = health.get("services", {}).get("deepseek_api", "?")
            print(f"\n[HEALTH] deepseek_api: {deepseek}\n")
        except Exception as e:
            print(f"[ERROR] Health check failed: {e}")
            return

    passed = 0
    failed = 0

    for tc in TEST_CASES:
        print(f"[{tc['id']}] {tc['label']}")
        print(f"    Query   : {tc['query']}")
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                check_text, llm_used, route_type, final_text, blocks = await run_query(client, tc["query"])

            route_ok = tc["expect_route"] is None or route_type == tc["expect_route"]
            llm_ok = llm_used == tc["expect_llm"]
            print(f"    Route   : {route_type or 'N/A':12s} {'[OK]' if route_ok else '[FAIL]'}")
            print(f"    LLM     : {'yes' if llm_used else 'no':12s} {'[OK]' if llm_ok else '[FAIL]'}")

            # Run quality checks on the LLM analysis text (or final_text)
            source = "analysis block" if any(b.get("type") == "analysis" for b in blocks) else "template text"
            print(f"    Checking: {source} ({len(check_text)} chars)")

            qc_passed = True
            for name, check_fn in tc["quality_checks"]:
                ok = check_fn(check_text)
                status = "[OK]" if ok else "[FAIL]"
                if not ok:
                    qc_passed = False
                print(f"      {status} {name}")

            # Print LLM analysis preview
            preview = check_text[:200].replace("\n", " ")
            print(f"    Preview : {preview}...")

            if route_ok and llm_ok and qc_passed:
                print(f"    Result  : PASS\n")
                passed += 1
            else:
                print(f"    Result  : FAIL\n")
                failed += 1

        except Exception as e:
            print(f"    [ERROR] {e}\n")
            failed += 1

    print("=" * 65)
    print(f"  Quality checks: {passed} passed / {failed} failed / {len(TEST_CASES)} total")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
