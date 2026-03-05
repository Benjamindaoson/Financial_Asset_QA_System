"""
测试RAG Pipeline
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.rag.pipeline import RAGPipeline
from app.models.schemas import KnowledgeResult, Document


class TestRAGPipelineInitialization:
    """测试RAG Pipeline初始化"""

    @patch('app.rag.pipeline.chromadb.PersistentClient')
    @patch('app.rag.pipeline.SentenceTransformer')
    @patch('app.rag.pipeline.FlagReranker')
    def test_pipeline_initialization(self, mock_reranker, mock_transformer, mock_chroma):
        """测试Pipeline初始化"""
        mock_client = Mock()
        mock_collection = Mock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chroma.return_value = mock_client

        pipeline = RAGPipeline()

        assert pipeline is not None
        assert pipeline.chroma_client is not None
        assert pipeline.collection is not None
        mock_chroma.assert_called_once()


class TestRAGPipelineEmbedding:
    """测试嵌入生成"""

    @pytest.fixture
    def pipeline(self):
        """创建pipeline实例"""
        with patch('app.rag.pipeline.chromadb.PersistentClient'), \
             patch('app.rag.pipeline.SentenceTransformer') as mock_transformer, \
             patch('app.rag.pipeline.FlagReranker'):

            mock_model = Mock()
            mock_transformer.return_value = mock_model

            pipeline = RAGPipeline()
            pipeline.embedding_model = mock_model

            return pipeline

    def test_embed_query(self, pipeline):
        """测试查询嵌入"""
        import numpy as np

        mock_embedding = np.array([0.1, 0.2, 0.3])
        pipeline.embedding_model.encode.return_value = mock_embedding

        result = pipeline._embed_query("测试查询")

        assert isinstance(result, list)
        assert len(result) == 3
        pipeline.embedding_model.encode.assert_called_once()


class TestRAGPipelineSearch:
    """测试搜索功能"""

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

            pipeline = RAGPipeline()
            pipeline.embedding_model = mock_model
            pipeline.reranker = mock_ranker

            return pipeline

    @pytest.mark.asyncio
    async def test_search_with_results(self, pipeline):
        """测试搜索返回结果"""
        import numpy as np

        # Mock embedding
        mock_embedding = np.array([0.1, 0.2, 0.3])
        pipeline.embedding_model.encode.return_value = mock_embedding

        # Mock collection query
        pipeline.collection.query.return_value = {
            'documents': [['文档1', '文档2', '文档3']],
            'metadatas': [[
                {'source': 'source1'},
                {'source': 'source2'},
                {'source': 'source3'}
            ]],
            'distances': [[0.1, 0.2, 0.3]]
        }

        # Mock reranker scores
        pipeline.reranker.compute_score.return_value = [0.9, 0.8, 0.7]

        result = await pipeline.search("测试查询")

        assert isinstance(result, KnowledgeResult)
        assert len(result.documents) > 0
        assert result.total_found == 3

    @pytest.mark.asyncio
    async def test_search_no_results(self, pipeline):
        """测试搜索无结果"""
        import numpy as np

        # Mock embedding
        mock_embedding = np.array([0.1, 0.2, 0.3])
        pipeline.embedding_model.encode.return_value = mock_embedding

        # Mock empty results
        pipeline.collection.query.return_value = {
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }

        result = await pipeline.search("测试查询")

        assert isinstance(result, KnowledgeResult)
        assert len(result.documents) == 0
        assert result.total_found == 0

    @pytest.mark.asyncio
    async def test_search_with_low_scores(self, pipeline):
        """测试搜索低分过滤"""
        import numpy as np

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

        # Mock low reranker scores (below threshold)
        pipeline.reranker.compute_score.return_value = [0.1, 0.2]

        result = await pipeline.search("测试查询")

        assert isinstance(result, KnowledgeResult)
        # Low scores should be filtered out
        assert len(result.documents) == 0


class TestRAGPipelineDocumentManagement:
    """测试文档管理"""

    @pytest.fixture
    def pipeline(self):
        """创建pipeline实例"""
        with patch('app.rag.pipeline.chromadb.PersistentClient'), \
             patch('app.rag.pipeline.SentenceTransformer') as mock_transformer, \
             patch('app.rag.pipeline.FlagReranker'):

            mock_model = Mock()
            mock_transformer.return_value = mock_model

            pipeline = RAGPipeline()
            pipeline.embedding_model = mock_model

            return pipeline

    def test_add_documents(self, pipeline):
        """测试添加文档"""
        import numpy as np

        documents = ["文档1", "文档2"]
        metadatas = [{"source": "s1"}, {"source": "s2"}]
        ids = ["id1", "id2"]

        # Mock embeddings
        mock_embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])
        pipeline.embedding_model.encode.return_value = mock_embeddings

        pipeline.add_documents(documents, metadatas, ids)

        pipeline.collection.add.assert_called_once()

    def test_get_collection_count(self, pipeline):
        """测试获取文档数量"""
        pipeline.collection.count.return_value = 100

        count = pipeline.get_collection_count()

        assert count == 100
        pipeline.collection.count.assert_called_once()
