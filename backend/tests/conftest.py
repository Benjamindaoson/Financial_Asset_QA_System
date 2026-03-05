"""
测试配置和fixtures
"""
import pytest
import sys
import os
from unittest.mock import Mock, AsyncMock, patch

# 添加backend到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client"""
    client = Mock()
    client.messages = Mock()
    return client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client"""
    client = Mock()
    client.chat = Mock()
    client.chat.completions = Mock()
    return client


@pytest.fixture
def mock_redis_client():
    """Mock Redis client"""
    client = Mock()
    client.get = Mock(return_value=None)
    client.set = Mock(return_value=True)
    client.ping = Mock(return_value=True)
    return client


@pytest.fixture
def mock_chroma_client():
    """Mock ChromaDB client"""
    client = Mock()
    collection = Mock()
    collection.query = Mock(return_value={
        'documents': [['test document']],
        'metadatas': [[{'source': 'test'}]],
        'distances': [[0.5]]
    })
    client.get_or_create_collection = Mock(return_value=collection)
    return client


@pytest.fixture
def sample_market_data():
    """Sample market data for testing"""
    return {
        'symbol': 'AAPL',
        'price': 150.0,
        'currency': 'USD',
        'name': 'Apple Inc.',
        'source': 'yfinance',
        'timestamp': '2024-03-05T10:00:00'
    }


@pytest.fixture
def sample_history_data():
    """Sample history data for testing"""
    return {
        'symbol': 'AAPL',
        'days': 30,
        'data': [
            {
                'date': '2024-03-01',
                'open': 148.0,
                'high': 152.0,
                'low': 147.0,
                'close': 150.0,
                'volume': 1000000
            }
        ],
        'source': 'yfinance',
        'timestamp': '2024-03-05T10:00:00'
    }


@pytest.fixture
def sample_rag_result():
    """Sample RAG result for testing"""
    return {
        'documents': [
            {
                'content': '市盈率是股票价格与每股收益的比率',
                'source': 'knowledge_base',
                'score': 0.85
            }
        ],
        'total_found': 1
    }
