"""
验证 AI 分析质量提升效果的测试脚本
检查 3 个 query 的 analysis 块内容
"""
import asyncio, httpx, json, re, sys

BASE = "http://127.0.0.1:8001"
CHAT = f"{BASE}/api/chat"

async def query(q, timeout=90):
    result = {"text": "", "analysis": "", "blocks": [], "tools": [], "route": None, "error": None}
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=timeout) as c:
            async with c.stream("POST", CHAT,
                json={"query": q, "session_id": "quality-test"},
                headers={"Accept": "text/event-stream"}) as r:
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    ev = json.loads(line[6:])
                    t = ev.get("type")
                    if t == "chunk":
                        result["text"] += ev.get("text", "")
                    elif t == "tool_start":
                        result["tools"].append(ev.get("name"))
                    elif t == "done":
                        d = ev.get("data", {})
                        result["blocks"] = d.get("blocks", [])
                        result["route"] = d.get("route", {}).get("type")
                        for b in d.get("blocks", []):
                            if b.get("type") == "analysis":
                                result["analysis"] = b["data"].get("text", "")
    except Exception as e:
        result["error"] = str(e)
    return result

SEP = "=" * 72

def check(label, cond, detail=""):
    s = "[PASS]" if cond else "[FAIL]"
    print(f"  {s}  {label}" + (f"  → {detail}" if detail else ""))
    return cond

async def main():
    print(f"\n{SEP}\nAI 分析质量验证 — 3 个测试 query\n{SEP}")

    # ── Query 1 ─────────────────────────────────────────────────────────────
    q1 = "阿里巴巴当前股价是多少"
    print(f"\n[Q1] {q1!r}")
    r1 = await query(q1)
    print(f"  route={r1['route']}  tools={r1['tools']}")
    analysis = r1["analysis"]
    print(f"  分析长度: {len(analysis)} 字")
    print(f"  分析内容:\n  {analysis[:400]}")
    print()
    check("无报错", r1["error"] is None, r1.get("error"))
    check("已调用 get_price", "get_price" in r1["tools"])
    check("已补充 get_change（7日趋势）", "get_change" in r1["tools"])
    check("analysis 块存在", bool(analysis))
    check("分析≥100字", len(analysis) >= 100, f"{len(analysis)}字")
    check("包含价格数字", bool(re.search(r"\d+\.?\d*", analysis)))
    check("不含'已结合知识库'等系统日志词", "已结合知识库" not in analysis and "已补充" not in analysis)
    check("主体文字不含'已结合'等", "已结合知识库" not in r1["text"] and "已补充外部新闻背景" not in r1["text"] and "已补充 SEC" not in r1["text"])

    # ── Query 2 ─────────────────────────────────────────────────────────────
    q2 = "BABA 最近7天涨跌情况如何"
    print(f"\n{SEP}\n[Q2] {q2!r}")
    r2 = await query(q2)
    print(f"  route={r2['route']}  tools={r2['tools']}")
    analysis2 = r2["analysis"]
    print(f"  分析长度: {len(analysis2)} 字")
    print(f"  分析内容:\n  {analysis2[:500]}")
    print()
    check("analysis 块存在", bool(analysis2))
    check("分析≥150字", len(analysis2) >= 150, f"{len(analysis2)}字")
    check("包含涨跌幅数字", bool(re.search(r"[+\-]?\d+\.?\d*%", analysis2)), analysis2[:80])
    check("包含趋势判断词", any(w in analysis2 for w in ["上涨","下跌","震荡","偏多","偏空","走弱","走强","区间","趋势"]))
    check("不含'已结合知识库'等系统词", "已结合知识库" not in analysis2 and "已补充外部" not in analysis2)
    # Check template text has no log fragments
    check("主体文字无系统状态描述", all(w not in r2["text"] for w in ["已结合知识库", "已补充外部新闻背景", "已补充 SEC"]))

    # ── Query 3 ─────────────────────────────────────────────────────────────
    q3 = "阿里巴巴最近为何大涨"
    print(f"\n{SEP}\n[Q3] {q3!r}")
    r3 = await query(q3, timeout=120)
    print(f"  route={r3['route']}  tools={r3['tools']}")
    analysis3 = r3["analysis"]
    print(f"  分析长度: {len(analysis3)} 字")
    print(f"  分析内容:\n  {analysis3[:600]}")
    print()
    check("路由为 hybrid", r3["route"] == "hybrid", r3["route"])
    check("调用了 search_web", "search_web" in r3["tools"])
    check("analysis 块存在", bool(analysis3))
    check("分析≥200字", len(analysis3) >= 200, f"{len(analysis3)}字")
    check("引用了具体事件/新闻", any(w in analysis3 for w in ["报道","发布","宣布","消息","公告","协议","政策","指导","监管","财报","业绩","季报","合作"]))
    check("归因与价格建立关联", any(w in analysis3 for w in ["推动","带动","传导","驱动","促使","导致","引发","拉升","提振","解读","预期","情绪"]))
    check("不含'已结合知识库'等系统词", "已结合知识库" not in analysis3 and "已补充外部" not in analysis3)

    print(f"\n{SEP}")
    print("测试完成")

if __name__ == "__main__":
    asyncio.run(main())
