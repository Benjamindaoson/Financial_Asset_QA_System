"""
Retrieval Evaluation Metrics.

Calculates recall@k, MRR@k, NDCG@k and rerank gains.
"""
from typing import List, Dict, Any, Optional
import math


def recall_at_k(relevant_items: List[str], retrieved_items: List[str], k: int) -> float:
    """
    Calculate Recall@k.
    
    Args:
        relevant_items: List of relevant item IDs
        retrieved_items: List of retrieved item IDs (in order)
        k: Top k items to consider
        
    Returns:
        Recall@k score (0-1)
    """
    if not relevant_items:
        return 0.0
    
    retrieved_top_k = retrieved_items[:k]
    relevant_set = set(relevant_items)
    retrieved_set = set(retrieved_top_k)
    
    overlap = len(relevant_set & retrieved_set)
    return overlap / len(relevant_set)


def mrr_at_k(relevant_items: List[str], retrieved_items: List[str], k: int) -> float:
    """
    Calculate Mean Reciprocal Rank@k.
    
    Args:
        relevant_items: List of relevant item IDs
        retrieved_items: List of retrieved item IDs (in order)
        k: Top k items to consider
        
    Returns:
        MRR@k score (0-1)
    """
    if not relevant_items:
        return 0.0
    
    relevant_set = set(relevant_items)
    retrieved_top_k = retrieved_items[:k]
    
    for rank, item in enumerate(retrieved_top_k, 1):
        if item in relevant_set:
            return 1.0 / rank
    
    return 0.0


def dcg_at_k(relevant_items: List[str], retrieved_items: List[str], k: int) -> float:
    """
    Calculate Discounted Cumulative Gain@k.
    
    Args:
        relevant_items: List of relevant item IDs
        retrieved_items: List of retrieved item IDs (in order)
        k: Top k items to consider
        
    Returns:
        DCG@k score
    """
    relevant_set = set(relevant_items)
    retrieved_top_k = retrieved_items[:k]
    
    dcg = 0.0
    for rank, item in enumerate(retrieved_top_k, 1):
        if item in relevant_set:
            # Relevance score = 1 for relevant items
            relevance = 1.0
            dcg += relevance / math.log2(rank + 1)
    
    return dcg


def ndcg_at_k(relevant_items: List[str], retrieved_items: List[str], k: int) -> float:
    """
    Calculate Normalized Discounted Cumulative Gain@k.
    
    Args:
        relevant_items: List of relevant item IDs
        retrieved_items: List of retrieved item IDs (in order)
        k: Top k items to consider
        
    Returns:
        NDCG@k score (0-1)
    """
    dcg = dcg_at_k(relevant_items, retrieved_items, k)
    
    # Ideal DCG (all relevant items at top)
    ideal_relevant = relevant_items[:k]
    ideal_dcg = dcg_at_k(ideal_relevant, ideal_relevant, k)
    
    if ideal_dcg == 0:
        return 0.0
    
    return dcg / ideal_dcg


def evaluate_retrieval(
    query_results: List[Dict[str, Any]],
    expected_evidence: Dict[str, List[str]]
) -> Dict[str, float]:
    """
    Evaluate retrieval quality across multiple queries.
    
    Args:
        query_results: List of query results with evidence IDs
        expected_evidence: Dict mapping query to expected evidence IDs
        
    Returns:
        Dictionary of metrics
    """
    recalls_1 = []
    recalls_5 = []
    recalls_10 = []
    mrrs_5 = []
    mrrs_10 = []
    ndcgs_5 = []
    ndcgs_10 = []
    
    for result in query_results:
        query = result.get("query", "")
        expected_ids = expected_evidence.get(query, [])
        
        # Extract retrieved evidence IDs
        retrieved_ids = []
        for ev in result.get("evidence", []):
            if isinstance(ev, dict):
                # Try different fields
                ev_id = ev.get("evidence_id") or ev.get("id") or ev.get("source", "")
            else:
                ev_id = str(ev)
            if ev_id:
                retrieved_ids.append(ev_id)
        
        if not expected_ids:
            continue
        
        # Calculate metrics
        recalls_1.append(recall_at_k(expected_ids, retrieved_ids, 1))
        recalls_5.append(recall_at_k(expected_ids, retrieved_ids, 5))
        recalls_10.append(recall_at_k(expected_ids, retrieved_ids, 10))
        mrrs_5.append(mrr_at_k(expected_ids, retrieved_ids, 5))
        mrrs_10.append(mrr_at_k(expected_ids, retrieved_ids, 10))
        ndcgs_5.append(ndcg_at_k(expected_ids, retrieved_ids, 5))
        ndcgs_10.append(ndcg_at_k(expected_ids, retrieved_ids, 10))
    
    # Average metrics
    n = len(recalls_1)
    if n == 0:
        return {
            "recall_at_1": 0.0,
            "recall_at_5": 0.0,
            "recall_at_10": 0.0,
            "mrr_at_5": 0.0,
            "mrr_at_10": 0.0,
            "ndcg_at_5": 0.0,
            "ndcg_at_10": 0.0
        }
    
    return {
        "recall_at_1": sum(recalls_1) / n,
        "recall_at_5": sum(recalls_5) / n,
        "recall_at_10": sum(recalls_10) / n,
        "mrr_at_5": sum(mrrs_5) / n,
        "mrr_at_10": sum(mrrs_10) / n,
        "ndcg_at_5": sum(ndcgs_5) / n,
        "ndcg_at_10": sum(ndcgs_10) / n
    }


def calculate_rerank_gain(
    before_rerank: Dict[str, float],
    after_rerank: Dict[str, float]
) -> Dict[str, float]:
    """
    Calculate improvement from reranking.
    
    Args:
        before_rerank: Metrics before reranking
        after_rerank: Metrics after reranking
        
    Returns:
        Dictionary of gains
    """
    gains = {}
    
    for metric in ["recall_at_5", "recall_at_10", "mrr_at_5", "mrr_at_10", "ndcg_at_5", "ndcg_at_10"]:
        before = before_rerank.get(metric, 0.0)
        after = after_rerank.get(metric, 0.0)
        
        if before > 0:
            gain = (after - before) / before
        else:
            gain = after if after > 0 else 0.0
        
        gains[f"rerank_gain_{metric}"] = gain
    
    return gains

