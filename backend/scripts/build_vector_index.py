#!/usr/bin/env python3
"""
将 data/knowledge、raw_data、dealed_data (md/json/html) 写入向量库。

用法:
  python -m scripts.build_vector_index           # 追加写入
  python -m scripts.build_vector_index --clear   # 清空后重建
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.pipeline import RAGPipeline


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """简单按字符分块"""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap if end < len(text) else len(text)
    return chunks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="清空现有向量库后重建")
    args = parser.parse_args()

    pipeline = RAGPipeline()
    if args.clear:
        try:
            pipeline.chroma_client.delete_collection("financial_knowledge")
            pipeline.collection = pipeline.chroma_client.get_or_create_collection(
                name="financial_knowledge",
                metadata={"hnsw:space": "cosine"},
            )
            print("已清空现有向量库")
        except Exception as e:
            print(f"清空失败: {e}")

    docs = pipeline._load_local_documents()

    if not docs:
        print("未找到文档，请检查 data/knowledge、data/raw_data、data/dealed_data")
        return

    all_texts = []
    all_metadatas = []
    all_ids = []
    idx = 0

    for doc in docs:
        content = doc["content"]
        source = doc["source"]
        chunks = chunk_text(content)
        for i, chunk in enumerate(chunks):
            all_texts.append(chunk)
            all_metadatas.append({"source": source, "chunk_index": i})
            all_ids.append(f"chunk_{idx}")
            idx += 1

    print(f"共 {len(docs)} 个文档，{len(all_texts)} 个块，准备写入向量库...")
    # 分批写入（ChromaDB 单次 add 可能有限制）
    batch_size = 100
    for i in range(0, len(all_texts), batch_size):
        batch_texts = all_texts[i : i + batch_size]
        batch_metas = all_metadatas[i : i + batch_size]
        batch_ids = all_ids[i : i + batch_size]
        pipeline.add_documents(batch_texts, batch_metas, batch_ids)
        print(f"  已写入 {min(i + batch_size, len(all_texts))}/{len(all_texts)} 块")
    print(f"完成。ChromaDB 当前文档数: {pipeline.collection.count()}")


if __name__ == "__main__":
    main()
