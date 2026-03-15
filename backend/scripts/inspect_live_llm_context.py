import asyncio
import json
import os
import sys

import requests

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.agent.core import AgentCore
from app.models import ToolResult


QUERY = "什么是市盈率"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    asyncio.run(run())


async def run() -> None:
    session = requests.Session()
    session.trust_env = False
    resp = session.post(
        "http://127.0.0.1:8001/api/chat",
        json={"query": QUERY, "session_id": "inspect-live-llm-context"},
        stream=True,
        timeout=180,
    )

    tool_results = []
    analysis_text = ""
    block_types = []
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        event = json.loads(line[6:])
        if event.get("type") == "tool_data":
            tool_results.append(
                ToolResult(
                    tool=event["tool"],
                    data=event["data"],
                    latency_ms=0,
                    status="success",
                    data_source=event["data"].get("source", event["tool"]),
                    cache_hit=False,
                    error_message=None,
                )
            )
        if event.get("type") == "done":
            blocks = event.get("data", {}).get("blocks", [])
            block_types = [block.get("type") for block in blocks]
            for block in blocks:
                if block.get("type") == "analysis":
                    analysis_text = (block.get("data") or {}).get("text", "")
            break

    agent = AgentCore()
    route = await agent.query_router.classify_async(QUERY)
    api_data, rag_context, news_context, api_completeness, rag_relevance = agent._build_llm_context(tool_results)

    print("=== Live LLM Context Inspection ===")
    print(f"query: {QUERY}")
    print(f"tool_results: {[result.tool for result in tool_results]}")
    print(f"done_blocks: {block_types}")
    print(f"rag_context 是否非空: {'YES' if bool(rag_context.strip()) else 'NO'}")
    print(
        f"rag_context 是否相关: {'YES' if any(k in rag_context for k in ('市盈率', 'PE', '每股收益', '估值')) else 'NO'}"
    )
    yaml_cleaned = not (
        rag_context.strip().startswith("---") or "---\ncategory:" in rag_context
    )
    print(f"rag_context 是否清除了YAML: {'YES' if yaml_cleaned else 'NO'}")
    print(f"route_type: {route.query_type.value}")
    print(f"api_completeness: {api_completeness}")
    print(f"rag_relevance: {rag_relevance}")
    print(f"api_data 预览: {api_data[:200].replace(chr(10), ' | ')}")
    print(f"rag_context 预览: {rag_context[:400].replace(chr(10), ' | ')}")
    print(f"news_context 预览: {news_context[:200].replace(chr(10), ' | ')}")
    print(
        "LLM 输出是否引用检索内容: "
        + (
            "YES"
            if analysis_text
            and any(keyword in analysis_text for keyword in ("市盈率", "PE", "每股收益", "估值"))
            else "NO"
        )
    )
    print(f"analysis 预览: {analysis_text[:400].replace(chr(10), ' | ')}")


if __name__ == "__main__":
    main()
