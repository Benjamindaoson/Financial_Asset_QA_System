#!/usr/bin/env python3
"""Test full TrustRAG system initialization with P0 components."""
import os
os.environ["TRUSTRAG_ENV"] = "dev"  # Use dev mode for fallbacks

from trust_rag.system import TrustRAG

print("Initializing TrustRAG with P0 components...")
try:
    rag = TrustRAG(artifact_dir="artifacts", auto_load_index=False)
    print("✅ TrustRAG initialized")
    print(f"   - retrieval_adapter: {rag.retrieval_adapter is not None}")
    print(f"   - embedding: {rag.retrieval_adapter.embedding_engine is not None if rag.retrieval_adapter else False}")
    print(f"   - bm25: {rag.retrieval_adapter.bm25_store is not None if rag.retrieval_adapter else False}")
    print(f"   - reranker: {rag.retrieval_adapter.reranker is not None if rag.retrieval_adapter else False}")
except Exception as e:
    print(f"❌ TrustRAG initialization failed: {e}")
    import traceback
    traceback.print_exc()
