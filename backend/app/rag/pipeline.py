"""
RAG Pipeline - Two-stage retrieval with bge-base-zh and bge-reranker
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from FlagEmbedding import FlagReranker
from typing import List
from pathlib import Path
from app.config import settings
from app.models import KnowledgeResult, Document


class RAGPipeline:
    """Two-stage RAG: Bi-Encoder retrieval + Cross-Encoder reranking"""

    def __init__(self):
        # Initialize ChromaDB
        persist_dir = Path(settings.CHROMA_PERSIST_DIR)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self.chroma_client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(
                anonymized_telemetry=False
            )
        )

        # Get or create collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="financial_knowledge",
            metadata={"hnsw:space": "cosine"}
        )

        # Initialize embedding model (bge-base-zh)
        self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)

        # Initialize reranker (bge-reranker)
        self.reranker = FlagReranker(settings.RERANKER_MODEL, use_fp16=True)

    def _embed_query(self, query: str) -> List[float]:
        """Generate query embedding"""
        embedding = self.embedding_model.encode(query, normalize_embeddings=True)
        return embedding.tolist()

    async def search(self, query: str) -> KnowledgeResult:
        """
        Two-stage search:
        1. Bi-Encoder: Vector search (Top-K=10)
        2. Cross-Encoder: Rerank (Top-N=3, score > threshold)
        """
        # Stage 1: Vector search
        query_embedding = self._embed_query(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=settings.RAG_TOP_K
        )

        if not results['documents'] or not results['documents'][0]:
            return KnowledgeResult(documents=[], total_found=0)

        # Prepare candidates for reranking
        candidates = []
        for i, doc in enumerate(results['documents'][0]):
            candidates.append({
                'content': doc,
                'source': results['metadatas'][0][i].get('source', 'unknown'),
                'distance': results['distances'][0][i] if results['distances'] else 0
            })

        # Stage 2: Reranking
        pairs = [[query, cand['content']] for cand in candidates]
        scores = self.reranker.compute_score(pairs)

        # Convert to list if single score
        if not isinstance(scores, list):
            scores = [scores]

        # Combine scores with candidates
        ranked = []
        for i, score in enumerate(scores):
            if score >= settings.RAG_SCORE_THRESHOLD:
                ranked.append({
                    'content': candidates[i]['content'],
                    'source': candidates[i]['source'],
                    'score': float(score)
                })

        # Sort by score and take top N
        ranked.sort(key=lambda x: x['score'], reverse=True)
        top_results = ranked[:settings.RAG_TOP_N]

        # Convert to Document models
        documents = [
            Document(
                content=item['content'],
                source=item['source'],
                score=item['score']
            )
            for item in top_results
        ]

        return KnowledgeResult(
            documents=documents,
            total_found=len(results['documents'][0])
        )

    def add_documents(self, documents: List[str], metadatas: List[dict], ids: List[str]):
        """Add documents to the knowledge base"""
        embeddings = self.embedding_model.encode(
            documents,
            normalize_embeddings=True,
            show_progress_bar=True
        )

        self.collection.add(
            documents=documents,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
            ids=ids
        )

    def get_collection_count(self) -> int:
        """Get total document count"""
        return self.collection.count()
