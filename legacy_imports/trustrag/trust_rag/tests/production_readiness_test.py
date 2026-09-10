import os
import logging
import pytest
from trust_rag.system import TrustRAG
from trust_rag.config import get_config
from trust_rag.core.monitoring import get_monitor

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_config_structure():
    """Verify that the refactored configuration structure is correct."""
    config = get_config()
    
    # Check DatabaseConfig (consolidated from VectorStoreConfig)
    assert hasattr(config, 'database')
    assert hasattr(config.database, 'host')
    assert hasattr(config.database, 'port')
    assert hasattr(config.database, 'vector_dim')
    
    # Check RerankConfig (renamed from RerankerConfig)
    assert hasattr(config, 'rerank')
    assert hasattr(config.rerank, 'model_name')
    assert hasattr(config.rerank, 'max_candidates')
    
    logger.info("✅ Configuration structure verified")

def test_system_initialization():
    """Verify that TrustRAG initializes correctly with the new config handles."""
    # Force dev mode for testing if postgres is not available
    os.environ["TRUSTRAG_ENV"] = "dev"
    
    rag = TrustRAG()
    
    assert rag.profiler is not None
    assert rag.planner is not None
    assert rag.retrieval_adapter is not None
    assert rag.judgment is not None
    
    logger.info("✅ TrustRAG system initialization verified")

def test_retrieval_pipeline_flow():
    """Verify end-to-end retrieval flow with mock/dev setup."""
    os.environ["TRUSTRAG_ENV"] = "dev"
    rag = TrustRAG()
    
    query = "What is the net profit of Apple in 2023?"
    
    # This should trigger the retrieval pipeline
    results = rag.process_query(query)
    
    assert results.verdict in ["VERIFIED", "REFUSED", "CONFLICT"]
    if results.answer:
        assert isinstance(results.answer.text, str)
    
    # Check monitoring record
    monitor = get_monitor()
    stats = monitor.get_operation_stats("query_processing")
    assert stats["count"] > 0
    
    logger.info("DONE: Retrieval pipeline flow verified")

if __name__ == "__main__":
    # Manual execution
    try:
        test_config_structure()
        test_system_initialization()
        test_retrieval_pipeline_flow()
        print("\nALL PRODUCTION READINESS TESTS PASSED!")
    except Exception as e:
        print(f"\nTEST FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
