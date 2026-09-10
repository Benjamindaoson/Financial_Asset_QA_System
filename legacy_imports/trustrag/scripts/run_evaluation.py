"""
Simple evaluation script to get real metrics for TrustRAG.
No external dependencies required.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trust_rag.engine.reasoning import (
    DebateOrchestrator,
    BeamSearchReranker,
    BeamSearchConfig,
    EvidenceNode,
)

def test_multi_agent_debate():
    """Test Multi-Agent Debate and collect metrics."""
    print("\n" + "="*60)
    print("🔬 Testing Multi-Agent Debate System")
    print("="*60)
    
    orchestrator = DebateOrchestrator(max_rounds=3)
    
    test_cases = [
        {
            "query": "What is the revenue of Company X in 2023?",
            "evidence": [
                "Company X reported total revenue of $10.5 billion in fiscal year 2023.",
                "The annual report confirms revenue growth of 15% year-over-year.",
                "Q4 2023 revenue was $2.8 billion, the strongest quarter."
            ],
            "expected_verdict": "VERIFIED"
        },
        {
            "query": "Did Company Y acquire Company Z?",
            "evidence": [
                "Company Y announced plans to acquire Company Z in March 2023.",
                "The acquisition was completed in September 2023 for $500 million.",
            ],
            "expected_verdict": "VERIFIED"
        },
        {
            "query": "What is the profit margin?",
            "evidence": [],  # No evidence
            "expected_verdict": "UNCERTAIN"
        },
        {
            "query": "Is the CEO John Smith?",
            "evidence": [
                "The CEO is Jane Doe, appointed in 2022.",
                "John Smith serves as CFO, not CEO."
            ],
            "expected_verdict": "REFUTED"
        },
    ]
    
    results = []
    for i, tc in enumerate(test_cases):
        print(f"\n--- Test Case {i+1}: {tc['query'][:40]}...")
        result = orchestrator.run_debate(tc["query"], tc["evidence"])
        
        correct = result.final_verdict == tc["expected_verdict"]
        results.append({
            "query": tc["query"],
            "verdict": result.final_verdict,
            "expected": tc["expected_verdict"],
            "correct": correct,
            "confidence": result.confidence,
            "rounds": result.rounds_completed
        })
        
        status = "✅" if correct else "❌"
        print(f"  Verdict: {result.final_verdict} (expected: {tc['expected_verdict']}) {status}")
        print(f"  Confidence: {result.confidence:.2f}")
        print(f"  Rounds: {result.rounds_completed}")
    
    accuracy = sum(1 for r in results if r["correct"]) / len(results)
    avg_confidence = sum(r["confidence"] for r in results) / len(results)
    avg_rounds = sum(r["rounds"] for r in results) / len(results)
    
    print(f"\n📊 Multi-Agent Debate Metrics:")
    print(f"  - Accuracy: {accuracy*100:.1f}%")
    print(f"  - Avg Confidence: {avg_confidence:.2f}")
    print(f"  - Avg Rounds: {avg_rounds:.1f}")
    
    return {"accuracy": accuracy, "avg_confidence": avg_confidence, "avg_rounds": avg_rounds}


def test_beam_search():
    """Test Beam Search Reranker and collect metrics."""
    print("\n" + "="*60)
    print("🔬 Testing Beam Search Path Reranker")
    print("="*60)
    
    config = BeamSearchConfig(beam_width=5, max_depth=4)
    reranker = BeamSearchReranker(config)
    
    # Build a test graph
    nodes = [
        EvidenceNode("company", "Company X financial data", "entity", 0.95),
        EvidenceNode("revenue", "Revenue is $10.5 billion in 2023", "fact", 0.90),
        EvidenceNode("growth", "Growth rate is 15% year-over-year", "fact", 0.85),
        EvidenceNode("report", "Annual Report 2023 official document", "document", 0.98),
        EvidenceNode("ceo", "CEO Jane Doe leadership", "entity", 0.88),
        EvidenceNode("strategy", "Strategic initiatives for expansion", "fact", 0.75),
    ]
    
    edges = [
        {"source": "company", "target": "revenue", "relation": "has_metric", "weight": 0.9},
        {"source": "company", "target": "ceo", "relation": "has_leader", "weight": 0.85},
        {"source": "revenue", "target": "growth", "relation": "implies", "weight": 0.8},
        {"source": "revenue", "target": "report", "relation": "from_document", "weight": 0.95},
        {"source": "ceo", "target": "strategy", "relation": "defines", "weight": 0.7},
        {"source": "growth", "target": "report", "relation": "from_document", "weight": 0.9},
    ]
    
    reranker.build_graph(nodes, edges)
    
    test_queries = [
        ("What is the revenue?", ["company"]),
        ("Who is the CEO?", ["company"]),
        ("What is the growth rate?", ["company"]),
    ]
    
    total_paths = 0
    total_score = 0
    total_coherence = 0
    
    for query, start in test_queries:
        print(f"\n--- Query: {query}")
        paths = reranker.search(query, start)
        
        if paths:
            best = paths[0]
            print(f"  Best path: {' -> '.join(n.node_id for n in best.nodes)}")
            print(f"  Score: {best.score:.3f}, Coherence: {best.coherence:.3f}")
            print(f"  Path length: {len(best.nodes)}")
            total_paths += len(paths)
            total_score += best.score
            total_coherence += best.coherence
        else:
            print("  No paths found")
    
    n = len(test_queries)
    print(f"\n📊 Beam Search Metrics:")
    print(f"  - Avg paths found: {total_paths/n:.1f}")
    print(f"  - Avg best score: {total_score/n:.3f}")
    print(f"  - Avg coherence: {total_coherence/n:.3f}")
    
    return {"avg_paths": total_paths/n, "avg_score": total_score/n, "avg_coherence": total_coherence/n}


if __name__ == "__main__":
    print("🚀 TrustRAG Evaluation Suite")
    print("="*60)
    
    debate_metrics = test_multi_agent_debate()
    beam_metrics = test_beam_search()
    
    print("\n" + "="*60)
    print("📈 FINAL EVALUATION SUMMARY")
    print("="*60)
    print(f"\nMulti-Agent Debate:")
    print(f"  ✓ Verdict Accuracy: {debate_metrics['accuracy']*100:.1f}%")
    print(f"  ✓ Avg Confidence: {debate_metrics['avg_confidence']:.2f}")
    
    print(f"\nBeam Search Reranker:")
    print(f"  ✓ Avg Path Score: {beam_metrics['avg_score']:.3f}")
    print(f"  ✓ Avg Coherence: {beam_metrics['avg_coherence']:.3f}")
    
    print("\n✅ All tests completed successfully!")

