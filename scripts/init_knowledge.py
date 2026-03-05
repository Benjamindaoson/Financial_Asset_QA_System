"""
Initialize financial knowledge base
Load markdown documents from data/knowledge/ and import into ChromaDB
"""
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

# Set working directory to backend for .env loading
os.chdir(backend_path)

from app.rag.pipeline import RAGPipeline
import hashlib


def load_markdown_files(knowledge_dir: Path):
    """Load all markdown files from knowledge directory"""
    documents = []
    metadatas = []
    ids = []

    md_files = list(knowledge_dir.glob("*.md"))
    print(f"Found {len(md_files)} markdown files")

    for md_file in md_files:
        print(f"Loading: {md_file.name}")
        content = md_file.read_text(encoding='utf-8')

        # Split by headers to create chunks
        chunks = split_by_headers(content, md_file.name)

        for idx, chunk in enumerate(chunks):
            # Generate unique ID
            chunk_id = hashlib.md5(f"{md_file.stem}_{idx}".encode()).hexdigest()

            documents.append(chunk)
            metadatas.append({
                'source': md_file.stem,
                'filename': md_file.name,
                'chunk_id': idx
            })
            ids.append(chunk_id)

    return documents, metadatas, ids


def split_by_headers(content: str, filename: str):
    """Split markdown content by headers (## level)"""
    chunks = []
    lines = content.split('\n')
    current_chunk = []

    for line in lines:
        # Check if line is a ## header
        if line.startswith('## '):
            # Save previous chunk if exists
            if current_chunk:
                chunk_text = '\n'.join(current_chunk).strip()
                if chunk_text:
                    chunks.append(chunk_text)
            # Start new chunk with header
            current_chunk = [line]
        else:
            current_chunk.append(line)

    # Add last chunk
    if current_chunk:
        chunk_text = '\n'.join(current_chunk).strip()
        if chunk_text:
            chunks.append(chunk_text)

    # If no chunks created (no ## headers), use whole content
    if not chunks:
        chunks = [content.strip()]

    print(f"  - Split into {len(chunks)} chunks")
    return chunks


def main():
    """Main function to initialize knowledge base"""
    print("=" * 60)
    print("Financial Knowledge Base Initialization")
    print("=" * 60)

    # Get knowledge directory
    project_root = Path(__file__).parent.parent
    knowledge_dir = project_root / "data" / "knowledge"

    if not knowledge_dir.exists():
        print(f"Error: Knowledge directory not found: {knowledge_dir}")
        return

    print(f"\nKnowledge directory: {knowledge_dir}")

    # Load documents
    print("\n[1/3] Loading markdown documents...")
    documents, metadatas, ids = load_markdown_files(knowledge_dir)
    print(f"Total chunks to import: {len(documents)}")

    # Initialize RAG pipeline
    print("\n[2/3] Initializing RAG pipeline...")
    rag = RAGPipeline()

    # Check existing documents
    existing_count = rag.get_collection_count()
    print(f"Existing documents in ChromaDB: {existing_count}")

    # Import documents
    print("\n[3/3] Importing documents to ChromaDB...")
    rag.add_documents(documents, metadatas, ids)

    # Verify import
    final_count = rag.get_collection_count()
    print(f"\n{'=' * 60}")
    print("Import completed successfully!")
    print(f"{'=' * 60}")
    print(f"Documents before: {existing_count}")
    print(f"Documents after: {final_count}")
    print(f"New documents added: {final_count - existing_count}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
