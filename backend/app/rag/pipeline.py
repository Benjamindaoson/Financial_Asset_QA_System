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

    QUERY_EXPANSIONS = {
        "市盈率": {"pe", "price-to-earnings", "valuation", "估值"},
        "市净率": {"pb", "price-to-book", "book value", "估值"},
        "市销率": {"ps", "price-to-sales", "sales"},
        "波动率": {"volatility", "risk", "drawdown", "technical"},
        "最大回撤": {"drawdown", "risk", "technical"},
        "财务报表": {"balance sheet", "income statement", "cash flow", "financial statements"},
        "现金流": {"cash flow", "financial statements"},
        "技术分析": {"technical", "rsi", "macd", "support", "resistance"},
        "债券": {"bond", "fixed income", "market instruments"},
        "etf": {"fund", "market instruments"},
        "宏观": {"macro", "economics", "macro economics"},
    }

    def __init__(self):
        # Initialize ChromaDB（解析为绝对路径，确保 RAG 向量库稳定接入）
        raw_dir = Path(settings.CHROMA_PERSIST_DIR)
        if not raw_dir.is_absolute():
            # 项目根 = backend 的父目录
            project_root = Path(__file__).resolve().parents[3]
            # ../vectorstore/chroma -> 项目根/vectorstore/chroma
            persist_dir = project_root / "vectorstore" / "chroma"
        else:
            persist_dir = raw_dir
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
        """Load from data/knowledge, raw_data/knowledge, raw_data/finance_report, dealed_data (md/json/html)."""
        base = Path(__file__).resolve().parents[3] / "data"
        documents = []
        seen_sources: set[str] = set()

        def add_doc(content: str, source: str, key: str) -> None:
            if not content or len(content.strip()) < 20:
                return
            if key in seen_sources:
                return
            seen_sources.add(key)
            documents.append({
                "source": source,
                "content": content,
                "tokens": self._tokenize_text(content),
            })

        # 1. knowledge, raw_data: 仅 md
        for rel_dir in ("knowledge", "raw_data/knowledge", "raw_data/finance_report"):
            dir_path = base / rel_dir
            if not dir_path.exists():
                continue
            for file_path in sorted(dir_path.rglob("*.md")):
                key = f"{rel_dir}/{file_path.name}"
                content = None
                for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
                    try:
                        content = file_path.read_text(encoding=encoding)
                        break
                    except Exception:
                        continue
                if content:
                    add_doc(content, file_path.name, key)

        # 2. dealed_data: md, json, html
        dealed_dir = base / "dealed_data"
        if dealed_dir.exists():
            for file_path in sorted(dealed_dir.iterdir()):
                if not file_path.is_file():
                    continue
                suffix = file_path.suffix.lower()
                key = f"dealed_data/{file_path.name}"
                content = None

                if suffix == ".md":
                    for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
                        try:
                            content = file_path.read_text(encoding=encoding)
                            break
                        except Exception:
                            continue
                elif suffix == ".json":
                    content = self._extract_text_from_mineru_json(file_path)
                elif suffix == ".html":
                    content = self._extract_text_from_html(file_path)

                if content:
                    add_doc(content, file_path.name, key)

        return documents

    @staticmethod
    def _extract_text_from_mineru_json(file_path: Path) -> str:
        """Extract text from MinerU JSON (pdf_info[].para_blocks[].lines[].spans[].content)."""
        try:
            import json
            data = json.loads(file_path.read_text(encoding="utf-8"))
            parts = []
            for page in data.get("pdf_info", []):
                for block in page.get("para_blocks", []):
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            c = span.get("content", "").strip()
                            if c:
                                parts.append(c)
            return "\n".join(parts) if parts else ""
        except Exception:
            return ""

    @staticmethod
    def _extract_text_from_html(file_path: Path) -> str:
        """Extract text from HTML body."""
        try:
            import re
            raw = file_path.read_text(encoding="utf-8")
            # 移除 script/style
            raw = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", raw, flags=re.I)
            raw = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", raw, flags=re.I)
            # 提取 body 文本
            body = re.search(r"<body[^>]*>([\s\S]*?)</body>", raw, re.I)
            if body:
                body = body.group(1)
            else:
                body = raw
            text = re.sub(r"<[^>]+>", " ", body)
            text = re.sub(r"\s+", " ", text)
            return text.strip()

        except Exception:
            return ""

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
        expanded_terms = set()
        for keyword, synonyms in self.QUERY_EXPANSIONS.items():
            if keyword in query.lower() or keyword in query:
                expanded_terms.update(synonyms)
        for term in expanded_terms:
            query_tokens.update(self._tokenize_text(term))
        if not query_tokens:
            return KnowledgeResult(documents=[], total_found=0)

        ranked = []
        for item in self._local_documents:
            overlap = len(query_tokens & item["tokens"])
            if overlap == 0 and any(term in item["content"].lower() for term in expanded_terms):
                overlap = 1
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

    async def search_grounded(self, query: str, score_threshold: float = 0.3) -> KnowledgeResult:
        """Direct vector search + Cross-Encoder reranking without token-match shortcircuit.

        Unlike search(), this always queries ChromaDB and applies the reranker.
        Only documents with reranker score >= score_threshold are returned.
        Raises an exception if models cannot be loaded so callers can fall back gracefully.
        """
        self._ensure_models()  # raises if BGE/reranker unavailable

        if self.collection.count() == 0:
            return KnowledgeResult(documents=[], total_found=0)

        query_embedding = self._embed_query(query)
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=settings.RAG_TOP_K,
        )

        if not results["documents"] or not results["documents"][0]:
            return KnowledgeResult(documents=[], total_found=0)

        candidates = [
            {
                "content": doc,
                "source": results["metadatas"][0][i].get("source", "unknown"),
            }
            for i, doc in enumerate(results["documents"][0])
        ]

        pairs = [[query, cand["content"]] for cand in candidates]
        # Handle FlagReranker API differences across versions
        try:
            scores = self.reranker.compute_score(pairs, normalize=True)
        except TypeError:
            import math
            raw = self.reranker.compute_score(pairs)
            if not isinstance(raw, list):
                raw = [raw]
            # Apply sigmoid to map raw logits into [0, 1]
            scores = [1.0 / (1.0 + math.exp(-float(s))) for s in raw]

        if not isinstance(scores, list):
            scores = [scores]

        ranked = [
            Document(
                content=candidates[i]["content"],
                source=candidates[i]["source"],
                score=float(score),
            )
            for i, score in enumerate(scores)
            if float(score) >= score_threshold
        ]
        ranked.sort(key=lambda d: d.score, reverse=True)

        return KnowledgeResult(
            documents=ranked[: settings.RAG_TOP_N],
            total_found=len(results["documents"][0]),
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
