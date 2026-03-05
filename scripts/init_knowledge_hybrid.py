"""
更新知识库初始化脚本 - 支持混合检索
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.hybrid_pipeline import HybridRAGPipeline


def init_knowledge_base():
    """初始化知识库并构建BM25索引"""
    print("=" * 60)
    print("初始化金融知识库（混合检索版本）")
    print("=" * 60)
    print()

    # 初始化混合检索管道
    pipeline = HybridRAGPipeline()

    # 知识库目录
    knowledge_dir = Path(__file__).parent.parent / "data" / "knowledge"

    if not knowledge_dir.exists():
        print(f"[错误] 知识库目录不存在: {knowledge_dir}")
        return

    # 读取所有Markdown文件
    md_files = list(knowledge_dir.glob("*.md"))

    if not md_files:
        print(f"[错误] 未找到知识文档")
        return

    print(f"[1/3] 找到 {len(md_files)} 个知识文档")
    print()

    # 处理文档
    all_documents = []
    all_metadatas = []
    all_ids = []
    bm25_documents = []
    bm25_ids = []

    for md_file in md_files:
        print(f"处理: {md_file.name}")

        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 按二级标题分块
        chunks = content.split("\n## ")

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue

            # 第一个块需要特殊处理（包含一级标题）
            if i == 0:
                lines = chunk.split("\n")
                if lines[0].startswith("# "):
                    title = lines[0].replace("# ", "").strip()
                    chunk_content = "\n".join(lines[1:]).strip()
                else:
                    title = md_file.stem
                    chunk_content = chunk.strip()
            else:
                lines = chunk.split("\n", 1)
                title = lines[0].strip()
                chunk_content = lines[1].strip() if len(lines) > 1 else ""

            if not chunk_content:
                continue

            # 生成唯一ID
            chunk_id = f"{md_file.stem}_{i}"

            # 添加到列表
            all_documents.append(chunk_content)
            all_metadatas.append({
                "source": md_file.name,
                "title": title,
                "chunk_id": chunk_id
            })
            all_ids.append(chunk_id)

            # BM25索引数据
            bm25_documents.append(chunk_content)
            bm25_ids.append(chunk_id)

    print()
    print(f"[2/3] 共分割出 {len(all_documents)} 个文档块")
    print()

    # 添加到ChromaDB（向量索引）
    print("[向量化] 正在生成向量嵌入...")
    pipeline.add_documents(all_documents, all_metadatas, all_ids)
    print(f"[成功] 向量索引已构建")
    print()

    # 构建BM25索引
    print("[BM25] 正在构建BM25索引...")
    pipeline.build_bm25_index(bm25_documents, bm25_ids)
    print(f"[成功] BM25索引已构建")
    print()

    # 验证
    total_count = pipeline.get_collection_count()
    print("=" * 60)
    print(f"[完成] 知识库初始化完成")
    print("=" * 60)
    print(f"文档总数: {total_count}")
    print(f"检索模式: 混合检索（向量 + BM25 + 重排序）")
    print()

    # 测试检索
    print("[测试] 运行测试查询...")
    print()

    test_queries = [
        "什么是市盈率？",
        "如何计算净利润率？",
        "MACD指标的含义"
    ]

    import asyncio

    async def test_search():
        for query in test_queries:
            print(f"查询: {query}")
            result = await pipeline.search(query, use_hybrid=True)

            if result.documents:
                print(f"  找到 {len(result.documents)} 个相关文档")
                print(f"  最佳匹配: {result.documents[0].source}")
                print(f"  相似度: {result.documents[0].score:.3f}")
            else:
                print(f"  未找到相关文档")
            print()

    asyncio.run(test_search())

    print("知识库已就绪！")


if __name__ == "__main__":
    init_knowledge_base()
