"""RAG pipeline with chunked knowledge retrieval and optional vector search."""

from __future__ import annotations

from pathlib import Path
import hashlib
import math
import re
from typing import Any, Dict, List, Optional, Sequence

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.models import Document, KnowledgeResult

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - optional runtime dependency
    SentenceTransformer = None

try:
    from FlagEmbedding import FlagReranker
except Exception:  # pragma: no cover - optional runtime dependency
    FlagReranker = None


class RAGPipeline:
    """Chunked RAG pipeline with lexical retrieval and optional vector retrieval."""

    COLLECTION_NAME = "financial_knowledge"
    LOCAL_EMBED_DIM = 256

    QUERY_EXPANSIONS = {
        "市盈率": {"pe", "price-to-earnings", "valuation", "估值"},
        "市净率": {"pb", "price-to-book", "book value", "估值"},
        "市销率": {"ps", "price-to-sales", "sales", "估值"},
        "ROE": {"return on equity", "净资产收益率", "fundamental", "financial statements"},
        "PEG": {"price/earnings to growth", "growth", "估值"},
        "DCF": {"discounted cash flow", "自由现金流", "估值", "现金流折现"},
        "自由现金流": {"fcf", "cash flow", "dcf", "估值"},
        "分红": {"dividend", "payout", "shareholder return"},
        "回购": {"buyback", "repurchase", "shareholder return"},
        "波动率": {"volatility", "risk", "drawdown", "technical"},
        "最大回撤": {"drawdown", "risk", "technical"},
        "夏普比率": {"sharpe", "risk-adjusted return", "risk", "return"},
        "信息比率": {"information ratio", "active return", "tracking error"},
        "Delta": {"greeks", "options", "hedging"},
        "Gamma": {"greeks", "options", "convexity"},
        "Theta": {"greeks", "options", "time decay"},
        "Vega": {"greeks", "options", "implied volatility"},
        "财务报表": {"balance sheet", "income statement", "cash flow", "financial statements"},
        "资产负债表": {"balance sheet", "financial statements"},
        "利润表": {"income statement", "financial statements"},
        "现金流量表": {"cash flow", "financial statements"},
        "现金流": {"cash flow", "financial statements", "经营现金流"},
        "技术分析": {"technical", "rsi", "macd", "support", "resistance"},
        "债券": {"bond", "fixed income", "market instruments", "duration"},
        "久期": {"duration", "bond", "fixed income"},
        "ETF": {"fund", "market instruments", "exchange traded fund"},
        "跟踪误差": {"tracking error", "etf", "index fund"},
        "信用利差": {"credit spread", "bond", "default risk"},
        "行业轮动": {"sector rotation", "business cycle", "allocation"},
        "宏观": {"macro", "economics", "macro economics", "gdp", "cpi", "ppi"},
        "美联储": {"federal reserve", "fed", "interest rate", "macro"},
        "加息": {"interest rate", "macro", "fed", "tightening"},
        "降息": {"interest rate", "macro", "fed", "easing"},
        "资产配置": {"asset allocation", "portfolio", "rebalancing", "diversification"},
        "再平衡": {"rebalancing", "asset allocation", "portfolio"},
        "仓位管理": {"position sizing", "risk budget", "portfolio"},
        "财务质量": {"earnings quality", "cash conversion", "accounting risk"},
        # 新增：金融市场基础知识教材相关扩展
        "金融市场": {"financial market", "资金融通", "价格发现", "流动性", "风险管理"},
        "资金融通": {"financing", "capital raising", "金融市场", "融资"},
        "价格发现": {"price discovery", "市场机制", "供求关系"},
        "流动性": {"liquidity", "变现", "流通性"},
        "直接融资": {"direct financing", "股票", "债券", "证券市场"},
        "间接融资": {"indirect financing", "银行", "信贷", "金融中介"},
        "LIBOR": {"伦敦银行间同业拆借利率", "libor", "基准利率", "银行间市场"},
        "巴塞尔": {"basel", "银行监管", "资本充足率", "巴塞尔协议"},
        "IOSCO": {"国际证监会", "证券监管", "投资者保护"},
        "纳斯达克": {"nasdaq", "美国", "股票市场", "交易所"},
        "联邦基金利率": {"federal funds rate", "美联储", "货币政策", "利率"},
        "金边债券": {"gilts", "英国", "国债", "政府债券"},
        "投资管理": {"investment management", "资产配置", "投资组合", "基金"},
        "证券从业": {"证券", "考试", "金融市场基础知识", "从业资格"},
        "基金从业": {"基金", "考试", "证券投资基金", "从业资格"},
    }

    SOURCE_KEYWORDS = {
        "valuation_metrics.md": {"市盈率", "市净率", "市销率", "估值", "pe", "pb", "ps", "ev", "ebitda"},
        "technical_analysis.md": {"技术分析", "macd", "rsi", "波动率", "最大回撤", "均线", "布林", "支撑", "阻力"},
        "financial_statements.md": {"财务报表", "利润表", "资产负债表", "现金流量表", "营收", "净利润", "roe"},
        "macro_economics.md": {"宏观", "gdp", "cpi", "ppi", "美联储", "加息", "降息", "通胀", "货币政策"},
        "market_instruments.md": {"股票", "债券", "久期", "基金", "etf", "衍生品", "国债"},
        "基本面分析.md": {"市盈率", "市净率", "roe", "净资产收益率", "peg", "股息率", "现金流"},
        "ETF专题.md": {"etf", "跟踪误差", "指数基金", "共同基金", "申购赎回"},
        "债券久期与利率.md": {"债券", "久期", "利率", "利率风险", "修正久期"},
        "风险收益指标专题.md": {"波动率", "最大回撤", "夏普比率", "胜率", "盈亏比"},
        "财报三表联动.md": {"三表联动", "利润表", "资产负债表", "现金流量表", "经营现金流"},
        "货币政策传导.md": {"货币政策", "加息", "降息", "股票", "债券", "汇率"},
        "资产配置基础.md": {"资产配置", "股债配置", "再平衡", "核心卫星", "组合"},
        "DCF估值与自由现金流.md": {"dcf", "自由现金流", "贴现率", "终值", "估值"},
        "分红回购与股东回报.md": {"分红", "回购", "股东回报", "派息率", "总股东回报"},
        "基金绩效指标.md": {"夏普比率", "索提诺", "信息比率", "超额收益", "跟踪误差"},
        "期权Greeks专题.md": {"delta", "gamma", "theta", "vega", "greeks"},
        "信用利差与债券定价.md": {"信用利差", "违约风险", "债券定价", "收益率曲线"},
        "行业轮动与景气度.md": {"行业轮动", "景气度", "库存周期", "估值扩张"},
        "仓位管理与风险预算.md": {"仓位管理", "风险预算", "止损", "头寸规模"},
        "财务质量信号.md": {"财务质量", "利润质量", "现金转换", "应收账款", "存货"},
        # 新增：金融市场基础知识教材关键词
        "教材_金融市场基础知识_第一章.md": {"金融市场", "资金融通", "价格发现", "流动性", "风险管理", "直接融资", "间接融资"},
        "教材_金融市场基础知识_第二节_全球金融市场.md": {"全球金融市场", "金融体系", "国际资金流动", "巴塞尔", "iosco", "iais"},
        "教材_金融市场基础知识_第三节_英国金融市场.md": {"伦敦", "外汇市场", "libor", "英国", "金边债券", "黄金市场"},
        "教材_金融市场基础知识_第四节_美国金融市场.md": {"美国", "纽约", "纳斯达克", "nyse", "联邦基金利率", "股票交易所"},
        # 新增：证券投资基金教材关键词（示例，根据实际章节内容调整）
        "教材_证券投资基金基础知识_第一章_投资管理基础.md": {"投资管理", "基金", "资产配置", "投资组合", "风险收益"},
    }

    QUESTION_FILLERS = {
        "什么",
        "什么是",
        "多少",
        "如何",
        "为什么",
        "怎么",
        "区别",
        "影响",
        "分别",
        "含义",
        "代表",
        "通常",
        "现在",
        "一下",
        "可以",
        "请问",
    }

    @staticmethod
    def _resolve_persist_dir() -> Path:
        configured = Path(settings.CHROMA_PERSIST_DIR)
        if configured.is_absolute():
            return configured
        backend_root = Path(__file__).resolve().parents[2]
        return (backend_root / configured).resolve()

    def __init__(self):
        persist_dir = self._resolve_persist_dir()
        persist_dir.mkdir(parents=True, exist_ok=True)

        self.chroma_client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self._refresh_collection()

        self.embedding_model = None
        self.embedding_backend = "uninitialized"
        self.reranker = None
        self.source_documents = self._load_source_documents()
        self.knowledge_chunks = self._build_knowledge_chunks(self.source_documents)
        self.chunk_map = {chunk["chunk_id"]: chunk for chunk in self.knowledge_chunks}

        if settings.RAG_AUTO_INDEX_ON_START and self.get_collection_count() == 0:
            try:
                self.index_local_knowledge(force=False)
            except Exception:
                pass

    def _ensure_embedding_model(self):
        if self.embedding_model is None:
            if SentenceTransformer is None:
                self.embedding_backend = "local-hash"
                return
            try:
                self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
                self.embedding_backend = "sentence-transformers"
            except Exception:
                self.embedding_model = None
                self.embedding_backend = "local-hash"

    def _refresh_collection(self):
        return self.chroma_client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def _ensure_reranker(self):
        if self.reranker is None:
            if FlagReranker is None:
                raise RuntimeError("FlagReranker is unavailable")
            self.reranker = FlagReranker(settings.RERANKER_MODEL, use_fp16=True)

    def _load_source_documents(self) -> List[Dict[str, Any]]:
        knowledge_dir = Path(__file__).resolve().parents[2] / "data" / "knowledge"
        documents: List[Dict[str, Any]] = []
        for file_path in sorted(knowledge_dir.glob("*.md")):
            content = None
            for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
                try:
                    content = file_path.read_text(encoding=encoding)
                    break
                except Exception:
                    continue
            if content is None:
                continue

            # Parse YAML frontmatter
            metadata, clean_content = self._parse_frontmatter(content)

            title = self._extract_title(clean_content) or file_path.stem
            documents.append(
                {
                    "source": file_path.name,
                    "title": title,
                    "content": clean_content,
                    "sections": self._split_sections(title, clean_content),
                    "topic_tokens": self.SOURCE_KEYWORDS.get(file_path.name, set()),
                    "metadata": metadata,  # Add metadata
                }
            )
        return documents

    @staticmethod
    def _parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
        """Parse YAML frontmatter from markdown content."""
        lines = content.split('\n')
        if not lines or lines[0].strip() != '---':
            return {}, content

        # Find closing ---
        end_idx = -1
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                end_idx = i
                break

        if end_idx == -1:
            return {}, content

        # Parse YAML (simple key-value parser)
        metadata = {}
        for line in lines[1:end_idx]:
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # Parse lists
                if value.startswith('[') and value.endswith(']'):
                    value = [v.strip() for v in value[1:-1].split(',')]

                metadata[key] = value

        # Return metadata and content without frontmatter
        clean_content = '\n'.join(lines[end_idx + 1:])
        return metadata, clean_content

    @staticmethod
    def _extract_title(content: str) -> str:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                return stripped.lstrip("#").strip()
        return ""

    def _split_sections(self, title: str, content: str) -> List[Dict[str, str]]:
        lines = content.splitlines()
        sections: List[Dict[str, str]] = []
        current_heading = "概览"
        current_prefix = ""
        buffer: List[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## "):
                if buffer:
                    sections.append({"section": current_heading, "content": "\n".join(buffer).strip()})
                current_prefix = stripped[3:].strip()
                current_heading = current_prefix
                buffer = []
                continue
            if stripped.startswith("### "):
                if buffer:
                    sections.append({"section": current_heading, "content": "\n".join(buffer).strip()})
                sub_heading = stripped[4:].strip()
                current_heading = f"{current_prefix} / {sub_heading}" if current_prefix else sub_heading
                buffer = []
                continue
            if stripped.startswith("# "):
                continue
            buffer.append(line)

        if buffer:
            sections.append({"section": current_heading, "content": "\n".join(buffer).strip()})

        return [section for section in sections if section["content"]] or [{"section": title, "content": content}]

    @staticmethod
    def _stable_chunk_id(source: str, section: str, index: int, text: str) -> str:
        digest = hashlib.md5(f"{source}:{section}:{index}:{text[:120]}".encode("utf-8")).hexdigest()[:10]
        return f"{source}:{index}:{digest}"

    def _chunk_text(self, text: str) -> List[str]:
        normalized = re.sub(r"\n{3,}", "\n\n", text.strip())
        if not normalized:
            return []

        chunk_size = max(240, settings.RAG_CHUNK_SIZE)
        overlap = max(40, min(settings.RAG_CHUNK_OVERLAP, chunk_size // 2))

        chunks: List[str] = []
        start = 0
        length = len(normalized)
        while start < length:
            end = min(length, start + chunk_size)
            if end < length:
                boundary = normalized.rfind("\n\n", start + chunk_size // 2, end)
                if boundary > start:
                    end = boundary

            chunk = normalized[start:end].strip()
            if chunk:
                chunks.append(chunk)

            if end >= length:
                break
            start = max(end - overlap, start + 1)

        return chunks

    def _build_knowledge_chunks(self, source_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        for document in source_documents:
            running_index = 0
            for section in document["sections"]:
                for chunk_text in self._chunk_text(section["content"]):
                    chunk_id = self._stable_chunk_id(document["source"], section["section"], running_index, chunk_text)
                    full_text = f"# {document['title']}\n## {section['section']}\n\n{chunk_text}".strip()
                    chunks.append(
                        {
                            "chunk_id": chunk_id,
                            "source": document["source"],
                            "title": document["title"],
                            "section": section["section"],
                            "content": full_text,
                            "raw_content": chunk_text,
                            "tokens": self._tokenize_text(full_text),
                            "title_tokens": self._tokenize_text(document["title"]),
                            "section_tokens": self._tokenize_text(section["section"]),
                            "topic_tokens": document["topic_tokens"],
                            "order": running_index,
                            "metadata": document.get("metadata", {}),  # Add metadata
                        }
                    )
                    running_index += 1
        return chunks

    @staticmethod
    def _tokenize_text(text: str) -> set[str]:
        lowered = text.lower()
        tokens = {
            token
            for token in re.split(r"[^0-9a-zA-Z\u4e00-\u9fff]+", lowered)
            if len(token) >= 2
        }
        for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", lowered):
            for size in range(2, min(6, len(chunk) + 1)):
                for index in range(0, len(chunk) - size + 1):
                    tokens.add(chunk[index:index + size])
        return tokens

    @staticmethod
    def _strip_question_noise(query: str) -> str:
        normalized = re.sub(r"[，。？！：、（）【】\[\]()?!.]", " ", query.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        for filler in sorted(RAGPipeline.QUESTION_FILLERS, key=len, reverse=True):
            normalized = normalized.replace(filler, " ")
        return re.sub(r"\s+", " ", normalized).strip()

    def _build_query_profile(self, query: str) -> Dict[str, Any]:
        normalized_query = self._strip_question_noise(query)
        query_tokens = self._tokenize_text(query)
        query_tokens.update(self._tokenize_text(normalized_query))

        expanded_terms: set[str] = set()
        matched_keywords: set[str] = set()
        for keyword, synonyms in self.QUERY_EXPANSIONS.items():
            if keyword in query.lower() or keyword in query:
                matched_keywords.add(keyword)
                expanded_terms.update(synonyms)

        for keyword in matched_keywords:
            query_tokens.update(self._tokenize_text(keyword))
        for term in expanded_terms:
            query_tokens.update(self._tokenize_text(term))

        return {
            "query_tokens": query_tokens,
            "expanded_terms": expanded_terms,
            "matched_keywords": matched_keywords,
            "normalized_query": normalized_query,
        }

    @staticmethod
    def _pick_focus_terms(
        query_tokens: set[str],
        matched_keywords: set[str],
        expanded_terms: set[str],
    ) -> List[str]:
        preferred = sorted(
            {
                token
                for token in (query_tokens | matched_keywords | expanded_terms)
                if len(token) >= 2 and token not in RAGPipeline.QUESTION_FILLERS
            },
            key=len,
            reverse=True,
        )
        return preferred[:12]

    def _extract_snippet(self, content: str, focus_terms: Sequence[str], max_chars: int = 380) -> str:
        compact = re.sub(r"\n{3,}", "\n\n", content).strip()
        lowered = compact.lower()

        for term in focus_terms:
            position = lowered.find(term.lower())
            if position >= 0:
                start = max(0, position - 80)
                end = min(len(compact), position + max_chars)
                snippet = compact[start:end].strip()
                if start > 0:
                    snippet = "..." + snippet
                if end < len(compact):
                    snippet += "..."
                return snippet
        return compact[:max_chars].strip()

    def _score_chunk(
        self,
        chunk: Dict[str, Any],
        query_tokens: set[str],
        expanded_terms: set[str],
        matched_keywords: set[str],
        normalized_query: str,
    ) -> float:
        content_lower = chunk["content"].lower()
        title_lower = chunk["title"].lower()
        section_lower = chunk["section"].lower()

        token_overlap = len(query_tokens & chunk["tokens"])
        title_overlap = len(query_tokens & chunk["title_tokens"])
        section_overlap = len(query_tokens & chunk["section_tokens"])
        keyword_hits = sum(1 for keyword in matched_keywords if keyword.lower() in content_lower)
        expanded_hits = sum(1 for term in expanded_terms if term in content_lower)
        exact_query_hit = 1 if normalized_query and normalized_query in content_lower else 0
        title_exact_hit = 1 if normalized_query and normalized_query in title_lower else 0
        section_exact_hit = 1 if normalized_query and normalized_query in section_lower else 0
        topic_hits = len((query_tokens | matched_keywords) & chunk.get("topic_tokens", set()))

        score = (
            token_overlap
            + title_overlap * 3.0
            + section_overlap * 2.0
            + keyword_hits * 2.5
            + expanded_hits * 0.5
            + exact_query_hit * 4.0
            + title_exact_hit * 4.0
            + section_exact_hit * 3.0
            + topic_hits * 3.0
        )

        if matched_keywords and not keyword_hits and title_overlap == 0 and section_overlap == 0:
            score *= 0.55
        return float(score)

    def _search_local_candidates(self, query: str, limit: Optional[int] = None) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        profile = self._build_query_profile(query)
        query_tokens = profile["query_tokens"]
        expanded_terms = profile["expanded_terms"]
        matched_keywords = profile["matched_keywords"]
        normalized_query = profile["normalized_query"]

        if not query_tokens:
            return [], profile

        candidates: List[Dict[str, Any]] = []
        focus_terms = self._pick_focus_terms(query_tokens, matched_keywords, expanded_terms)
        for chunk in self.knowledge_chunks:
            raw_score = self._score_chunk(
                chunk=chunk,
                query_tokens=query_tokens,
                expanded_terms=expanded_terms,
                matched_keywords=matched_keywords,
                normalized_query=normalized_query,
            )
            if raw_score <= 0:
                continue
            candidates.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "source": chunk["source"],
                    "title": chunk["title"],
                    "section": chunk["section"],
                    "content": self._extract_snippet(chunk["content"], focus_terms),
                    "raw_score": raw_score,
                    "retrieval_stage": "lexical",
                    "metadata": {
                        "topic_tokens": sorted(chunk.get("topic_tokens", set())),
                        "order": chunk["order"],
                    },
                }
            )

        if not candidates:
            return [], profile

        candidates.sort(key=lambda item: item["raw_score"], reverse=True)
        top_score = candidates[0]["raw_score"]
        threshold = max(2.0, top_score * 0.4)
        filtered = [item for item in candidates if item["raw_score"] >= threshold]
        for item in filtered:
            item["score"] = round(item["raw_score"] / top_score, 4)
        return filtered[: limit or settings.RAG_LEXICAL_TOP_K], profile

    def _candidate_to_document(self, candidate: Dict[str, Any]) -> Document:
        return Document(
            content=candidate["content"],
            source=candidate["source"],
            score=float(candidate["score"]),
            title=candidate.get("title"),
            section=candidate.get("section"),
            chunk_id=candidate.get("chunk_id"),
            retrieval_stage=candidate.get("retrieval_stage"),
            metadata=candidate.get("metadata"),
        )

    def _search_local_documents(self, query: str) -> KnowledgeResult:
        candidates, _ = self._search_local_candidates(query, limit=settings.RAG_TOP_N)
        return KnowledgeResult(
            documents=[self._candidate_to_document(item) for item in candidates[: settings.RAG_TOP_N]],
            total_found=len(candidates),
            query=query,
            retrieval_meta={"strategy": "lexical"},
        )

    def _collection_size(self) -> int:
        try:
            return int(self.collection.count())
        except Exception:
            try:
                self.collection = self._refresh_collection()
                return int(self.collection.count())
            except Exception:
                return 0

    def _local_hash_embedding(self, text: str) -> List[float]:
        vector = [0.0] * self.LOCAL_EMBED_DIM
        for token in self._tokenize_text(text):
            index = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self.LOCAL_EMBED_DIM
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def _embed_texts(self, texts: Sequence[str], show_progress_bar: bool = False) -> List[List[float]]:
        self._ensure_embedding_model()
        if self.embedding_model is not None:
            embeddings = self.embedding_model.encode(
                list(texts),
                normalize_embeddings=True,
                show_progress_bar=show_progress_bar,
            )
            if hasattr(embeddings, "tolist"):
                embeddings = embeddings.tolist()
            if embeddings and not isinstance(embeddings[0], list):
                embeddings = [embeddings]
            return embeddings

        self.embedding_backend = "local-hash"
        return [self._local_hash_embedding(text) for text in texts]

    def _embed_query(self, query: str) -> List[float]:
        return self._embed_texts([query])[0]

    def _vector_search_candidates(self, query: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if self._collection_size() <= 0:
            return []

        query_embedding = self._embed_query(query)
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit or settings.RAG_VECTOR_TOP_K,
            )
        except Exception:
            self.collection = self._refresh_collection()
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit or settings.RAG_VECTOR_TOP_K,
            )
        if not results["documents"] or not results["documents"][0]:
            return []

        distances = results.get("distances", [[]])[0] if results.get("distances") else []
        metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
        ids = results.get("ids", [[]])[0] if results.get("ids") else []
        candidates: List[Dict[str, Any]] = []
        for index, document in enumerate(results["documents"][0]):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else 1.0
            vector_score = max(0.0, 1.0 - float(distance))
            candidates.append(
                {
                    "chunk_id": ids[index] if index < len(ids) else metadata.get("chunk_id"),
                    "source": metadata.get("source", "unknown"),
                    "title": metadata.get("title"),
                    "section": metadata.get("section"),
                    "content": document,
                    "score": round(vector_score, 4),
                    "retrieval_stage": "vector",
                    "metadata": metadata,
                }
            )
        return candidates

    def _compute_rerank_scores(self, pairs: List[List[str]]) -> List[float]:
        self._ensure_reranker()
        try:
            scores = self.reranker.compute_score(pairs, normalize=True)
        except TypeError:
            scores = self.reranker.compute_score(pairs)

        if not isinstance(scores, list):
            scores = [scores]

        normalized = [float(score) for score in scores]
        if any(score < 0 or score > 1 for score in normalized):
            if len(normalized) == 1:
                normalized = [1 / (1 + math.exp(-normalized[0]))]
            else:
                min_score = min(normalized)
                max_score = max(normalized)
                if max_score - min_score > 1e-6:
                    normalized = [(score - min_score) / (max_score - min_score) for score in normalized]
                else:
                    normalized = [1 / (1 + math.exp(-score)) for score in normalized]
        return [max(0.0, min(score, 1.0)) for score in normalized]

    async def search(self, query: str) -> KnowledgeResult:
        lexical_result = self._search_local_documents(query)
        if lexical_result.documents:
            return lexical_result

        candidates = self._vector_search_candidates(query, limit=settings.RAG_TOP_K)
        if not candidates:
            return KnowledgeResult(documents=[], total_found=0, query=query, retrieval_meta={"strategy": "vector"})

        pairs = [[query, candidate["content"]] for candidate in candidates]
        scores = self._compute_rerank_scores(pairs)

        ranked: List[Dict[str, Any]] = []
        for index, rerank_score in enumerate(scores):
            if rerank_score < settings.RAG_SCORE_THRESHOLD:
                continue
            item = candidates[index]
            item["score"] = round(float(rerank_score), 4)
            item["retrieval_stage"] = "vector_rerank"
            ranked.append(item)

        ranked.sort(key=lambda item: item["score"], reverse=True)
        return KnowledgeResult(
            documents=[self._candidate_to_document(item) for item in ranked[: settings.RAG_TOP_N]],
            total_found=len(candidates),
            query=query,
            retrieval_meta={"strategy": "vector_rerank"},
        )

    def _serialize_chunk_metadata(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "chunk_id": chunk["chunk_id"],
            "source": chunk["source"],
            "title": chunk["title"],
            "section": chunk["section"],
            "order": int(chunk["order"]),
        }

    def index_local_knowledge(self, force: bool = False, batch_size: int = 32) -> Dict[str, Any]:
        if not self.knowledge_chunks:
            return {"indexed": False, "reason": "no_chunks", "chunks": 0}

        if force:
            try:
                self.chroma_client.delete_collection(name=self.COLLECTION_NAME)
            except Exception:
                pass
            self.collection = self._refresh_collection()

        if not force and self._collection_size() >= len(self.knowledge_chunks):
            return {"indexed": False, "reason": "up_to_date", "chunks": len(self.knowledge_chunks)}

        for start in range(0, len(self.knowledge_chunks), batch_size):
            batch = self.knowledge_chunks[start:start + batch_size]
            texts = [item["content"] for item in batch]
            embeddings = self._embed_texts(texts, show_progress_bar=False)
            payload = {
                "ids": [item["chunk_id"] for item in batch],
                "documents": texts,
                "embeddings": embeddings,
                "metadatas": [self._serialize_chunk_metadata(item) for item in batch],
            }
            if hasattr(self.collection, "upsert"):
                self.collection.upsert(**payload)
            else:
                self.collection.add(**payload)

        return {
            "indexed": True,
            "chunks": len(self.knowledge_chunks),
            "vector_index_count": self._collection_size(),
        }

    def get_collection_count(self) -> int:
        return self._collection_size()

    def get_status(self) -> Dict[str, Any]:
        return {
            "sources": len(self.source_documents),
            "chunks": len(self.knowledge_chunks),
            "vector_index_count": self._collection_size(),
            "bm25_ready": False,
            "embedding_model_ready": self.embedding_model is not None,
            "embedding_backend": self.embedding_backend,
            "reranker_ready": self.reranker is not None,
            "auto_index_enabled": settings.RAG_AUTO_INDEX_ON_START,
        }

    def add_documents(self, documents: List[str], metadatas: List[dict], ids: List[str]):
        embeddings = self._embed_texts(documents, show_progress_bar=True)
        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
