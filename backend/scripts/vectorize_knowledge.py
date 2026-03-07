"""
Vectorize and index financial knowledge data into ChromaDB.
"""
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

import chromadb
from chromadb.config import Settings


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


def vectorize_and_index(entries: List[Dict[str, Any]], collection_name: str = "financial_knowledge"):
    """Vectorize entries and index into ChromaDB."""
    print(f"\nInitializing ChromaDB...")

    # Setup ChromaDB client
    base_dir = Path(__file__).parent.parent
    vectorstore_path = base_dir / "vectorstore"
    vectorstore_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(vectorstore_path),
        settings=Settings(anonymized_telemetry=False)
    )

    # Get or create collection
    try:
        collection = client.get_collection(name=collection_name)
        print(f"Using existing collection: {collection_name}")
        existing_count = collection.count()
        print(f"Existing entries: {existing_count}")
    except:
        collection = client.create_collection(
            name=collection_name,
            metadata={"description": "Financial knowledge base for RAG"}
        )
        print(f"Created new collection: {collection_name}")

    # Prepare data for indexing
    documents = []
    metadatas = []
    ids = []

    for idx, entry in enumerate(entries):
        # Create document text
        doc_text = f"{entry['title']}\n\n{entry['content']}"
        documents.append(doc_text)

        # Create metadata
        metadata = {
            "title": entry["title"],
            "category": entry.get("category", "general"),
            "source": entry.get("source", "unknown"),
            "keywords": ",".join(entry.get("keywords", []))
        }
        metadatas.append(metadata)

        # Create unique ID
        ids.append(f"doc_{idx}_{entry['title'][:20]}")

    print(f"\nIndexing {len(documents)} documents...")

    # Add documents to collection in batches
    batch_size = 100
    for i in range(0, len(documents), batch_size):
        batch_docs = documents[i:i+batch_size]
        batch_metas = metadatas[i:i+batch_size]
        batch_ids = ids[i:i+batch_size]

        collection.add(
            documents=batch_docs,
            metadatas=batch_metas,
            ids=batch_ids
        )
        print(f"Indexed batch {i//batch_size + 1}: {len(batch_docs)} documents")

    # Verify indexing
    final_count = collection.count()
    print(f"\nTotal documents in collection: {final_count}")

    return collection


def test_search(collection, query: str = "什么是市盈率？"):
    """Test search functionality."""
    print(f"\n" + "=" * 60)
    print(f"Testing search with query: {query}")
    print("=" * 60)

    results = collection.query(
        query_texts=[query],
        n_results=3
    )

    print(f"\nTop 3 results:")
    for idx, (doc, metadata, distance) in enumerate(zip(
        results['documents'][0],
        results['metadatas'][0],
        results['distances'][0]
    )):
        print(f"\n{idx + 1}. {metadata['title']}")
        print(f"   Category: {metadata['category']}")
        print(f"   Distance: {distance:.4f}")
        print(f"   Content: {doc[:100]}...")


def main():
    """Main execution function."""
    print("=" * 60)
    print("Financial Knowledge Vectorization & Indexing")
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
    collection = vectorize_and_index(entries)

    # Test search
    test_search(collection, "什么是市盈率？")
    test_search(collection, "如何进行价值投资？")

    print("\n" + "=" * 60)
    print("OK: Vectorization and indexing completed successfully")
    print("=" * 60)
    print("\nThe knowledge base is now ready for RAG queries!")


if __name__ == "__main__":
    main()
