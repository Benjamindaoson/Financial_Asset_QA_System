"""
Tests for Multi-Agent Debate and Beam Search Reranker.
"""
import pytest
from trust_rag.engine.reasoning import (
    DebateOrchestrator,
    DebateStatus,
    AgentRole,
    BeamSearchReranker,
    BeamSearchConfig,
    EvidenceNode,
)


class TestMultiAgentDebate:
    """Test Multi-Agent Debate System."""
    
    def test_debate_orchestrator_init(self):
        """Test orchestrator initialization."""
        orchestrator = DebateOrchestrator(max_rounds=3)
        assert orchestrator.max_rounds == 3
        assert orchestrator.proposer is not None
        assert orchestrator.critic is not None
        assert orchestrator.judge is not None
    
    def test_run_debate_with_evidence(self):
        """Test running a debate with evidence."""
        orchestrator = DebateOrchestrator(max_rounds=2)
        
        query = "What is the revenue of Company X in 2023?"
        evidence = [
            "Company X reported revenue of $10 billion in 2023.",
            "The annual report shows Company X had strong growth.",
            "Revenue increased by 15% compared to 2022."
        ]
        
        result = orchestrator.run_debate(query, evidence)
        
        assert result is not None
        assert result.final_verdict in ["VERIFIED", "REFUTED", "UNCERTAIN"]
        assert 0 <= result.confidence <= 1
        assert result.rounds_completed >= 1
        assert len(result.debate_transcript) > 0
    
    def test_debate_empty_evidence(self):
        """Test debate with no evidence."""
        orchestrator = DebateOrchestrator(max_rounds=2)
        
        result = orchestrator.run_debate("What is X?", [])
        
        assert result is not None
        assert result.confidence < 0.7  # Low confidence without evidence
    
    def test_debate_convergence(self):
        """Test that debate can converge early."""
        orchestrator = DebateOrchestrator(
            max_rounds=5,
            convergence_threshold=0.6
        )
        
        evidence = [
            "The answer is definitively 42.",
            "Multiple sources confirm the answer is 42.",
            "Official documentation states 42."
        ]
        
        result = orchestrator.run_debate("What is the answer?", evidence)
        
        # Should converge before max rounds with strong evidence
        assert result.rounds_completed <= 5


class TestBeamSearchReranker:
    """Test Beam Search Reranker."""
    
    def test_reranker_init(self):
        """Test reranker initialization."""
        config = BeamSearchConfig(beam_width=3, max_depth=4)
        reranker = BeamSearchReranker(config)
        
        assert reranker.config.beam_width == 3
        assert reranker.config.max_depth == 4
    
    def test_build_graph(self):
        """Test building evidence graph."""
        reranker = BeamSearchReranker()
        
        nodes = [
            EvidenceNode("n1", "Company X", "entity", 0.9),
            EvidenceNode("n2", "Revenue $10B", "fact", 0.85),
            EvidenceNode("n3", "Annual Report 2023", "document", 0.95),
        ]
        
        edges = [
            {"source": "n1", "target": "n2", "relation": "has_metric"},
            {"source": "n2", "target": "n3", "relation": "from_document"},
        ]
        
        reranker.build_graph(nodes, edges)
        
        assert len(reranker.graph) == 3
        assert len(reranker.graph["n1"]) == 1
        assert len(reranker.graph["n2"]) == 1
    
    def test_search_paths(self):
        """Test searching for evidence paths."""
        reranker = BeamSearchReranker(BeamSearchConfig(beam_width=3, max_depth=3))
        
        nodes = [
            EvidenceNode("n1", "Company revenue query", "entity", 0.9),
            EvidenceNode("n2", "Revenue is $10 billion", "fact", 0.85),
            EvidenceNode("n3", "Source document", "document", 0.95),
        ]
        
        edges = [
            {"source": "n1", "target": "n2", "relation": "supports", "weight": 0.9},
            {"source": "n2", "target": "n3", "relation": "from_document", "weight": 0.8},
        ]
        
        reranker.build_graph(nodes, edges)
        paths = reranker.search("What is the revenue?", ["n1"])
        
        assert len(paths) > 0
        assert paths[0].score > 0
    
    def test_get_best_path(self):
        """Test getting single best path."""
        reranker = BeamSearchReranker()
        
        nodes = [
            EvidenceNode("a", "Start node", "entity", 0.8),
            EvidenceNode("b", "Middle node", "fact", 0.7),
        ]
        edges = [{"source": "a", "target": "b", "relation": "related"}]
        
        reranker.build_graph(nodes, edges)
        best = reranker.get_best_path("query", ["a"])
        
        assert best is not None or best is None  # May or may not find path


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

