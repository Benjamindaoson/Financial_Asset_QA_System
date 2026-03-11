#!/usr/bin/env python3
"""
重新索引知识库脚本
用于在添加新教材数据后重建向量数据库索引
"""

import sys
from pathlib import Path

# 添加backend目录到Python路径
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))

from app.rag.pipeline import RAGPipeline
from app.rag.hybrid_pipeline import HybridRAGPipeline


def main():
    """主函数"""
    print("=" * 60)
    print("知识库重新索引脚本")
    print("=" * 60)

    # 初始化RAG Pipeline
    print("\n[1/4] 初始化RAG Pipeline...")
    rag = RAGPipeline()

    # 显示当前知识库状态
    print(f"\n[2/4] 当前知识库状态:")
    print(f"  - 文档数量: {len(rag.source_documents)}")
    print(f"  - 知识块数量: {len(rag.knowledge_chunks)}")
    print(f"  - 向量数据库记录数: {rag.get_collection_count()}")

    # 列出所有文档
    print(f"\n  已加载的文档:")
    for i, doc in enumerate(rag.source_documents, 1):
        metadata = doc.get('metadata', {})
        category = metadata.get('category', '未分类')
        print(f"    {i}. {doc['source']} ({category})")

    # 重新索引
    print(f"\n[3/4] 开始重新索引...")
    print("  - 清空现有索引...")
    rag.collection.delete(where={})  # 清空集合

    print("  - 重建向量索引...")
    rag.index_local_knowledge(force=True)

    # 验证索引结果
    print(f"\n[4/4] 索引完成！")
    print(f"  - 新的向量数据库记录数: {rag.get_collection_count()}")

    # 测试检索
    print(f"\n[测试] 测试检索功能...")
    test_queries = [
        "什么是金融市场的资金融通功能？",
        "直接融资和间接融资有什么区别？",
        "LIBOR是什么？",
    ]

    hybrid_rag = HybridRAGPipeline()

    for query in test_queries:
        print(f"\n  查询: {query}")
        results = hybrid_rag.search(query, top_k=3)
        if results:
            print(f"    ✅ 检索成功，找到 {len(results)} 个结果")
            print(f"    最佳匹配: {results[0].source} (置信度: {results[0].confidence:.1f}%)")
        else:
            print(f"    ❌ 未找到结果")

    print("\n" + "=" * 60)
    print("重新索引完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
