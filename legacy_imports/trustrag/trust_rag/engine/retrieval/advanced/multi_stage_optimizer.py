"""
Multi-Stage Retrieval Optimizer for GraphRAG.

This module optimizes multi-stage retrieval strategies for improved recall,
precision, and response times, with specialized support for long-tail queries.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


class MultiStageRetrievalOptimizer:
    """
    Advanced multi-stage retrieval optimizer with adaptive strategies.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize multi-stage retrieval optimizer.

        Args:
            config: Optimizer configuration
        """
        self.config = config or {}

        # Performance targets
        self.target_recall = self.config.get('target_recall', 0.85)  # 85% for long-tail queries
        self.target_precision = self.config.get('target_precision', 0.75)
        self.target_latency_p95 = self.config.get('target_latency_p95', 500)  # ms

        # Retrieval stages configuration
        self.stages = {
            'initial_retrieval': {
                'strategies': ['vector_search', 'bm25_search'],
                'parallel': True,
                'timeout': 100,  # ms
                'target_candidates': 100
            },
            'expansion_stage': {
                'strategies': ['query_expansion', 'semantic_expansion'],
                'parallel': False,
                'timeout': 150,
                'expansion_factor': 1.5
            },
            'refinement_stage': {
                'strategies': ['graph_search', 'hybrid_search'],
                'parallel': True,
                'timeout': 200,
                'refinement_candidates': 50
            },
            'reranking_stage': {
                'strategies': ['cross_encoder_rerank', 'diversity_rerank'],
                'parallel': False,
                'timeout': 100,
                'final_candidates': 20
            }
        }

        # Adaptive components
        self.weight_adapter = None
        self.performance_monitor = None

        # Execution settings
        self.max_workers = self.config.get('max_workers', 8)
        self.enable_caching = self.config.get('enable_caching', True)
        self.cache_ttl = self.config.get('cache_ttl', 3600)

        # Query result cache
        self.result_cache = {}
        self.query_cache = {}

        # Performance tracking
        self.execution_stats = defaultdict(list)
        self.stage_timings = defaultdict(list)

        # Initialize components
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        logger.info("Multi-stage retrieval optimizer initialized")

    def optimize_retrieval(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute optimized multi-stage retrieval for a query.

        Args:
            query: Input query
            context: Query context and metadata

        Returns:
            Optimized retrieval results
        """
        start_time = time.time()
        context = context or {}

        # Generate cache key
        cache_key = self._generate_cache_key(query, context)

        # Check cache
        if self.enable_caching and cache_key in self.result_cache:
            cached_result = self.result_cache[cache_key]
            if time.time() - cached_result['timestamp'] < self.cache_ttl:
                logger.info(f"Using cached retrieval result for query")
                return cached_result['result']

        # Analyze query characteristics
        query_analysis = self._analyze_query(query, context)

        # Determine optimal retrieval strategy
        strategy_config = self._determine_optimal_strategy(query_analysis)

        # Execute multi-stage retrieval
        retrieval_result = self._execute_multi_stage_retrieval(query, query_analysis, strategy_config)

        # Apply final optimizations
        final_result = self._apply_final_optimizations(retrieval_result, query_analysis)

        # Cache result
        if self.enable_caching:
            self.result_cache[cache_key] = {
                'result': final_result,
                'timestamp': time.time()
            }

        # Record performance metrics
        total_time = time.time() - start_time
        self._record_performance_metrics(query_analysis, final_result, total_time)

        final_result['execution_time'] = total_time
        final_result['performance_metrics'] = self._calculate_performance_metrics(final_result, total_time)

        logger.info(f"Optimized retrieval completed in {total_time:.2f}s")

        return final_result

    def _analyze_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze query characteristics for optimization."""
        analysis = {
            'query_length': len(query),
            'query_type': self._classify_query_type(query),
            'complexity': self._assess_query_complexity(query),
            'domain_specificity': self._calculate_domain_specificity(query),
            'temporal_signals': self._detect_temporal_signals(query),
            'entity_mentions': self._extract_entity_mentions(query),
            'is_long_tail': False,
            'estimated_difficulty': 'medium'
        }

        # Determine if long-tail query
        analysis['is_long_tail'] = self._is_long_tail_query(analysis)

        # Estimate difficulty
        analysis['estimated_difficulty'] = self._estimate_query_difficulty(analysis)

        return analysis

    def _classify_query_type(self, query: str) -> str:
        """Classify query type for strategy selection."""
        query_lower = query.lower()

        # Factual queries
        if any(word in query_lower for word in ['what', 'who', 'when', 'where', 'how many', 'how much']):
            return 'factual'

        # Conceptual queries
        if any(word in query_lower for word in ['explain', 'describe', 'what is', 'how does']):
            return 'conceptual'

        # Comparative queries
        if any(word in query_lower for word in ['compare', 'versus', 'vs', 'difference', 'better']):
            return 'comparative'

        # Procedural queries
        if any(word in query_lower for word in ['how to', 'steps', 'process', 'guide']):
            return 'procedural'

        # Relational queries
        if any(word in query_lower for word in ['relationship', 'connection', 'related', 'link']):
            return 'relational'

        return 'general'

    def _assess_query_complexity(self, query: str) -> str:
        """Assess computational complexity of query."""
        words = query.split()
        length = len(words)

        # Complexity indicators
        technical_terms = len([w for w in words if w in [
            'algorithm', 'neural', 'network', 'graph', 'embedding', 'retrieval',
            'optimization', 'performance', 'scalability', 'distributed'
        ]])

        question_words = len([w for w in words if w.lower() in [
            'what', 'how', 'why', 'when', 'where', 'who', 'which', 'whose'
        ]])

        # Calculate complexity score
        complexity_score = (
            min(length / 50, 1.0) * 0.4 +  # Length factor
            min(technical_terms / 5, 1.0) * 0.4 +  # Technical factor
            min(question_words / 3, 1.0) * 0.2  # Question factor
        )

        if complexity_score > 0.7:
            return 'high'
        elif complexity_score > 0.4:
            return 'medium'
        else:
            return 'low'

    def _calculate_domain_specificity(self, query: str) -> float:
        """Calculate how domain-specific a query is."""
        domain_terms = {
            'technical': ['algorithm', 'neural', 'network', 'graph', 'embedding', 'retrieval', 'optimization'],
            'business': ['revenue', 'profit', 'market', 'customer', 'strategy', 'analysis'],
            'scientific': ['hypothesis', 'experiment', 'theory', 'research', 'methodology'],
            'medical': ['patient', 'treatment', 'diagnosis', 'clinical', 'therapy']
        }

        words = query.lower().split()
        domain_matches = 0
        total_terms = 0

        for domain, terms in domain_terms.items():
            domain_matches += len([w for w in words if w in terms])
            total_terms += len(terms)

        return domain_matches / max(len(words), 1)

    def _detect_temporal_signals(self, query: str) -> List[str]:
        """Detect temporal signals in query."""
        temporal_indicators = [
            'recent', 'latest', 'new', 'old', 'before', 'after', 'during',
            'yesterday', 'today', 'tomorrow', 'last week', 'this year'
        ]

        words = query.lower().split()
        return [word for word in words if word in temporal_indicators]

    def _extract_entity_mentions(self, query: str) -> List[str]:
        """Extract potential entity mentions."""
        # Simple entity extraction (could be enhanced with NER)
        words = query.split()
        entities = []

        # Look for capitalized words (potential proper nouns)
        for word in words:
            if word[0].isupper() and len(word) > 3:
                entities.append(word)

        return entities

    def _is_long_tail_query(self, analysis: Dict[str, Any]) -> bool:
        """Determine if query is a long-tail query."""
        indicators = [
            analysis['query_length'] > 100,  # Long query
            analysis['complexity'] == 'high',  # High complexity
            len(analysis['entity_mentions']) > 2,  # Many entities
            analysis['domain_specificity'] > 0.3,  # Domain specific
            len(analysis['temporal_signals']) > 0  # Temporal aspects
        ]

        return sum(indicators) >= 2

    def _estimate_query_difficulty(self, analysis: Dict[str, Any]) -> str:
        """Estimate overall query difficulty."""
        difficulty_score = 0

        if analysis['complexity'] == 'high':
            difficulty_score += 3
        elif analysis['complexity'] == 'medium':
            difficulty_score += 2

        if analysis['is_long_tail']:
            difficulty_score += 2

        if analysis['domain_specificity'] > 0.5:
            difficulty_score += 1

        if analysis['query_type'] in ['comparative', 'relational']:
            difficulty_score += 1

        if difficulty_score >= 5:
            return 'very_hard'
        elif difficulty_score >= 3:
            return 'hard'
        elif difficulty_score >= 1:
            return 'medium'
        else:
            return 'easy'

    def _determine_optimal_strategy(self, query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Determine optimal retrieval strategy based on query analysis."""
        base_strategy = self.stages.copy()

        # Adjust strategy based on query characteristics
        if query_analysis['is_long_tail']:
            # For long-tail queries, emphasize expansion and refinement
            base_strategy['expansion_stage']['expansion_factor'] = 2.0
            base_strategy['refinement_stage']['refinement_candidates'] = 75

        if query_analysis['complexity'] == 'high':
            # For complex queries, use more sophisticated strategies
            base_strategy['refinement_stage']['strategies'].append('graph_reasoning')

        if query_analysis['query_type'] == 'factual':
            # For factual queries, prioritize precision
            base_strategy['reranking_stage']['strategies'] = ['cross_encoder_rerank', 'factuality_rerank']

        if query_analysis['estimated_difficulty'] in ['hard', 'very_hard']:
            # For difficult queries, increase timeouts and candidates
            for stage_config in base_strategy.values():
                stage_config['timeout'] = int(stage_config['timeout'] * 1.5)
                if 'candidates' in stage_config:
                    stage_config['candidates'] = int(stage_config['candidates'] * 1.3)

        return base_strategy

    def _execute_multi_stage_retrieval(self, query: str, query_analysis: Dict[str, Any],
                                      strategy_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute multi-stage retrieval pipeline."""
        results = {
            'stage_results': {},
            'intermediate_candidates': [],
            'final_candidates': [],
            'stage_timings': {}
        }

        current_candidates = []

        # Execute each stage
        for stage_name, stage_config in strategy_config.items():
            stage_start = time.time()

            try:
                stage_result = self._execute_retrieval_stage(
                    stage_name, stage_config, query, query_analysis, current_candidates
                )

                results['stage_results'][stage_name] = stage_result
                results['stage_timings'][stage_name] = time.time() - stage_start

                # Update candidates for next stage
                if 'candidates' in stage_result:
                    current_candidates = stage_result['candidates']
                    results['intermediate_candidates'].extend(current_candidates)

            except Exception as e:
                logger.error(f"Stage {stage_name} failed: {e}")
                results['stage_results'][stage_name] = {'error': str(e)}
                results['stage_timings'][stage_name] = time.time() - stage_start

        # Final candidates are from the last stage
        if current_candidates:
            results['final_candidates'] = current_candidates[:20]  # Top 20

        return results

    def _execute_retrieval_stage(self, stage_name: str, stage_config: Dict[str, Any],
                               query: str, query_analysis: Dict[str, Any],
                               previous_candidates: List[Any]) -> Dict[str, Any]:
        """Execute a single retrieval stage."""
        stage_result = {'stage': stage_name}

        if stage_name == 'initial_retrieval':
            # Parallel initial retrieval
            futures = []
            for strategy in stage_config['strategies']:
                future = self.executor.submit(
                    self._execute_strategy, strategy, query, query_analysis, []
                )
                futures.append(future)

            # Collect results
            all_candidates = []
            for future in as_completed(futures, timeout=stage_config['timeout']/1000):
                try:
                    result = future.result()
                    all_candidates.extend(result.get('candidates', []))
                except Exception as e:
                    logger.warning(f"Strategy execution failed: {e}")

            # Merge and deduplicate
            merged_candidates = self._merge_candidates(all_candidates)
            stage_result['candidates'] = merged_candidates[:stage_config['target_candidates']]

        elif stage_name == 'expansion_stage':
            # Query expansion
            expanded_queries = self._expand_query(query, query_analysis)

            # Retrieve with expanded queries
            expanded_candidates = []
            for expanded_query in expanded_queries:
                result = self._execute_strategy('vector_search', expanded_query, query_analysis, [])
                expanded_candidates.extend(result.get('candidates', []))

            stage_result['candidates'] = self._merge_candidates(expanded_candidates)

        elif stage_name == 'refinement_stage':
            # Refine previous candidates using advanced strategies
            refined_candidates = []
            for strategy in stage_config['strategies']:
                result = self._execute_strategy(strategy, query, query_analysis, previous_candidates)
                refined_candidates.extend(result.get('candidates', []))

            stage_result['candidates'] = self._merge_candidates(refined_candidates)[:stage_config['refinement_candidates']]

        elif stage_name == 'reranking_stage':
            # Final reranking
            reranked = self._rerank_candidates(previous_candidates, query, query_analysis)
            stage_result['candidates'] = reranked[:stage_config['final_candidates']]

        return stage_result

    def _execute_strategy(self, strategy: str, query: str, query_analysis: Dict[str, Any],
                         candidates: List[Any]) -> Dict[str, Any]:
        """Execute a specific retrieval strategy."""
        # This would integrate with actual retrieval strategies
        # For now, return mock results
        mock_candidates = [
            {'id': f'candidate_{i}', 'score': 0.8 - i * 0.01, 'text': f'Mock result {i}'}
            for i in range(10)
        ]

        return {
            'strategy': strategy,
            'candidates': mock_candidates,
            'execution_time': np.random.uniform(0.1, 0.5)
        }

    def _expand_query(self, query: str, query_analysis: Dict[str, Any]) -> List[str]:
        """Expand query for better retrieval."""
        expansions = [query]  # Original query

        # Add related terms
        if query_analysis['query_type'] == 'factual':
            expansions.append(f"{query} information")
            expansions.append(f"{query} details")

        elif query_analysis['query_type'] == 'conceptual':
            expansions.append(f"{query} explanation")
            expansions.append(f"{query} overview")

        # Add entity-focused expansions
        for entity in query_analysis['entity_mentions'][:2]:  # Limit to 2 entities
            expansions.append(f"{entity} {query}")

        return expansions[:5]  # Limit expansions

    def _merge_candidates(self, candidate_lists: List[List[Any]]) -> List[Any]:
        """Merge and deduplicate candidates from multiple sources."""
        all_candidates = []
        seen_ids = set()

        for candidate_list in candidate_lists:
            for candidate in candidate_list:
                candidate_id = candidate.get('id', str(candidate))
                if candidate_id not in seen_ids:
                    all_candidates.append(candidate)
                    seen_ids.add(candidate_id)

        # Sort by score (assuming higher is better)
        all_candidates.sort(key=lambda x: x.get('score', 0), reverse=True)

        return all_candidates

    def _rerank_candidates(self, candidates: List[Any], query: str, query_analysis: Dict[str, Any]) -> List[Any]:
        """Rerank candidates using advanced scoring."""
        if not candidates:
            return []

        # Apply reranking logic
        for candidate in candidates:
            # Boost score based on query relevance
            relevance_boost = self._calculate_relevance_boost(candidate, query, query_analysis)
            candidate['score'] = candidate.get('score', 0) + relevance_boost

            # Diversity penalty (optional)
            diversity_penalty = self._calculate_diversity_penalty(candidate, candidates)
            candidate['score'] -= diversity_penalty

        # Re-sort by final score
        candidates.sort(key=lambda x: x.get('score', 0), reverse=True)

        return candidates

    def _calculate_relevance_boost(self, candidate: Dict[str, Any], query: str, query_analysis: Dict[str, Any]) -> float:
        """Calculate relevance boost for candidate."""
        text = candidate.get('text', '').lower()
        query_lower = query.lower()

        # Simple term overlap boost
        query_terms = set(query_lower.split())
        text_terms = set(text.split())

        overlap = len(query_terms.intersection(text_terms))
        boost = overlap * 0.1

        # Boost for long-tail queries
        if query_analysis['is_long_tail'] and overlap > 2:
            boost *= 1.5

        return boost

    def _calculate_diversity_penalty(self, candidate: Dict[str, Any], all_candidates: List[Any]) -> float:
        """Calculate diversity penalty to avoid redundant results."""
        # Simple diversity based on text similarity
        candidate_text = candidate.get('text', '')
        similar_count = 0

        for other in all_candidates:
            if other != candidate:
                other_text = other.get('text', '')
                similarity = self._calculate_text_similarity(candidate_text, other_text)
                if similarity > 0.7:  # Very similar
                    similar_count += 1

        return similar_count * 0.05  # Small penalty per similar result

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple text similarity."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def _apply_final_optimizations(self, retrieval_result: Dict[str, Any], query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Apply final optimizations to retrieval results."""
        final_result = retrieval_result.copy()

        # Ensure we have final candidates
        if not final_result.get('final_candidates'):
            final_result['final_candidates'] = final_result.get('intermediate_candidates', [])[:20]

        # Add metadata
        final_result['query_analysis'] = query_analysis
        final_result['optimization_applied'] = [
            'multi_stage_retrieval',
            'query_expansion' if query_analysis['is_long_tail'] else None,
            'adaptive_reranking',
            'diversity_penalty'
        ]
        final_result['optimization_applied'] = [opt for opt in final_result['optimization_applied'] if opt]

        # Calculate quality metrics
        final_result['quality_metrics'] = self._calculate_quality_metrics(
            final_result['final_candidates'], query_analysis
        )

        return final_result

    def _calculate_quality_metrics(self, candidates: List[Any], query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate quality metrics for retrieval results."""
        if not candidates:
            return {'recall_estimate': 0.0, 'precision_estimate': 0.0, 'diversity_score': 0.0}

        # Estimate recall and precision (simplified)
        avg_score = np.mean([c.get('score', 0) for c in candidates])
        score_std = np.std([c.get('score', 0) for c in candidates])

        # Diversity based on score distribution
        diversity_score = 1.0 - (score_std / max(avg_score, 0.1))

        # Long-tail specific metrics
        if query_analysis['is_long_tail']:
            # For long-tail queries, higher diversity is better
            diversity_score *= 1.2

        return {
            'avg_candidate_score': avg_score,
            'score_distribution_std': score_std,
            'diversity_score': diversity_score,
            'num_candidates': len(candidates),
            'recall_estimate': min(avg_score * 1.2, 1.0),  # Rough estimate
            'precision_estimate': min(avg_score * 0.8, 1.0)  # Rough estimate
        }

    def _record_performance_metrics(self, query_analysis: Dict[str, Any], result: Dict[str, Any], total_time: float):
        """Record performance metrics for analysis."""
        self.execution_stats['total_time'].append(total_time)
        self.execution_stats['query_complexity'].append(query_analysis['complexity'])
        self.execution_stats['is_long_tail'].append(query_analysis['is_long_tail'])

        # Keep only recent stats
        max_stats = 1000
        for key in self.execution_stats:
            if len(self.execution_stats[key]) > max_stats:
                self.execution_stats[key] = self.execution_stats[key][-max_stats:]

    def _calculate_performance_metrics(self, result: Dict[str, Any], total_time: float) -> Dict[str, Any]:
        """Calculate performance metrics for the retrieval."""
        timings = result.get('stage_timings', {})

        return {
            'total_retrieval_time': total_time,
            'stage_breakdown': timings,
            'bottleneck_stage': max(timings.items(), key=lambda x: x[1])[0] if timings else None,
            'parallelization_efficiency': self._calculate_parallelization_efficiency(timings),
            'latency_p95_target_met': total_time * 1000 <= self.target_latency_p95,
            'recall_target_met': result.get('quality_metrics', {}).get('recall_estimate', 0) >= self.target_recall
        }

    def _calculate_parallelization_efficiency(self, timings: Dict[str, float]) -> float:
        """Calculate how well parallelization was utilized."""
        if not timings:
            return 0.0

        total_sequential_time = sum(timings.values())
        max_parallel_time = max(timings.values())

        # Efficiency = sequential_time / parallel_time
        efficiency = total_sequential_time / max_parallel_time if max_parallel_time > 0 else 0.0

        return min(efficiency, len(timings))  # Cap at number of stages

    def _generate_cache_key(self, query: str, context: Dict[str, Any]) -> str:
        """Generate cache key for query."""
        import hashlib
        key_components = [query]
        key_components.extend([f"{k}:{v}" for k, v in sorted(context.items())])
        key_string = '|'.join(key_components)
        return hashlib.md5(key_string.encode()).hexdigest()

    def get_optimization_stats(self) -> Dict[str, Any]:
        """Get optimization statistics."""
        stats = {
            'total_optimizations': len(self.execution_stats['total_time']),
            'avg_retrieval_time': np.mean(self.execution_stats['total_time']) if self.execution_stats['total_time'] else 0,
            'long_tail_query_ratio': np.mean(self.execution_stats['is_long_tail']) if self.execution_stats['is_long_tail'] else 0,
            'cache_hit_rate': 0.0,  # Would need to track cache hits
            'performance_targets': {
                'target_recall': self.target_recall,
                'target_latency_p95': self.target_latency_p95,
                'target_precision': self.target_precision
            }
        }

        # Calculate complexity distribution
        if self.execution_stats['query_complexity']:
            complexity_counts = {}
            for complexity in self.execution_stats['query_complexity']:
                complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1
            stats['complexity_distribution'] = complexity_counts

        return stats

    def update_strategy_weights(self, feedback: Dict[str, Any]):
        """
        Update strategy weights based on performance feedback.

        Args:
            feedback: Performance feedback data
        """
        # This would integrate with the adaptive weighting system
        logger.info("Strategy weights updated based on feedback")

    def enable_adaptive_optimization(self, enable: bool = True):
        """Enable adaptive optimization based on query patterns."""
        self.adaptive_optimization = enable
        logger.info(f"Adaptive optimization {'enabled' if enable else 'disabled'}")

    def clear_cache(self):
        """Clear retrieval cache."""
        self.result_cache.clear()
        self.query_cache.clear()
        logger.info("Retrieval cache cleared")
