"""
Dynamic Weighting Strategy for GraphRAG.

This module implements dynamic weight adjustment for multi-stage retrieval,
using GNN-based relevance assessment and adaptive weighting algorithms.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)


class DynamicWeightingStrategy:
    """
    Dynamic weighting strategy for multi-stage retrieval.

    Adapts weights based on query characteristics, retrieval performance,
    and GNN-based relevance assessment.
    """

    def __init__(self):
        """Initialize dynamic weighting strategy."""
        # Base weights for different retrieval methods
        self.base_weights = {
            'graph_semantic': 0.35,
            'graph_path': 0.25,
            'graph_entity': 0.20,
            'traditional_vector': 0.15,
            'traditional_bm25': 0.05
        }

        # Adaptive parameters
        self.learning_rate = 0.1
        self.momentum = 0.9
        self.performance_history = []

        # Query type modifiers
        self.query_type_multipliers = {
            'factual': {'graph_semantic': 1.2, 'traditional_vector': 0.8},
            'analytical': {'graph_path': 1.3, 'graph_entity': 1.1},
            'comparative': {'graph_entity': 1.4, 'traditional_vector': 0.7},
            'temporal': {'graph_path': 1.2, 'traditional_bm25': 1.1},
            'long_tail': {'graph_semantic': 1.1, 'traditional_vector': 1.2}
        }

        # Performance tracking
        self.method_performance = defaultdict(lambda: {'success_rate': 0.5, 'avg_score': 0.5})

        logger.info("Dynamic weighting strategy initialized")

    def apply_weights(
        self,
        query: str,
        candidates: List[Tuple[Any, Dict[str, Any]]],
        query_profile: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Any, Dict[str, float]]]:
        """
        Apply dynamic weighting to retrieval candidates.

        Args:
            query: Original query string
            candidates: List of (chunk, metadata) tuples
            query_profile: Query profiling information

        Returns:
            List of (chunk, weights_dict) tuples with final scores
        """
        if not candidates:
            return []

        try:
            # Determine query type
            query_type = self._classify_query_type(query, query_profile)

            # Get adaptive weights based on query type and performance
            adaptive_weights = self._get_adaptive_weights(query_type)

            # Apply weights to each candidate
            weighted_candidates = []
            for chunk, metadata in candidates:
                source = metadata.get('source', 'unknown')

                # Get base score
                base_score = getattr(chunk, 'score', 0.5)

                # Apply method-specific weighting
                method_weight = adaptive_weights.get(source, 0.1)

                # Calculate final score
                final_score = base_score * method_weight

                # Additional adjustments
                adjustments = self._calculate_adjustments(chunk, metadata, query_type)
                final_score *= adjustments.get('multiplier', 1.0)
                final_score += adjustments.get('additive', 0.0)

                # Create weights dictionary
                weights_dict = {
                    'final_score': final_score,
                    'base_score': base_score,
                    'method_weight': method_weight,
                    'query_type': query_type,
                    'adjustments': adjustments,
                    'source': source
                }

                weighted_candidates.append((chunk, weights_dict))

            # Update performance tracking
            self._update_performance_tracking(weighted_candidates, query_type)

            return weighted_candidates

        except Exception as e:
            logger.error(f"Dynamic weighting failed: {e}")
            # Return with default weights
            return [(chunk, {'final_score': getattr(chunk, 'score', 0.5),
                           'method_weight': 1.0,
                           'source': metadata.get('source', 'unknown')})
                   for chunk, metadata in candidates]

    def _classify_query_type(
        self,
        query: str,
        query_profile: Optional[Dict[str, Any]]
    ) -> str:
        """
        Classify query type for weighting adjustments.

        Args:
            query: Query string
            query_profile: Query profiling information

        Returns:
            Query type classification
        """
        query_lower = query.lower()

        # Use profile information if available
        if query_profile:
            if query_profile.get('is_long_tail', False):
                return 'long_tail'
            if query_profile.get('requires_analysis', False):
                return 'analytical'

        # Keyword-based classification
        if any(word in query_lower for word in ['compare', 'vs', 'versus', 'difference', 'which', 'better']):
            return 'comparative'
        elif any(word in query_lower for word in ['trend', 'over time', 'historical', 'change', 'growth']):
            return 'temporal'
        elif any(word in query_lower for word in ['calculate', 'compute', 'analyze', 'what is']):
            return 'analytical'
        elif any(word in query_lower for word in ['what', 'how much', 'when', 'where', 'who']):
            return 'factual'

        # Check query length for long-tail detection
        if len(query.split()) > 10:
            return 'long_tail'

        return 'factual'  # Default

    def _get_adaptive_weights(self, query_type: str) -> Dict[str, float]:
        """
        Get adaptive weights based on query type and performance history.

        Args:
            query_type: Classified query type

        Returns:
            Dictionary of method weights
        """
        # Start with base weights
        weights = self.base_weights.copy()

        # Apply query type multipliers
        if query_type in self.query_type_multipliers:
            multipliers = self.query_type_multipliers[query_type]
            for method, multiplier in multipliers.items():
                if method in weights:
                    weights[method] *= multiplier

        # Apply performance-based adjustments
        for method in weights:
            if method in self.method_performance:
                perf = self.method_performance[method]
                # Boost methods with good performance, penalize poor performers
                performance_multiplier = 0.8 + (perf['success_rate'] * 0.4)
                weights[method] *= performance_multiplier

        # Normalize weights to sum to 1
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        return weights

    def _calculate_adjustments(
        self,
        chunk: Any,
        metadata: Dict[str, Any],
        query_type: str
    ) -> Dict[str, float]:
        """
        Calculate additional score adjustments.

        Args:
            chunk: Retrieval chunk
            metadata: Chunk metadata
            query_type: Query type

        Returns:
            Dictionary of adjustment factors
        """
        adjustments = {'multiplier': 1.0, 'additive': 0.0}

        try:
            # Recency boost for temporal queries
            if query_type == 'temporal':
                # Check if chunk has temporal information
                text = getattr(chunk, 'text', '').lower()
                if any(word in text for word in ['year', 'quarter', 'month', 'recent', 'latest']):
                    adjustments['multiplier'] *= 1.1

            # Entity match boost
            if metadata.get('has_entity_match', False):
                adjustments['multiplier'] *= 1.15

            # Diversity penalty (to avoid redundancy)
            if metadata.get('similarity_to_previous', 0) > 0.8:
                adjustments['multiplier'] *= 0.9

            # Source reliability boost
            source = metadata.get('source', '')
            if 'graph' in source:
                adjustments['multiplier'] *= 1.05  # Slight boost for graph sources

            # Length appropriateness
            text_length = len(getattr(chunk, 'text', ''))
            if query_type == 'factual' and text_length < 100:
                adjustments['multiplier'] *= 1.1  # Prefer concise answers for facts
            elif query_type == 'analytical' and text_length > 200:
                adjustments['multiplier'] *= 1.05  # Prefer detailed answers for analysis

        except Exception as e:
            logger.warning(f"Failed to calculate adjustments: {e}")

        return adjustments

    def _update_performance_tracking(
        self,
        weighted_candidates: List[Tuple[Any, Dict[str, float]]],
        query_type: str
    ) -> None:
        """
        Update performance tracking for adaptive learning.

        Args:
            weighted_candidates: Weighted candidate results
            query_type: Query type
        """
        try:
            # Track performance by method
            method_scores = defaultdict(list)

            for chunk, weights in weighted_candidates:
                source = weights.get('source', 'unknown')
                final_score = weights.get('final_score', 0)
                method_scores[source].append(final_score)

            # Update method performance
            for method, scores in method_scores.items():
                if scores:
                    avg_score = np.mean(scores)
                    success_rate = np.mean([1 if s > 0.6 else 0 for s in scores])

                    # Exponential moving average update
                    current_perf = self.method_performance[method]
                    current_perf['avg_score'] = (
                        self.momentum * current_perf['avg_score'] +
                        (1 - self.momentum) * avg_score
                    )
                    current_perf['success_rate'] = (
                        self.momentum * current_perf['success_rate'] +
                        (1 - self.momentum) * success_rate
                    )

            # Track overall performance
            if weighted_candidates:
                avg_final_score = np.mean([w['final_score'] for _, w in weighted_candidates])
                self.performance_history.append({
                    'query_type': query_type,
                    'avg_score': avg_final_score,
                    'timestamp': None  # Would add timestamp
                })

                # Keep only recent history
                if len(self.performance_history) > 100:
                    self.performance_history = self.performance_history[-100:]

        except Exception as e:
            logger.warning(f"Failed to update performance tracking: {e}")

    def get_weighting_stats(self) -> Dict[str, Any]:
        """
        Get weighting strategy statistics.

        Returns:
            Dictionary with weighting statistics
        """
        return {
            'base_weights': self.base_weights,
            'query_type_multipliers': self.query_type_multipliers,
            'method_performance': dict(self.method_performance),
            'performance_history_length': len(self.performance_history),
            'learning_rate': self.learning_rate,
            'momentum': self.momentum
        }

    def reset_adaptation(self) -> None:
        """Reset adaptive parameters to defaults."""
        self.method_performance.clear()
        self.performance_history.clear()
        logger.info("Adaptive parameters reset to defaults")

    def update_from_feedback(self, feedback: Dict[str, Any]) -> None:
        """
        Update weighting strategy based on user feedback.

        Args:
            feedback: User feedback data
        """
        try:
            if 'preferred_sources' in feedback:
                # Boost weights for preferred sources
                preferred = feedback['preferred_sources']
                for source in preferred:
                    if source in self.base_weights:
                        self.base_weights[source] *= 1.1

            if 'disliked_sources' in feedback:
                # Reduce weights for disliked sources
                disliked = feedback['disliked_sources']
                for source in disliked:
                    if source in self.base_weights:
                        self.base_weights[source] *= 0.9

            # Normalize weights
            total = sum(self.base_weights.values())
            self.base_weights = {k: v / total for k, v in self.base_weights.items()}

            logger.info("Updated weights based on user feedback")

        except Exception as e:
            logger.warning(f"Failed to update from feedback: {e}")

    def export_weights(self) -> Dict[str, Any]:
        """
        Export current weights and parameters for persistence.

        Returns:
            Dictionary with all weighting parameters
        """
        return {
            'base_weights': self.base_weights,
            'method_performance': dict(self.method_performance),
            'performance_history': self.performance_history,
            'learning_rate': self.learning_rate,
            'momentum': self.momentum,
            'query_type_multipliers': self.query_type_multipliers
        }

    def import_weights(self, weights_data: Dict[str, Any]) -> None:
        """
        Import weights and parameters from saved data.

        Args:
            weights_data: Exported weights data
        """
        try:
            self.base_weights.update(weights_data.get('base_weights', {}))
            self.method_performance.update(weights_data.get('method_performance', {}))
            self.performance_history.extend(weights_data.get('performance_history', []))
            self.learning_rate = weights_data.get('learning_rate', self.learning_rate)
            self.momentum = weights_data.get('momentum', self.momentum)

            if 'query_type_multipliers' in weights_data:
                self.query_type_multipliers.update(weights_data['query_type_multipliers'])

            logger.info("Imported weighting parameters")

        except Exception as e:
            logger.warning(f"Failed to import weights: {e}")







