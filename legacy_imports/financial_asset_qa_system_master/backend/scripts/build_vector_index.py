#!/usr/bin/env python3
"""Build single-collection and multi-domain ChromaDB indexes from local knowledge files."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings
from app.rag.chunking import chunk_document
from app.rag.domain_classifier import (
    classify_document,
    get_domain_chunks_path,
    get_domain_documents_path,
)
from app.rag.domain_router import DOMAINS
from app.rag.pipeline import RAGPipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Clear multi-domain collections before rebuilding")
    parser.add_argument("--rebuild-single", action="store_true", help="Re-embed and rebuild financial_knowledge before splitting domains")
    args = parser.parse_args()

    pipeline = RAGPipeline()
    raw_dir = Path(settings.CHROMA_PERSIST_DIR)
    persist_dir = raw_dir if raw_dir.is_absolute() else Path(__file__).resolve().parents[2] / "vectorstore" / "chroma"
    persist_dir.mkdir(parents=True, exist_ok=True)

    if args.clear:
        for collection_name in [f"knowledge_{domain}" for domain in DOMAINS]:
            try:
                pipeline.chroma_client.delete_collection(collection_name)
            except Exception:
                pass
        print("Cleared multi-domain collections")

    if args.rebuild_single:
        try:
            pipeline.chroma_client.delete_collection("financial_knowledge")
        except Exception:
            pass
        pipeline.collection = pipeline.chroma_client.get_or_create_collection(
            name="financial_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
        print("Rebuilding financial_knowledge from source documents")

    docs = pipeline._load_local_documents()
    if not docs:
        print("No knowledge documents found under data/knowledge, data/raw_data, or data/dealed_data")
        return

    classified_docs = []
    domain_documents = {domain: [] for domain in DOMAINS}
    domain_counts = defaultdict(int)

    for doc in docs:
        classification = classify_document(
            doc["source"],
            doc["content"],
            doc.get("key"),
        )
        enriched = dict(doc)
        enriched["domain"] = classification.domain
        enriched["domain_confidence"] = classification.confidence
        enriched["domain_scores"] = classification.scores
        classified_docs.append(enriched)
        domain_documents[classification.domain].append(
            {
                "source": enriched["source"],
                "key": enriched.get("key"),
                "content": enriched["content"],
                "domain": classification.domain,
                "domain_confidence": classification.confidence,
            }
        )
        domain_counts[classification.domain] += 1

    all_texts = []
    all_metadatas = []
    all_ids = []
    all_chunks_for_json = []
    domain_chunks = {domain: [] for domain in DOMAINS}

    for doc in classified_docs:
        content = doc["content"]
        source = doc["source"]
        doc_key = doc.get("key", source)
        for chunk in chunk_document(content, source, doc_key):
            metadata = {
                "source": source,
                "chunk_index": chunk["chunk_index"],
                "chunk_id": chunk["chunk_id"],
                "domain": doc["domain"],
            }
            chunk_record = {
                "content": chunk["content"],
                "source": source,
                "chunk_id": chunk["chunk_id"],
                "chunk_index": chunk["chunk_index"],
                "domain": doc["domain"],
                "doc_key": doc_key,
            }
            all_texts.append(chunk["content"])
            all_metadatas.append(metadata)
            all_ids.append(chunk["chunk_id"])
            all_chunks_for_json.append(chunk_record)
            domain_chunks[doc["domain"]].append(chunk_record)

    print(f"Loaded {len(docs)} documents and {len(all_chunks_for_json)} chunks")
    for domain in DOMAINS:
        print(f"  {domain}: {domain_counts[domain]} docs / {len(domain_chunks[domain])} chunks")

    single_collection = pipeline.collection
    domain_collections = {
        domain: pipeline.chroma_client.get_or_create_collection(
            name=f"knowledge_{domain}",
            metadata={"hnsw:space": "cosine"},
        )
        for domain in DOMAINS
    }

    can_reuse_single = single_collection.count() > 0 and not args.rebuild_single
    if can_reuse_single:
        print("Reusing embeddings from financial_knowledge and splitting into domain collections")
        existing = single_collection.get(include=["documents", "embeddings", "metadatas"])
        by_domain = defaultdict(lambda: {"documents": [], "embeddings": [], "metadatas": [], "ids": []})
        source_domain = {
            document["source"]: document["domain"]
            for domain in DOMAINS
            for document in domain_documents[domain]
        }

        for doc_id, document, embedding, metadata in zip(
            existing["ids"],
            existing["documents"],
            existing["embeddings"],
            existing["metadatas"],
        ):
            source = (metadata or {}).get("source", "unknown")
            domain = source_domain.get(source)
            if domain is None:
                domain = classify_document(source, document, doc_id).domain
            enriched_metadata = dict(metadata or {})
            enriched_metadata["domain"] = domain
            bucket = by_domain[domain]
            bucket["documents"].append(document)
            bucket["embeddings"].append(embedding)
            bucket["metadatas"].append(enriched_metadata)
            bucket["ids"].append(doc_id)

        for domain, payload in by_domain.items():
            if not payload["ids"]:
                continue
            domain_collections[domain].add(**payload)
            print(f"  Split into knowledge_{domain}: {len(payload['ids'])} chunks")
    else:
        pipeline._ensure_models()
        batch_size = 100
        for start in range(0, len(all_texts), batch_size):
            batch_texts = all_texts[start : start + batch_size]
            batch_metas = all_metadatas[start : start + batch_size]
            batch_ids = all_ids[start : start + batch_size]
            embeddings = pipeline.embedding_model.encode(
                batch_texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            embedding_rows = embeddings.tolist()

            single_collection.add(
                documents=batch_texts,
                embeddings=embedding_rows,
                metadatas=batch_metas,
                ids=batch_ids,
            )

            domain_indexes = defaultdict(list)
            for offset, metadata in enumerate(batch_metas):
                domain_indexes[metadata["domain"]].append(offset)

            for domain, indexes in domain_indexes.items():
                domain_collections[domain].add(
                    documents=[batch_texts[index] for index in indexes],
                    embeddings=[embedding_rows[index] for index in indexes],
                    metadatas=[batch_metas[index] for index in indexes],
                    ids=[batch_ids[index] for index in indexes],
                )

            print(f"  Indexed {min(start + batch_size, len(all_texts))}/{len(all_texts)} chunks")

    with open(persist_dir / "chunks.json", "w", encoding="utf-8") as file:
        json.dump(all_chunks_for_json, file, ensure_ascii=False, indent=0)

    for domain in DOMAINS:
        with open(get_domain_chunks_path(persist_dir, domain), "w", encoding="utf-8") as file:
            json.dump(domain_chunks[domain], file, ensure_ascii=False, indent=0)
        with open(get_domain_documents_path(persist_dir, domain), "w", encoding="utf-8") as file:
            json.dump(domain_documents[domain], file, ensure_ascii=False, indent=0)

    with open(persist_dir / "domain_index_report.json", "w", encoding="utf-8") as file:
        json.dump(
            {
                "single_collection": "financial_knowledge",
                "single_collection_chunks": len(all_chunks_for_json),
                "domains": {
                    domain: {
                        "documents": domain_counts[domain],
                        "chunks": len(domain_chunks[domain]),
                        "collection": f"knowledge_{domain}",
                    }
                    for domain in DOMAINS
                },
            },
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(f"financial_knowledge: {single_collection.count()} chunks")
    for domain in DOMAINS:
        print(f"knowledge_{domain}: {domain_collections[domain].count()} chunks")


if __name__ == "__main__":
    main()
