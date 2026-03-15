"""验证RAG链路是否真正接入 - 保存为 backend/scripts/verify_rag.py 并运行"""
import asyncio
import sys
import json
import os
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 禁用代理，确保直接访问本地服务
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
os.environ.pop('http_proxy', None)
os.environ.pop('https_proxy', None)
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main():
    # 1. 检查 ChromaDB 索引
    print("=== 检查 ChromaDB ===")
    try:
        from app.rag.pipeline import RAGPipeline
        pipeline = RAGPipeline()
        count = pipeline.collection.count() if hasattr(pipeline, 'collection') and pipeline.collection else 0
        print(f"ChromaDB 索引数量: {count}")
        if count == 0:
            print("❌ ChromaDB 为空，RAG向量检索不可用")
        else:
            print(f"✅ ChromaDB 有 {count} 条索引")
    except Exception as e:
        print(f"❌ ChromaDB 加载失败: {e}")

    # 2. 实际执行一次知识检索
    print("\n=== 测试知识检索 ===")
    try:
        from app.agent.core import AgentCore
        agent = AgentCore()

        # 找到实际的检索方法
        search_methods = [m for m in dir(agent) if 'search' in m.lower() or 'knowledge' in m.lower() or 'rag' in m.lower()]
        print(f"相关方法: {search_methods}")

        if hasattr(agent, '_search_knowledge_async'):
            result = await agent._search_knowledge_async("什么是市盈率")
        elif hasattr(agent, 'rag_pipeline'):
            result = agent.rag_pipeline.search("什么是市盈率")
        else:
            result = None
            print("⚠️ 未找到知识检索方法，跳过直接检索测试")

        if result:
            result_str = json.dumps(result, ensure_ascii=False, default=str) if isinstance(result, dict) else str(result)
            print(f"检索结果前500字: {result_str[:500]}")

            if any(kw in result_str for kw in ["市盈率", "PE", "每股收益", "valuation", "Price-to-Earnings"]):
                print("✅ RAG检索返回了与市盈率相关的内容")
            else:
                print("❌ RAG检索返回的内容与市盈率无关")
    except Exception as e:
        print(f"❌ 知识检索测试失败: {e}")
        import traceback
        traceback.print_exc()

    # 3. 测试完整的 AgentCore.run() 流程
    print("\n=== 测试完整问答流程（什么是市盈率）===")
    try:
        agent = AgentCore()
        rag_evidence = False
        llm_evidence = False
        all_text = ""

        async for event in agent.run("什么是市盈率"):
            event_str = json.dumps(event, ensure_ascii=False, default=str) if isinstance(event, dict) else str(event)
            all_text += event_str

            # 检测RAG证据
            if any(kw in event_str for kw in ["知识库", "valuation", "market_instruments", "基本面", "PE", "每股收益", "valuation_metrics"]):
                rag_evidence = True

            # 检测LLM分析
            if "analysis" in event_str:
                llm_evidence = True

        print(f"RAG 检索证据: {'✅ 找到' if rag_evidence else '❌ 未找到'}")
        print(f"LLM 分析证据: {'✅ 找到' if llm_evidence else '❌ 未找到'}")

        if rag_evidence and llm_evidence:
            print("\n✅✅ RAG + LLM 链路完整可用")
        elif llm_evidence and not rag_evidence:
            print("\n❌ LLM在工作但RAG没有接入 — AI回答可能是纯模型生成，不是基于知识库")
        elif not llm_evidence:
            print("\n❌ LLM没有生成分析 — 检查 ResponseGenerator 和 DEEPSEEK_API_KEY")

    except Exception as e:
        print(f"❌ 完整流程测试失败: {e}")
        import traceback
        traceback.print_exc()


asyncio.run(main())
