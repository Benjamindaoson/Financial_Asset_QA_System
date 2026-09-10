"""
A/B Testing Framework for GraphRAG.

This module provides A/B testing capabilities to evaluate and validate
model improvements and system changes in production.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import hashlib
import random
import json
from datetime import datetime, timedelta
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


class ABTest:
    """
    Individual A/B test configuration and execution.
    """

    def __init__(
        self,
        test_id: str,
        name: str,
        description: str,
        variants: Dict[str, Dict[str, Any]],
        target_metric: str,
        sample_size: int = 1000,
        duration_days: int = 7,
        traffic_split: Optional[Dict[str, float]] = None
    ):
        """
        Initialize A/B test.

        Args:
            test_id: Unique test identifier
            name: Human-readable test name
            description: Test description
            variants: Test variants configuration
            target_metric: Primary metric to optimize
            sample_size: Minimum sample size per variant
            duration_days: Test duration in days
            traffic_split: Traffic distribution across variants
        """
        self.test_id = test_id
        self.name = name
        self.description = description
        self.variants = variants
        self.target_metric = target_metric
        self.sample_size = sample_size
        self.duration_days = duration_days

        # Default equal traffic split
        if traffic_split is None:
            equal_split = 1.0 / len(variants)
            traffic_split = {variant_id: equal_split for variant_id in variants.keys()}

        self.traffic_split = traffic_split

        # Test state
        self.start_time = None
        self.end_time = None
        self.is_active = False
        self.results = {variant_id: {'samples': 0, 'metrics': defaultdict(list)}
                       for variant_id in variants.keys()}

        # Statistical analysis
        self.confidence_level = 0.95
        self.minimum_effect_size = 0.05

    def start_test(self):
        """Start the A/B test."""
        self.start_time = datetime.utcnow()
        self.is_active = True
        logger.info(f"Started A/B test: {self.name} ({self.test_id})")

    def end_test(self) -> Dict[str, Any]:
        """End the A/B test and return results."""
        self.end_time = datetime.utcnow()
        self.is_active = False

        results = self.analyze_results()
        logger.info(f"Ended A/B test: {self.name} - Winner: {results.get('winner', 'none')}")

        return results

    def assign_variant(self, user_id: str) -> str:
        """
        Assign user to a test variant using consistent hashing.

        Args:
            user_id: User identifier

        Returns:
            Assigned variant ID
        """
        if not self.is_active:
            return list(self.variants.keys())[0]  # Default to first variant

        # Use consistent hashing for variant assignment
        hash_value = int(hashlib.md5(f"{self.test_id}_{user_id}".encode()).hexdigest(), 16)
        normalized_hash = hash_value / 2**128  # Normalize to 0-1

        # Assign based on traffic split
        cumulative_split = 0.0
        for variant_id, split in self.traffic_split.items():
            cumulative_split += split
            if normalized_hash <= cumulative_split:
                return variant_id

        # Fallback
        return list(self.variants.keys())[0]

    def record_metric(self, user_id: str, variant_id: str, metric_name: str, value: float):
        """
        Record a metric value for a user-variant pair.

        Args:
            user_id: User identifier
            variant_id: Variant identifier
            metric_name: Metric name
            value: Metric value
        """
        if variant_id in self.results:
            self.results[variant_id]['samples'] += 1
            self.results[variant_id]['metrics'][metric_name].append(value)

    def analyze_results(self) -> Dict[str, Any]:
        """
        Analyze test results and determine winner.

        Returns:
            Analysis results
        """
        analysis = {
            'test_id': self.test_id,
            'test_name': self.name,
            'duration_days': (self.end_time - self.start_time).days if self.end_time and self.start_time else 0,
            'variants': {},
            'winner': None,
            'confidence': 0.0,
            'statistical_significance': False,
            'recommendation': 'continue_testing'
        }

        # Analyze each variant
        variant_metrics = {}
        for variant_id, data in self.results.items():
            samples = data['samples']
            metrics = data['metrics']

            variant_analysis = {
                'samples': samples,
                'metrics': {}
            }

            # Calculate metric statistics
            for metric_name, values in metrics.items():
                if values:
                    variant_analysis['metrics'][metric_name] = {
                        'mean': np.mean(values),
                        'std': np.std(values),
                        'count': len(values),
                        'median': np.median(values)
                    }

            analysis['variants'][variant_id] = variant_analysis
            variant_metrics[variant_id] = variant_analysis['metrics']

        # Determine winner for target metric
        if self.target_metric and len(variant_metrics) >= 2:
            winner_analysis = self._determine_winner(variant_metrics, self.target_metric)
            analysis.update(winner_analysis)

        return analysis

    def _determine_winner(self, variant_metrics: Dict[str, Dict], target_metric: str) -> Dict[str, Any]:
        """Determine the winning variant using statistical testing."""
        winner_info = {
            'winner': None,
            'confidence': 0.0,
            'statistical_significance': False,
            'effect_size': 0.0
        }

        if target_metric not in variant_metrics[list(variant_metrics.keys())[0]]:
            return winner_info

        # Extract target metric values for all variants
        variant_values = {}
        for variant_id, metrics in variant_metrics.items():
            if target_metric in metrics:
                values = self.results[variant_id]['metrics'][target_metric]
                if len(values) >= 10:  # Minimum sample size
                    variant_values[variant_id] = values

        if len(variant_values) < 2:
            return winner_info

        # Perform statistical test (simplified t-test approximation)
        variant_ids = list(variant_values.keys())
        best_variant = None
        best_mean = float('-inf') if self._is_higher_better(target_metric) else float('inf')
        second_best_mean = best_mean

        means = {}
        for variant_id, values in variant_values.items():
            mean_val = np.mean(values)
            means[variant_id] = mean_val

            if self._is_higher_better(target_metric):
                if mean_val > best_mean:
                    second_best_mean = best_mean
                    best_mean = mean_val
                    best_variant = variant_id
                elif mean_val > second_best_mean:
                    second_best_mean = mean_val
            else:
                if mean_val < best_mean:
                    second_best_mean = best_mean
                    best_mean = mean_val
                    best_variant = variant_id
                elif mean_val < second_best_mean:
                    second_best_mean = mean_val

        if best_variant and second_best_mean != best_mean:
            # Calculate effect size and confidence
            effect_size = abs(best_mean - second_best_mean) / max(abs(best_mean), abs(second_best_mean))

            # Simplified confidence calculation based on sample sizes and variance
            total_samples = sum(len(variant_values[v]) for v in variant_values)
            confidence = min(effect_size * np.sqrt(total_samples / 100), 1.0)

            winner_info.update({
                'winner': best_variant,
                'confidence': confidence,
                'effect_size': effect_size,
                'statistical_significance': effect_size > self.minimum_effect_size and confidence > 0.8
            })

        return winner_info

    def _is_higher_better(self, metric_name: str) -> bool:
        """Determine if higher values are better for a metric."""
        higher_better = [
            'accuracy', 'recall', 'precision', 'f1_score',
            'user_satisfaction', 'thumbs_up_ratio', 'avg_rating'
        ]

        lower_better = [
            'response_time', 'latency', 'error_rate', 'memory_usage'
        ]

        if metric_name in higher_better:
            return True
        elif metric_name in lower_better:
            return False
        else:
            return True  # Default to higher better

    def get_status(self) -> Dict[str, Any]:
        """Get current test status."""
        return {
            'test_id': self.test_id,
            'name': self.name,
            'is_active': self.is_active,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'progress': self._calculate_progress(),
            'variants': list(self.variants.keys()),
            'target_metric': self.target_metric
        }

    def _calculate_progress(self) -> float:
        """Calculate test progress (0-1)."""
        if not self.is_active or not self.start_time:
            return 0.0

        elapsed_time = (datetime.utcnow() - self.start_time).total_seconds()
        total_duration = self.duration_days * 24 * 3600

        time_progress = min(elapsed_time / total_duration, 1.0)

        # Sample progress
        total_samples = sum(data['samples'] for data in self.results.values())
        sample_progress = min(total_samples / (self.sample_size * len(self.variants)), 1.0)

        return (time_progress + sample_progress) / 2.0


class ABTester:
    """
    A/B testing framework for GraphRAG system evaluation.
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize A/B tester.

        Args:
            storage_path: Path to store test results
        """
        self.storage_path = storage_path or "artifacts/ab_tests"
        self.active_tests = {}
        self.completed_tests = {}
        self.test_templates = self._load_test_templates()

        # Create storage directory
        import os
        os.makedirs(self.storage_path, exist_ok=True)

        logger.info("A/B tester initialized")

    def create_test(
        self,
        name: str,
        description: str,
        variants: Dict[str, Dict[str, Any]],
        target_metric: str,
        **kwargs
    ) -> str:
        """
        Create a new A/B test.

        Args:
            name: Test name
            description: Test description
            variants: Test variants
            target_metric: Metric to optimize
            **kwargs: Additional test parameters

        Returns:
            Test ID
        """
        test_id = f"ab_{int(datetime.utcnow().timestamp())}_{hash(name) % 10000}"

        test = ABTest(
            test_id=test_id,
            name=name,
            description=description,
            variants=variants,
            target_metric=target_metric,
            **kwargs
        )

        self.active_tests[test_id] = test
        self._save_test_config(test)

        logger.info(f"Created A/B test: {name} ({test_id})")
        return test_id

    def create_test_from_template(
        self,
        template_name: str,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create test from predefined template.

        Args:
            template_name: Template name
            custom_config: Custom configuration overrides

        Returns:
            Test ID
        """
        if template_name not in self.test_templates:
            raise ValueError(f"Unknown template: {template_name}")

        template = self.test_templates[template_name]
        config = {**template, **(custom_config or {})}

        return self.create_test(**config)

    def start_test(self, test_id: str):
        """Start an A/B test."""
        if test_id in self.active_tests:
            self.active_tests[test_id].start_test()
        else:
            raise ValueError(f"Test {test_id} not found")

    def end_test(self, test_id: str) -> Dict[str, Any]:
        """End an A/B test and get results."""
        if test_id not in self.active_tests:
            raise ValueError(f"Test {test_id} not found")

        test = self.active_tests[test_id]
        results = test.end_test()

        # Move to completed tests
        self.completed_tests[test_id] = test
        del self.active_tests[test_id]

        # Save results
        self._save_test_results(test_id, results)

        return results

    def get_variant_for_user(self, user_id: str, test_id: str) -> str:
        """
        Get test variant assignment for user.

        Args:
            user_id: User identifier
            test_id: Test identifier

        Returns:
            Assigned variant ID
        """
        if test_id in self.active_tests:
            return self.active_tests[test_id].assign_variant(user_id)
        else:
            # Default to first variant if test completed or not found
            return "control"

    def record_user_metric(
        self,
        user_id: str,
        test_id: str,
        metric_name: str,
        value: float,
        variant_id: Optional[str] = None
    ):
        """
        Record a metric value for a user in a test.

        Args:
            user_id: User identifier
            test_id: Test identifier
            metric_name: Metric name
            value: Metric value
            variant_id: Specific variant (optional)
        """
        if test_id in self.active_tests:
            test = self.active_tests[test_id]

            # Get variant if not provided
            if variant_id is None:
                variant_id = test.assign_variant(user_id)

            test.record_metric(user_id, variant_id, metric_name, value)

    def get_test_status(self, test_id: str) -> Dict[str, Any]:
        """Get status of a test."""
        if test_id in self.active_tests:
            test = self.active_tests[test_id]
            return test.get_status()
        elif test_id in self.completed_tests:
            test = self.completed_tests[test_id]
            status = test.get_status()
            status['completed'] = True
            return status
        else:
            raise ValueError(f"Test {test_id} not found")

    def get_active_tests(self) -> List[Dict[str, Any]]:
        """Get list of active tests."""
        return [test.get_status() for test in self.active_tests.values()]

    def get_completed_tests(self) -> List[Dict[str, Any]]:
        """Get list of completed tests."""
        return [test.get_status() for test in self.completed_tests.values()]

    def get_test_results(self, test_id: str) -> Dict[str, Any]:
        """Get results for a completed test."""
        if test_id not in self.completed_tests:
            raise ValueError(f"Test {test_id} not completed or not found")

        test = self.completed_tests[test_id]
        return test.analyze_results()

    def _load_test_templates(self) -> Dict[str, Dict[str, Any]]:
        """Load predefined test templates."""
        return {
            'retrieval_optimization': {
                'name': 'Retrieval Strategy Optimization',
                'description': 'Compare different retrieval strategies',
                'variants': {
                    'control': {'retrieval_strategy': 'bm25'},
                    'variant_a': {'retrieval_strategy': 'dense_only'},
                    'variant_b': {'retrieval_strategy': 'hybrid_sparse_dense'}
                },
                'target_metric': 'recall_rate',
                'sample_size': 500,
                'duration_days': 5
            },

            'response_length': {
                'name': 'Response Length Optimization',
                'description': 'Test optimal response length',
                'variants': {
                    'short': {'max_length': 200},
                    'medium': {'max_length': 500},
                    'long': {'max_length': 1000}
                },
                'target_metric': 'user_satisfaction',
                'sample_size': 300,
                'duration_days': 3
            },

            'model_temperature': {
                'name': 'Generation Temperature Tuning',
                'description': 'Find optimal generation temperature',
                'variants': {
                    'conservative': {'temperature': 0.1},
                    'balanced': {'temperature': 0.7},
                    'creative': {'temperature': 1.2}
                },
                'target_metric': 'answer_quality',
                'sample_size': 400,
                'duration_days': 4
            },

            'multimodal_fusion': {
                'name': 'Multimodal Fusion Strategy',
                'description': 'Compare multimodal fusion approaches',
                'variants': {
                    'text_only': {'fusion_method': 'text_only'},
                    'late_fusion': {'fusion_method': 'late_fusion'},
                    'early_fusion': {'fusion_method': 'early_fusion'}
                },
                'target_metric': 'multimodal_accuracy',
                'sample_size': 600,
                'duration_days': 7
            }
        }

    def _save_test_config(self, test: ABTest):
        """Save test configuration."""
        try:
            config = {
                'test_id': test.test_id,
                'name': test.name,
                'description': test.description,
                'variants': test.variants,
                'target_metric': test.target_metric,
                'sample_size': test.sample_size,
                'duration_days': test.duration_days,
                'traffic_split': test.traffic_split,
                'created_at': datetime.utcnow().isoformat()
            }

            filepath = f"{self.storage_path}/{test.test_id}_config.json"
            with open(filepath, 'w') as f:
                json.dump(config, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save test config: {e}")

    def _save_test_results(self, test_id: str, results: Dict[str, Any]):
        """Save test results."""
        try:
            results['saved_at'] = datetime.utcnow().isoformat()

            filepath = f"{self.storage_path}/{test_id}_results.json"
            with open(filepath, 'w') as f:
                json.dump(results, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save test results: {e}")

    def generate_test_report(self, test_id: str) -> Dict[str, Any]:
        """
        Generate comprehensive test report.

        Args:
            test_id: Test identifier

        Returns:
            Test report
        """
        if test_id not in self.completed_tests:
            raise ValueError(f"Test {test_id} not completed")

        test = self.completed_tests[test_id]
        results = test.analyze_results()

        report = {
            'test_info': {
                'id': test.test_id,
                'name': test.name,
                'description': test.description,
                'duration': (test.end_time - test.start_time).days if test.end_time and test.start_time else 0,
                'target_metric': test.target_metric
            },
            'results': results,
            'insights': self._generate_test_insights(results),
            'recommendations': self._generate_test_recommendations(results)
        }

        return report

    def _generate_test_insights(self, results: Dict[str, Any]) -> List[str]:
        """Generate insights from test results."""
        insights = []

        winner = results.get('winner')
        confidence = results.get('confidence', 0)
        variants = results.get('variants', {})

        if winner:
            winner_data = variants.get(winner, {})
            winner_metrics = winner_data.get('metrics', {})

            insights.append(f"Variant '{winner}' showed the best performance with {confidence:.1%} confidence")

            # Add metric-specific insights
            target_metric = results.get('target_metric', 'unknown')
            if target_metric in winner_metrics:
                winner_value = winner_metrics[target_metric]['mean']
                insights.append(f"Average {target_metric}: {winner_value:.3f}")

        # Compare variants
        if len(variants) >= 2:
            variant_names = list(variants.keys())
            best_variant = max(variants.keys(),
                             key=lambda v: variants[v]['metrics'].get(target_metric, {}).get('mean', 0))

            insights.append(f"Best performing variant: {best_variant}")

        return insights

    def _generate_test_recommendations(self, results: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on test results."""
        recommendations = []

        winner = results.get('winner')
        statistical_significance = results.get('statistical_significance', False)

        if winner and statistical_significance:
            recommendations.append(f"Roll out variant '{winner}' to all users")
            recommendations.append("Monitor key metrics for 2 weeks after rollout")
        elif winner:
            recommendations.append(f"Consider rolling out variant '{winner}' but continue monitoring")
            recommendations.append("Run additional tests to increase statistical confidence")
        else:
            recommendations.append("No clear winner - consider running test longer or with larger sample size")
            recommendations.append("Review test configuration and variants")

        return recommendations







