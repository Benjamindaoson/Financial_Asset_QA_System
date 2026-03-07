"""
Vectorize and index financial knowledge data into ChromaDB using RAGPipeline.
This ensures data is indexed using the same configuration as the application.
"""
import json
import sys
import asyncio
from pathlib import Path
from typing import List, Dict, Any

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.rag.hybrid_pipeline import HybridRAGPipeline


def load_knowledge_files(data_dir: Path) -> List[Dict[str, Any]]:
    """Load all JSON knowledge files from directory."""
    all_entries = []

    json_files = list(data_dir.glob("*.json"))
    print(f"Found {len(json_files)} JSON files")

    for json_file in json_files:
        print(f"Loading {json_file.name}...")
        with open(json_file, "r", encoding="utf-8") as f:
            entries = json.load(f)
            all_entries.extend(entries)

    return all_entries


async def vectorize_and_index(entries: List[Dict[str, Any]]):
    """Vectorize entries and index into ChromaDB using RAGPipeline."""
    print(f"\nInitializing RAG Pipeline...")

    # Initialize pipeline (uses settings.CHROMA_PERSIST_DIR)
    pipeline = HybridRAGPipeline()

    # Check existing count
    existing_count = pipeline.get_collection_count()
    print(f"Existing documents in collection: {existing_count}")

    # Prepare data for indexing
    documents = []
    metadatas = []
    ids = []
    corpus_texts = []  # For BM25 index

    for idx, entry in enumerate(entries):
        # Create document text
        doc_text = f"{entry['title']}\n\n{entry['content']}"
        documents.append(doc_text)
        corpus_texts.append(doc_text)

        # Create metadata
        metadata = {
            "title": entry["title"],
            "category": entry.get("category", "general"),
            "source": entry.get("source", "unknown"),
            "keywords": ",".join(entry.get("keywords", []))
        }
        metadatas.append(metadata)

        # Create unique ID
        doc_id = f"doc_{idx}_{entry['title'][:20].replace(' ', '_')}"
        ids.append(doc_id)

    print(f"\nIndexing {len(documents)} documents...")

    # Add documents to ChromaDB in batches to avoid exceeding max batch size
    batch_size = 5000  # Safe batch size under ChromaDB's limit
    total_added = 0

    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i:i+batch_size]
        batch_metas = metadatas[i:i+batch_size]
        batch_ids = ids[i:i+batch_size]

        print(f"  Adding batch {i//batch_size + 1}: {len(batch_docs)} documents...")
        pipeline.add_documents(batch_docs, batch_metas, batch_ids)
        total_added += len(batch_docs)
        print(f"  Progress: {total_added}/{len(documents)} documents added")

    print(f"OK: Added {total_added} documents to ChromaDB")

    # Build BM25 index for hybrid search
    print(f"\nBuilding BM25 index...")
    pipeline.build_bm25_index(corpus_texts, ids)
    print(f"OK: BM25 index built with {len(corpus_texts)} documents")

    # Verify indexing
    final_count = pipeline.get_collection_count()
    print(f"\nTotal documents in collection: {final_count}")

    return pipeline


async def test_search(pipeline: HybridRAGPipeline, query: str):
    """Test search functionality."""
    print(f"\n" + "=" * 60)
    print(f"Testing search with query: {query}")
    print("=" * 60)

    # Test vector search only
    print("\n[Vector Search Only]")
    result = await pipeline.search(query, use_hybrid=False)
    print(f"Found {len(result.documents)} documents")
    for idx, doc in enumerate(result.documents[:3]):
        print(f"\n{idx + 1}. Score: {doc.score:.4f}")
        print(f"   Content: {doc.content[:100]}...")

    # Test hybrid search
    print("\n[Hybrid Search (Vector + BM25 + RRF)]")
    result = await pipeline.search(query, use_hybrid=True)
    print(f"Found {len(result.documents)} documents")
    for idx, doc in enumerate(result.documents[:3]):
        print(f"\n{idx + 1}. Score: {doc.score:.4f}")
        print(f"   Content: {doc.content[:100]}...")


async def main():
    """Main execution function."""
    print("=" * 60)
    print("Financial Knowledge Vectorization & Indexing")
    print("Using RAGPipeline for consistent configuration")
    print("=" * 60)

    # Load knowledge data
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data" / "knowledge_base" / "raw"

    if not data_dir.exists():
        print(f"ERROR: Data directory not found: {data_dir}")
        return

    print(f"\nLoading data from: {data_dir}")
    entries = load_knowledge_files(data_dir)

    if not entries:
        print("ERROR: No knowledge entries found")
        return

    print(f"Loaded {len(entries)} total entries")

    # Vectorize and index
    pipeline = await vectorize_and_index(entries)

    # Test searches
    await test_search(pipeline, "什么是市盈率？")
    await test_search(pipeline, "如何进行价值投资？")
    await test_search(pipeline, "什么是技术分析？")

    print("\n" + "=" * 60)
    print("OK: Vectorization and indexing completed successfully")
    print("=" * 60)
    print("\nThe knowledge base is now ready for RAG queries!")
    print(f"- Vector search: Enabled")
    print(f"- BM25 search: Enabled")
    print(f"- Hybrid search: Enabled")
    print(f"- Total documents: {pipeline.get_collection_count()}")


if __name__ == "__main__":
    asyncio.run(main())
