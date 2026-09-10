"""
Long Tail Query Optimizer for GraphRAG.

This module specializes in optimizing retrieval for long-tail queries that are
infrequent, complex, or domain-specific, using advanced techniques like
multi-hop reasoning, query decomposition, and knowledge graph traversal.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import numpy as np
from collections import defaultdict, Counter
import re
from pathlib import Path

logger = logging.getLogger(__name__)


class LongTailQueryAnalyzer:
    """
    Analyzes queries to determine if they are long-tail and what strategies to apply.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize long-tail query analyzer.

        Args:
            config: Analysis configuration
        """
        self.config = config or {}

        # Long-tail detection thresholds
        self.rarity_threshold = self.config.get('rarity_threshold', 0.1)  # Term frequency threshold
        self.complexity_threshold = self.config.get('complexity_threshold', 0.7)  # Query complexity threshold
        self.domain_specificity_threshold = self.config.get('domain_specificity_threshold', 0.8)

        # Query pattern recognition
        self.long_tail_patterns = [
            r'\b(?:how|what|why|when|where|who)\s+.*\?.*\?',  # Multiple questions
            r'\b(?:explain|describe|analyze)\s+.*\b(?:in detail|comprehensively)\b',  # Detailed explanations
            r'\b(?:relationship|connection|interaction)\s+between\b',  # Relationship queries
            r'\b(?:impact|effect|influence)\s+of\s+.*\s+on\b',  # Impact analysis
            r'\b(?:compare|contrast|difference)\s+between\b',  # Comparative queries
            r'\b(?:evolution|development|progression)\s+of\b',  # Temporal queries
        ]

        # Domain-specific terms (expandable)
        self.domain_terms = {
            'technical': ['algorithm', 'implementation', 'architecture', 'framework', 'optimization'],
            'scientific': ['hypothesis', 'experiment', 'methodology', 'analysis', 'conclusion'],
            'business': ['strategy', 'market', 'revenue', 'growth', 'competition'],
            'medical': ['diagnosis', 'treatment', 'symptoms', 'prognosis', 'therapy']
        }

        logger.info("Long-tail query analyzer initialized")

    def analyze_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze query to determine long-tail characteristics.

        Args:
            query: Query string
            context: Additional context

        Returns:
            Analysis results
        """
        context = context or {}

        analysis = {
            'is_long_tail': False,
            'complexity_score': 0.0,
            'rarity_score': 0.0,
            'domain_specificity': 0.0,
            'query_type': 'general',
            'decomposition_needed': False,
            'multi_hop_needed': False,
            'specialized_strategy': None,
            'confidence': 0.0
        }

        try:
            # Calculate complexity score
            analysis['complexity_score'] = self._calculate_complexity(query)

            # Calculate rarity score
            analysis['rarity_score'] = self._calculate_rarity(query, context)

            # Calculate domain specificity
            analysis['domain_specificity'] = self._calculate_domain_specificity(query)

            # Pattern matching
            pattern_matches = self._match_patterns(query)
            analysis['pattern_matches'] = pattern_matches

            # Determine if long-tail
            analysis['is_long_tail'] = self._is_long_tail_query(
                analysis['complexity_score'],
                analysis['rarity_score'],
                analysis['domain_specificity'],
                pattern_matches
            )

            # Determine query type and strategies
            if analysis['is_long_tail']:
                analysis['query_type'] = self._classify_query_type(query, pattern_matches)
                analysis['decomposition_needed'] = analysis['complexity_score'] > 0.8
                analysis['multi_hop_needed'] = self._needs_multi_hop(query, pattern_matches)
                analysis['specialized_strategy'] = self._recommend_strategy(analysis)

            # Calculate confidence
            analysis['confidence'] = self._calculate_confidence(analysis)

        except Exception as e:
            logger.warning(f"Query analysis failed: {e}")

        return analysis

    def _calculate_complexity(self, query: str) -> float:
        """Calculate query complexity score."""
        words = query.lower().split()
        score = 0.0

        # Length factor
        length_score = min(len(words) / 20, 1.0)  # Normalize to 20 words
        score += 0.3 * length_score

        # Technical terms
        technical_terms = ['algorithm', 'implementation', 'analysis', 'optimization',
                          'architecture', 'framework', 'methodology', 'hypothesis']
        technical_count = sum(1 for word in words if word in technical_terms)
        technical_score = min(technical_count / 5, 1.0)  # Normalize to 5 technical terms
        score += 0.3 * technical_score

        # Question complexity
        question_words = ['how', 'what', 'why', 'when', 'where', 'who', 'which', 'whose']
        question_count = sum(1 for word in words if word in question_words)
        question_score = min(question_count / 3, 1.0)  # Normalize to 3 questions
        score += 0.2 * question_score

        # Conjunctions and qualifiers
        qualifiers = ['and', 'or', 'but', 'however', 'although', 'because', 'therefore']
        qualifier_count = sum(1 for word in words if word in qualifiers)
        qualifier_score = min(qualifier_count / 5, 1.0)  # Normalize to 5 qualifiers
        score += 0.2 * qualifier_score

        return score

    def _calculate_rarity(self, query: str, context: Dict[str, Any]) -> float:
        """Calculate query rarity based on term frequency."""
        # This would typically use historical query data
        # For now, use heuristics based on uncommon terms

        words = query.lower().split()
        rare_terms = 0
        total_terms = len(words)

        # Common English words (simplified)
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
                       'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been',
                       'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                       'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'}

        for word in words:
            if len(word) > 3 and word not in common_words:
                # Check if it's a technical or uncommon term
                if any(char.isdigit() for char in word) or '-' in word or '_' in word:
                    rare_terms += 1  # Technical terms, numbers, compounds
                elif word in self.domain_terms.get('technical', []) + \
                          self.domain_terms.get('scientific', []):
                    rare_terms += 1  # Domain-specific terms

        return min(rare_terms / max(total_terms * 0.5, 1), 1.0)

    def _calculate_domain_specificity(self, query: str) -> float:
        """Calculate domain specificity score."""
        words = query.lower().split()
        domain_matches = 0

        for domain, terms in self.domain_terms.items():
            matches = sum(1 for word in words if word in terms)
            if matches > 0:
                domain_matches += matches

        return min(domain_matches / max(len(words) * 0.3, 1), 1.0)

    def _match_patterns(self, query: str) -> List[str]:
        """Match query against long-tail patterns."""
        matches = []
        query_lower = query.lower()

        for pattern in self.long_tail_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                matches.append(pattern)

        return matches

    def _is_long_tail_query(self, complexity: float, rarity: float,
                           domain_specificity: float, patterns: List[str]) -> bool:
        """Determine if query is long-tail."""
        # Multi-factor decision
        pattern_bonus = min(len(patterns) * 0.2, 0.4)  # Bonus for pattern matches

        combined_score = (
            0.4 * complexity +
            0.3 * rarity +
            0.2 * domain_specificity +
            pattern_bonus
        )

        return combined_score > 0.6  # Threshold for long-tail classification

    def _classify_query_type(self, query: str, patterns: List[str]) -> str:
        """Classify the type of long-tail query."""
        query_lower = query.lower()

        if any('relationship' in p or 'connection' in p for p in patterns):
            return 'relational'
        elif any('explain' in p or 'describe' in p for p in patterns):
            return 'explanatory'
        elif any('compare' in p or 'contrast' in p for p in patterns):
            return 'comparative'
        elif any('evolution' in p or 'development' in p for p in patterns):
            return 'temporal'
        elif any('impact' in p or 'effect' in p for p in patterns):
            return 'causal'
        elif 'how' in query_lower and 'work' in query_lower:
            return 'mechanistic'
        else:
            return 'complex_general'

    def _needs_multi_hop(self, query: str, patterns: List[str]) -> bool:
        """Determine if query needs multi-hop reasoning."""
        # Multi-hop indicators
        multi_hop_keywords = ['relationship', 'connection', 'interaction', 'impact',
                            'effect', 'influence', 'causes', 'leads to', 'depends on']

        query_lower = query.lower()
        keyword_matches = sum(1 for keyword in multi_hop_keywords if keyword in query_lower)

        return keyword_matches > 0 or len(patterns) > 1

    def _recommend_strategy(self, analysis: Dict[str, Any]) -> str:
        """Recommend specialized retrieval strategy."""
        query_type = analysis.get('query_type', 'general')

        strategy_map = {
            'relational': 'graph_traversal',
            'explanatory': 'multi_source_fusion',
            'comparative': 'parallel_retrieval',
            'temporal': 'temporal_reasoning',
            'causal': 'causal_inference',
            'mechanistic': 'step_by_step_reasoning',
            'complex_general': 'adaptive_ensemble'
        }

        return strategy_map.get(query_type, 'adaptive_ensemble')

    def _calculate_confidence(self, analysis: Dict[str, Any]) -> float:
        """Calculate confidence in the analysis."""
        factors = [
            analysis.get('complexity_score', 0),
            analysis.get('rarity_score', 0),
            analysis.get('domain_specificity', 0),
            min(len(analysis.get('pattern_matches', [])) * 0.2, 1.0)
        ]

        return sum(factors) / len(factors)


class LongTailQueryDecomposer:
    """
    Decomposes complex long-tail queries into simpler sub-queries.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize query decomposer.

        Args:
            config: Decomposition configuration
        """
        self.config = config or {}

        # Decomposition patterns
        self.decomposition_rules = {
            'comparative': self._decompose_comparative,
            'relational': self._decompose_relational,
            'explanatory': self._decompose_explanatory,
            'causal': self._decompose_causal,
            'temporal': self._decompose_temporal
        }

    def decompose_query(self, query: str, query_type: str) -> List[Dict[str, Any]]:
        """
        Decompose complex query into sub-queries.

        Args:
            query: Original query
            query_type: Type of query

        Returns:
            List of sub-queries with metadata
        """
        if query_type in self.decomposition_rules:
            decomposer = self.decomposition_rules[query_type]
            return decomposer(query)
        else:
            # Default decomposition: split by conjunctions
            return self._decompose_general(query)

    def _decompose_comparative(self, query: str) -> List[Dict[str, Any]]:
        """Decompose comparative queries."""
        sub_queries = []

        # Find comparison targets
        compare_pattern = r'compare\s+(.*?)\s+(?:with|and|to)\s+(.*?)(?:\s|$|[\.,])'
        match = re.search(compare_pattern, query, re.IGNORECASE)

        if match:
            item1, item2 = match.groups()

            sub_queries.extend([
                {
                    'text': f"What is {item1}?",
                    'type': 'factual',
                    'focus': item1,
                    'weight': 0.4
                },
                {
                    'text': f"What is {item2}?",
                    'type': 'factual',
                    'focus': item2,
                    'weight': 0.4
                },
                {
                    'text': f"Differences between {item1} and {item2}",
                    'type': 'comparative_detail',
                    'focus': f"{item1}_vs_{item2}",
                    'weight': 0.2
                }
            ])

        return sub_queries

    def _decompose_relational(self, query: str) -> List[Dict[str, Any]]:
        """Decompose relational queries."""
        sub_queries = []

        # Find entities and relationships
        entities = self._extract_entities(query)
        relationship_keywords = ['relationship', 'connection', 'interaction', 'between']

        if len(entities) >= 2:
            for i, entity1 in enumerate(entities):
                for j, entity2 in enumerate(entities):
                    if i != j:
                        sub_queries.append({
                            'text': f"Relationship between {entity1} and {entity2}",
                            'type': 'relational',
                            'entities': [entity1, entity2],
                            'weight': 0.3
                        })

        return sub_queries[:5]  # Limit to top 5

    def _decompose_explanatory(self, query: str) -> List[Dict[str, Any]]:
        """Decompose explanatory queries."""
        sub_queries = []

        # Break down explanation requests
        explain_pattern = r'explain\s+(.*?)(?:\s|$|[\.,])'
        match = re.search(explain_pattern, query, re.IGNORECASE)

        if match:
            topic = match.group(1)

            sub_queries.extend([
                {
                    'text': f"What is {topic}?",
                    'type': 'definition',
                    'focus': topic,
                    'weight': 0.3
                },
                {
                    'text': f"How does {topic} work?",
                    'type': 'mechanistic',
                    'focus': topic,
                    'weight': 0.3
                },
                {
                    'text': f"Examples of {topic}",
                    'type': 'illustrative',
                    'focus': topic,
                    'weight': 0.2
                },
                {
                    'text': f"Importance of {topic}",
                    'type': 'evaluative',
                    'focus': topic,
                    'weight': 0.2
                }
            ])

        return sub_queries

    def _decompose_causal(self, query: str) -> List[Dict[str, Any]]:
        """Decompose causal queries."""
        sub_queries = []

        # Find cause-effect relationships
        cause_pattern = r'(?:impact|effect|influence)\s+of\s+(.*?)\s+on\s+(.*?)(?:\s|$|[\.,])'
        match = re.search(cause_pattern, query, re.IGNORECASE)

        if match:
            cause, effect = match.groups()

            sub_queries.extend([
                {
                    'text': f"What is {cause}?",
                    'type': 'factual',
                    'focus': cause,
                    'weight': 0.2
                },
                {
                    'text': f"What is {effect}?",
                    'type': 'factual',
                    'focus': effect,
                    'weight': 0.2
                },
                {
                    'text': f"How {cause} affects {effect}",
                    'type': 'causal_mechanism',
                    'entities': [cause, effect],
                    'weight': 0.4
                },
                {
                    'text': f"Evidence for {cause} affecting {effect}",
                    'type': 'evidentiary',
                    'entities': [cause, effect],
                    'weight': 0.2
                }
            ])

        return sub_queries

    def _decompose_temporal(self, query: str) -> List[Dict[str, Any]]:
        """Decompose temporal queries."""
        sub_queries = []

        # Find temporal aspects
        temporal_pattern = r'(?:evolution|development|progression|history)\s+of\s+(.*?)(?:\s|$|[\.,])'
        match = re.search(temporal_pattern, query, re.IGNORECASE)

        if match:
            topic = match.group(1)

            sub_queries.extend([
                {
                    'text': f"Origins of {topic}",
                    'type': 'historical',
                    'focus': topic,
                    'temporal_aspect': 'beginning',
                    'weight': 0.2
                },
                {
                    'text': f"Current state of {topic}",
                    'type': 'current_status',
                    'focus': topic,
                    'temporal_aspect': 'present',
                    'weight': 0.3
                },
                {
                    'text': f"Future of {topic}",
                    'type': 'predictive',
                    'focus': topic,
                    'temporal_aspect': 'future',
                    'weight': 0.2
                },
                {
                    'text': f"Key changes in {topic} over time",
                    'type': 'transformative',
                    'focus': topic,
                    'temporal_aspect': 'evolution',
                    'weight': 0.3
                }
            ])

        return sub_queries

    def _decompose_general(self, query: str) -> List[Dict[str, Any]]:
        """General query decomposition."""
        # Split by conjunctions and semicolons
        parts = re.split(r'\s+(?:and|or|but|however|although|because|therefore|;)\s+', query)

        sub_queries = []
        for i, part in enumerate(parts):
            if len(part.strip()) > 10:  # Minimum length
                sub_queries.append({
                    'text': part.strip(),
                    'type': 'general',
                    'part_index': i,
                    'weight': 1.0 / len(parts)
                })

        return sub_queries

    def _extract_entities(self, query: str) -> List[str]:
        """Extract entities from query (simplified)."""
        # Simple entity extraction - in practice, would use NER
        words = query.split()
        entities = []

        # Look for capitalized words (potential proper nouns)
        for word in words:
            if word[0].isupper() and len(word) > 2:
                entities.append(word)

        # Look for quoted phrases
        quoted = re.findall(r'"([^"]*)"', query)
        entities.extend(quoted)

        return list(set(entities))  # Remove duplicates


class LongTailRetrievalOptimizer:
    """
    Optimizes retrieval specifically for long-tail queries.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize long-tail retrieval optimizer.

        Args:
            config: Optimization configuration
        """
        self.config = config or {}

        # Target recall rate
        self.target_recall = self.config.get('target_recall', 0.85)

        # Strategy weights
        self.strategy_weights = {
            'query_expansion': 0.3,
            'multi_hop_reasoning': 0.4,
            'graph_traversal': 0.3
        }

        # Performance tracking
        self.performance_stats = {
            'queries_processed': 0,
            'recall_achieved': 0.0,
            'avg_processing_time': 0.0
        }

        # Initialize analyzers
        self.analyzer = LongTailQueryAnalyzer(self.config)
        self.decomposer = LongTailQueryDecomposer(self.config)

        logger.info("Long-tail retrieval optimizer initialized")

    def optimize_retrieval(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Optimize retrieval for a potentially long-tail query.

        Args:
            query: Query string
            context: Additional context

        Returns:
            Optimization results and strategy recommendations
        """
        # Analyze query
        analysis = self.analyzer.analyze_query(query, context)

        optimization = {
            'query_analysis': analysis,
            'optimization_needed': analysis['is_long_tail'],
            'recommended_strategies': [],
            'query_decomposition': [],
            'expected_recall_improvement': 0.0,
            'processing_steps': []
        }

        if not analysis['is_long_tail']:
            optimization['recommended_strategies'] = ['standard_retrieval']
            return optimization

        # Decompose query if needed
        if analysis['decomposition_needed']:
            sub_queries = self.decomposer.decompose_query(query, analysis['query_type'])
            optimization['query_decomposition'] = sub_queries
            optimization['processing_steps'].append('query_decomposition')

        # Determine optimal strategies
        strategies = self._select_optimal_strategies(analysis, sub_queries if 'sub_queries' in locals() else [])

        optimization['recommended_strategies'] = strategies
        optimization['processing_steps'].extend([
            'multi_strategy_retrieval',
            'result_fusion',
            'quality_assessment'
        ])

        # Estimate recall improvement
        optimization['expected_recall_improvement'] = self._estimate_recall_improvement(analysis, strategies)

        # Update stats
        self.performance_stats['queries_processed'] += 1

        return optimization

    def _select_optimal_strategies(self, analysis: Dict[str, Any], sub_queries: List[Dict[str, Any]]) -> List[str]:
        """Select optimal retrieval strategies."""
        strategies = []

        query_type = analysis.get('query_type', 'general')

        # Base strategies for all long-tail queries
        strategies.extend(['query_expansion', 'semantic_search'])

        # Type-specific strategies
        if query_type == 'relational':
            strategies.extend(['graph_traversal', 'entity_linking'])
        elif query_type == 'explanatory':
            strategies.extend(['multi_source_fusion', 'evidence_aggregation'])
        elif query_type == 'comparative':
            strategies.extend(['parallel_retrieval', 'difference_analysis'])
        elif query_type == 'causal':
            strategies.extend(['causal_reasoning', 'correlation_analysis'])
        elif query_type == 'temporal':
            strategies.extend(['temporal_reasoning', 'sequence_analysis'])

        # Add multi-hop if needed
        if analysis.get('multi_hop_needed', False):
            strategies.append('multi_hop_reasoning')

        # Add decomposition-based strategies
        if sub_queries:
            strategies.append('subquery_fusion')

        # Ensure diversity but limit to top strategies
        unique_strategies = list(set(strategies))

        # Prioritize based on query characteristics
        prioritized = self._prioritize_strategies(unique_strategies, analysis)

        return prioritized[:5]  # Top 5 strategies

    def _prioritize_strategies(self, strategies: List[str], analysis: Dict[str, Any]) -> List[str]:
        """Prioritize strategies based on query analysis."""
        strategy_scores = {}

        for strategy in strategies:
            score = 0.0

            # Base score from configuration
            score += self.strategy_weights.get(strategy, 0.1)

            # Boost based on query type
            query_type = analysis.get('query_type', 'general')
            if strategy == 'graph_traversal' and query_type == 'relational':
                score += 0.3
            elif strategy == 'multi_hop_reasoning' and analysis.get('multi_hop_needed', False):
                score += 0.4
            elif strategy == 'query_expansion' and analysis.get('complexity_score', 0) > 0.7:
                score += 0.2

            strategy_scores[strategy] = score

        # Sort by score
        sorted_strategies = sorted(strategy_scores.items(), key=lambda x: x[1], reverse=True)

        return [strategy for strategy, _ in sorted_strategies]

    def _estimate_recall_improvement(self, analysis: Dict[str, Any], strategies: List[str]) -> float:
        """Estimate recall improvement from applied strategies."""
        base_recall = 0.6  # Base recall for standard retrieval
        improvement = 0.0

        strategy_improvements = {
            'query_expansion': 0.15,
            'graph_traversal': 0.20,
            'multi_hop_reasoning': 0.25,
            'multi_source_fusion': 0.18,
            'subquery_fusion': 0.22,
            'semantic_search': 0.12
        }

        for strategy in strategies:
            improvement += strategy_improvements.get(strategy, 0.05)

        # Cap improvement based on query difficulty
        max_improvement = 0.4 if analysis.get('complexity_score', 0) > 0.8 else 0.3

        return min(improvement, max_improvement)

    def batch_optimize(self, queries: List[str], contexts: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """
        Optimize retrieval for multiple queries in batch.

        Args:
            queries: List of query strings
            contexts: List of contexts (optional)

        Returns:
            List of optimization results
        """
        contexts = contexts or [{}] * len(queries)

        results = []
        for query, context in zip(queries, contexts):
            try:
                result = self.optimize_retrieval(query, context)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to optimize query '{query}': {e}")
                results.append({
                    'query_analysis': {'is_long_tail': False},
                    'optimization_needed': False,
                    'recommended_strategies': ['standard_retrieval'],
                    'error': str(e)
                })

        return results

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        return self.performance_stats.copy()

    def update_performance(self, actual_recall: float, processing_time: float):
        """Update performance statistics."""
        # Exponential moving average for recall
        current_recall = self.performance_stats['recall_achieved']
        alpha = 0.1
        self.performance_stats['recall_achieved'] = alpha * actual_recall + (1 - alpha) * current_recall

        # Exponential moving average for processing time
        current_time = self.performance_stats['avg_processing_time']
        self.performance_stats['avg_processing_time'] = alpha * processing_time + (1 - alpha) * current_time







