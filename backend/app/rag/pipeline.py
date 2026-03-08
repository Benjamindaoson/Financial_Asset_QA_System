"""
RAG Pipeline - Two-stage retrieval with bge-base-zh and bge-reranker
"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List
from pathlib import Path
import re
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

        self.embedding_model = None
        self.reranker = None
        self._local_documents = self._load_local_documents()

    def _ensure_models(self):
        """Load heavy embedding models only when vector retrieval is needed."""
        if self.embedding_model is None:
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        if self.reranker is None:
            from FlagEmbedding import FlagReranker
            self.reranker = FlagReranker(settings.RERANKER_MODEL, use_fp16=True)

    def _load_local_documents(self) -> List[dict]:
        knowledge_dir = (Path(__file__).resolve().parents[3] / "data" / "knowledge")
        documents = []
        for file_path in sorted(knowledge_dir.glob("*.md")):
            try:
                content = file_path.read_text(encoding="utf-8")
            except Exception:
                continue
            documents.append(
                {
                    "source": file_path.name,
                    "content": content,
                    "tokens": self._tokenize_text(content),
                }
            )
        return documents

    @staticmethod
    def _tokenize_text(text: str) -> set[str]:
        lowered = text.lower()
        tokens = {
            token
            for token in re.split(r"[^0-9a-zA-Z\u4e00-\u9fff]+", lowered)
            if len(token) >= 2
        }
        for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", lowered):
            for size in range(2, min(5, len(chunk) + 1)):
                for index in range(0, len(chunk) - size + 1):
                    tokens.add(chunk[index:index + size])
        return tokens

    def _search_local_documents(self, query: str) -> KnowledgeResult:
        query_tokens = self._tokenize_text(query)
        if not query_tokens:
            return KnowledgeResult(documents=[], total_found=0)

        ranked = []
        for item in self._local_documents:
            overlap = len(query_tokens & item["tokens"])
            if overlap == 0:
                continue
            snippet = item["content"][:600].strip()
            ranked.append(
                Document(
                    content=snippet,
                    source=item["source"],
                    score=float(overlap),
                )
            )

        ranked.sort(key=lambda doc: doc.score, reverse=True)
        top_results = ranked[:settings.RAG_TOP_N]
        return KnowledgeResult(documents=top_results, total_found=len(ranked))

    def _embed_query(self, query: str) -> List[float]:
        """Generate query embedding"""
        self._ensure_models()
        embedding = self.embedding_model.encode(query, normalize_embeddings=True)
        return embedding.tolist()

    async def search(self, query: str) -> KnowledgeResult:
        """
        Two-stage search:
        1. Bi-Encoder: Vector search (Top-K=10)
        2. Cross-Encoder: Rerank (Top-N=3, score > threshold)
        """
        local_result = self._search_local_documents(query)
        if local_result.documents:
            return local_result

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
        scores = self.reranker.compute_score(pairs, normalize=True)

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
        self._ensure_models()
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
