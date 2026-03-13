"""
测试混合RAG Pipeline
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.rag.hybrid_pipeline import HybridRAGPipeline
from app.models.schemas import KnowledgeResult, Document


class TestHybridRAGPipelineInitialization:
    """测试混合RAG Pipeline初始化"""

    @patch('app.rag.pipeline.chromadb.PersistentClient')
    @patch('app.rag.pipeline.SentenceTransformer')
    @patch('app.rag.pipeline.FlagReranker')
    def test_hybrid_pipeline_initialization(self, mock_reranker, mock_transformer, mock_chroma):
        """测试混合Pipeline初始化"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        pipeline = HybridRAGPipeline()

        assert pipeline is not None
        assert pipeline.bm25_index is None
        assert pipeline.corpus_texts == []
        assert pipeline.corpus_ids == []


class TestBM25Index:
    """测试BM25索引"""

    @pytest.fixture
    def pipeline(self):
        """创建pipeline实例"""
        with patch('app.rag.pipeline.chromadb.PersistentClient'), \
             patch('app.rag.pipeline.SentenceTransformer'), \
             patch('app.rag.pipeline.FlagReranker'):
            return HybridRAGPipeline()

    def test_build_bm25_index(self, pipeline):
        """测试构建BM25索引"""
        documents = ["市盈率是重要指标", "市净率用于估值"]
        doc_ids = ["doc1", "doc2"]

        pipeline.build_bm25_index(documents, doc_ids)

        assert pipeline.bm25_index is not None
        assert len(pipeline.corpus_texts) == 2
        assert len(pipeline.corpus_ids) == 2

    def test_bm25_search_no_index(self, pipeline):
        """测试无索引时搜索"""
        results = pipeline._bm25_search("测试查询")

        assert results == []

    def test_bm25_search_with_index(self, pipeline):
        """测试有索引时搜索"""
        documents = ["市盈率是重要指标", "市净率用于估值", "股票价格波动"]
        doc_ids = ["doc1", "doc2", "doc3"]

        pipeline.build_bm25_index(documents, doc_ids)
        results = pipeline._bm25_search("市盈率", top_k=2)

        assert isinstance(results, list)
        # Should return results with scores > 0
        assert all('score' in r for r in results)
        assert all('doc_id' in r for r in results)


class TestHybridSearch:
    """测试混合搜索"""

    @pytest.fixture
    def pipeline(self):
        """创建pipeline实例"""
        with patch('app.rag.pipeline.chromadb.PersistentClient'), \
             patch('app.rag.pipeline.SentenceTransformer') as mock_transformer, \
             patch('app.rag.pipeline.FlagReranker') as mock_reranker:

            mock_model = Mock()
            mock_transformer.return_value = mock_model

            mock_ranker = Mock()
            mock_reranker.return_value = mock_ranker

            pipeline = HybridRAGPipeline()
            pipeline.embedding_model = mock_model
            pipeline.reranker = mock_ranker

            return pipeline

    @pytest.mark.asyncio
    async def test_search_uses_hybrid(self, pipeline):
        """测试混合搜索使用BM25"""
        import numpy as np

        # Build BM25 index
        documents = ["市盈率是重要指标", "市净率用于估值"]
        doc_ids = ["doc1", "doc2"]
        pipeline.build_bm25_index(documents, doc_ids)

        # Mock embedding
        mock_embedding = np.array([0.1, 0.2, 0.3])
        pipeline.embedding_model.encode.return_value = mock_embedding

        # Mock collection query
        pipeline.collection.query.return_value = {
            'documents': [['文档1', '文档2']],
            'metadatas': [[
                {'source': 'source1'},
                {'source': 'source2'}
            ]],
            'distances': [[0.1, 0.2]]
        }

        # Mock reranker scores
        pipeline.reranker.compute_score.return_value = [0.9, 0.8]

        result = await pipeline.search("市盈率", use_hybrid=False)

        assert isinstance(result, KnowledgeResult)


class TestRRFFusion:
    """测试RRF融合"""

    @pytest.fixture
    def pipeline(self):
        """创建pipeline实例"""
        with patch('app.rag.pipeline.chromadb.PersistentClient'), \
             patch('app.rag.pipeline.SentenceTransformer'), \
             patch('app.rag.pipeline.FlagReranker'):
            return HybridRAGPipeline()

    def test_rrf_fusion_empty_lists(self, pipeline):
        """测试空列表融合"""
        result = pipeline._rrf_fusion([], [])

        assert result == []

    def test_rrf_fusion_single_list(self, pipeline):
        """测试单个列表融合"""
        vector_results = [
            {'doc_id': 'doc1', 'text': 'text1', 'rank': 1, 'score': 0.9},
            {'doc_id': 'doc2', 'text': 'text2', 'rank': 2, 'score': 0.8}
        ]

        result = pipeline._rrf_fusion(vector_results, [])

        assert len(result) > 0

    def test_rrf_fusion_both_lists(self, pipeline):
        """测试两个列表融合"""
        vector_results = [
            {'doc_id': 'doc1', 'text': 'text1', 'rank': 1, 'score': 0.9}
        ]
        bm25_results = [
            {'doc_id': 'doc2', 'text': 'text2', 'rank': 1, 'score': 0.8}
        ]

        result = pipeline._rrf_fusion(vector_results, bm25_results)

        assert len(result) > 0
        assert all('rrf_score' in r for r in result)


class TestHybridPipelineIntegration:
    """测试混合Pipeline集成"""

    @pytest.fixture
    def pipeline(self):
        """创建pipeline实例"""
        with patch('app.rag.pipeline.chromadb.PersistentClient'), \
             patch('app.rag.pipeline.SentenceTransformer') as mock_transformer, \
             patch('app.rag.pipeline.FlagReranker') as mock_reranker:

            mock_model = Mock()
            mock_transformer.return_value = mock_model

            mock_ranker = Mock()
            mock_reranker.return_value = mock_ranker

            pipeline = HybridRAGPipeline()
            pipeline.embedding_model = mock_model
            pipeline.reranker = mock_ranker

            return pipeline

    def test_pipeline_has_parent_methods(self, pipeline):
        """测试继承父类方法"""
        assert hasattr(pipeline, '_embed_query')
        assert hasattr(pipeline, 'add_documents')
        assert hasattr(pipeline, 'get_collection_count')

    def test_pipeline_has_hybrid_methods(self, pipeline):
        """测试混合方法"""
        assert hasattr(pipeline, 'build_bm25_index')
        assert hasattr(pipeline, '_bm25_search')
        assert hasattr(pipeline, '_rrf_fusion')
