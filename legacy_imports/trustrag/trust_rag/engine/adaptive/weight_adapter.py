"""
Weight Adapter for GraphRAG.

This module dynamically adjusts retrieval weights based on query features,
user feedback, and performance metrics.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import time
import numpy as np
from collections import defaultdict
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class WeightAdapter:
    """
    Dynamic weight adjustment for multi-stage retrieval strategies.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize weight adapter.

        Args:
            config: Configuration for weight adaptation
        """
        self.config = config or {}

        # Default weights for different retrieval strategies
        self.default_weights = {
            'vector_search': 0.4,
            'bm25_search': 0.3,
            'graph_search': 0.2,
            'hybrid_search': 0.1
        }

        # Current weights (start with defaults)
        self.current_weights = self.default_weights.copy()

        # Adaptation parameters
        self.learning_rate = self.config.get('learning_rate', 0.1)
        self.adaptation_window = self.config.get('adaptation_window', 100)  # queries
        self.min_weight = self.config.get('min_weight', 0.05)
        self.max_weight = self.config.get('max_weight', 0.8)

        # Historical performance tracking
        self.performance_history = []
        self.query_features_history = []
        self.feedback_history = []

        # Weight evolution tracking
        self.weight_history = [self.current_weights.copy()]

        # Feature importance weights
        self.feature_weights = self._initialize_feature_weights()

        logger.info("Weight adapter initialized")

    def _initialize_feature_weights(self) -> Dict[str, float]:
        """Initialize feature importance weights for adaptation."""
        return {
            'query_length': 0.2,
            'query_complexity': 0.3,
            'domain_specificity': 0.2,
            'temporal_freshness': 0.1,
            'user_feedback': 0.4,
            'performance_metrics': 0.3,
            'retrieval_precision': 0.3,
            'retrieval_recall': 0.2,
            'response_quality': 0.4
        }

    def adapt_weights(
        self,
        query: str,
        query_features: Dict[str, Any],
        retrieval_results: Dict[str, Any],
        user_feedback: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """
        Adapt retrieval weights based on query features and feedback.

        Args:
            query: Query string
            query_features: Extracted query features
            retrieval_results: Results from different retrieval strategies
            user_feedback: User feedback on results

        Returns:
            Adapted weights for retrieval strategies
        """
        # Store historical data
        self._store_historical_data(query, query_features, retrieval_results, user_feedback)

        # Calculate adaptation factors
        adaptation_factors = self._calculate_adaptation_factors(
            query_features, retrieval_results, user_feedback
        )

        # Apply weight adaptation
        new_weights = self._apply_weight_adaptation(adaptation_factors)

        # Normalize weights
        new_weights = self._normalize_weights(new_weights)

        # Update current weights
        self.current_weights = new_weights
        self.weight_history.append(new_weights.copy())

        logger.info(f"Adapted weights: {new_weights}")

        return new_weights.copy()

    def _store_historical_data(
        self,
        query: str,
        query_features: Dict[str, Any],
        retrieval_results: Dict[str, Any],
        user_feedback: Optional[Dict[str, Any]]
    ):
        """Store historical data for learning."""
        historical_entry = {
            'timestamp': time.time(),
            'query': query,
            'query_features': query_features,
            'retrieval_results': retrieval_results,
            'user_feedback': user_feedback or {},
            'previous_weights': self.current_weights.copy()
        }

        self.performance_history.append(historical_entry)
        self.query_features_history.append(query_features)

        # Maintain history size
        if len(self.performance_history) > self.adaptation_window:
            self.performance_history = self.performance_history[-self.adaptation_window:]
            self.query_features_history = self.query_features_history[-self.adaptation_window:]

    def _calculate_adaptation_factors(
        self,
        query_features: Dict[str, Any],
        retrieval_results: Dict[str, Any],
        user_feedback: Optional[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Calculate adaptation factors for each retrieval strategy.

        Args:
            query_features: Query feature analysis
            retrieval_results: Retrieval performance metrics
            user_feedback: User feedback

        Returns:
            Adaptation factors for each strategy
        """
        adaptation_factors = {}

        # Extract strategy performance
        strategy_performance = self._extract_strategy_performance(retrieval_results)

        for strategy in self.default_weights.keys():
            factor = 0.0

            # Base performance factor
            if strategy in strategy_performance:
                perf = strategy_performance[strategy]
                factor += self.feature_weights['performance_metrics'] * perf.get('efficiency', 0.5)

            # Query feature alignment
            query_alignment = self._calculate_query_alignment(strategy, query_features)
            factor += self.feature_weights['query_complexity'] * query_alignment

            # User feedback factor
            if user_feedback:
                feedback_factor = self._calculate_feedback_factor(strategy, user_feedback)
                factor += self.feature_weights['user_feedback'] * feedback_factor

            # Historical performance trend
            trend_factor = self._calculate_historical_trend(strategy)
            factor += 0.1 * trend_factor  # Lower weight for trend

            adaptation_factors[strategy] = factor

        return adaptation_factors

    def _extract_strategy_performance(self, retrieval_results: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """Extract performance metrics for each retrieval strategy."""
        strategy_performance = {}

        if 'strategy_results' in retrieval_results:
            for strategy_name, results in retrieval_results['strategy_results'].items():
                perf = {
                    'precision': results.get('precision', 0.5),
                    'recall': results.get('recall', 0.5),
                    'latency': results.get('latency', 100.0),
                    'efficiency': self._calculate_efficiency_score(results)
                }
                strategy_performance[strategy_name] = perf

        return strategy_performance

    def _calculate_efficiency_score(self, results: Dict[str, Any]) -> float:
        """Calculate efficiency score combining precision, recall, and latency."""
        precision = results.get('precision', 0.5)
        recall = results.get('recall', 0.5)
        latency = results.get('latency', 100.0)

        # Normalize latency (lower is better, target < 200ms)
        latency_score = max(0, 1.0 - (latency - 50) / 300)

        # Combined efficiency score
        efficiency = (precision * 0.4 + recall * 0.4 + latency_score * 0.2)

        return efficiency

    def _calculate_query_alignment(self, strategy: str, query_features: Dict[str, Any]) -> float:
        """Calculate how well a strategy aligns with query features."""
        alignment = 0.5  # Base alignment

        query_type = query_features.get('query_type', 'general')
        query_complexity = query_features.get('complexity', 'medium')
        domain_specificity = query_features.get('domain_specificity', 0.5)

        # Strategy-specific alignments
        if strategy == 'vector_search':
            # Good for semantic similarity
            if query_type in ['semantic', 'conceptual']:
                alignment += 0.3
            if query_complexity == 'high':
                alignment += 0.2

        elif strategy == 'bm25_search':
            # Good for keyword matching
            if query_type in ['factual', 'keyword']:
                alignment += 0.3
            if domain_specificity > 0.7:
                alignment += 0.2

        elif strategy == 'graph_search':
            # Good for relational queries
            if query_type in ['relational', 'causal']:
                alignment += 0.3
            if query_complexity == 'high':
                alignment += 0.2

        elif strategy == 'hybrid_search':
            # Good general-purpose
            alignment += 0.1  # Slight boost for hybrid

        return min(1.0, alignment)

    def _calculate_feedback_factor(self, strategy: str, user_feedback: Dict[str, Any]) -> float:
        """Calculate feedback factor for strategy adjustment."""
        feedback_score = 0.5  # Neutral

        # Extract feedback metrics
        relevance_score = user_feedback.get('relevance_score', 0.5)
        usefulness_score = user_feedback.get('usefulness_score', 0.5)
        satisfaction_score = user_feedback.get('satisfaction_score', 0.5)

        # Combine feedback scores
        combined_feedback = (relevance_score + usefulness_score + satisfaction_score) / 3.0

        # Strategy-specific feedback interpretation
        if strategy in user_feedback.get('preferred_strategies', []):
            feedback_score = combined_feedback + 0.2
        elif strategy in user_feedback.get('dispreferred_strategies', []):
            feedback_score = combined_feedback - 0.2
        else:
            feedback_score = combined_feedback

        return max(0.0, min(1.0, feedback_score))

    def _calculate_historical_trend(self, strategy: str) -> float:
        """Calculate historical performance trend for strategy."""
        if len(self.performance_history) < 5:
            return 0.0

        # Look at recent performance history
        recent_history = self.performance_history[-10:]

        strategy_scores = []
        for entry in recent_history:
            results = entry.get('retrieval_results', {})
            strategy_results = results.get('strategy_results', {})

            if strategy in strategy_results:
                perf = strategy_results[strategy]
                efficiency = self._calculate_efficiency_score(perf)
                strategy_scores.append(efficiency)

        if len(strategy_scores) < 2:
            return 0.0

        # Calculate trend (recent - older)
        recent_avg = np.mean(strategy_scores[-3:])
        older_avg = np.mean(strategy_scores[:-3])

        trend = recent_avg - older_avg

        return trend

    def _apply_weight_adaptation(self, adaptation_factors: Dict[str, float]) -> Dict[str, float]:
        """Apply adaptation factors to current weights."""
        new_weights = {}

        for strategy, current_weight in self.current_weights.items():
            if strategy in adaptation_factors:
                # Calculate weight adjustment
                factor = adaptation_factors[strategy]
                adjustment = (factor - 0.5) * self.learning_rate  # Center around 0.5

                # Apply adjustment with momentum
                new_weight = current_weight + adjustment

                # Apply constraints
                new_weight = max(self.min_weight, min(self.max_weight, new_weight))

                new_weights[strategy] = new_weight
            else:
                new_weights[strategy] = current_weight

        return new_weights

    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Normalize weights to sum to 1.0."""
        total_weight = sum(weights.values())

        if total_weight == 0:
            return self.default_weights.copy()

        normalized = {k: v / total_weight for k, v in weights.items()}

        return normalized

    def get_optimal_weights(self, query_features: Dict[str, Any]) -> Dict[str, float]:
        """
        Get optimal weights for given query features without adaptation.

        Args:
            query_features: Query feature analysis

        Returns:
            Optimal weights for the query
        """
        # Calculate query-specific weights based on features
        optimal_weights = {}

        query_type = query_features.get('query_type', 'general')
        complexity = query_features.get('complexity', 'medium')
        domain_specificity = query_features.get('domain_specificity', 0.5)

        # Base weights adjusted by query characteristics
        if query_type == 'factual':
            optimal_weights = {
                'vector_search': 0.2,
                'bm25_search': 0.5,
                'graph_search': 0.2,
                'hybrid_search': 0.1
            }
        elif query_type == 'semantic':
            optimal_weights = {
                'vector_search': 0.6,
                'bm25_search': 0.2,
                'graph_search': 0.1,
                'hybrid_search': 0.1
            }
        elif query_type == 'relational':
            optimal_weights = {
                'vector_search': 0.2,
                'bm25_search': 0.2,
                'graph_search': 0.5,
                'hybrid_search': 0.1
            }
        else:  # general or unknown
            optimal_weights = self.current_weights.copy()

        # Adjust for complexity
        if complexity == 'high':
            # Increase graph search for complex queries
            optimal_weights['graph_search'] = min(0.6, optimal_weights['graph_search'] + 0.2)
            optimal_weights['hybrid_search'] = min(0.3, optimal_weights['hybrid_search'] + 0.1)
        elif complexity == 'low':
            # Increase BM25 for simple queries
            optimal_weights['bm25_search'] = min(0.6, optimal_weights['bm25_search'] + 0.1)

        # Adjust for domain specificity
        if domain_specificity > 0.7:
            # Increase BM25 for domain-specific queries
            optimal_weights['bm25_search'] = min(0.6, optimal_weights['bm25_search'] + 0.1)

        return optimal_weights

    def reset_weights(self):
        """Reset weights to default values."""
        self.current_weights = self.default_weights.copy()
        self.weight_history = [self.current_weights.copy()]
        logger.info("Weights reset to default values")

    def save_weights(self, filepath: Union[str, Path]):
        """Save current weights and history to file."""
        filepath = Path(filepath)

        data = {
            'current_weights': self.current_weights,
            'weight_history': self.weight_history,
            'feature_weights': self.feature_weights,
            'config': self.config,
            'timestamp': time.time()
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Weights saved to {filepath}")

    def load_weights(self, filepath: Union[str, Path]):
        """Load weights and history from file."""
        filepath = Path(filepath)

        if not filepath.exists():
            logger.warning(f"Weight file not found: {filepath}")
            return

        with open(filepath, 'r') as f:
            data = json.load(f)

        self.current_weights = data.get('current_weights', self.default_weights.copy())
        self.weight_history = data.get('weight_history', [self.current_weights.copy()])
        self.feature_weights = data.get('feature_weights', self._initialize_feature_weights())

        logger.info(f"Weights loaded from {filepath}")

    def get_adaptation_stats(self) -> Dict[str, Any]:
        """Get statistics about weight adaptation."""
        if not self.weight_history:
            return {'status': 'no_history'}

        stats = {
            'total_adaptations': len(self.weight_history) - 1,
            'current_weights': self.current_weights,
            'weight_stability': self._calculate_weight_stability(),
            'adaptation_trends': self._calculate_adaptation_trends(),
            'feature_importance': self.feature_weights,
            'performance_history_size': len(self.performance_history)
        }

        return stats

    def _calculate_weight_stability(self) -> float:
        """Calculate weight stability over time."""
        if len(self.weight_history) < 2:
            return 1.0

        # Calculate variance in weights over time
        weight_arrays = []
        for weights in self.weight_history[-20:]:  # Last 20 adaptations
            weight_arrays.append(list(weights.values()))

        weight_arrays = np.array(weight_arrays)
        variances = np.var(weight_arrays, axis=0)
        avg_variance = np.mean(variances)

        # Convert to stability score (lower variance = higher stability)
        stability = max(0.0, 1.0 - avg_variance * 10)

        return stability

    def _calculate_adaptation_trends(self) -> Dict[str, Any]:
        """Calculate trends in weight adaptation."""
        if len(self.weight_history) < 5:
            return {'status': 'insufficient_data'}

        trends = {}

        for strategy in self.default_weights.keys():
            weights_over_time = [w.get(strategy, 0) for w in self.weight_history[-20:]]

            if len(weights_over_time) >= 2:
                # Simple linear trend
                x = np.arange(len(weights_over_time))
                slope = np.polyfit(x, weights_over_time, 1)[0]

                if slope > 0.001:
                    trends[strategy] = 'increasing'
                elif slope < -0.001:
                    trends[strategy] = 'decreasing'
                else:
                    trends[strategy] = 'stable'

        return trends

    def update_feature_weights(self, feature_updates: Dict[str, float]):
        """Update feature importance weights."""
        for feature, weight in feature_updates.items():
            if feature in self.feature_weights:
                self.feature_weights[feature] = max(0.0, min(1.0, weight))

        logger.info(f"Updated feature weights: {self.feature_weights}")

    def get_recommendations(self) -> List[str]:
        """Get recommendations for weight adaptation improvements."""
        recommendations = []

        stats = self.get_adaptation_stats()

        if stats.get('weight_stability', 1.0) < 0.7:
            recommendations.append("Consider reducing learning rate to improve weight stability")

        if len(self.performance_history) < self.adaptation_window * 0.5:
            recommendations.append("Collect more performance data for better adaptation")

        trends = stats.get('adaptation_trends', {})
        oscillating_strategies = [s for s, t in trends.items() if t not in ['stable', 'insufficient_data']]

        if len(oscillating_strategies) > 2:
            recommendations.append("Multiple strategies oscillating - consider adjusting feature weights")

        return recommendations







