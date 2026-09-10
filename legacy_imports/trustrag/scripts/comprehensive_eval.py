"""
Comprehensive TrustRAG Evaluation Suite.
Generates real metrics for resume claims.
"""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trust_rag.engine.reasoning import (
    DebateOrchestrator, BeamSearchReranker, BeamSearchConfig, EvidenceNode,
)

def test_multi_agent_debate_comprehensive():
    """Comprehensive Multi-Agent Debate evaluation."""
    print("\n" + "="*60)
    print("🔬 Comprehensive Multi-Agent Debate Evaluation")
    print("="*60)
    
    orchestrator = DebateOrchestrator(max_rounds=3)
    
    test_cases = [
        # VERIFIED cases - clear evidence supports the claim
        {"query": "What is the revenue of Company X in 2023?",
         "evidence": ["Company X reported total revenue of $10.5 billion in fiscal year 2023.",
                      "The annual report confirms revenue growth of 15% year-over-year."],
         "expected": "VERIFIED", "category": "numeric"},
        {"query": "Did Company Y acquire Company Z?",
         "evidence": ["Company Y announced plans to acquire Company Z in March 2023.",
                      "The acquisition was completed in September 2023 for $500 million."],
         "expected": "VERIFIED", "category": "factual"},
        {"query": "Is the headquarters in New York?",
         "evidence": ["The company headquarters is located in New York City.",
                      "The NYC office serves as the global headquarters."],
         "expected": "VERIFIED", "category": "factual"},
        {"query": "What was the Q4 profit?",
         "evidence": ["Q4 2023 net profit reached $2.3 billion.",
                      "Quarterly earnings exceeded analyst expectations."],
         "expected": "VERIFIED", "category": "numeric"},
        
        # REFUTED cases - evidence contradicts the query assumption
        {"query": "Is the CEO John Smith?",
         "evidence": ["The CEO is Jane Doe, appointed in 2022.",
                      "John Smith serves as CFO, not CEO."],
         "expected": "REFUTED", "category": "factual"},
        {"query": "Did the company report a loss in 2023?",
         "evidence": ["The company reported record profits in 2023.",
                      "Net income increased by 25% compared to 2022."],
         "expected": "REFUTED", "category": "factual"},
        {"query": "Is the stock price below $100?",
         "evidence": ["Current stock price is $156.78.",
                      "Stock has traded above $100 for the past 12 months."],
         "expected": "REFUTED", "category": "numeric"},
        
        # UNCERTAIN cases - insufficient or no evidence
        {"query": "What is the profit margin?",
         "evidence": [],
         "expected": "UNCERTAIN", "category": "numeric"},
        {"query": "Will the company expand to Europe?",
         "evidence": ["The company is considering international expansion.",
                      "No specific plans have been announced."],
         "expected": "UNCERTAIN", "category": "speculative"},
        {"query": "What is the employee count?",
         "evidence": [],
         "expected": "UNCERTAIN", "category": "numeric"},
    ]
    
    results = {"VERIFIED": [], "REFUTED": [], "UNCERTAIN": []}
    category_results = {}
    
    for i, tc in enumerate(test_cases):
        start = time.time()
        result = orchestrator.run_debate(tc["query"], tc["evidence"])
        elapsed = time.time() - start
        
        correct = result.final_verdict == tc["expected"]
        cat = tc["category"]
        if cat not in category_results:
            category_results[cat] = {"correct": 0, "total": 0}
        category_results[cat]["total"] += 1
        if correct:
            category_results[cat]["correct"] += 1
        
        results[tc["expected"]].append({
            "correct": correct, "confidence": result.confidence,
            "rounds": result.rounds_completed, "time": elapsed
        })
        
        status = "✅" if correct else "❌"
        print(f"  [{i+1:2d}] {tc['query'][:35]:35s} | {result.final_verdict:10s} {status}")
    
    # Calculate metrics
    total = sum(len(v) for v in results.values())
    correct = sum(sum(1 for r in v if r["correct"]) for v in results.values())
    accuracy = correct / total
    
    print(f"\n📊 DETAILED METRICS:")
    print(f"  Overall Accuracy: {accuracy*100:.1f}% ({correct}/{total})")
    
    for verdict, data in results.items():
        if data:
            v_acc = sum(1 for r in data if r["correct"]) / len(data)
            v_conf = sum(r["confidence"] for r in data) / len(data)
            print(f"  {verdict}: Accuracy={v_acc*100:.0f}%, Avg Confidence={v_conf:.2f}")
    
    print(f"\n  By Category:")
    for cat, stats in category_results.items():
        cat_acc = stats["correct"] / stats["total"]
        print(f"    {cat}: {cat_acc*100:.0f}% ({stats['correct']}/{stats['total']})")
    
    return {"accuracy": accuracy, "total_cases": total, "by_verdict": results}


def test_beam_search_comprehensive():
    """Comprehensive Beam Search evaluation."""
    print("\n" + "="*60)
    print("🔬 Comprehensive Beam Search Evaluation")
    print("="*60)
    
    config = BeamSearchConfig(beam_width=5, max_depth=4)
    reranker = BeamSearchReranker(config)
    
    # Build test graph
    nodes = [
        EvidenceNode("company", "Company X financial data", "entity", 0.95),
        EvidenceNode("revenue", "Revenue is $10.5 billion in 2023", "fact", 0.90),
        EvidenceNode("growth", "Growth rate is 15% year-over-year", "fact", 0.85),
        EvidenceNode("report", "Annual Report 2023 official document", "document", 0.98),
        EvidenceNode("ceo", "CEO Jane Doe leadership", "entity", 0.88),
        EvidenceNode("strategy", "Strategic initiatives for expansion", "fact", 0.75),
        EvidenceNode("market", "Market share increased to 25%", "fact", 0.82),
        EvidenceNode("competitor", "Competitor analysis data", "document", 0.70),
    ]
    
    edges = [
        {"source": "company", "target": "revenue", "relation": "has_metric", "weight": 0.9},
        {"source": "company", "target": "ceo", "relation": "has_leader", "weight": 0.85},
        {"source": "company", "target": "market", "relation": "has_metric", "weight": 0.8},
        {"source": "revenue", "target": "growth", "relation": "implies", "weight": 0.8},
        {"source": "revenue", "target": "report", "relation": "from_document", "weight": 0.95},
        {"source": "ceo", "target": "strategy", "relation": "defines", "weight": 0.7},
        {"source": "growth", "target": "report", "relation": "from_document", "weight": 0.9},
        {"source": "market", "target": "competitor", "relation": "compared_to", "weight": 0.6},
    ]
    
    reranker.build_graph(nodes, edges)
    
    queries = [
        ("What is the revenue?", ["company"]),
        ("Who is the CEO?", ["company"]),
        ("What is the growth rate?", ["company"]),
        ("What is the market share?", ["company"]),
    ]
    
    total_score, total_coherence, total_length = 0, 0, 0
    
    for query, start in queries:
        paths = reranker.search(query, start)
        if paths:
            best = paths[0]
            print(f"  Query: {query}")
            print(f"    Path: {' -> '.join(n.node_id for n in best.nodes)}")
            print(f"    Score: {best.score:.3f}, Coherence: {best.coherence:.3f}")
            total_score += best.score
            total_coherence += best.coherence
            total_length += len(best.nodes)
    
    n = len(queries)
    print(f"\n📊 BEAM SEARCH METRICS:")
    print(f"  Avg Path Score: {total_score/n:.3f}")
    print(f"  Avg Coherence: {total_coherence/n:.3f}")
    print(f"  Avg Path Length: {total_length/n:.1f}")
    
    return {"avg_score": total_score/n, "avg_coherence": total_coherence/n}


if __name__ == "__main__":
    print("🚀 TrustRAG Comprehensive Evaluation Suite")
    print("="*60)
    print("Generating REAL metrics for resume validation...")

    debate_metrics = test_multi_agent_debate_comprehensive()
    beam_metrics = test_beam_search_comprehensive()

    print("\n" + "="*60)
    print("📈 FINAL METRICS FOR RESUME")
    print("="*60)

    print(f"""
┌─────────────────────────────────────────────────────────────┐
│  MULTI-AGENT DEBATE SYSTEM                                  │
├─────────────────────────────────────────────────────────────┤
│  ✓ Verdict Accuracy:     {debate_metrics['accuracy']*100:5.1f}%                          │
│  ✓ Test Cases:           {debate_metrics['total_cases']:5d}                             │
│  ✓ Supports: VERIFIED / REFUTED / UNCERTAIN verdicts        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  BEAM SEARCH PATH RERANKER                                  │
├─────────────────────────────────────────────────────────────┤
│  ✓ Avg Path Score:       {beam_metrics['avg_score']:5.3f}                          │
│  ✓ Avg Coherence:        {beam_metrics['avg_coherence']:5.3f}                          │
│  ✓ Multi-hop reasoning with evidence chain optimization     │
└─────────────────────────────────────────────────────────────┘

These are REAL metrics from actual test runs.
Use these numbers in your resume with confidence!
""")

    print("✅ Evaluation complete!")

