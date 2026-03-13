"""
End-to-end RAG system test
测试RAG系统的完整功能
"""
import asyncio
import sys
from pathlib import Path
import io

# Fix Windows encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent))

from app.rag.hybrid_pipeline import HybridRAGPipeline


async def test_knowledge_search():
    """测试知识库搜索"""
    print("=" * 60)
    print("Test 1: Knowledge Base Search")
    print("=" * 60)

    pipeline = HybridRAGPipeline()

    test_queries = [
        "什么是市盈率",
        "如何分析财务报表",
        "ETF是什么",
        "技术分析的主要指标有哪些",
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        try:
            result = await pipeline.search(query, use_hybrid=True)

            if result and result.documents:
                print(f"  [OK] 找到 {len(result.documents)} 个相关文档")
                doc = result.documents[0]
                print(f"  标题: {doc.title}")
                print(f"  来源: {doc.source}")
                print(f"  相关度: {doc.score:.4f}")
                print(f"  内容预览: {doc.content[:80]}...")
            else:
                print(f"  [WARN] 未找到相关文档")

        except Exception as e:
            print(f"  [ERROR] 搜索失败: {e}")
            return False

    return True


async def test_agent_integration():
    """测试AgentCore集成"""
    print("\n" + "=" * 60)
    print("Test 2: AgentCore Integration")
    print("=" * 60)

    from app.agent.core import AgentCore

    agent = AgentCore()

    test_query = "什么是市盈率"
    print(f"\n通过AgentCore查询: {test_query}")

    try:
        result = await agent._execute_tool("search_knowledge", {"query": test_query})

        if result.get("success"):
            print(f"  [OK] search_knowledge 工具正常")
            data = result.get("data", {})
            docs = data.get("documents", [])
            print(f"  返回文档数: {len(docs)}")

            if docs:
                print(f"  第一个文档:")
                print(f"    标题: {docs[0].get('title', 'N/A')}")
                print(f"    来源: {docs[0].get('source', 'N/A')}")
                print(f"    相关度: {docs[0].get('score', 0):.4f}")

            # Check confidence score
            confidence = data.get("confidence", 0)
            confidence_level = data.get("confidence_level", "unknown")
            print(f"  置信度: {confidence:.4f} ({confidence_level})")

            return True
        else:
            print(f"  [ERROR] search_knowledge 失败")
            return False

    except Exception as e:
        print(f"  [ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_hybrid_retrieval():
    """测试混合检索"""
    print("\n" + "=" * 60)
    print("Test 3: Hybrid Retrieval (Vector + BM25)")
    print("=" * 60)

    pipeline = HybridRAGPipeline()

    query = "市盈率"
    print(f"\n查询: {query}")

    try:
        # Test with hybrid=True
        result_hybrid = await pipeline.search(query, use_hybrid=True)
        print(f"  混合检索: 找到 {len(result_hybrid.documents) if result_hybrid else 0} 个文档")

        # Test with hybrid=False (vector only)
        result_vector = await pipeline.search(query, use_hybrid=False)
        print(f"  向量检索: 找到 {len(result_vector.documents) if result_vector else 0} 个文档")

        # Check if BM25 is working
        if hasattr(pipeline, 'bm25_index') and pipeline.bm25_index:
            print(f"  [OK] BM25索引已加载")
        else:
            print(f"  [WARN] BM25索引未加载")

        return True

    except Exception as e:
        print(f"  [ERROR] 测试失败: {e}")
        return False


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("RAG System End-to-End Test")
    print("=" * 60 + "\n")

    results = []

    # Test 1: Knowledge search
    result1 = await test_knowledge_search()
    results.append(("知识库搜索", result1))

    # Test 2: Agent integration
    result2 = await test_agent_integration()
    results.append(("AgentCore集成", result2))

    # Test 3: Hybrid retrieval
    result3 = await test_hybrid_retrieval()
    results.append(("混合检索", result3))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, passed in results:
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {name}")

    all_passed = all(r[1] for r in results)

    print("\n" + "=" * 60)
    if all_passed:
        print("[SUCCESS] All tests passed!")
        print("RAG system is working correctly.")
        print("\nNext step: Test in frontend with queries like:")
        print("  - 什么是市盈率")
        print("  - 如何分析财务报表")
        print("  - ETF的优势是什么")
    else:
        print("[FAILURE] Some tests failed.")
        print("Please check the errors above.")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
