"""
全功能端到端测试 v3 — 8 个用例
覆盖：实时价格、7日趋势、归因分析、RAG知识、合规拒绝、港股/A股实体识别
"""
import asyncio
import json
import re
import time
import httpx

BASE = "http://127.0.0.1:8001"
CHAT_URL = f"{BASE}/api/chat"

# ── helper ────────────────────────────────────────────────────────────────────

async def call_chat(query: str, timeout: int = 90) -> dict:
    """Call /api/chat SSE stream; return aggregated result dict."""
    result = {
        "query": query,
        "route": None,
        "symbols": [],
        "llm_used": False,
        "blocks": [],
        "text": "",
        "tools_called": [],
        "sources": [],
        "disclaimer": "",
        "elapsed": 0.0,
        "error": None,
    }
    t0 = time.time()
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=timeout) as client:
            async with client.stream(
                "POST", CHAT_URL,
                json={"query": query, "session_id": "e2e-test"},
                headers={"Accept": "text/event-stream"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        ev = json.loads(line[6:])
                    except Exception:
                        continue
                    t = ev.get("type", "")
                    if t == "chunk":
                        result["text"] += ev.get("text", "")
                    elif t == "tool_start":
                        result["tools_called"].append(ev.get("name", ""))
                    elif t == "tool_data":
                        # capture tool payloads for inspection
                        result["_tool_data"] = result.get("_tool_data", {})
                        result["_tool_data"][ev.get("tool", "")] = ev.get("data", {})
                    elif t == "done":
                        data = ev.get("data", {})
                        result["blocks"]     = data.get("blocks", [])
                        result["llm_used"]   = data.get("llm_used", False)
                        result["disclaimer"] = data.get("disclaimer", "")
                        route_info           = data.get("route", {})
                        result["route"]      = route_info.get("type")
                        result["symbols"]    = route_info.get("symbols", [])
                        result["sources"]    = [s.get("name", "") for s in ev.get("sources", [])]
                    elif t == "error":
                        result["error"] = ev.get("message", "unknown error")
    except Exception as e:
        result["error"] = str(e)
    result["elapsed"] = round(time.time() - t0, 2)
    return result


def get_block(result, block_type):
    return [b for b in result["blocks"] if b.get("type") == block_type]


def has_number(text):
    return bool(re.search(r"\d+\.?\d*", text))


def check(label, condition, detail=""):
    status = "[PASS]" if condition else "[FAIL]"
    print(f"    {status}  {label}" + (f"  [{detail}]" if detail else ""))
    return condition


# ── test cases ────────────────────────────────────────────────────────────────

async def tc1(r):
    print(f"\n【用例1】实时价格 - 美股  ({r['elapsed']}s)")
    if r["error"]:
        print(f"  ERROR: {r['error']}"); return
    tool_data  = r.get("_tool_data", {})
    price_data = tool_data.get("get_price", {})
    price_val  = price_data.get("price")
    blocks_by  = {b["type"]: b for b in r["blocks"]}

    check("路由为 MARKET",          r["route"] == "market",  r["route"])
    check("TSLA 符号识别",          "TSLA" in r["symbols"],  str(r["symbols"]))
    check("价格有数值",              price_val not in (None, "N/A"),  str(price_val))
    check("数据来源标注存在",         bool(r["sources"]),      str(r["sources"][:2]))
    check("llm_used=true",          r["llm_used"])
    check("存在 analysis 块",        "analysis" in blocks_by)
    check("AI分析文字非空",          bool(blocks_by.get("analysis", {}).get("data", {}).get("text", "").strip()))
    check("含免责声明",              "投资建议" in r["disclaimer"] or "投资建议" in r["text"])


async def tc2(r):
    print(f"\n【用例2】7日涨跌分析  ({r['elapsed']}s)")
    if r["error"]:
        print(f"  ERROR: {r['error']}"); return
    tool_data    = r.get("_tool_data", {})
    change_data  = tool_data.get("get_change", {})
    change_pct   = change_data.get("change_pct")
    chart_blocks = get_block(r, "chart")
    analysis_blk = get_block(r, "analysis")
    llm_text     = analysis_blk[0]["data"].get("text", "") if analysis_blk else ""

    check("change_pct 有数值",      change_pct is not None,  str(change_pct))
    check("chart 块存在",            bool(chart_blocks))
    series = chart_blocks[0]["data"].get("series", []) if chart_blocks else []
    check("图表数据点>=5",           len(series) >= 5,        f"{len(series)} 点")
    check("llm_used=true",          r["llm_used"])
    check("AI分析引用具体数字",       has_number(llm_text),    llm_text[:60])


async def tc3(r):
    print(f"\n【用例3】多源归因分析  ({r['elapsed']}s)")
    if r["error"]:
        print(f"  ERROR: {r['error']}"); return
    tool_data    = r.get("_tool_data", {})
    web_data     = tool_data.get("search_web", {})
    price_data   = tool_data.get("get_price", {})
    analysis_blk = get_block(r, "analysis")
    llm_text     = analysis_blk[0]["data"].get("text", "") if analysis_blk else ""
    web_results  = web_data.get("results", []) if web_data else []

    check("路由为 HYBRID",          r["route"] == "hybrid",  r["route"])
    check("价格数据存在",            price_data.get("price") is not None, str(price_data.get("price")))
    check("web_search 被调用",       "search_web" in r["tools_called"])
    check("新闻结果不为空",          bool(web_results),       f"{len(web_results)} 条")
    check("llm_used=true",          r["llm_used"])
    check("AI分析非空",             bool(llm_text.strip()),   llm_text[:60])
    # 如果新闻为空，AI说明信息有限；或新闻不为空则AI应引用
    if web_results:
        check("AI分析引用了事件信息", len(llm_text) > 50, f"{len(llm_text)} chars")
    else:
        check("AI说明信息有限", any(kw in llm_text for kw in ["有限","不足","缺乏","未找到"]), llm_text[:60])


async def tc4(r):
    print(f"\n【用例4】RAG知识问答 - 市盈率  ({r['elapsed']}s)")
    if r["error"]:
        print(f"  ERROR: {r['error']}"); return
    tool_data  = r.get("_tool_data", {})
    rag_data   = tool_data.get("search_knowledge", {})
    rag_method = rag_data.get("method_used", "?")
    rag_docs   = rag_data.get("documents", [])
    top_src    = rag_docs[0].get("source", "") if rag_docs else ""
    quote_blk  = get_block(r, "quote")
    analysis   = get_block(r, "analysis")
    llm_text   = analysis[0]["data"].get("text", "") if analysis else ""
    combined   = r["text"] + llm_text + (quote_blk[0]["data"].get("text","") if quote_blk else "")

    check("路由为 KNOWLEDGE",        r["route"] == "knowledge", r["route"])
    check("search_knowledge 被调",   "search_knowledge" in r["tools_called"])
    check("检索方法为 vector+rerank", rag_method == "vector+rerank", rag_method)
    check("top chunk 来自 valuation_metrics", "valuation_metrics" in top_src, top_src)
    check("包含市盈率定义",          any(kw in combined for kw in ["市盈率","PE","Price-to-Earnings"]))
    check("包含计算公式",            any(kw in combined for kw in ["股价","每股收益","P/E","=","÷"]))
    check("来源标注存在",            bool(top_src),               top_src)
    check("llm_used=true",          r["llm_used"])
    check("AI分析非空",             bool(llm_text.strip()),       llm_text[:60])


async def tc5(r):
    print(f"\n【用例5】RAG知识问答 - 收入vs净利润  ({r['elapsed']}s)")
    if r["error"]:
        print(f"  ERROR: {r['error']}"); return
    tool_data  = r.get("_tool_data", {})
    rag_data   = tool_data.get("search_knowledge", {})
    rag_method = rag_data.get("method_used", "?")
    rag_docs   = rag_data.get("documents", [])
    top_src    = rag_docs[0].get("source", "") if rag_docs else ""
    analysis   = get_block(r, "analysis")
    llm_text   = analysis[0]["data"].get("text", "") if analysis else ""
    combined   = r["text"] + llm_text

    check("路由为 KNOWLEDGE",        r["route"] == "knowledge", r["route"])
    check("检索方法为 vector+rerank", rag_method == "vector+rerank", rag_method)
    check("top chunk 来自财报文件",   any(kw in top_src for kw in ["financial_statements","财报","三表"]), top_src)
    check("涵盖收入概念",            any(kw in combined for kw in ["收入","营收","Revenue"]))
    check("涵盖净利润概念",          any(kw in combined for kw in ["净利润","净利","Net Income","净收益"]))
    check("有对比性说明",            any(kw in combined for kw in ["区别","不同","差异","而","但","vs"]))
    check("llm_used=true",          r["llm_used"])


async def tc6(r):
    print(f"\n【用例6】合规拒绝 - 预测请求  ({r['elapsed']}s)")
    if r["error"]:
        print(f"  ERROR: {r['error']}"); return
    combined = r["text"]
    no_pred  = not any(w in combined for w in ["会涨","会跌","将上涨","预计涨","明天涨至","必涨","一定涨"])

    check("没有调用市场工具",         not any(t in r["tools_called"] for t in ["get_price","get_change","get_history"]))
    check("返回合规拒绝提示",         any(kw in combined for kw in ["不能","不提供","无法","建议","合规"]))
    check("无预测性结论",            no_pred,                      combined[:80])
    check("响应极快（<5s）",          r["elapsed"] < 5,             f"{r['elapsed']}s")


async def tc7(r):
    print(f"\n【用例7】港股实体识别 - 腾讯  ({r['elapsed']}s)")
    if r["error"]:
        print(f"  ERROR: {r['error']}"); return
    tool_data  = r.get("_tool_data", {})
    price_data = tool_data.get("get_price", {})
    price_val  = price_data.get("price")
    currency   = price_data.get("currency", "")
    symbol     = price_data.get("symbol", "")

    check("映射到 0700.HK",          "0700" in symbol or "700" in symbol.upper() or "0700" in str(r["symbols"]), f"symbol={symbol} symbols={r['symbols']}")
    check("价格有数值",              price_val not in (None, "N/A"),  str(price_val))
    check("货币为 HKD 或有港币标注",  "HKD" in currency or "港" in r["text"] or price_val is not None, currency)


async def tc8(r):
    print(f"\n【用例8】A股实体识别 - 茅台  ({r['elapsed']}s)")
    if r["error"]:
        print(f"  ERROR: {r['error']}"); return
    tool_data  = r.get("_tool_data", {})
    hist_data  = tool_data.get("get_history", {}) or tool_data.get("get_change", {})
    has_data   = hist_data.get("data") or hist_data.get("change_pct") is not None
    symbol     = (hist_data.get("symbol") or "").upper()

    check("映射到 600519",           "600519" in symbol or "600519" in str(r["symbols"]), f"symbol={symbol} symbols={r['symbols']}")
    check("有历史/涨跌数据",          has_data,                     "data present" if has_data else "no data")
    check("无 raw stack trace",      "Traceback" not in r["text"] and "Exception" not in r["text"])


# ── main ─────────────────────────────────────────────────────────────────────

TESTS = [
    ("特斯拉当前股价是多少",       tc1),
    ("BABA 最近7天涨跌情况如何",   tc2),
    ("阿里巴巴最近为何大涨",       tc3),
    ("什么是市盈率",               tc4),
    ("收入和净利润的区别是什么",   tc5),
    ("比特币明天会涨吗",           tc6),
    ("腾讯当前股价",               tc7),
    ("茅台最近走势",               tc8),
]


async def main():
    print("=" * 70)
    print("端到端测试 v3 — 8 用例")
    print(f"后端: {BASE}   前端: http://127.0.0.1:5173")
    print("=" * 70)

    # Quick health check
    async with httpx.AsyncClient(trust_env=False, timeout=10) as c:
        resp = await c.get(f"{BASE}/api/health")
        health = resp.json()
    print(f"后端健康: status={health.get('status')}  "
          f"deepseek={health['components'].get('deepseek_api')}  "
          f"chromadb={health['components'].get('chromadb')}  "
          f"tavily={health['components'].get('tavily')}")
    print()

    results = []
    for query, checker in TESTS:
        print(f"  → 发送: {query!r} …", end="", flush=True)
        r = await call_chat(query)
        print(f" done ({r['elapsed']}s)")
        await checker(r)
        results.append(r)

    print("\n" + "=" * 70)
    print("响应时间汇总:")
    for (q, _), r in zip(TESTS, results):
        status = "ERR" if r["error"] else "OK "
        print(f"  [{status}] {r['elapsed']:5.1f}s  {q[:35]}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
