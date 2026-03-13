"""
混合检索管道 - 结合向量检索和BM25
Hybrid Retrieval Pipeline combining vector search and BM25
"""
from typing import List, Dict, Any
import numpy as np
from rank_bm25 import BM25Okapi
import jieba
from app.rag.pipeline import RAGPipeline
from app.models import KnowledgeResult, Document


class HybridRAGPipeline(RAGPipeline):
    """
    混合检索管道：向量检索 + BM25 + 重排序

    检索流程：
    1. 向量检索 (Top-K=20)
    2. BM25检索 (Top-K=20)
    3. RRF融合 (Reciprocal Rank Fusion)
    4. 重排序 (Top-N=3)
    """

    def __init__(self):
        super().__init__()
        self.bm25_index = None
        self.corpus_texts = []
        self.corpus_ids = []

    def build_bm25_index(self, documents: List[str], doc_ids: List[str]):
        """
        构建BM25索引

        Args:
            documents: 文档文本列表
            doc_ids: 文档ID列表
        """
        # 使用jieba分词
        tokenized_corpus = [list(jieba.cut(doc)) for doc in documents]

        # 构建BM25索引
        self.bm25_index = BM25Okapi(tokenized_corpus)
        self.corpus_texts = documents
        self.corpus_ids = doc_ids

        print(f"[BM25] 索引已构建，文档数: {len(documents)}")

    def _bm25_search(self, query: str, top_k: int = 20) -> List[Dict[str, Any]]:
        """
        BM25检索

        Args:
            query: 查询文本
            top_k: 返回Top-K结果

        Returns:
            检索结果列表
        """
        if not self.bm25_index:
            return []

        # 分词
        query_tokens = list(jieba.cut(query))

        # 计算BM25分数
        scores = self.bm25_index.get_scores(query_tokens)

        # 获取Top-K索引
        top_indices = np.argsort(scores)[-top_k:][::-1]

        # 构建结果
        results = []
        for idx in top_indices:
            if scores[idx] > 0:  # 只返回有分数的结果
                results.append({
                    'doc_id': self.corpus_ids[idx],
                    'text': self.corpus_texts[idx],
                    'score': float(scores[idx]),
                    'rank': len(results) + 1
                })

        return results

    def _rrf_fusion(
        self,
        vector_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        k: int = 60
    ) -> List[Dict[str, Any]]:
        """
        RRF (Reciprocal Rank Fusion) 融合算法

        RRF Score = sum(1 / (k + rank))

        Args:
            vector_results: 向量检索结果
            bm25_results: BM25检索结果
            k: RRF参数（默认60）

        Returns:
            融合后的结果
        """
        # 收集所有文档
        doc_scores = {}

        # 向量检索结果
        for result in vector_results:
            doc_id = result['doc_id']
            rank = result['rank']
            rrf_score = 1.0 / (k + rank)

            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    'doc_id': doc_id,
                    'text': result['text'],
                    'vector_score': result['score'],
                    'bm25_score': 0.0,
                    'rrf_score': 0.0
                }

            doc_scores[doc_id]['rrf_score'] += rrf_score

        # BM25检索结果
        for result in bm25_results:
            doc_id = result['doc_id']
            rank = result['rank']
            rrf_score = 1.0 / (k + rank)

            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    'doc_id': doc_id,
                    'text': result['text'],
                    'vector_score': 0.0,
                    'bm25_score': result['score'],
                    'rrf_score': 0.0
                }
            else:
                doc_scores[doc_id]['bm25_score'] = result['score']

            doc_scores[doc_id]['rrf_score'] += rrf_score

        # 按RRF分数排序
        fused_results = sorted(
            doc_scores.values(),
            key=lambda x: x['rrf_score'],
            reverse=True
        )

        return fused_results

    async def search(self, query: str, use_hybrid: bool = True) -> KnowledgeResult:
        """
        混合检索

        Args:
            query: 查询文本
            use_hybrid: 是否使用混合检索（False则仅使用向量检索）

        Returns:
            检索结果
        """
        # 1. 向量检索
        vector_result = await super().search(query)

        if not use_hybrid or not self.bm25_index:
            # 如果不使用混合检索或BM25索引未构建，直接返回向量检索结果
            return vector_result

        # 转换向量检索结果格式
        vector_results = [
            {
                'doc_id': doc.source,
                'text': doc.content,
                'score': doc.score,
                'rank': i + 1
            }
            for i, doc in enumerate(vector_result.documents)
        ]

        # 2. BM25检索
        bm25_results = self._bm25_search(query, top_k=20)

        # 3. RRF融合
        fused_results = self._rrf_fusion(vector_results, bm25_results)

        # 4. 准备重排序候选
        # 取融合后的Top-20进行重排序
        candidates = []
        for result in fused_results[:20]:
            candidates.append({
                'content': result['text'],
                'source': result['doc_id'],
                'distance': 1.0 - result['rrf_score']  # 转换为距离
            })

        # 5. 重排序
        if candidates:
            pairs = [[query, cand['content']] for cand in candidates]
            scores = self.reranker.compute_score(pairs, normalize=True)

            if not isinstance(scores, list):
                scores = [scores]

            # 组合重排序分数
            ranked = []
            for i, score in enumerate(scores):
                if score >= 0.3:  # 降低阈值以获得更多结果
                    ranked.append({
                        'content': candidates[i]['content'],
                        'source': candidates[i]['source'],
                        'score': float(score)
                    })

            # 按分数排序
            ranked.sort(key=lambda x: x['score'], reverse=True)
            top_results = ranked[:3]

            # 转换为Document模型
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
                total_found=len(fused_results)
            )

        # 如果没有候选结果，返回空
        return KnowledgeResult(documents=[], total_found=0)
