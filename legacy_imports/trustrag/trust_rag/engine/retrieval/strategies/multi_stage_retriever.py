"""
Multi-Stage Retriever for GraphRAG.

This module implements a multi-stage retrieval pipeline that combines
traditional retrieval with graph-based methods and query expansion.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import numpy as np
from collections import defaultdict

from .graph_retrieval import GraphRetrievalStrategy
from .query_expansion import QueryExpansionStrategy
from .dynamic_weighting import DynamicWeightingStrategy
from ..scored_chunk import ScoredChunk
from ..types import RetrievalResult

logger = logging.getLogger(__name__)


class MultiStageRetriever:
    """
    Multi-stage retrieval system combining multiple strategies.

    Stages:
    1. Query Expansion (BERT/ColBERT)
    2. Graph-based Retrieval
    3. Traditional Vector Retrieval
    4. Dynamic Weighting & Re-ranking
    5. Evidence Fusion
    """

    def __init__(
        self,
        graph_strategy: Optional[GraphRetrievalStrategy] = None,
        expansion_strategy: Optional[QueryExpansionStrategy] = None,
        weighting_strategy: Optional[DynamicWeightingStrategy] = None,
        traditional_retriever: Optional[Any] = None,
        long_tail_optimizer: Optional['LongTailRetrievalOptimizer'] = None
    ):
        """
        Initialize multi-stage retriever.

        Args:
            graph_strategy: Graph-based retrieval strategy
            expansion_strategy: Query expansion strategy
            weighting_strategy: Dynamic weighting strategy
            traditional_retriever: Traditional vector retriever (fallback)
            long_tail_optimizer: Long-tail query optimization (optional)
        """
        self.graph_strategy = graph_strategy
        self.expansion_strategy = expansion_strategy or QueryExpansionStrategy()
        self.weighting_strategy = weighting_strategy or DynamicWeightingStrategy()
        self.traditional_retriever = traditional_retriever
        self.long_tail_optimizer = long_tail_optimizer

        # Stage weights and thresholds
        self.stage_weights = {
            'graph': 0.4,
            'traditional': 0.3,
            'expansion': 0.3
        }

        self.quality_thresholds = {
            'min_graph_results': 5,
            'min_traditional_results': 10,
            'expansion_confidence': 0.7
        }

        logger.info("Multi-stage retriever initialized")

    def retrieve(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        query_profile: Optional[Dict[str, Any]] = None
    ) -> RetrievalResult:
        """
        Execute multi-stage retrieval pipeline.

        Args:
            query: Original query string
            top_k: Number of results to return
            filters: Optional filtering criteria
            query_profile: Query profiling information

        Returns:
            Retrieval results with evidence trails
        """
        logger.info(f"Starting multi-stage retrieval for query: {query[:100]}...")

        # Stage 0: Long-tail Query Optimization (if available)
        long_tail_optimization = None
        if self.long_tail_optimizer:
            long_tail_optimization = self.long_tail_optimizer.optimize_retrieval(query, query_profile)
            if long_tail_optimization['optimization_needed']:
                logger.info(f"Applying long-tail optimization for query type: {long_tail_optimization['query_analysis']['query_type']}")
                # Adjust retrieval strategy based on optimization results
                self._apply_long_tail_optimization(long_tail_optimization)

        # Stage 1: Query Expansion
        expanded_queries = self._stage_query_expansion(query, query_profile)
        logger.debug(f"Generated {len(expanded_queries)} expanded queries")

        # Stage 2: Parallel Retrieval (Graph + Traditional)
        graph_results = []
        traditional_results = []

        if self.graph_strategy:
            graph_results = self._stage_graph_retrieval(expanded_queries, top_k, filters)
            logger.debug(f"Graph retrieval returned {len(graph_results)} results")

        if self.traditional_retriever:
            traditional_results = self._stage_traditional_retrieval(expanded_queries, top_k, filters)
            logger.debug(f"Traditional retrieval returned {len(traditional_results)} results")

        # Stage 3: Dynamic Weighting and Re-ranking
        combined_results = self._stage_dynamic_weighting(
            query, graph_results, traditional_results, query_profile
        )

        # Stage 4: Evidence Fusion and Final Selection
        final_results = self._stage_evidence_fusion(combined_results, top_k)

        # Create retrieval result
        retrieval_result = RetrievalResult(
            chunks=final_results,
            audit_info={
                'stages_executed': ['expansion', 'graph', 'traditional', 'weighting', 'fusion'],
                'graph_results_count': len(graph_results),
                'traditional_results_count': len(traditional_results),
                'expanded_queries_count': len(expanded_queries),
                'final_results_count': len(final_results)
            }
        )

        logger.info(f"Multi-stage retrieval completed with {len(final_results)} final results")
        return retrieval_result

    def _stage_query_expansion(
        self,
        original_query: str,
        query_profile: Optional[Dict[str, Any]]
    ) -> List[str]:
        """
        Stage 1: Expand query using BERT/ColBERT techniques.

        Args:
            original_query: Original user query
            query_profile: Query profiling information

        Returns:
            List of expanded queries including original
        """
        expanded_queries = [original_query]  # Always include original

        try:
            if self.expansion_strategy:
                # Generate expanded queries
                expansions = self.expansion_strategy.expand_query(
                    original_query,
                    query_profile=query_profile,
                    max_expansions=3
                )

                # Filter by confidence
                confident_expansions = [
                    exp for exp in expansions
                    if exp.get('confidence', 0) >= self.quality_thresholds['expansion_confidence']
                ]

                expanded_queries.extend([exp['query'] for exp in confident_expansions])

        except Exception as e:
            logger.warning(f"Query expansion failed: {e}")

        return list(set(expanded_queries))  # Remove duplicates

    def _stage_graph_retrieval(
        self,
        queries: List[str],
        top_k: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[ScoredChunk]:
        """
        Stage 2a: Graph-based retrieval.

        Args:
            queries: List of queries to search
            top_k: Number of results per query
            filters: Optional filters

        Returns:
            List of scored chunks from graph retrieval
        """
        all_results = []

        try:
            for query in queries:
                results = self.graph_strategy.retrieve(
                    query=query,
                    top_k=top_k,
                    filters=filters
                )
                all_results.extend(results)

        except Exception as e:
            logger.warning(f"Graph retrieval failed: {e}")

        return all_results

    def _stage_traditional_retrieval(
        self,
        queries: List[str],
        top_k: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[ScoredChunk]:
        """
        Stage 2b: Traditional vector retrieval.

        Args:
            queries: List of queries to search
            top_k: Number of results per query
            filters: Optional filters

        Returns:
            List of scored chunks from traditional retrieval
        """
        all_results = []

        try:
            for query in queries:
                # This would call the traditional retriever
                # For now, return empty list as placeholder
                results = []
                all_results.extend(results)

        except Exception as e:
            logger.warning(f"Traditional retrieval failed: {e}")

        return all_results

    def _stage_dynamic_weighting(
        self,
        original_query: str,
        graph_results: List[ScoredChunk],
        traditional_results: List[ScoredChunk],
        query_profile: Optional[Dict[str, Any]]
    ) -> List[Tuple[ScoredChunk, Dict[str, float]]]:
        """
        Stage 3: Dynamic weighting and re-ranking.

        Args:
            original_query: Original query
            graph_results: Results from graph retrieval
            traditional_results: Results from traditional retrieval
            query_profile: Query profiling information

        Returns:
            List of (chunk, weights_dict) tuples
        """
        # Combine all results
        all_results = []
        all_results.extend([(chunk, {'source': 'graph'}) for chunk in graph_results])
        all_results.extend([(chunk, {'source': 'traditional'}) for chunk in traditional_results])

        if not all_results:
            return []

        try:
            # Apply dynamic weighting
            weighted_results = self.weighting_strategy.apply_weights(
                query=original_query,
                candidates=all_results,
                query_profile=query_profile
            )

            return weighted_results

        except Exception as e:
            logger.warning(f"Dynamic weighting failed: {e}")
            # Return results with default weights
            return [(chunk, {'final_score': chunk.score, 'source': meta['source']})
                   for chunk, meta in all_results]

    def _stage_evidence_fusion(
        self,
        weighted_results: List[Tuple[ScoredChunk, Dict[str, float]]],
        top_k: int
    ) -> List[ScoredChunk]:
        """
        Stage 4: Evidence fusion and final selection.

        Args:
            weighted_results: Results with weights applied
            top_k: Number of final results to return

        Returns:
            Final selected and scored chunks
        """
        if not weighted_results:
            return []

        # Sort by final weighted score
        sorted_results = sorted(
            weighted_results,
            key=lambda x: x[1].get('final_score', 0),
            reverse=True
        )

        # Apply diversity and redundancy filtering
        final_results = self._apply_diversity_filtering(sorted_results, top_k)

        # Update final scores based on fusion
        for i, (chunk, weights) in enumerate(final_results):
            chunk.rank = i + 1
            chunk.final_score = weights.get('final_score', chunk.score)

        return [chunk for chunk, _ in final_results]

    def _apply_diversity_filtering(
        self,
        sorted_results: List[Tuple[ScoredChunk, Dict[str, float]]],
        top_k: int,
        diversity_threshold: float = 0.8
    ) -> List[Tuple[ScoredChunk, Dict[str, float]]]:
        """
        Apply diversity filtering to avoid redundant results.

        Args:
            sorted_results: Sorted results with weights
            top_k: Target number of results
            diversity_threshold: Similarity threshold for filtering

        Returns:
            Diversity-filtered results
        """
        if len(sorted_results) <= top_k:
            return sorted_results

        selected = [sorted_results[0]]  # Always include top result

        for candidate, weights in sorted_results[1:]:
            # Check similarity with already selected results
            is_diverse = True

            for selected_chunk, _ in selected:
                similarity = self._calculate_chunk_similarity(candidate, selected_chunk)
                if similarity > diversity_threshold:
                    is_diverse = False
                    break

            if is_diverse:
                selected.append((candidate, weights))

            if len(selected) >= top_k:
                break

        return selected

    def _calculate_chunk_similarity(self, chunk1: ScoredChunk, chunk2: ScoredChunk) -> float:
        """
        Calculate similarity between two chunks.

        Args:
            chunk1: First chunk
            chunk2: Second chunk

        Returns:
            Similarity score (0-1)
        """
        # Simple text-based similarity (could use embeddings)
        text1 = chunk1.chunk.text.lower() if hasattr(chunk1.chunk, 'text') else ""
        text2 = chunk2.chunk.text.lower() if hasattr(chunk2.chunk, 'text') else ""

        if not text1 or not text2:
            return 0.0

        # Jaccard similarity on words
        words1 = set(text1.split())
        words2 = set(text2.split())

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def update_stage_weights(self, performance_metrics: Dict[str, float]) -> None:
        """
        Update stage weights based on performance metrics.

        Args:
            performance_metrics: Performance metrics for each stage
        """
        try:
            # Adaptive weight adjustment based on performance
            graph_perf = performance_metrics.get('graph_retrieval_quality', 0.5)
            traditional_perf = performance_metrics.get('traditional_retrieval_quality', 0.5)
            expansion_perf = performance_metrics.get('query_expansion_quality', 0.5)

            # Normalize weights
            total_perf = graph_perf + traditional_perf + expansion_perf
            if total_perf > 0:
                self.stage_weights = {
                    'graph': graph_perf / total_perf,
                    'traditional': traditional_perf / total_perf,
                    'expansion': expansion_perf / total_perf
                }

            logger.info(f"Updated stage weights: {self.stage_weights}")

        except Exception as e:
            logger.warning(f"Failed to update stage weights: {e}")

    def get_retrieval_stats(self) -> Dict[str, Any]:
        """
        Get retrieval statistics and configuration.

        Returns:
            Dictionary with retrieval statistics
        """
        return {
            'stage_weights': self.stage_weights,
            'quality_thresholds': self.quality_thresholds,
            'strategies_available': {
                'graph_strategy': self.graph_strategy is not None,
                'expansion_strategy': self.expansion_strategy is not None,
                'weighting_strategy': self.weighting_strategy is not None,
                'traditional_retriever': self.traditional_retriever is not None,
                'long_tail_optimizer': self.long_tail_optimizer is not None
            }
        }

    def _apply_long_tail_optimization(self, optimization: Dict[str, Any]):
        """
        Apply long-tail query optimization to retrieval strategy.

        Args:
            optimization: Long-tail optimization results
        """
        try:
            # Adjust stage weights based on recommended strategies
            recommended_strategies = optimization.get('recommended_strategies', [])

            # Boost weights for recommended strategies
            weight_adjustments = {
                'graph_traversal': 'graph',
                'semantic_search': 'traditional',
                'query_expansion': 'expansion',
                'multi_hop_reasoning': 'graph',
                'subquery_fusion': 'expansion'
            }

            for strategy in recommended_strategies:
                if strategy in weight_adjustments:
                    stage = weight_adjustments[strategy]
                    self.stage_weights[stage] = min(0.8, self.stage_weights[stage] + 0.1)

            # Adjust quality thresholds for long-tail queries
            if optimization.get('query_analysis', {}).get('complexity_score', 0) > 0.7:
                # Lower thresholds for complex queries to ensure more results
                self.quality_thresholds['min_graph_results'] = max(3, self.quality_thresholds['min_graph_results'] - 2)
                self.quality_thresholds['min_traditional_results'] = max(5, self.quality_thresholds['min_traditional_results'] - 5)

            # Re-normalize weights
            total_weight = sum(self.stage_weights.values())
            self.stage_weights = {k: v / total_weight for k, v in self.stage_weights.items()}

            logger.debug(f"Applied long-tail optimization: {self.stage_weights}")

        except Exception as e:
            logger.warning(f"Failed to apply long-tail optimization: {e}")
