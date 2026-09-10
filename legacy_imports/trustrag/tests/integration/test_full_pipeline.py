"""
TrustRAG Full Pipeline Integration Tests.

Tests the complete flow:
1. Document ingestion
2. Index loading
3. Query processing
4. Evidence selection
5. Answer generation
6. Post-binding verification
"""
import os
import sys
import json
import tempfile
import shutil
import pytest

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from trust_rag.system import TrustRAG, SystemResult
from trust_rag.config import get_config, reload_config
from trust_rag.engine.ingest.pipeline import IngestPipeline
from trust_rag.engine.retrieval.index_loader import IndexLoader
from trust_rag.engine.retrieval.adapter import RetrievalAdapter
from trust_rag.core.judgment.orchestrator import JudgmentOrchestrator
from trust_rag.core.judgment.validation import PostBindingVerifier
from trust_rag.engine.generation.prompts import AnswerPromptGenerator


class TestSystemInitialization:
    """Test system initialization and configuration."""
    
    def test_system_initializes(self):
        """System should initialize without errors."""
        rag = TrustRAG(artifact_dir="artifacts", auto_load_index=False)
        assert rag is not None
        assert rag.profiler is not None
        assert rag.planner is not None
        assert rag.retrieval_adapter is not None
        assert rag.judgment is not None
    
    def test_config_loads(self):
        """Configuration should load with defaults."""
        config = get_config()
        assert config is not None
        assert config.paths is not None
        assert config.feature_flags is not None
        assert config.query_thresholds.confidence_threshold == 0.7
    
    def test_index_loader_handles_empty_dir(self):
        """IndexLoader should handle empty/missing directory."""
        loader = IndexLoader(ingestion_dir="/nonexistent/path")
        chunks = loader.load_all_chunks()
        assert chunks == []


class TestRetrievalAdapter:
    """Test retrieval adapter with real text search."""
    
    def setup_method(self):
        """Set up test adapter with sample data."""
        self.adapter = RetrievalAdapter()
        
        # Sample documents
        self.sample_docs = [
            {
                "chunk_id": "chunk_1",
                "evidence_id": "ev_001",
                "doc_id": "nvidia_fy2023",
                "text": "Nvidia's total revenue for fiscal year 2023 was $60.9 billion USD, representing significant growth.",
                "modality": "text_native",
                "page_number": 5
            },
            {
                "chunk_id": "chunk_2",
                "evidence_id": "ev_002",
                "doc_id": "nvidia_fy2023",
                "text": "Net income for FY2023 reached $29.7 billion, driven by strong data center sales.",
                "modality": "text_native",
                "page_number": 10
            },
            {
                "chunk_id": "chunk_3",
                "evidence_id": "ev_003",
                "doc_id": "nvidia_fy2023",
                "text": "Gross profit margin improved to 56.9% compared to prior year.",
                "modality": "table_native",
                "page_number": 15
            }
        ]
        
        self.adapter.seed_mock_data("base", self.sample_docs)
    
    def test_text_search_returns_results(self):
        """Text search should return relevant results."""
        from trust_rag.engine.retrieval.adapter import RetrievalRequest, RetrievalStrategy
        
        request = RetrievalRequest(
            query="What was Nvidia's revenue?",
            tier="base",
            strategy=RetrievalStrategy.SPARSE,
            top_k=5
        )
        
        results = self.adapter.search(request)
        
        assert len(results) > 0
        # First result should be about revenue
        assert "revenue" in results[0].text.lower() or "60.9" in results[0].text
    
    def test_search_scores_relevance(self):
        """Search should score relevant documents higher."""
        from trust_rag.engine.retrieval.adapter import RetrievalRequest, RetrievalStrategy
        
        request = RetrievalRequest(
            query="net income profit billion",
            tier="base",
            strategy=RetrievalStrategy.SPARSE,
            top_k=5
        )
        
        results = self.adapter.search(request)
        
        # Net income doc should score high
        net_income_found = any("net income" in r.text.lower() for r in results[:2])
        assert net_income_found
    
    def test_document_count(self):
        """Should track document counts per tier."""
        counts = self.adapter.get_document_count()
        assert counts["base"] == 3


class TestJudgmentOrchestrator:
    """Test judgment orchestrator with evidence selection."""
    
    def setup_method(self):
        """Set up orchestrator."""
        self.orchestrator = JudgmentOrchestrator()
    
    def test_empty_candidates_refused(self):
        """Empty candidates should result in REFUSE."""
        from trust_rag.core.profile import QueryProfile, QueryIntent, RiskLevel
        
        profile = QueryProfile(
            raw_query="test",
            intents=[QueryIntent.FACTUAL],
            risk_level=RiskLevel.MEDIUM
        )
        
        verdict = self.orchestrator.arbitrate("test query", [], profile)
        
        assert verdict.status == "REFUSE"
        assert "No supporting evidence" in verdict.reason or "未在文档库中找到支持证据" in verdict.reason
    
    def test_valid_candidates_allowed(self):
        """Valid candidates should result in ALLOW."""
        from trust_rag.core.profile import QueryProfile, QueryIntent, RiskLevel
        from trust_rag.engine.retrieval.scored_chunk import ScoredChunk, ScoreBreakdown
        
        profile = QueryProfile(
            raw_query="What was revenue?",
            intents=[QueryIntent.FACTUAL],
            risk_level=RiskLevel.LOW
        )
        
        candidates = [
            ScoredChunk(
                chunk_id="chunk_1",
                evidence_id="ev_001",
                doc_id="test_doc",
                text="Revenue was $60.9 billion USD.",
                tier="base",
                strategy="sparse",
                scores=ScoreBreakdown(
                    dense=0.8,
                    sparse=0.9,
                    anchor=0.0,
                    final=0.85
                ),
                ingest_status="OK"
            )
        ]
        
        verdict = self.orchestrator.arbitrate("What was revenue?", candidates, profile)
        
        assert verdict.status == "ALLOW"
        assert verdict.confidence > 0


class TestAnswerGeneration:
    """Test answer generation from evidence."""
    
    def setup_method(self):
        """Set up generator."""
        self.generator = AnswerPromptGenerator()
    
    def test_generates_answer_from_evidence(self):
        """Should generate answer from evidence bindings."""
        from trust_rag.engine.retrieval.scored_chunk import ScoredChunk, ScoreBreakdown
        
        evidence = ScoredChunk(
            chunk_id="chunk_1",
            evidence_id="ev_001",
            doc_id="nvidia_fy2023",
            text="Nvidia's total revenue for FY2023 was $60.9 billion.",
            tier="base",
            strategy="sparse",
            scores=ScoreBreakdown(final=0.9)
        )
        
        bindings = {
            "query": "What was Nvidia's revenue?",
            "core_evidence": [evidence]
        }
        
        answer = self.generator.generate_answer("What was Nvidia's revenue?", bindings)
        
        assert answer is not None
        assert len(answer) > 0
        # Should contain value from evidence
        assert "60.9" in answer or "billion" in answer.lower()
    
    def test_no_hardcoded_responses(self):
        """Should not return hardcoded responses for unknown queries."""
        bindings = {"core_evidence": []}
        
        answer = self.generator.generate_answer("What is the meaning of life?", bindings)
        
        # Should indicate no evidence, not a made-up answer
        assert "unable" in answer.lower() or "no" in answer.lower()


class TestPostBindingVerification:
    """Test post-binding verification."""
    
    def setup_method(self):
        """Set up verifier."""
        self.verifier = PostBindingVerifier()
    
    def test_verifies_grounded_answer(self):
        """Should pass verification for grounded answer."""
        answer = "Nvidia's revenue was $60.9 billion in FY2023."
        bindings = {
            "core_evidence": [
                {"text": "Nvidia Corporation total revenue for fiscal year 2023 was $60.9 billion USD."}
            ]
        }
        
        result = self.verifier.verify(answer, bindings, query="What was Nvidia's revenue?")
        
        # Should pass even with minor issues
        assert result.passed
        # Numbers should be grounded (no high severity issues)
        high_issues = [i for i in result.issues if i.severity == "high"]
        assert len(high_issues) == 0
    
    def test_detects_ungrounded_numbers(self):
        """Should detect numbers not in evidence."""
        answer = "Revenue was $999 trillion."
        bindings = {
            "core_evidence": [
                {"text": "Total revenue was $60.9 billion USD."}
            ]
        }
        
        result = self.verifier.verify(answer, bindings)
        
        # Should flag the ungrounded number
        has_ungrounded_issue = any(
            i.issue_type == "ungrounded_number" 
            for i in result.issues
        )
        assert has_ungrounded_issue


class TestEndToEndQuery:
    """Test complete query flow."""
    
    def setup_method(self):
        """Set up system with test data."""
        self.rag = TrustRAG(artifact_dir="artifacts", auto_load_index=False)
        
        # Seed test data directly into adapter
        test_docs = [
            {
                "chunk_id": "test_chunk_1",
                "evidence_id": "test_ev_001",
                "doc_id": "nvidia_fy2023",
                "text": "Nvidia Corporation reported total revenue of $60.9 billion for the fiscal year 2023.",
                "modality": "text_native",
                "page_number": 1
            },
            {
                "chunk_id": "test_chunk_2",
                "evidence_id": "test_ev_002",
                "doc_id": "nvidia_fy2023",
                "text": "Net income for FY2023 was $29.7 billion, up significantly from prior year.",
                "modality": "text_native",
                "page_number": 2
            }
        ]
        
        self.rag.retrieval.adapter.seed_mock_data("base", test_docs)
    
    def test_fast_path_query(self):
        """Fast path should return verified result."""
        result = self.rag.process_query("What was Nvidia's revenue for FY2023?")
        
        assert result is not None
        assert result.verdict in ["VERIFIED", "REFUSED"]
        assert result.trace_id.startswith("tr_")
    
    def test_out_of_scope_refused(self):
        """Out of scope queries should be refused."""
        result = self.rag.process_query("Who won the World Cup in France?")
        
        # Should be refused as non-financial
        assert result.verdict == "REFUSED"
    
    def test_retrieval_based_query(self):
        """Retrieval-based query should work with seeded data."""
        result = self.rag.process_query("What was Nvidia net income?")
        
        assert result is not None
        assert result.trace_id is not None
        
        # Should either find evidence or refuse
        if result.verdict == "VERIFIED":
            assert result.answer is not None
            assert result.answer.confidence > 0


class TestCanonicalFactStore:
    """Test canonical fact store with aliases."""
    
    def setup_method(self):
        """Set up fact store with test data."""
        self.temp_dir = tempfile.mkdtemp()
        self.fact_file = os.path.join(self.temp_dir, "facts.jsonl")
        
        # Create test facts
        facts = [
            {"type": "header", "version": "1.0", "count": 2},
            {
                "entity": "Nvidia",
                "metric": "revenue",
                "period": "FY2023",
                "value": 60.9,
                "unit": "B USD",
                "source_evidence_ids": ["ev_1"],
                "authority_rank": 1,
                "aliases": ["total revenue", "sales"]
            },
            {
                "entity": "Apple",
                "metric": "revenue",
                "period": "FY2023",
                "value": 383.3,
                "unit": "B USD",
                "source_evidence_ids": ["ev_2"],
                "authority_rank": 1
            }
        ]
        
        with open(self.fact_file, "w") as f:
            for fact in facts:
                f.write(json.dumps(fact) + "\n")
        
        from trust_rag.core.offline.canonical_fact_store import CanonicalFactStore
        self.store = CanonicalFactStore(self.fact_file)
    
    def teardown_method(self):
        """Clean up temp files."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_exact_lookup(self):
        """Should find fact with exact match."""
        fact = self.store.lookup("revenue", "FY2023", "Nvidia")
        
        assert fact is not None
        assert fact.value == 60.9
        assert fact.entity == "Nvidia"
    
    def test_alias_lookup(self):
        """Should find fact using metric alias."""
        fact = self.store.lookup("total revenue", "FY2023", "Nvidia")
        
        assert fact is not None
        assert fact.metric == "revenue"
    
    def test_entity_alias_lookup(self):
        """Should find fact using entity alias."""
        fact = self.store.lookup("revenue", "FY2023", "nvda")
        
        assert fact is not None
        assert fact.entity == "Nvidia"
    
    def test_multiple_entities(self):
        """Should differentiate between entities."""
        nvidia = self.store.lookup("revenue", "FY2023", "Nvidia")
        apple = self.store.lookup("revenue", "FY2023", "Apple")
        
        assert nvidia.value == 60.9
        assert apple.value == 383.3


class TestIndexLoader:
    """Test index loader functionality."""
    
    def setup_method(self):
        """Create temp directory with test chunks."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test document directory
        doc_dir = os.path.join(self.temp_dir, "test_doc")
        os.makedirs(doc_dir)
        
        # Create chunks file
        chunks = [
            {
                "evidence_id": "ev_test_1",
                "text": "Test chunk content about revenue.",
                "doc_id": "test_doc",
                "page_number": 1,
                "modality": "text",
                "granularity": "composite"
            },
            {
                "evidence_id": "ev_test_2",
                "text": "Another test chunk about profit.",
                "doc_id": "test_doc",
                "page_number": 2,
                "modality": "text",
                "granularity": "atomic"
            }
        ]
        
        with open(os.path.join(doc_dir, "chunks.jsonl"), "w") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk) + "\n")
        
        self.loader = IndexLoader(ingestion_dir=self.temp_dir)
    
    def teardown_method(self):
        """Clean up temp directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_loads_chunks(self):
        """Should load chunks from directory."""
        chunks = self.loader.load_all_chunks()
        
        assert len(chunks) == 2
        assert chunks[0]["evidence_id"] == "ev_test_1"
    
    def test_organizes_by_tier(self):
        """Should organize chunks by tier."""
        self.loader.load_all_chunks()
        by_tier = self.loader.get_chunks_by_tier()
        
        # Atomic should go to micro, composite to base
        assert len(by_tier["micro"]) == 1
        assert len(by_tier["base"]) == 1
    
    def test_seeds_adapter(self):
        """Should seed adapter with chunks."""
        adapter = RetrievalAdapter()
        stats = self.loader.seed_adapter(adapter)
        
        assert stats.total_chunks == 2
        assert "test_doc" in stats.documents


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

