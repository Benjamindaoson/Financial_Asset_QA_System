#!/usr/bin/env python3
"""Test BM25 retrieval functionality with realistic conditions."""
from trust_rag.engine.retrieval.bm25_store import BM25Store

store = BM25Store()
docs = [
    {'id': 'c1', 'text': 'Apple Q3 revenue was 100 billion dollars'},
    {'id': 'c2', 'text': 'Tesla net income increased 50 percent'},
    {'id': 'c3', 'text': 'Microsoft revenue grew by 15 percent'},
    {'id': 'c4', 'text': 'Google cloud revenue reached 10 billion'},
    {'id': 'c5', 'text': 'Amazon AWS revenue increased significantly'}
]
count = store.add_documents(docs)
print(f"Added {count} documents")
print(f"Initialized: {store._initialized}")

query = 'Apple revenue'
results = store.search(query, top_k=3)
print(f"BM25 Results: {len(results)} results")
for doc, score in results:
    print(f"  {doc['id']} score={score:.3f}")

# Verify Apple is #1
if results and results[0][0]['id'] == 'c1':
    print("✅ BM25 correctly ranked Apple document first")
else:
    print("❌ BM25 ranking failed")
