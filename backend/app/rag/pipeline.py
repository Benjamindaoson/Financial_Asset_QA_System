"""RAG pipeline with chunked knowledge retrieval and optional vector search."""

from __future__ import annotations

import hashlib
import html
import math
import os
import re
from pathlib import Path
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
    LOCAL_EMBED_DIM = 768
    DEFINITION_QUERY_HINTS = {
        "\u4ec0\u4e48\u662f",
        "\u5b9a\u4e49",
        "\u542b\u4e49",
        "\u4ecb\u7ecd",
        "\u89e3\u91ca",
        "\u600e\u4e48\u8ba1\u7b97",
        "\u5982\u4f55\u8ba1\u7b97",
        "\u516c\u5f0f",
        "what is",
        "definition",
        "formula",
    }
    CONCEPT_ALIASES = {
        "pe": {
            "\u5e02\u76c8\u7387",
            "pe",
            "p/e",
            "pe ratio",
            "price-to-earnings",
            "price to earnings",
        },
        "pb": {
            "\u5e02\u51c0\u7387",
            "pb",
            "p/b",
            "pb ratio",
            "price-to-book",
            "price to book",
        },
        "eps": {
            "eps",
            "\u6bcf\u80a1\u6536\u76ca",
            "earnings per share",
        },
        "peg": {
            "peg",
            "peg ratio",
            "\u5e02\u76c8\u7387\u76f8\u5bf9\u76c8\u5229\u589e\u957f\u6bd4",
        },
        "roe": {
            "roe",
            "\u51c0\u8d44\u4ea7\u6536\u76ca\u7387",
            "\u6743\u76ca\u56de\u62a5\u7387",
            "return on equity",
        },
        "ps": {
            "\u5e02\u9500\u7387",
            "ps",
            "p/s",
            "ps ratio",
            "price-to-sales",
            "price to sales",
        },
        "ev_ebitda": {
            "ev/ebitda",
            "ev to ebitda",
            "enterprise value to ebitda",
            "\u4f01\u4e1a\u4ef7\u503c\u500d\u6570",
        },
        "bvps": {
            "bvps",
            "\u6bcf\u80a1\u51c0\u8d44\u4ea7",
            "book value per share",
        },
        "fcf": {
            "fcf",
            "\u81ea\u7531\u73b0\u91d1\u6d41",
            "free cash flow",
        },
        "gross_margin": {
            "\u6bdb\u5229\u7387",
            "gross margin",
            "gross profit margin",
        },
        "net_margin": {
            "\u51c0\u5229\u7387",
            "net margin",
            "net profit margin",
        },
    }

    QUERY_EXPANSIONS = {
        "市盈率": {"pe", "price-to-earnings", "valuation", "估值"},
        "市净率": {"pb", "price-to-book", "book value", "估值"},
        "市销率": {"ps", "price-to-sales", "sales", "估值"},
        "ROE": {"return on equity", "净资产收益率", "fundamental", "financial statements"},
        "PEG": {"price/earnings to growth", "growth", "估值"},
        "EV/EBITDA": {"enterprise value to ebitda", "企业价值倍数", "估值", "并购"},
        "BVPS": {"book value per share", "每股净资产", "pb", "净资产"},
        "DCF": {"discounted cash flow", "自由现金流", "估值", "现金流折现"},
        "自由现金流": {"fcf", "cash flow", "dcf", "估值"},
        "毛利率": {"gross margin", "gross profit margin", "profitability", "利润率"},
        "净利率": {"net margin", "net profit margin", "profitability", "利润率"},
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

    SOURCE_DIRECTORIES = (
        ("backend/data/knowledge", "concept"),
        ("data/knowledge", "textbook"),
        ("data/raw_data/knowledge", "concept"),
        ("data/raw_data/finance_report", "report"),
    )

    @staticmethod
    def _resolve_persist_dir() -> Path:
        configured = Path(settings.CHROMA_PERSIST_DIR)
        if configured.is_absolute():
            return configured
        backend_root = Path(__file__).resolve().parents[2]
        return (backend_root / configured).resolve()

    @staticmethod
    def _repo_root() -> Path:
        return Path(__file__).resolve().parents[3]

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
        self.reranker_backend = "uninitialized"
        self._embedding_attempted = False
        self._reranker_attempted = False
        self.source_documents = self._load_source_documents()
        self.knowledge_chunks = self._build_knowledge_chunks(self.source_documents)
        self.chunk_map = {chunk["chunk_id"]: chunk for chunk in self.knowledge_chunks}

        current_vector_count = self.get_collection_count()
        self.vector_index_synced = current_vector_count == len(self.knowledge_chunks)
        should_sync_index = settings.RAG_AUTO_INDEX_ON_START
        if should_sync_index and self.knowledge_chunks:
            try:
                sync_result = self.index_local_knowledge(force=current_vector_count > len(self.knowledge_chunks))
                self.vector_index_synced = bool(
                    sync_result.get("indexed") or sync_result.get("reason") == "up_to_date"
                )
            except Exception:
                self.vector_index_synced = False

    @staticmethod
    def _resolve_runtime_dir(configured_path: str) -> Path:
        configured = Path(configured_path)
        if configured.is_absolute():
            return configured
        backend_root = Path(__file__).resolve().parents[2]
        return (backend_root / configured).resolve()

    def _configure_model_runtime(self) -> None:
        hf_home = self._resolve_runtime_dir(settings.HF_HOME)
        transformers_cache = self._resolve_runtime_dir(settings.TRANSFORMERS_CACHE)
        hf_home.mkdir(parents=True, exist_ok=True)
        transformers_cache.mkdir(parents=True, exist_ok=True)
        os.environ["HF_HOME"] = str(hf_home)
        os.environ["TRANSFORMERS_CACHE"] = str(transformers_cache)
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    def _resolve_local_model_path(self, model_name: str) -> Optional[Path]:
        candidate = Path(model_name)
        if candidate.exists():
            return candidate.resolve()

        model_slug = model_name.replace("/", "--")
        model_leaf = model_name.split("/")[-1]
        search_roots = [
            self._resolve_runtime_dir(settings.HF_HOME),
            self._resolve_runtime_dir(settings.TRANSFORMERS_CACHE),
        ]
        for root in search_roots:
            for base_name in (f"models--{model_slug}", model_leaf, model_slug):
                base_dir = root / base_name
                if not base_dir.exists():
                    continue
                for marker in ("modules.json", "config.json", "sentence_bert_config.json"):
                    matches = list(base_dir.rglob(marker))
                    if matches:
                        return matches[0].parent.resolve()
        return None

    def _ensure_embedding_model(self):
        if self.embedding_model is not None or self._embedding_attempted:
            return

        self._embedding_attempted = True
        if SentenceTransformer is None:
            self.embedding_backend = "local-hash"
            return

        self._configure_model_runtime()
        model_path = self._resolve_local_model_path(settings.EMBEDDING_MODEL)
        if model_path is None:
            self.embedding_backend = "local-hash"
            return
        try:
            try:
                self.embedding_model = SentenceTransformer(
                    str(model_path),
                    cache_folder=os.environ.get("HF_HOME"),
                    local_files_only=True,
                )
            except TypeError:
                self.embedding_model = SentenceTransformer(str(model_path))
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
        if self.reranker is not None:
            return
        if self._reranker_attempted:
            raise RuntimeError("FlagReranker is unavailable")

        self._reranker_attempted = True
        if FlagReranker is None:
            self.reranker_backend = "unavailable"
            raise RuntimeError("FlagReranker is unavailable")

        self._configure_model_runtime()
        model_path = self._resolve_local_model_path(settings.RERANKER_MODEL)
        if model_path is None:
            self.reranker_backend = "disabled"
            raise RuntimeError("FlagReranker is unavailable")
        try:
            try:
                self.reranker = FlagReranker(
                    str(model_path),
                    use_fp16=True,
                    local_files_only=True,
                )
            except TypeError:
                self.reranker = FlagReranker(str(model_path), use_fp16=True)
            self.reranker_backend = "flag-embedding"
        except Exception as exc:
            self.reranker = None
            self.reranker_backend = "disabled"
            raise RuntimeError("FlagReranker is unavailable") from exc

    def _load_source_documents(self) -> List[Dict[str, Any]]:
        documents: List[Dict[str, Any]] = []
        repo_root = self._repo_root()
        seen_paths: set[Path] = set()

        for relative_dir, default_source_type in self.SOURCE_DIRECTORIES:
            source_dir = repo_root / relative_dir
            if not source_dir.exists():
                continue

            candidate_files = [*source_dir.glob("*.md"), *source_dir.glob("*.html")]
            for file_path in sorted(candidate_files):
                resolved = file_path.resolve()
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)

                raw_content = self._read_source_file(file_path)
                if raw_content is None:
                    continue

                if file_path.suffix.lower() == ".md":
                    frontmatter, clean_content = self._parse_frontmatter(raw_content)
                else:
                    frontmatter, clean_content = {}, self._html_to_text(raw_content)

                clean_content = clean_content.strip()
                if not clean_content:
                    continue

                inferred = self._infer_document_metadata(
                    file_path=file_path,
                    content=clean_content,
                    default_source_type=default_source_type,
                )
                metadata = {**inferred, **frontmatter}
                title = metadata.get("title") or self._extract_title(clean_content) or file_path.stem
                source_path = str(file_path.relative_to(repo_root)).replace("\\", "/")
                topic_tokens = set(self.SOURCE_KEYWORDS.get(file_path.name, set()))
                topic_tokens.update(self._metadata_topic_tokens(metadata, title))

                documents.append(
                    {
                        "source": file_path.name,
                        "source_path": source_path,
                        "title": title,
                        "content": clean_content,
                        "sections": self._split_sections(title, clean_content),
                        "topic_tokens": topic_tokens,
                        "metadata": metadata,
                    }
                )
        return documents

    def _metadata_topic_tokens(self, metadata: Dict[str, Any], title: str) -> set[str]:
        values: List[str] = [title]
        for key in ("category", "difficulty", "title"):
            value = metadata.get(key)
            if isinstance(value, str):
                values.append(value)
        for key in ("tags", "related_topics"):
            value = metadata.get(key)
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, list):
                values.extend(str(item) for item in value if item)

        tokens: set[str] = set()
        for value in values:
            tokens.update(self._tokenize_text(value))
        return tokens

    @staticmethod
    def _read_source_file(file_path: Path) -> Optional[str]:
        for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030"):
            try:
                return file_path.read_text(encoding=encoding)
            except Exception:
                continue
        return None

    @staticmethod
    def _html_to_text(content: str) -> str:
        cleaned = re.sub(r"(?is)<script.*?>.*?</script>", " ", content)
        cleaned = re.sub(r"(?is)<style.*?>.*?</style>", " ", cleaned)
        cleaned = re.sub(r"(?i)<br\s*/?>", "\n", cleaned)
        cleaned = re.sub(r"(?i)</p>", "\n\n", cleaned)
        cleaned = re.sub(r"(?i)</h[1-6]>", "\n", cleaned)
        cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
        cleaned = html.unescape(cleaned)
        cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
        return cleaned.strip()

    def _infer_document_metadata(self, file_path: Path, content: str, default_source_type: str) -> Dict[str, Any]:
        source_path = str(file_path).replace("\\", "/").lower()
        source_type = default_source_type
        if "finance_report" in source_path or "财报" in file_path.stem:
            source_type = "report"
        elif "教材" in file_path.stem:
            source_type = "textbook"

        return {
            "source_type": source_type,
            "asset_code": self._infer_asset_code(file_path),
            "date": self._infer_document_date(file_path),
            "language": self._infer_language(content),
            "source_path": str(file_path),
        }

    @staticmethod
    def _infer_asset_code(file_path: Path) -> Optional[str]:
        stem = file_path.stem.upper()
        patterns = (
            r"(?:财报_|REPORT_)?([A-Z]{2,5}(?:\.[A-Z]{1,3})?)_(?:\d{4}Q[1-4]|\d{4}H[1-2])",
            r"([A-Z]{2,5})-\d{8}",
            r"\b([A-Z]{2,5}(?:\.[A-Z]{1,3})?)\b",
        )
        for pattern in patterns:
            match = re.search(pattern, stem)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _infer_document_date(file_path: Path) -> Optional[str]:
        stem = file_path.stem
        for pattern in (r"(\d{4}-\d{2}-\d{2})", r"(\d{8})", r"(\d{4}Q[1-4])", r"(\d{4}H[1-2])"):
            match = re.search(pattern, stem, re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).upper()
            if re.fullmatch(r"\d{8}", value):
                return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
            return value
        return None

    @staticmethod
    def _infer_language(content: str) -> str:
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", content))
        latin_chars = len(re.findall(r"[A-Za-z]", content))
        return "zh" if chinese_chars >= latin_chars else "en"

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

    @staticmethod
    def _is_table_like(text: str) -> bool:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 2:
            return False
        pipe_lines = sum(1 for line in lines if line.count("|") >= 2)
        numeric_lines = sum(1 for line in lines if re.search(r"\d", line) and ("|" in line or "\t" in line))
        return pipe_lines >= 2 or numeric_lines >= 2

    def _infer_chunk_type(self, source_type: str, section: str, chunk_text: str) -> str:
        if self._is_table_like(chunk_text):
            return "table"
        lowered = f"{section}\n{chunk_text}".lower()
        if source_type == "report":
            if any(token in lowered for token in ("revenue", "income", "margin", "guidance", "eps", "profit", "cash flow")):
                return "report_metric"
            return "report_text"
        return "text"

    @staticmethod
    def _is_exam_like_chunk(source_type: str, chunk_text: str) -> bool:
        if source_type != "textbook":
            return False

        option_hits = len(re.findall(r"(?m)^\s*[A-D][\.\u3001\uff0e]\s*", chunk_text))
        numbered_question = bool(re.search(r"(?m)^\s*\d+[\.\u3001]\s*", chunk_text))
        answer_like = any(
            marker in chunk_text
            for marker in ("\u7b54\u6848", "\u77e5\u8bc6\u70b9", "\u6b63\u786e\u7684\u662f", "\u9519\u8bef\u7684\u662f")
        )
        blank_like = "\uff08 \uff09" in chunk_text or "（ ）" in chunk_text
        return (numbered_question or blank_like) and (answer_like or option_hits >= 3)

    def _should_skip_chunk(self, chunk_metadata: Dict[str, Any], chunk_text: str) -> bool:
        return self._is_exam_like_chunk(chunk_metadata.get("source_type", ""), chunk_text)

    def _build_knowledge_chunks(self, source_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        chunks: List[Dict[str, Any]] = []
        for document in source_documents:
            running_index = 0
            for section in document["sections"]:
                for chunk_text in self._chunk_text(section["content"]):
                    chunk_id = self._stable_chunk_id(document.get("source_path", document["source"]), section["section"], running_index, chunk_text)
                    full_text = f"# {document['title']}\n## {section['section']}\n\n{chunk_text}".strip()
                    chunk_type = self._infer_chunk_type(document.get("metadata", {}).get("source_type", ""), section["section"], chunk_text)
                    chunk_metadata = {
                        **document.get("metadata", {}),
                        "section": section["section"],
                        "source_path": document.get("source_path"),
                        "chunk_type": chunk_type,
                        "is_table": chunk_type == "table",
                        "is_exam_like": self._is_exam_like_chunk(
                            document.get("metadata", {}).get("source_type", ""),
                            chunk_text,
                        ),
                    }
                    if self._should_skip_chunk(chunk_metadata, chunk_text):
                        running_index += 1
                        continue
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
                            "metadata": chunk_metadata,
                        }
                    )
                    running_index += 1
        return chunks

    def generate_query_variants(self, query: str) -> List[str]:
        variants = [query.strip()]
        lowered = query.lower()
        replacements = {
            "p/e": "市盈率",
            "pe": "市盈率",
            "p/b": "市净率",
            "pb": "市净率",
            "p/s": "市销率",
            "ps": "市销率",
            "eps": "每股收益",
            "ev/ebitda": "企业价值倍数",
            "bvps": "每股净资产",
            "fcf": "自由现金流",
            "gross margin": "毛利率",
            "net margin": "净利率",
        }

        for needle, canonical in replacements.items():
            if needle in lowered and canonical not in query:
                variants.append(f"{query} {canonical}")

        for keyword, synonyms in self.QUERY_EXPANSIONS.items():
            keyword_lower = keyword.lower()
            if keyword_lower in lowered or keyword in query:
                variants.append(f"{query} {' '.join(sorted(synonyms)[:2])}")
                continue
            if any(synonym.lower() in lowered for synonym in synonyms):
                variants.append(f"{query} {keyword}")

        deduped: List[str] = []
        seen: set[str] = set()
        for variant in variants:
            normalized = re.sub(r"\s+", " ", variant).strip()
            if normalized and normalized not in seen:
                deduped.append(normalized)
                seen.add(normalized)
        return deduped[: max(settings.RAG_MULTI_QUERY_NUM, 3)]

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
        canonical_concepts: set[str] = set()
        lowered_query = query.lower()
        for keyword, synonyms in self.QUERY_EXPANSIONS.items():
            if keyword in query.lower() or keyword in query:
                matched_keywords.add(keyword)
                expanded_terms.update(synonyms)

        for canonical, aliases in self.CONCEPT_ALIASES.items():
            if any(alias in lowered_query or alias in query for alias in aliases):
                canonical_concepts.add(canonical)
                for alias in aliases:
                    query_tokens.update(self._tokenize_text(alias))

        prefers_definition = any(hint in lowered_query or hint in query for hint in self.DEFINITION_QUERY_HINTS)
        formula_intent = any(token in lowered_query or token in query for token in ("\u516c\u5f0f", "\u8ba1\u7b97", "formula"))
        if canonical_concepts and not re.search(r"\b[A-Z]{2,5}(?:\.[A-Z]{1,3})?\b", query):
            prefers_definition = True

        for keyword in matched_keywords:
            query_tokens.update(self._tokenize_text(keyword))
        for term in expanded_terms:
            query_tokens.update(self._tokenize_text(term))

        return {
            "query_tokens": query_tokens,
            "expanded_terms": expanded_terms,
            "matched_keywords": matched_keywords,
            "normalized_query": normalized_query,
            "canonical_concepts": canonical_concepts,
            "prefers_definition": prefers_definition,
            "formula_intent": formula_intent,
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
        canonical_concepts: set[str],
        prefers_definition: bool,
        formula_intent: bool,
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
        metadata = chunk.get("metadata", {})
        chunk_type = metadata.get("chunk_type")
        source_type = metadata.get("source_type")
        is_exam_like = bool(metadata.get("is_exam_like"))
        table_boost = 0.0
        report_boost = 0.0
        concept_boost = 0.0
        source_prior = 0.0
        lowered_query = normalized_query.lower()

        if chunk_type == "table" and any(token in lowered_query for token in ("revenue", "income", "profit", "eps", "margin", "guidance", "cash flow")):
            table_boost = 2.5
        if source_type == "report" and any(token in lowered_query for token in ("report", "earnings", "filing", "10-k", "10-q", "quarter")):
            report_boost = 1.5
        if source_type == "concept":
            source_prior += 1.8
        elif source_type == "textbook":
            source_prior += 0.2

        if canonical_concepts:
            for canonical in canonical_concepts:
                aliases = self.CONCEPT_ALIASES.get(canonical, set())
                title_hits = sum(1 for alias in aliases if alias in title_lower)
                section_hits = sum(1 for alias in aliases if alias in section_lower)
                content_hits = sum(1 for alias in aliases if alias in content_lower)
                concept_boost += title_hits * 4.0 + section_hits * 3.0 + min(content_hits, 2) * 0.8
            if prefers_definition:
                if "\u5b9a\u4e49" in section_lower:
                    concept_boost += 4.5
                elif formula_intent and any(tag in section_lower for tag in ("\u516c\u5f0f", "\u8ba1\u7b97")):
                    concept_boost += 3.5
                elif any(tag in section_lower for tag in ("\u516c\u5f0f", "\u8ba1\u7b97")):
                    concept_boost += 1.0
                elif "\u4f7f\u7528\u63d0\u793a" in section_lower:
                    concept_boost += 0.3
            if prefers_definition and chunk["source"] == "core_finance_metrics.md":
                concept_boost += 4.0
            elif prefers_definition and chunk["source"] in {"valuation_metrics.md", "\u57fa\u672c\u9762\u5206\u6790.md"}:
                concept_boost += 1.5

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
            + table_boost
            + report_boost
            + concept_boost
            + source_prior
        )

        if matched_keywords and not keyword_hits and title_overlap == 0 and section_overlap == 0:
            score *= 0.55
        if prefers_definition and is_exam_like:
            score *= 0.12
        return float(score)

    def _search_local_candidates(self, query: str, limit: Optional[int] = None) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        profile = self._build_query_profile(query)
        query_tokens = profile["query_tokens"]
        expanded_terms = profile["expanded_terms"]
        matched_keywords = profile["matched_keywords"]
        normalized_query = profile["normalized_query"]
        canonical_concepts = profile["canonical_concepts"]
        prefers_definition = profile["prefers_definition"]
        formula_intent = profile["formula_intent"]

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
                canonical_concepts=canonical_concepts,
                prefers_definition=prefers_definition,
                formula_intent=formula_intent,
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
                        **chunk.get("metadata", {}),
                        "topic_tokens": sorted(chunk.get("topic_tokens", set())),
                        "order": chunk["order"],
                    },
                }
            )

        if not candidates:
            return [], profile

        candidates.sort(key=lambda item: item["raw_score"], reverse=True)
        if prefers_definition:
            non_exam_candidates = [item for item in candidates if not item["metadata"].get("is_exam_like")]
            if non_exam_candidates:
                candidates = non_exam_candidates + [item for item in candidates if item["metadata"].get("is_exam_like")]
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
        if not self.vector_index_synced:
            return []
        if self._collection_size() <= 0:
            return []

        query_embedding = self._embed_query(query)
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit or settings.RAG_VECTOR_TOP_K,
            )
        except Exception:
            try:
                self.collection = self._refresh_collection()
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=limit or settings.RAG_VECTOR_TOP_K,
                )
            except Exception:
                return []
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

    def rerank_documents(self, query: str, documents: List[Document]) -> List[Document]:
        if not documents:
            return []

        pairs = [[query, document.content] for document in documents]
        scores = self._compute_rerank_scores(pairs)
        reranked: List[Document] = []
        for index, document in enumerate(documents):
            reranked_doc = document.model_copy(deep=True)
            rerank_score = float(scores[index]) if index < len(scores) else float(document.score)
            base_score = float(document.score or 0.0)
            reranked_doc.score = round(base_score * 0.35 + rerank_score * 0.65, 4)
            metadata = dict(reranked_doc.metadata or {})
            metadata["pre_rerank_score"] = base_score
            metadata["rerank_score"] = rerank_score
            reranked_doc.metadata = metadata
            reranked.append(reranked_doc)

        reranked.sort(key=lambda item: item.score, reverse=True)
        return reranked

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
        metadata = chunk.get("metadata", {})
        return {
            "chunk_id": chunk["chunk_id"],
            "source": chunk["source"],
            "title": chunk["title"],
            "section": chunk["section"],
            "order": int(chunk["order"]),
            "source_type": metadata.get("source_type", "") or "",
            "asset_code": metadata.get("asset_code", "") or "",
            "date": metadata.get("date", "") or "",
            "language": metadata.get("language", "") or "",
            "source_path": metadata.get("source_path", "") or "",
            "chunk_type": metadata.get("chunk_type", "") or "",
            "is_table": bool(metadata.get("is_table", False)),
            "is_exam_like": bool(metadata.get("is_exam_like", False)),
        }

    def index_local_knowledge(self, force: bool = False, batch_size: int = 32) -> Dict[str, Any]:
        if not self.knowledge_chunks:
            self.vector_index_synced = False
            return {"indexed": False, "reason": "no_chunks", "chunks": 0}

        if force:
            try:
                self.chroma_client.delete_collection(name=self.COLLECTION_NAME)
            except Exception:
                pass
            self.collection = self._refresh_collection()

        if not force and self._collection_size() >= len(self.knowledge_chunks):
            self.vector_index_synced = True
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

        self.vector_index_synced = True
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
            "reranker_backend": self.reranker_backend,
            "vector_index_synced": self.vector_index_synced,
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
