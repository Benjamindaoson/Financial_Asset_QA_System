"""
BM25 Sparse Index for hybrid retrieval.
implementation note: Efficient sparse retrieval with jieba for Chinese.
"""
import logging
from typing import List, Dict, Any, Optional
import os

logger = logging.getLogger(__name__)


class BM25Store:
    """
    BM25-based sparse retrieval index.

    Features:
    - BM25Okapi scoring
    - Chinese text support with jieba
    - Efficient indexing and search
    - Hybrid retrieval ready
    """

    def __init__(self):
        self.documents: List[Dict] = []
        self.tokenized_corpus: List[List[str]] = []
        self.bm25 = None
        self._initialized = False

    def add_documents(self, documents: List[Dict]):
        """
        Add documents to BM25 index.

        Args:
            documents: List of document dicts with 'text' field
        """
        if not documents:
            return

        logger.info(f"Adding {len(documents)} documents to BM25 index")

        for doc in documents:
            text = doc.get("text", "").strip()
            if text:
                self.documents.append(doc)
                tokens = self._tokenize(text)
                self.tokenized_corpus.append(tokens)

        # Rebuild index
        self._build_index()
        return len(documents)

    def search(self, query: str, top_k: int = 10, filters: Optional[Dict[str, Any]] = None) -> List[tuple]:
        """
        Search BM25 index.

        Args:
            query: Search query
            top_k: Number of top results
            filters: Optional metadata filters

        Returns:
            List of (document, score) tuples
        """
        if not self._initialized or not self.bm25:
            logger.warning("BM25 index not initialized")
            return []

        tokens = self._tokenize(query)
        if not tokens:
            return []

        # Get BM25 scores
        scores = self.bm25.get_scores(tokens)

        # Get top-k results
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # Only include positive scores
                doc = self.documents[idx].copy()
                doc["bm25_score"] = float(scores[idx])
                results.append((doc, float(scores[idx])))

        logger.debug(f"BM25 search returned {len(results)} results for query: {query[:50]}...")
        return results

    def _build_index(self):
        """Build BM25 index from tokenized corpus."""
        if not self.tokenized_corpus:
            return

        try:
            from rank_bm25 import BM25Okapi
            self.bm25 = BM25Okapi(self.tokenized_corpus)
            self._initialized = True
            logger.info(f"Built BM25 index with {len(self.documents)} documents")
        except ImportError:
            logger.error("rank-bm25 not installed. Install with: pip install rank-bm25")
            self._initialized = False

    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text with Chinese support.

        Uses jieba for Chinese, falls back to simple splitting for English.
        """
        if not text:
            return []

        # Detect if text contains Chinese characters
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in text)

        if has_chinese:
            # Use jieba for Chinese text
            try:
                import jieba
                tokens = list(jieba.cut(text))
                # Filter out very short tokens and punctuation
                tokens = [token for token in tokens if len(token.strip()) > 1 and token.strip()]
                return tokens
            except ImportError:
                logger.warning("jieba not installed, falling back to simple tokenization")
                # Fall back to character-level for Chinese
                return [char for char in text if char.strip() and '\u4e00' <= char <= '\u9fff']

        else:
            # Simple tokenization for English and other languages
            import re
            # Split on whitespace and punctuation
            tokens = re.findall(r'\b\w+\b', text.lower())
            return tokens

    def clear(self):
        """Clear all documents from index."""
        self.documents.clear()
        self.tokenized_corpus.clear()
        self.bm25 = None
        self._initialized = False
        logger.info("Cleared BM25 index")

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "document_count": len(self.documents),
            "initialized": self._initialized,
            "avg_document_length": (
                sum(len(tokens) for tokens in self.tokenized_corpus) / len(self.tokenized_corpus)
                if self.tokenized_corpus else 0
            ),
            "total_terms": len(set(token for tokens in self.tokenized_corpus for token in tokens))
        }

    def delete_documents(self, doc_ids: List[str]) -> int:
        """Delete documents by ID."""
        deleted = 0
        new_docs = []
        new_corpus = []
        for doc, tokens in zip(self.documents, self.tokenized_corpus):
            if doc.get("id") not in doc_ids:
                new_docs.append(doc)
                new_corpus.append(tokens)
            else:
                deleted += 1
        self.documents = new_docs
        self.tokenized_corpus = new_corpus
        if deleted > 0:
            self._build_index()
        return deleted

    def update_document(self, doc_id: str, new_text: str, new_metadata: Dict[str, Any]) -> bool:
        """Update a document."""
        for i, doc in enumerate(self.documents):
            if doc.get("id") == doc_id:
                doc["text"] = new_text
                doc["metadata"] = new_metadata
                self.tokenized_corpus[i] = self._tokenize(new_text)
                self._build_index()
                return True
        return False

    def optimize_index(self):
        """Optimize the BM25 index."""
        self._build_index()
        logger.info("BM25 index optimized")

    def health_check(self) -> Dict[str, Any]:
        """Health check for BM25 store."""
        return {
            "healthy": self._initialized,
            "document_count": len(self.documents),
            "type": "bm25"
        }

    def save(self, path: str):
        """Save index to disk."""
        import json

        data = {
            "documents": self.documents,
            "tokenized_corpus": self.tokenized_corpus
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved BM25 index to {path}")

    def load(self, path: str):
        """Load index from disk."""
        import json

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.documents = data["documents"]
        self.tokenized_corpus = data["tokenized_corpus"]
        self._build_index()

        logger.info(f"Loaded BM25 index with {len(self.documents)} documents")


# Global BM25 store instance
_bm25_store = None

def get_bm25_store() -> BM25Store:
    """Get global BM25 store instance."""
    global _bm25_store
    if _bm25_store is None:
        _bm25_store = BM25Store()
    return _bm25_store
