import json
import os
import sys
from collections import Counter

import requests


BASE = os.environ.get("BASE_URL", "http://127.0.0.1:5173")
QUERIES = [
    "特斯拉当前股价是多少",
    "BABA 最近7天涨跌情况如何",
    "阿里巴巴最近为何1月15日大涨",
    "特斯拉近期走势如何",
    "什么是市盈率",
    "收入和净利润的区别是什么",
    "特斯拉最近季度财报摘要是什么",
]


def extract_text(block):
    data = block.get("data")
    if isinstance(data, dict) and isinstance(data.get("text"), str):
        return data["text"]
    if isinstance(block.get("text"), str):
        return block["text"]
    return str(data or "")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    session = requests.Session()
    session.trust_env = False

    for idx, query in enumerate(QUERIES, start=1):
        print(f"=== Query {idx}: {query} ===")
        resp = session.post(
            f"{BASE}/api/chat",
            json={"query": query, "session_id": f"q{idx}"},
            stream=True,
            timeout=180,
        )
        print(f"HTTP状态: {resp.status_code}")

        tool_counts = Counter()
        rag_docs = 0
        web_results = 0
        sec_results = 0
        block_types = []
        analysis_preview = ""
        key_metrics = None
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event.get("type") == "tool_data":
                tool = event.get("tool")
                tool_counts[tool] += 1
                data = event.get("data", {})
                if tool == "search_knowledge":
                    rag_docs = max(rag_docs, len(data.get("documents", [])))
                if tool == "search_web":
                    web_results = max(web_results, len(data.get("results", [])))
                if tool == "search_sec":
                    sec_results = max(sec_results, len(data.get("results", [])))
            if event.get("type") == "done":
                blocks = event.get("data", {}).get("blocks", [])
                block_types = [block.get("type") for block in blocks]
                for block in blocks:
                    if block.get("type") == "analysis" and not analysis_preview:
                        analysis_preview = extract_text(block)[:220].replace("\n", " ")
                    if block.get("type") == "key_metrics":
                        key_metrics = block.get("data")
                print(f"tools: {dict(tool_counts)}")
                print(f"block_types: {block_types}")
                print(f"rag_docs: {rag_docs}, web_results: {web_results}, sec_results: {sec_results}")
                print(f"key_metrics: {key_metrics}")
                print(f"analysis_preview: {analysis_preview}")
                break
        print()


if __name__ == "__main__":
    main()
