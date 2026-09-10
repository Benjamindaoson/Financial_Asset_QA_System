"""
Response Optimizer for GraphRAG.

This module optimizes response times through quantization, caching,
batch processing, and inference acceleration techniques.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future
import numpy as np

logger = logging.getLogger(__name__)


class ResponseOptimizer:
    """
    Comprehensive response time optimization for GraphRAG queries.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize response optimizer.

        Args:
            config: Optimization configuration
        """
        self.config = config or {}

        # Performance targets
        self.target_p95_latency = self.config.get('target_p95_latency', 500)  # milliseconds
        self.target_mean_latency = self.config.get('target_mean_latency', 200)  # milliseconds

        # Optimization strategies
        self.enable_quantization = self.config.get('enable_quantization', True)
        self.enable_caching = self.config.get('enable_caching', True)
        self.enable_batch_processing = self.config.get('enable_batch_processing', True)
        self.enable_async_processing = self.config.get('enable_async_processing', True)

        # Caching
        self.query_cache = {}
        self.response_cache = {}
        self.cache_ttl = self.config.get('cache_ttl', 3600)  # 1 hour

        # Batch processing
        self.batch_size = self.config.get('batch_size', 8)
        self.batch_timeout = self.config.get('batch_timeout', 0.1)  # 100ms
        self.pending_batches = {}
        self.batch_executor = ThreadPoolExecutor(max_workers=4)

        # Performance monitoring
        self.latency_history = []
        self.max_history_size = 1000

        # Model optimization
        self.quantized_models = {}
        self.model_cache = {}

        logger.info("Response optimizer initialized")

    def optimize_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Optimize and process a query with response time optimizations.

        Args:
            query: Input query
            context: Query context information

        Returns:
            Optimization results and processed query
        """
        start_time = time.time()
        context = context or {}

        optimization_result = {
            'original_query': query,
            'optimization_applied': [],
            'cache_hit': False,
            'batch_processed': False,
            'quantization_used': False,
            'processing_time': 0.0,
            'estimated_latency': 0.0
        }

        try:
            # Step 1: Check cache
            if self.enable_caching:
                cache_result = self._check_query_cache(query, context)
                if cache_result:
                    optimization_result['cache_hit'] = True
                    optimization_result['cached_response'] = cache_result
                    optimization_result['optimization_applied'].append('cache_hit')
                    optimization_result['processing_time'] = time.time() - start_time
                    return optimization_result

            # Step 2: Query preprocessing and optimization
            optimized_query = self._preprocess_query(query, context)
            optimization_result['optimized_query'] = optimized_query

            # Step 3: Determine processing strategy
            processing_strategy = self._determine_processing_strategy(query, context)

            if processing_strategy == 'batch':
                optimization_result['batch_processed'] = True
                optimization_result['optimization_applied'].append('batch_processing')
            elif processing_strategy == 'async':
                optimization_result['optimization_applied'].append('async_processing')

            # Step 4: Apply quantization if applicable
            if self.enable_quantization and self._should_quantize(query):
                optimization_result['quantization_used'] = True
                optimization_result['optimization_applied'].append('quantization')

            # Step 5: Estimate latency
            optimization_result['estimated_latency'] = self._estimate_query_latency(
                query, optimization_result['optimization_applied']
            )

            optimization_result['processing_time'] = time.time() - start_time

        except Exception as e:
            logger.error(f"Query optimization failed: {e}")
            optimization_result['error'] = str(e)

        return optimization_result

    def _check_query_cache(self, query: str, context: Dict[str, Any]) -> Optional[Any]:
        """
        Check if query result is cached.

        Args:
            query: Query string
            context: Query context

        Returns:
            Cached result if available
        """
        cache_key = self._generate_cache_key(query, context)

        if cache_key in self.response_cache:
            cached_item = self.response_cache[cache_key]
            if time.time() - cached_item['timestamp'] < self.cache_ttl:
                logger.info(f"Cache hit for query: {query[:50]}...")
                return cached_item['result']
            else:
                # Remove expired cache entry
                del self.response_cache[cache_key]

        return None

    def _generate_cache_key(self, query: str, context: Dict[str, Any]) -> str:
        """
        Generate cache key for query.

        Args:
            query: Query string
            context: Query context

        Returns:
            Cache key
        """
        import hashlib
        key_components = [query]

        # Include relevant context in cache key
        if 'user_id' in context:
            key_components.append(str(context['user_id']))
        if 'session_id' in context:
            key_components.append(str(context['session_id']))

        key_string = '|'.join(key_components)
        return hashlib.md5(key_string.encode()).hexdigest()

    def _preprocess_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess and optimize query.

        Args:
            query: Original query
            context: Query context

        Returns:
            Optimized query information
        """
        optimized = {
            'text': query,
            'length': len(query),
            'complexity': self._assess_query_complexity(query),
            'optimizations': []
        }

        # Query length optimization
        if len(query) > 1000:
            optimized['text'] = query[:1000] + "..."
            optimized['optimizations'].append('truncated')

        # Remove unnecessary whitespace
        optimized['text'] = ' '.join(optimized['text'].split())
        if optimized['text'] != query:
            optimized['optimizations'].append('whitespace_normalized')

        # Keyword extraction for faster processing
        keywords = self._extract_query_keywords(query)
        optimized['keywords'] = keywords

        return optimized

    def _assess_query_complexity(self, query: str) -> str:
        """
        Assess computational complexity of query.

        Args:
            query: Query string

        Returns:
            Complexity level
        """
        length = len(query)
        question_words = len([w for w in query.lower().split() if w in
                            ['what', 'how', 'why', 'when', 'where', 'who', 'which']])
        technical_terms = len([w for w in query.lower().split() if w in
                             ['algorithm', 'neural', 'network', 'graph', 'embedding', 'retrieval']])

        if length > 500 or question_words > 2 or technical_terms > 3:
            return 'high'
        elif length > 200 or question_words > 1 or technical_terms > 1:
            return 'medium'
        else:
            return 'low'

    def _extract_query_keywords(self, query: str) -> List[str]:
        """
        Extract important keywords from query.

        Args:
            query: Query string

        Returns:
            List of keywords
        """
        # Simple keyword extraction (could use more sophisticated NLP)
        words = query.lower().split()
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}

        keywords = [word for word in words if len(word) > 3 and word not in stop_words][:5]
        return keywords

    def _determine_processing_strategy(self, query: str, context: Dict[str, Any]) -> str:
        """
        Determine optimal processing strategy for query.

        Args:
            query: Query string
            context: Query context

        Returns:
            Processing strategy
        """
        # Check if batch processing is beneficial
        if (self.enable_batch_processing and
            len(self.pending_batches) < self.batch_size and
            self._assess_query_complexity(query) != 'high'):
            return 'batch'

        # Check if async processing is needed
        if self.enable_async_processing and context.get('async_preferred', False):
            return 'async'

        return 'sync'

    def _should_quantize(self, query: str) -> bool:
        """
        Determine if quantization should be used for this query.

        Args:
            query: Query string

        Returns:
            Whether to use quantization
        """
        if not self.enable_quantization:
            return False

        # Use quantization for complex queries to reduce computation
        complexity = self._assess_query_complexity(query)
        return complexity in ['high', 'medium']

    def _estimate_query_latency(self, query: str, optimizations: List[str]) -> float:
        """
        Estimate query processing latency.

        Args:
            query: Query string
            optimizations: Applied optimizations

        Returns:
            Estimated latency in milliseconds
        """
        base_latency = 300.0  # Base latency in ms

        # Adjust based on query complexity
        complexity = self._assess_query_complexity(query)
        if complexity == 'high':
            base_latency *= 2.0
        elif complexity == 'medium':
            base_latency *= 1.5

        # Adjust based on optimizations
        if 'cache_hit' in optimizations:
            base_latency *= 0.1  # speedup target
        if 'batch_processing' in optimizations:
            base_latency *= 0.8  # 20% speedup
        if 'quantization' in optimizations:
            base_latency *= 0.7  # 30% speedup

        return base_latency

    def process_batch_queries(self, queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process multiple queries in batch for efficiency.

        Args:
            queries: List of query dictionaries

        Returns:
            List of processed results
        """
        if not queries:
            return []

        start_time = time.time()
        batch_id = f"batch_{int(time.time() * 1000)}"

        logger.info(f"Processing batch of {len(queries)} queries")

        # Simulate batch processing
        results = []
        for query_info in queries:
            result = self.optimize_query(
                query_info.get('query', ''),
                query_info.get('context', {})
            )
            results.append(result)

        batch_time = time.time() - start_time
        logger.info(f"Batch processing completed in {batch_time:.2f}s")

        return results

    def cache_response(self, query: str, context: Dict[str, Any], response: Any):
        """
        Cache query response for future use.

        Args:
            query: Query string
            context: Query context
            response: Response to cache
        """
        if not self.enable_caching:
            return

        cache_key = self._generate_cache_key(query, context)

        self.response_cache[cache_key] = {
            'result': response,
            'timestamp': time.time(),
            'query': query,
            'context': context
        }

        # Limit cache size
        if len(self.response_cache) > 1000:
            # Remove oldest entries
            sorted_cache = sorted(self.response_cache.items(),
                                key=lambda x: x[1]['timestamp'])
            for old_key, _ in sorted_cache[:100]:
                del self.response_cache[old_key]

    def record_latency(self, latency_ms: float):
        """
        Record query latency for performance monitoring.

        Args:
            latency_ms: Query latency in milliseconds
        """
        self.latency_history.append({
            'latency': latency_ms,
            'timestamp': time.time()
        })

        # Maintain history size
        if len(self.latency_history) > self.max_history_size:
            self.latency_history = self.latency_history[-self.max_history_size:]

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics.

        Returns:
            Performance metrics
        """
        if not self.latency_history:
            return {'status': 'no_data'}

        latencies = [item['latency'] for item in self.latency_history]

        stats = {
            'total_queries': len(latencies),
            'mean_latency': np.mean(latencies),
            'median_latency': np.median(latencies),
            'p95_latency': np.percentile(latencies, 95),
            'p99_latency': np.percentile(latencies, 99),
            'min_latency': np.min(latencies),
            'max_latency': np.max(latencies),
            'cache_hit_rate': self._calculate_cache_hit_rate(),
            'batch_processing_rate': 0.0,  # Would need to track this
            'target_p95_achieved': np.percentile(latencies, 95) <= self.target_p95_latency,
            'target_mean_achieved': np.mean(latencies) <= self.target_mean_latency
        }

        return stats

    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        # This would require tracking cache hits vs misses
        # For now, return a placeholder
        return 0.0

    def optimize_model_inference(self, model_name: str, input_data: Any) -> Dict[str, Any]:
        """
        Optimize model inference using quantization and acceleration.

        Args:
            model_name: Name of model to optimize
            input_data: Input data for inference

        Returns:
            Optimization results
        """
        optimization_result = {
            'model': model_name,
            'optimization_applied': [],
            'original_latency': 0.0,
            'optimized_latency': 0.0,
            'speedup': 1.0
        }

        try:
            # Apply quantization if enabled
            if self.enable_quantization and model_name in self.quantized_models:
                optimization_result['optimization_applied'].append('quantization')
                # Simulate quantization speedup
                optimization_result['speedup'] *= 1.5

            # Apply other optimizations
            if self._should_use_tensorrt(model_name):
                optimization_result['optimization_applied'].append('tensorrt')
                optimization_result['speedup'] *= 2.0

            if self._should_use_onnx(model_name):
                optimization_result['optimization_applied'].append('onnx')
                optimization_result['speedup'] *= 1.3

            optimization_result['optimized_latency'] = 100.0 / optimization_result['speedup']  # Example calculation

        except Exception as e:
            logger.error(f"Model inference optimization failed: {e}")
            optimization_result['error'] = str(e)

        return optimization_result

    def _should_use_tensorrt(self, model_name: str) -> bool:
        """Determine if TensorRT should be used."""
        tensorrt_models = self.config.get('tensorrt_models', [])
        return model_name in tensorrt_models

    def _should_use_onnx(self, model_name: str) -> bool:
        """Determine if ONNX Runtime should be used."""
        onnx_models = self.config.get('onnx_models', [])
        return model_name in onnx_models

    def preload_frequent_queries(self, query_patterns: List[str]):
        """
        Preload results for frequently asked query patterns.

        Args:
            query_patterns: List of query patterns to preload
        """
        logger.info(f"Preloading {len(query_patterns)} query patterns")

        for pattern in query_patterns:
            try:
                # Generate sample queries from pattern
                sample_queries = self._generate_sample_queries(pattern)

                for query in sample_queries:
                    # Process and cache query
                    result = self.optimize_query(query)
                    if 'cached_response' not in result:
                        # Simulate processing and cache result
                        mock_response = f"Response for: {query}"
                        self.cache_response(query, {}, mock_response)

            except Exception as e:
                logger.warning(f"Failed to preload pattern {pattern}: {e}")

    def _generate_sample_queries(self, pattern: str) -> List[str]:
        """
        Generate sample queries from a pattern.

        Args:
            pattern: Query pattern

        Returns:
            List of sample queries
        """
        # Simple pattern expansion
        if '{}' in pattern:
            samples = [
                pattern.format('machine learning'),
                pattern.format('neural networks'),
                pattern.format('graph databases')
            ]
        else:
            samples = [pattern]

        return samples

    def enable_adaptive_optimization(self, enable: bool = True):
        """
        Enable adaptive optimization based on query patterns.

        Args:
            enable: Whether to enable adaptive optimization
        """
        self.adaptive_optimization = enable

        if enable:
            logger.info("Adaptive optimization enabled")
            # Would start background thread to analyze patterns and adjust strategies
        else:
            logger.info("Adaptive optimization disabled")

    def get_optimization_recommendations(self) -> Dict[str, Any]:
        """
        Get recommendations for further optimization.

        Returns:
            Optimization recommendations
        """
        stats = self.get_performance_stats()

        recommendations = []

        if stats.get('p95_latency', 0) > self.target_p95_latency:
            recommendations.append({
                'type': 'latency_optimization',
                'description': 'P95 latency exceeds target - consider increasing batch size or enabling more aggressive quantization',
                'priority': 'high'
            })

        if stats.get('cache_hit_rate', 0) < 0.3:
            recommendations.append({
                'type': 'caching_optimization',
                'description': 'Low cache hit rate - consider increasing cache TTL or preloading more query patterns',
                'priority': 'medium'
            })

        if len(self.response_cache) > 500:
            recommendations.append({
                'type': 'memory_optimization',
                'description': 'Large cache size - consider implementing cache eviction policy',
                'priority': 'low'
            })

        return {
            'recommendations': recommendations,
            'current_stats': stats
        }







