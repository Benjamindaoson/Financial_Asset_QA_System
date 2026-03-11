"""
混合检索管道
Hybrid Retrieval Pipeline

实现 Vector + BM25 + Reranker 的混合检索策略
"""
import logging
from typing import List, Dict, Optional, Tuple
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


class BM25Retriever:
    """BM25关键词检索器"""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        初始化BM25检索器

        Args:
            k1: 词频饱和参数
            b: 长度归一化参数
        """
        self.k1 = k1
        self.b = b
        self.corpus = []
        self.corpus_ids = []
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        self.avgdl = 0

    def fit(self, documents: List[str], doc_ids: List[str]):
        """
        训练BM25模型

        Args:
            documents: 文档列表
            doc_ids: 文档ID列表
        """
        self.corpus = documents
        self.corpus_ids = doc_ids

        # 分词
        tokenized_corpus = [self._tokenize(doc) for doc in documents]

        # 计算文档长度
        self.doc_len = [len(tokens) for tokens in tokenized_corpus]
        self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0

        # 计算IDF
        df = defaultdict(int)
        for tokens in tokenized_corpus:
            for token in set(tokens):
                df[token] += 1

        num_docs = len(documents)
        self.idf = {
            token: np.log((num_docs - freq + 0.5) / (freq + 0.5) + 1.0)
            for token, freq in df.items()
        }

        self.doc_freqs = []
        for tokens in tokenized_corpus:
            token_freqs = defaultdict(int)
            for token in tokens:
                token_freqs[token] += 1
            self.doc_freqs.append(token_freqs)

        logger.info(f"BM25模型训练完成: {num_docs}个文档, 平均长度{self.avgdl:.1f}")

    def search(self, query: str, top_k: int = 20) -> List[Tuple[str, float]]:
        """
        BM25检索

        Args:
            query: 查询文本
            top_k: 返回top-k结果

        Returns:
            (doc_id, score)列表
        """
        if not self.corpus:
            return []

        query_tokens = self._tokenize(query)

        scores = []
        for idx, doc_freq in enumerate(self.doc_freqs):
            score = 0.0

            for token in query_tokens:
                if token not in self.idf:
                    continue

                idf = self.idf[token]
                tf = doc_freq.get(token, 0)

                # BM25公式
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (
                    1 - self.b + self.b * self.doc_len[idx] / self.avgdl
                )

                score += idf * (numerator / denominator)

            scores.append((self.corpus_ids[idx], score))

        # 排序并返回top-k
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def _tokenize(self, text: str) -> List[str]:
        """
        简单分词（中英文混合）

        Args:
            text: 文本

        Returns:
            词列表
        """
        # 简单的字符级分词（中文）+ 空格分词（英文）
        tokens = []

        # 先按空格分割
        words = text.lower().split()

        for word in words:
            # 如果是英文单词，直接添加
            if word.isascii():
                tokens.append(word)
            else:
                # 中文按字符分割
                tokens.extend(list(word))

        return tokens


class ReciprocalRankFusion:
    """倒数排名融合（RRF）"""

    @staticmethod
    def fuse(
        rankings: List[List[Tuple[str, float]]],
        k: int = 60
    ) -> List[Tuple[str, float]]:
        """
        融合多个排名列表

        Args:
            rankings: 多个排名列表，每个列表包含(doc_id, score)
            k: RRF参数

        Returns:
            融合后的排名列表
        """
        rrf_scores = defaultdict(float)

        for ranking in rankings:
            for rank, (doc_id, _) in enumerate(ranking):
                # RRF公式: 1 / (k + rank)
                rrf_scores[doc_id] += 1.0 / (k + rank + 1)

        # 按RRF分数排序
        fused = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )

        return fused


class BGEReranker:
    """BGE重排序器"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-large"):
        """
        初始化重排序器

        Args:
            model_name: 模型名称
        """
        self.model_name = model_name
        self.model = None
        self._load_model()

    def _load_model(self):
        """加载重排序模型"""
        try:
            from FlagEmbedding import FlagReranker

            self.model = FlagReranker(self.model_name, use_fp16=True)
            logger.info(f"重排序模型加载成功: {self.model_name}")
        except ImportError:
            logger.warning("FlagEmbedding未安装，重排序功能不可用")
            logger.warning("安装: pip install FlagEmbedding")
        except Exception as e:
            logger.error(f"重排序模型加载失败: {e}")

    def rerank(
        self,
        query: str,
        documents: List[Dict],
        top_k: int = 10
    ) -> List[Dict]:
        """
        重排序文档

        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回top-k结果

        Returns:
            重排序后的文档列表
        """
        if not self.model:
            logger.warning("重排序模型未加载，返回原始顺序")
            return documents[:top_k]

        if not documents:
            return []

        try:
            # 准备输入对
            pairs = [[query, doc.get("content", "")] for doc in documents]

            # 计算分数
            scores = self.model.compute_score(pairs)

            # 如果只有一个文档，scores可能是标量
            if not isinstance(scores, list):
                scores = [scores]

            # 按分数排序
            doc_scores = list(zip(documents, scores))
            doc_scores.sort(key=lambda x: x[1], reverse=True)

            # 返回top-k
            reranked = [doc for doc, score in doc_scores[:top_k]]

            logger.debug(f"重排序完成: {len(documents)} -> {len(reranked)}")
            return reranked

        except Exception as e:
            logger.error(f"重排序失败: {e}")
            return documents[:top_k]


class HybridRetriever:
    """混合检索器（Vector + BM25 + Reranker）"""

    def __init__(
        self,
        chroma_collection,
        use_reranker: bool = True,
        reranker_model: str = "BAAI/bge-reranker-large"
    ):
        """
        初始化混合检索器

        Args:
            chroma_collection: ChromaDB集合
            use_reranker: 是否使用重排序
            reranker_model: 重排序模型名称
        """
        self.collection = chroma_collection
        self.bm25 = BM25Retriever()
        self.rrf = ReciprocalRankFusion()
        self.use_reranker = use_reranker

        if use_reranker:
            self.reranker = BGEReranker(reranker_model)
        else:
            self.reranker = None

        self._initialize_bm25()

    def _initialize_bm25(self):
        """初始化BM25索引"""
        try:
            # 获取所有文档
            results = self.collection.get()

            if results and results.get("documents"):
                documents = results["documents"]
                ids = results["ids"]

                # 训练BM25
                self.bm25.fit(documents, ids)
                logger.info(f"BM25索引初始化完成: {len(documents)}个文档")
            else:
                logger.warning("集合为空，BM25索引未初始化")

        except Exception as e:
            logger.error(f"BM25索引初始化失败: {e}")

    def search(
        self,
        query: str,
        top_k: int = 10,
        vector_weight: float = 0.5,
        bm25_weight: float = 0.5
    ) -> List[Dict]:
        """
        混合检索

        Args:
            query: 查询文本
            top_k: 返回top-k结果
            vector_weight: 向量检索权重
            bm25_weight: BM25检索权重

        Returns:
            检索结果列表
        """
        # 1. 向量检索
        vector_results = self._vector_search(query, top_k=20)

        # 2. BM25检索
        bm25_results = self.bm25.search(query, top_k=20)

        # 3. RRF融合
        fused_results = self.rrf.fuse([
            [(doc["id"], doc.get("distance", 0)) for doc in vector_results],
            bm25_results
        ])

        # 4. 获取融合后的文档
        fused_docs = self._get_documents_by_ids(
            [doc_id for doc_id, _ in fused_results[:top_k * 2]]
        )

        # 5. 重排序（可选）
        if self.use_reranker and self.reranker:
            final_results = self.reranker.rerank(query, fused_docs, top_k=top_k)
        else:
            final_results = fused_docs[:top_k]

        logger.info(f"混合检索完成: 向量{len(vector_results)} + BM25{len(bm25_results)} -> 融合{len(fused_docs)} -> 最终{len(final_results)}")

        return final_results

    def _vector_search(self, query: str, top_k: int = 20) -> List[Dict]:
        """向量检索"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )

            documents = []
            if results and results.get("documents"):
                for i in range(len(results["documents"][0])):
                    doc = {
                        "id": results["ids"][0][i],
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                        "distance": results["distances"][0][i] if results.get("distances") else 0
                    }
                    documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            return []

    def _get_documents_by_ids(self, doc_ids: List[str]) -> List[Dict]:
        """根据ID获取文档"""
        try:
            results = self.collection.get(ids=doc_ids)

            documents = []
            if results and results.get("documents"):
                for i in range(len(results["documents"])):
                    doc = {
                        "id": results["ids"][i],
                        "content": results["documents"][i],
                        "metadata": results["metadatas"][i] if results.get("metadatas") else {}
                    }
                    documents.append(doc)

            return documents

        except Exception as e:
            logger.error(f"获取文档失败: {e}")
            return []


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO)

    import chromadb

    # 连接ChromaDB
    client = chromadb.PersistentClient(
        path="f:/Financial_Asset_QA_System_cyx-master/data/chroma_db"
    )

    try:
        collection = client.get_collection("financial_knowledge")

        # 创建混合检索器
        retriever = HybridRetriever(collection, use_reranker=False)

        # 测试查询
        query = "苹果公司2025年Q4的营收是多少"
        results = retriever.search(query, top_k=5)

        print(f"\n查询: {query}")
        print(f"结果数: {len(results)}\n")

        for i, doc in enumerate(results):
            print(f"{i+1}. {doc['content'][:100]}...")
            print(f"   来源: {doc['metadata'].get('source_file', 'N/A')}")
            print()

    except Exception as e:
        print(f"测试失败: {e}")
