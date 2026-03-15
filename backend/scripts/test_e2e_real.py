import json
import os
import sys
from typing import Any

import requests


BASE = os.environ.get("BASE_URL", "http://127.0.0.1:8001")


def iter_sse(resp: requests.Response):
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        try:
            yield json.loads(line[6:])
        except json.JSONDecodeError:
            continue


def block_text(block: dict[str, Any]) -> str:
    if isinstance(block.get("text"), str):
        return block["text"]
    data = block.get("data")
    if isinstance(data, dict) and isinstance(data.get("text"), str):
        return data["text"]
    return str(data or "")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session = requests.Session()
    session.trust_env = False

    print("=== 测试1：特斯拉当前股价 ===")
    resp = session.post(
        f"{BASE}/api/chat",
        json={"query": "特斯拉当前股价是多少", "session_id": "test1"},
        stream=True,
        timeout=180,
    )
    print(f"HTTP状态: {resp.status_code}")
    events = list(iter_sse(resp))
    print(f"总事件数: {len(events)}")

    tsla_price_found = False
    test1_analysis_found = False
    for event in events:
        if event.get("type") == "tool_data":
            payload = json.dumps(event, ensure_ascii=False)
            if "TSLA" in payload or "Tesla" in payload or "price" in payload.lower():
                tsla_price_found = True
            print(f"事件类型: {event.get('type')}, tool={event.get('tool')}")
        if event.get("type") == "done" and event.get("data", {}).get("blocks"):
            for block in event["data"]["blocks"]:
                content = block_text(block)
                print(f"Block类型: {block.get('type')}, 内容前80字: {content[:80]}")
                if block.get("type") == "analysis":
                    test1_analysis_found = True

    print(f"TSLA价格数据存在: {'YES' if tsla_price_found else 'NO'}")
    print(f"analysis block存在: {'YES' if test1_analysis_found else 'NO'}")

    print("\n=== 测试2：什么是市盈率 ===")
    resp = session.post(
        f"{BASE}/api/chat",
        json={"query": "什么是市盈率", "session_id": "test2"},
        stream=True,
        timeout=180,
    )
    print(f"HTTP状态: {resp.status_code}")
    events = list(iter_sse(resp))
    print(f"总事件数: {len(events)}")

    rag_found = False
    llm_found = False
    rag_reference_found = False
    for event in events:
        event_str = json.dumps(event, ensure_ascii=False)
        if (
            "知识库" in event_str
            or "knowledge" in event_str.lower()
            or "valuation" in event_str.lower()
            or "市盈率" in event_str
            or "PE" in event_str
        ):
            rag_found = True
        if event.get("type") == "tool_data" and event.get("tool") == "search_knowledge":
            docs = event.get("data", {}).get("documents", [])
            print(
                f"RAG事件: method={event.get('data', {}).get('method_used')}, "
                f"docs={len(docs)}"
            )
            for doc in docs[:3]:
                preview = doc.get("content", "").replace("\n", " ")[:120]
                print(f"  来源: {doc.get('source')}, 预览: {preview}")
        if event.get("type") == "done":
            blocks = event.get("data", {}).get("blocks", [])
            for block in blocks:
                text = block_text(block)
                print(f"Block类型: {block.get('type')}, 内容前120字: {text[:120]}")
                if block.get("type") == "analysis":
                    llm_found = True
                    if any(keyword in text for keyword in ("市盈率", "PE", "股价", "每股收益", "估值")):
                        rag_reference_found = True

    print(f"RAG检索证据: {'YES' if rag_found else 'NO'}")
    print(f"LLM分析存在: {'YES' if llm_found else 'NO'}")
    print(f"AI分析引用知识点: {'YES' if rag_reference_found else 'NO'}")


if __name__ == "__main__":
    main()
