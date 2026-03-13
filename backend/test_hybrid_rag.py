"""
验证脚本：测试混合检索 pipeline 升级后的 3 个 query
直接实例化 AgentCore，调用 _search_knowledge_async()，
无需后端服务运行。
"""
import asyncio
import sys
import os

# 确保在 backend 目录下运行
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

# 加载 .env
from dotenv import load_dotenv
load_dotenv()

from app.agent.core import AgentCore

QUERIES = [
    ("Q1 估值指标", "什么是市盈率"),
    ("Q2 财务对比", "收入和净利润的区别是什么"),
    ("Q3 超出知识库", "什么是可转债的强赎条款"),
]

SEP = "=" * 68


async def run():
    print(f"\n{SEP}")
    print("初始化 AgentCore（含 RAG pipeline）…")
    agent = AgentCore()
    print(f"_vector_rag_available = {agent._vector_rag_available}")
    print(SEP)

    for label, query in QUERIES:
        print(f"\n{label}: {query!r}")
        print("-" * 60)
        data = await agent._search_knowledge_async(query)

        method = data.get("method_used", "?")
        docs = data.get("documents", [])
        no_match = data.get("no_relevant_content", False)
        supp_web = data.get("supplemental_web")

        print(f"  检索方法   : {method}")
        print(f"  返回 chunk : {len(docs)}")
        print(f"  no_relevant: {no_match}")

        if docs:
            top = docs[0]
            print(f"  TOP score  : {top.get('score', '?'):.4f}")
            print(f"  TOP source : {top.get('source', '?')}")
            print(f"  TOP preview: {top.get('content', '')[:120].strip()!r}")

        if supp_web:
            items = supp_web.get("results", [])
            print(f"  补充 Web   : {len(items)} 条结果")
            if items:
                print(f"  Web[0]     : {items[0].get('title', '')[:80]}")

        print()

    print(SEP)
    print("测试完成")


if __name__ == "__main__":
    asyncio.run(run())
