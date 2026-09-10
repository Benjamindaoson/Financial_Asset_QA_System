"""
Model Adapter for GraphRAG.

This module adapts GraphRAG models based on user feedback and performance metrics,
enabling continuous improvement of system responses.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import torch
import torch.nn as nn
from collections import defaultdict
import numpy as np

from ..retrieval.strategies.dynamic_weighting import DynamicWeightingStrategy
from .feedback_analyzer import FeedbackAnalyzer

logger = logging.getLogger(__name__)


class ModelAdapter:
    """
    Adapts GraphRAG models based on user feedback and performance analysis.
    """

    def __init__(self, dynamic_weighting: Optional[DynamicWeightingStrategy] = None):
        """
        Initialize model adapter.

        Args:
            dynamic_weighting: Dynamic weighting strategy instance
        """
        self.dynamic_weighting = dynamic_weighting or DynamicWeightingStrategy()
        self.feedback_analyzer = FeedbackAnalyzer()

        # Adaptation history
        self.adaptation_history = []
        self.performance_baseline = {}

        # Adaptation parameters
        self.learning_rate = 0.1
        self.min_feedback_threshold = 10  # Minimum feedback items for adaptation
        self.adaptation_cooldown = 3600  # Minimum seconds between adaptations

        self.last_adaptation_time = 0

        logger.info("Model adapter initialized")

    def adapt_from_feedback(
        self,
        feedback_items: List[Any],
        current_performance: Dict[str, float],
        adaptation_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Adapt model based on user feedback.

        Args:
            feedback_items: Recent feedback items
            current_performance: Current system performance metrics
            adaptation_config: Adaptation configuration

        Returns:
            Adaptation results and recommendations
        """
        config = adaptation_config or {}
        adaptation_result = {
            'adapted': False,
            'changes_made': [],
            'performance_impact': {},
            'recommendations': [],
            'confidence': 0.0
        }

        try:
            # Check adaptation conditions
            if not self._should_adapt(feedback_items):
                adaptation_result['reason'] = 'insufficient_feedback_or_cooldown'
                return adaptation_result

            # Analyze feedback
            analysis = self.feedback_analyzer.analyze_feedback_batch(feedback_items)

            # Determine adaptation strategy
            adaptation_strategy = self._determine_adaptation_strategy(analysis, current_performance)

            if adaptation_strategy:
                # Apply adaptations
                changes = self._apply_adaptations(adaptation_strategy, analysis)

                adaptation_result.update({
                    'adapted': True,
                    'changes_made': changes,
                    'strategy': adaptation_strategy,
                    'analysis_summary': analysis['summary'],
                    'confidence': self._calculate_adaptation_confidence(analysis)
                })

                # Record adaptation
                self._record_adaptation(adaptation_result)

                logger.info(f"Model adaptation completed: {len(changes)} changes applied")

            else:
                adaptation_result['reason'] = 'no_adaptation_needed'

        except Exception as e:
            logger.error(f"Model adaptation failed: {e}")
            adaptation_result['error'] = str(e)

        return adaptation_result

    def _should_adapt(self, feedback_items: List[Any]) -> bool:
        """Determine if adaptation should be performed."""
        import time

        # Check feedback volume
        if len(feedback_items) < self.min_feedback_threshold:
            return False

        # Check cooldown period
        current_time = time.time()
        if current_time - self.last_adaptation_time < self.adaptation_cooldown:
            return False

        # Check feedback quality (diversity)
        feedback_types = set()
        for item in feedback_items:
            feedback_types.add(item.feedback_type.value)

        if len(feedback_types) < 2:  # Need diverse feedback
            return False

        return True

    def _determine_adaptation_strategy(
        self,
        analysis: Dict[str, Any],
        performance: Dict[str, float]
    ) -> Optional[str]:
        """
        Determine the best adaptation strategy based on analysis.

        Args:
            analysis: Feedback analysis results
            performance: Current performance metrics

        Returns:
            Adaptation strategy name or None
        """
        # Analyze key metrics
        avg_rating = analysis['summary'].get('avg_rating')
        error_rate = analysis['error_analysis']['error_rate']
        sentiment = analysis['sentiment_analysis']['overall_sentiment']

        # Determine strategy based on issues
        if avg_rating and avg_rating < 3.0:  # Poor ratings
            return 'aggressive_retrieval_optimization'
        elif error_rate > 0.3:  # High error rate
            return 'accuracy_focused_adaptation'
        elif sentiment == 'negative':
            return 'user_experience_optimization'
        elif performance.get('recall_rate', 1.0) < 0.8:  # Low recall
            return 'retrieval_enhancement'
        elif performance.get('response_time', 0) > 2.0:  # Slow responses
            return 'performance_optimization'
        else:
            return None  # No adaptation needed

    def _apply_adaptations(
        self,
        strategy: str,
        analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Apply the determined adaptation strategy.

        Args:
            strategy: Adaptation strategy
            analysis: Feedback analysis

        Returns:
            List of changes made
        """
        changes = []

        if strategy == 'aggressive_retrieval_optimization':
            changes.extend(self._optimize_retrieval_aggressively(analysis))

        elif strategy == 'accuracy_focused_adaptation':
            changes.extend(self._focus_on_accuracy(analysis))

        elif strategy == 'user_experience_optimization':
            changes.extend(self._optimize_user_experience(analysis))

        elif strategy == 'retrieval_enhancement':
            changes.extend(self._enhance_retrieval(analysis))

        elif strategy == 'performance_optimization':
            changes.extend(self._optimize_performance(analysis))

        # Apply changes to dynamic weighting
        if changes:
            self._update_dynamic_weighting(changes)

        return changes

    def _optimize_retrieval_aggressively(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Aggressively optimize retrieval based on poor ratings."""
        changes = []

        # Increase weight for graph-based retrieval
        changes.append({
            'type': 'weight_adjustment',
            'component': 'graph_retrieval',
            'parameter': 'weight',
            'old_value': 0.35,
            'new_value': 0.5,
            'reason': 'poor_user_ratings'
        })

        # Enable more expansive query expansion
        changes.append({
            'type': 'parameter_adjustment',
            'component': 'query_expansion',
            'parameter': 'max_expansions',
            'old_value': 5,
            'new_value': 8,
            'reason': 'improve_answer_quality'
        })

        # Adjust reranking threshold
        changes.append({
            'type': 'parameter_adjustment',
            'component': 'reranker',
            'parameter': 'confidence_threshold',
            'old_value': 0.7,
            'new_value': 0.6,
            'reason': 'balance_precision_recall'
        })

        return changes

    def _focus_on_accuracy(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Focus on accuracy improvements."""
        changes = []

        # Increase evidence verification strictness
        changes.append({
            'type': 'parameter_adjustment',
            'component': 'evidence_verification',
            'parameter': 'min_confidence_threshold',
            'old_value': 0.8,
            'new_value': 0.9,
            'reason': 'reduce_errors'
        })

        # Enable stricter answer validation
        changes.append({
            'type': 'feature_toggle',
            'component': 'post_binding_verification',
            'parameter': 'enabled',
            'old_value': False,
            'new_value': True,
            'reason': 'prevent_hallucinations'
        })

        # Adjust judgment orchestrator thresholds
        changes.append({
            'type': 'parameter_adjustment',
            'component': 'judgment_orchestrator',
            'parameter': 'conservative_threshold',
            'old_value': 0.7,
            'new_value': 0.8,
            'reason': 'favor_accuracy_over_coverage'
        })

        return changes

    def _optimize_user_experience(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Optimize user experience based on negative sentiment."""
        changes = []

        # Improve response formatting
        changes.append({
            'type': 'parameter_adjustment',
            'component': 'answer_generation',
            'parameter': 'max_response_length',
            'old_value': 1000,
            'new_value': 800,
            'reason': 'concise_responses'
        })

        # Add more user-friendly explanations
        changes.append({
            'type': 'feature_toggle',
            'component': 'answer_explanations',
            'parameter': 'detailed_explanations',
            'old_value': False,
            'new_value': True,
            'reason': 'better_user_understanding'
        })

        # Adjust confidence thresholds for refusal
        changes.append({
            'type': 'parameter_adjustment',
            'component': 'pre_judgment_gate',
            'parameter': 'refusal_threshold',
            'old_value': 0.3,
            'new_value': 0.4,
            'reason': 'reduce_uncertain_responses'
        })

        return changes

    def _enhance_retrieval(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Enhance retrieval capabilities."""
        changes = []

        # Increase retrieval depth
        changes.append({
            'type': 'parameter_adjustment',
            'component': 'multi_stage_retriever',
            'parameter': 'max_path_depth',
            'old_value': 3,
            'new_value': 4,
            'reason': 'improve_recall'
        })

        # Enable additional retrieval strategies
        changes.append({
            'type': 'feature_toggle',
            'component': 'colbert_retrieval',
            'parameter': 'enabled',
            'old_value': False,
            'new_value': True,
            'reason': 'better_semantic_matching'
        })

        # Adjust BM25 weight
        changes.append({
            'type': 'weight_adjustment',
            'component': 'bm25_retrieval',
            'parameter': 'weight',
            'old_value': 0.05,
            'new_value': 0.1,
            'reason': 'balance_sparse_dense_retrieval'
        })

        return changes

    def _optimize_performance(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Optimize system performance."""
        changes = []

        # Enable response caching
        changes.append({
            'type': 'feature_toggle',
            'component': 'response_cache',
            'parameter': 'enabled',
            'old_value': False,
            'new_value': True,
            'reason': 'reduce_response_time'
        })

        # Optimize batch processing
        changes.append({
            'type': 'parameter_adjustment',
            'component': 'inference_optimizer',
            'parameter': 'max_batch_size',
            'old_value': 32,
            'new_value': 16,
            'reason': 'balance_throughput_latency'
        })

        # Enable model quantization if not already
        changes.append({
            'type': 'feature_toggle',
            'component': 'model_quantization',
            'parameter': 'int8_quantization',
            'old_value': False,
            'new_value': True,
            'reason': 'faster_inference'
        })

        return changes

    def _update_dynamic_weighting(self, changes: List[Dict[str, Any]]):
        """Update dynamic weighting strategy based on changes."""
        try:
            weight_updates = {}
            param_updates = {}

            for change in changes:
                if change['type'] == 'weight_adjustment':
                    component = change['component']
                    weight_updates[component] = change['new_value']
                elif change['type'] == 'parameter_adjustment':
                    component = change['component']
                    param = change['parameter']
                    param_updates[f"{component}.{param}"] = change['new_value']

            # Apply updates to dynamic weighting
            if weight_updates:
                self.dynamic_weighting.update_from_feedback({'weight_updates': weight_updates})

            if param_updates:
                self.dynamic_weighting.update_from_feedback({'param_updates': param_updates})

        except Exception as e:
            logger.warning(f"Failed to update dynamic weighting: {e}")

    def _calculate_adaptation_confidence(self, analysis: Dict[str, Any]) -> float:
        """Calculate confidence in adaptation decisions."""
        try:
            # Base confidence on feedback volume and consistency
            feedback_count = analysis['summary']['total_feedback']

            # Volume factor
            volume_confidence = min(feedback_count / 50, 1.0)  # Max at 50 feedback items

            # Consistency factor (agreement in feedback)
            rating_std = np.std([
                item.content.get('rating', 3) for item in analysis.get('feedback_items', [])
                if item.feedback_type.value == 'rating'
            ]) if analysis.get('feedback_items') else 0

            consistency_confidence = max(0, 1.0 - rating_std / 2)  # Lower std = higher confidence

            # Quality factor
            quality_metrics = analysis.get('quality_metrics', {})
            quality_confidence = quality_metrics.get('feedback_completeness', 0.5)

            confidence = (volume_confidence + consistency_confidence + quality_confidence) / 3.0

            return float(confidence)

        except Exception:
            return 0.5

    def _record_adaptation(self, adaptation_result: Dict[str, Any]):
        """Record adaptation for history tracking."""
        import time

        record = {
            'timestamp': time.time(),
            'changes': adaptation_result.get('changes_made', []),
            'strategy': adaptation_result.get('strategy'),
            'confidence': adaptation_result.get('confidence', 0.0),
            'performance_before': self.performance_baseline.copy(),
        }

        self.adaptation_history.append(record)
        self.last_adaptation_time = time.time()

        # Keep only recent history
        if len(self.adaptation_history) > 10:
            self.adaptation_history = self.adaptation_history[-10:]

    def get_adaptation_history(self) -> List[Dict[str, Any]]:
        """Get adaptation history."""
        return self.adaptation_history.copy()

    def evaluate_adaptation_impact(
        self,
        pre_adaptation_metrics: Dict[str, float],
        post_adaptation_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Evaluate the impact of recent adaptations.

        Args:
            pre_adaptation_metrics: Metrics before adaptation
            post_adaptation_metrics: Metrics after adaptation

        Returns:
            Impact analysis
        """
        impact = {
            'overall_improvement': 0.0,
            'metric_changes': {},
            'significant_improvements': [],
            'regressions': []
        }

        for metric, pre_value in pre_adaptation_metrics.items():
            if metric in post_adaptation_metrics:
                post_value = post_adaptation_metrics[metric]
                change = post_value - pre_value
                relative_change = change / abs(pre_value) if pre_value != 0 else 0

                impact['metric_changes'][metric] = {
                    'pre_value': pre_value,
                    'post_value': post_value,
                    'absolute_change': change,
                    'relative_change': relative_change
                }

                # Classify improvements/regressions for key metrics
                if metric in ['recall_rate', 'accuracy', 'user_satisfaction']:
                    if relative_change > 0.05:  # 5% improvement
                        impact['significant_improvements'].append(metric)
                    elif relative_change < -0.05:  # 5% regression
                        impact['regressions'].append(metric)

        # Calculate overall improvement score
        positive_changes = sum(1 for change in impact['metric_changes'].values()
                             if change['relative_change'] > 0)
        total_changes = len(impact['metric_changes'])

        impact['overall_improvement'] = positive_changes / total_changes if total_changes > 0 else 0.0

        return impact

    def recommend_next_adaptation(
        self,
        current_metrics: Dict[str, float],
        recent_feedback: List[Any]
    ) -> Dict[str, Any]:
        """
        Recommend next adaptation based on current state.

        Args:
            current_metrics: Current system metrics
            recent_feedback: Recent feedback items

        Returns:
            Adaptation recommendation
        """
        recommendation = {
            'recommended': False,
            'strategy': None,
            'confidence': 0.0,
            'rationale': [],
            'expected_impact': {}
        }

        try:
            if not recent_feedback:
                recommendation['rationale'].append('insufficient_recent_feedback')
                return recommendation

            # Analyze current performance
            analysis = self.feedback_analyzer.analyze_feedback_batch(recent_feedback)

            # Check performance thresholds
            recall_rate = current_metrics.get('recall_rate', 1.0)
            response_time = current_metrics.get('response_time', 0)
            user_satisfaction = analysis['summary'].get('avg_rating')

            if user_satisfaction and user_satisfaction < 3.5:
                recommendation.update({
                    'recommended': True,
                    'strategy': 'user_experience_optimization',
                    'confidence': 0.8,
                    'rationale': ['low_user_satisfaction'],
                    'expected_impact': {'user_satisfaction': '+0.5'}
                })

            elif recall_rate < 0.85:
                recommendation.update({
                    'recommended': True,
                    'strategy': 'retrieval_enhancement',
                    'confidence': 0.7,
                    'rationale': ['low_recall_rate'],
                    'expected_impact': {'recall_rate': '+0.1'}
                })

            elif response_time > 1.5:
                recommendation.update({
                    'recommended': True,
                    'strategy': 'performance_optimization',
                    'confidence': 0.6,
                    'rationale': ['slow_response_time'],
                    'expected_impact': {'response_time': '-0.5s'}
                })

        except Exception as e:
            logger.warning(f"Failed to generate adaptation recommendation: {e}")

        return recommendation







