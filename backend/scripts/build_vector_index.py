#!/usr/bin/env python3
"""
将 data/knowledge、raw_data、dealed_data (md/json/html) 写入向量库。

统一分块策略：段落级语义分块 (chunk_size=600, overlap=120)，同时写入 ChromaDB 和 chunks.json，
供 BM25 与 Token-Match 使用。

用法:
  python -m scripts.build_vector_index           # 追加写入
  python -m scripts.build_vector_index --clear   # 清空后重建
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.rag.chunking import chunk_document
from app.rag.pipeline import RAGPipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="清空现有向量库后重建")
    args = parser.parse_args()

    pipeline = RAGPipeline()
    raw_dir = Path(settings.CHROMA_PERSIST_DIR)
    persist_dir = raw_dir if raw_dir.is_absolute() else Path(__file__).resolve().parents[2] / "vectorstore" / "chroma"

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
    all_chunks_for_json = []
    idx = 0

    for doc in docs:
        content = doc["content"]
        source = doc["source"]
        doc_key = doc.get("key", source)
        doc_chunks = chunk_document(content, source, doc_key)
        for ch in doc_chunks:
            all_texts.append(ch["content"])
            all_metadatas.append({
                "source": source,
                "chunk_index": ch["chunk_index"],
                "chunk_id": ch["chunk_id"],
            })
            all_ids.append(ch["chunk_id"])
            all_chunks_for_json.append({
                "content": ch["content"],
                "source": source,
                "chunk_id": ch["chunk_id"],
            })
            idx += 1

    print(f"共 {len(docs)} 个文档，{len(all_texts)} 个块，准备写入向量库...")
    batch_size = 100
    for i in range(0, len(all_texts), batch_size):
        batch_texts = all_texts[i : i + batch_size]
        batch_metas = all_metadatas[i : i + batch_size]
        batch_ids = all_ids[i : i + batch_size]
        pipeline.add_documents(batch_texts, batch_metas, batch_ids)
        print(f"  已写入 {min(i + batch_size, len(all_texts))}/{len(all_texts)} 块")

    chunks_path = persist_dir / "chunks.json"
    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    with open(chunks_path, "w", encoding="utf-8") as f:
        json.dump(all_chunks_for_json, f, ensure_ascii=False, indent=0)
    print(f"已保存 chunks.json ({len(all_chunks_for_json)} 条)")
    print(f"完成。ChromaDB 当前文档数: {pipeline.collection.count()}")


if __name__ == "__main__":
    main()
