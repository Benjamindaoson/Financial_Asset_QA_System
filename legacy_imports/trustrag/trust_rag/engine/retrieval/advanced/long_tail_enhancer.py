"""
Long-Tail Query Enhancer for GraphRAG.

This module specializes in improving retrieval performance for long-tail queries
through advanced expansion, reasoning, and multi-hop retrieval techniques.
"""

import logging
from typing import Dict, List, Any, Optional, Callable, Union
import time
import re
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


class LongTailQueryEnhancer:
    """
    Specialized enhancer for long-tail queries with advanced retrieval techniques.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize long-tail query enhancer.

        Args:
            config: Enhancement configuration
        """
        self.config = config or {}

        # Performance targets
        self.target_recall = self.config.get('target_recall', 0.85)  # 85% recall target
        self.max_expansion_factor = self.config.get('max_expansion_factor', 3.0)
        self.max_hops = self.config.get('max_hops', 3)  # Multi-hop retrieval

        # Enhancement strategies
        self.strategies = {
            'semantic_expansion': self._semantic_expansion,
            'entity_based_expansion': self._entity_based_expansion,
            'contextual_expansion': self._contextual_expansion,
            'multi_hop_reasoning': self._multi_hop_reasoning,
            'temporal_expansion': self._temporal_expansion,
            'domain_specific_expansion': self._domain_specific_expansion
        }

        # Knowledge sources for expansion
        self.domain_knowledge = self._load_domain_knowledge()
        self.entity_relationships = self._load_entity_relationships()

        # Performance tracking
        self.enhancement_stats = defaultdict(list)

        logger.info("Long-tail query enhancer initialized")

    def enhance_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Enhance a long-tail query for better retrieval.

        Args:
            query: Original query
            context: Query context and metadata

        Returns:
            Enhanced query information
        """
        start_time = time.time()
        context = context or {}

        # Analyze query characteristics
        query_analysis = self._analyze_long_tail_query(query, context)

        # Determine enhancement strategies
        strategies_to_apply = self._select_enhancement_strategies(query_analysis)

        # Apply enhancements
        enhanced_queries = [query]  # Start with original
        enhancement_metadata = {}

        for strategy_name in strategies_to_apply:
            if strategy_name in self.strategies:
                try:
                    strategy_result = self.strategies[strategy_name](query, query_analysis, context)
                    if strategy_result['queries']:
                        enhanced_queries.extend(strategy_result['queries'])
                        enhancement_metadata[strategy_name] = strategy_result['metadata']
                except Exception as e:
                    logger.warning(f"Strategy {strategy_name} failed: {e}")

        # Deduplicate and rank enhanced queries
        final_queries = self._deduplicate_and_rank_queries(enhanced_queries, query)

        # Create enhancement result
        result = {
            'original_query': query,
            'enhanced_queries': final_queries,
            'expansion_factor': len(final_queries),
            'strategies_applied': strategies_to_apply,
            'enhancement_metadata': enhancement_metadata,
            'query_analysis': query_analysis,
            'enhancement_time': time.time() - start_time,
            'expected_recall_improvement': self._estimate_recall_improvement(query_analysis, strategies_to_apply)
        }

        # Record statistics
        self._record_enhancement_stats(result)

        logger.info(f"Enhanced long-tail query: {len(final_queries)} variations generated")

        return result

    def _analyze_long_tail_query(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze query to identify long-tail characteristics."""
        analysis = {
            'length': len(query),
            'word_count': len(query.split()),
            'complexity_indicators': [],
            'entity_density': 0.0,
            'specificity_score': 0.0,
            'temporal_signals': [],
            'domain_signals': [],
            'relational_signals': [],
            'long_tail_factors': []
        }

        words = query.lower().split()

        # Length-based indicators
        if analysis['word_count'] > 15:
            analysis['long_tail_factors'].append('very_long_query')

        # Complexity indicators
        complex_patterns = [
            r'\b(and|or|but|however|therefore|thus)\b',  # Connectives
            r'\b(compare|contrast|versus|vs\.?)\b',  # Comparative
            r'\b(relationship|connection|correlation|impact)\b',  # Relational
            r'\b(specific|particular|exact|precise)\b',  # Specificity
            r'\b(recent|latest|new|old|before|after)\b'  # Temporal
        ]

        for pattern in complex_patterns:
            if re.search(pattern, query.lower()):
                analysis['complexity_indicators'].append(pattern.strip(r'\b').strip(r'\b.*?'))

        # Entity density (capitalized words, potential proper nouns)
        capitalized_words = [w for w in query.split() if w[0].isupper()]
        analysis['entity_density'] = len(capitalized_words) / max(analysis['word_count'], 1)

        # Specificity score
        specific_terms = [
            'specific', 'particular', 'exact', 'precise', 'detailed',
            'comprehensive', 'thorough', 'in-depth', 'advanced'
        ]
        analysis['specificity_score'] = len([w for w in words if w in specific_terms]) / max(analysis['word_count'], 1)

        # Temporal signals
        temporal_words = ['recent', 'latest', 'new', 'old', 'before', 'after', 'during',
                         'yesterday', 'today', 'tomorrow', 'last', 'this', 'next']
        analysis['temporal_signals'] = [w for w in words if w in temporal_words]

        # Domain signals
        domain_terms = {
            'technical': ['algorithm', 'framework', 'architecture', 'infrastructure', 'scalability'],
            'business': ['revenue', 'profit', 'market', 'strategy', 'stakeholder', 'ROI'],
            'scientific': ['hypothesis', 'methodology', 'experiment', 'theory', 'research'],
            'medical': ['patient', 'clinical', 'treatment', 'diagnosis', 'therapy']
        }

        for domain, terms in domain_terms.items():
            domain_matches = [w for w in words if w in terms]
            if domain_matches:
                analysis['domain_signals'].extend(domain_matches)

        # Relational signals
        relational_words = ['relationship', 'connection', 'correlation', 'impact', 'influence',
                           'depends', 'related', 'associated', 'linked']
        analysis['relational_signals'] = [w for w in words if w in relational_words]

        # Long-tail factors
        if analysis['entity_density'] > 0.3:
            analysis['long_tail_factors'].append('high_entity_density')

        if analysis['specificity_score'] > 0.1:
            analysis['long_tail_factors'].append('high_specificity')

        if len(analysis['complexity_indicators']) > 2:
            analysis['long_tail_factors'].append('high_complexity')

        if analysis['temporal_signals']:
            analysis['long_tail_factors'].append('temporal_aspects')

        if analysis['relational_signals']:
            analysis['long_tail_factors'].append('relational_query')

        analysis['is_long_tail'] = len(analysis['long_tail_factors']) >= 2

        return analysis

    def _select_enhancement_strategies(self, query_analysis: Dict[str, Any]) -> List[str]:
        """Select appropriate enhancement strategies based on query analysis."""
        strategies = []

        # Base strategies
        strategies.append('semantic_expansion')

        # Conditional strategies based on query characteristics
        if query_analysis['entity_density'] > 0.2:
            strategies.append('entity_based_expansion')

        if query_analysis['temporal_signals']:
            strategies.append('temporal_expansion')

        if query_analysis['domain_signals']:
            strategies.append('domain_specific_expansion')

        if query_analysis['relational_signals']:
            strategies.append('multi_hop_reasoning')

        if len(query_analysis['complexity_indicators']) > 1:
            strategies.append('contextual_expansion')

        # Limit strategies to prevent over-expansion
        return strategies[:4]

    def _semantic_expansion(self, query: str, analysis: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform semantic expansion of the query."""
        expanded_queries = []

        # Synonym expansion
        synonyms = self._get_query_synonyms(query)
        for synonym_set in synonyms:
            expanded_queries.append(' '.join(synonym_set))

        # Related concept expansion
        related_concepts = self._get_related_concepts(query, analysis)
        for concept in related_concepts:
            expanded_queries.append(f"{query} {concept}")

        # Abstraction level expansion
        abstract_queries = self._create_abstract_queries(query, analysis)
        expanded_queries.extend(abstract_queries)

        return {
            'queries': expanded_queries[:5],  # Limit to 5 expansions
            'metadata': {
                'expansion_type': 'semantic',
                'synonym_sets': len(synonyms),
                'related_concepts': len(related_concepts),
                'abstract_levels': len(abstract_queries)
            }
        }

    def _entity_based_expansion(self, query: str, analysis: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform entity-based query expansion."""
        expanded_queries = []

        # Extract entities from query
        entities = self._extract_entities(query)

        # Generate entity-focused queries
        for entity in entities:
            # Entity-centric queries
            expanded_queries.append(f"{entity} details")
            expanded_queries.append(f"information about {entity}")
            expanded_queries.append(f"{entity} context")

            # Entity relationships
            related_entities = self.entity_relationships.get(entity, [])
            for related in related_entities[:3]:  # Limit relationships
                expanded_queries.append(f"{entity} and {related}")
                expanded_queries.append(f"relationship between {entity} and {related}")

        return {
            'queries': expanded_queries[:8],  # Limit to 8 expansions
            'metadata': {
                'expansion_type': 'entity_based',
                'entities_found': len(entities),
                'relationships_used': sum(len(self.entity_relationships.get(e, [])) for e in entities)
            }
        }

    def _contextual_expansion(self, query: str, analysis: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform contextual expansion based on query complexity."""
        expanded_queries = []

        # Break down complex queries
        sub_queries = self._decompose_complex_query(query, analysis)

        # Create focused sub-queries
        for sub_query in sub_queries:
            expanded_queries.append(sub_query)
            # Add context-preserving expansions
            expanded_queries.append(f"{sub_query} in context of {query[:50]}...")

        # Add prerequisite knowledge queries
        if analysis['complexity_indicators']:
            for indicator in analysis['complexity_indicators'][:2]:
                expanded_queries.append(f"understanding {indicator} in {query[:30]}...")

        return {
            'queries': expanded_queries[:6],
            'metadata': {
                'expansion_type': 'contextual',
                'sub_queries': len(sub_queries),
                'complexity_indicators': len(analysis['complexity_indicators'])
            }
        }

    def _multi_hop_reasoning(self, query: str, analysis: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform multi-hop reasoning expansion."""
        expanded_queries = []

        # Identify reasoning chains
        reasoning_chains = self._identify_reasoning_chains(query, analysis)

        # Generate multi-hop queries
        for chain in reasoning_chains:
            # Direct relationship
            expanded_queries.append(f"{chain[0]} {chain[1]}")

            # Multi-hop paths
            if len(chain) > 2:
                for i in range(len(chain) - 1):
                    expanded_queries.append(f"how {chain[i]} connects to {chain[i + 1]}")

            # Full chain reasoning
            if len(chain) >= 3:
                chain_str = ' -> '.join(chain)
                expanded_queries.append(f"reasoning chain: {chain_str}")

        return {
            'queries': expanded_queries[:7],
            'metadata': {
                'expansion_type': 'multi_hop',
                'reasoning_chains': len(reasoning_chains),
                'max_chain_length': max(len(chain) for chain in reasoning_chains) if reasoning_chains else 0
            }
        }

    def _temporal_expansion(self, query: str, analysis: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform temporal expansion for time-sensitive queries."""
        expanded_queries = []

        temporal_signals = analysis['temporal_signals']

        # Time-aware expansions
        time_expansions = {
            'recent': ['latest', 'current', 'new', 'updated'],
            'old': ['previous', 'historical', 'legacy', 'outdated'],
            'before': ['prior', 'preceding', 'earlier'],
            'after': ['following', 'subsequent', 'later']
        }

        for signal in temporal_signals:
            if signal in time_expansions:
                for expansion in time_expansions[signal]:
                    # Replace temporal signal in query
                    expanded_query = query.replace(signal, expansion)
                    if expanded_query != query:
                        expanded_queries.append(expanded_query)

        # Add time-bounded queries
        if temporal_signals:
            expanded_queries.append(f"{query} timeline")
            expanded_queries.append(f"{query} over time")
            expanded_queries.append(f"evolution of {query}")

        return {
            'queries': expanded_queries[:5],
            'metadata': {
                'expansion_type': 'temporal',
                'temporal_signals': len(temporal_signals),
                'time_expansions': len(expanded_queries)
            }
        }

    def _domain_specific_expansion(self, query: str, analysis: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform domain-specific expansion."""
        expanded_queries = []

        domain_signals = analysis['domain_signals']

        # Domain-specific knowledge expansion
        for term in domain_signals:
            domain_knowledge = self.domain_knowledge.get(term, {})
            related_terms = domain_knowledge.get('related', [])

            for related in related_terms[:3]:
                expanded_queries.append(f"{query} {related}")
                expanded_queries.append(f"{related} aspects of {query}")

        return {
            'queries': expanded_queries[:6],
            'metadata': {
                'expansion_type': 'domain_specific',
                'domain_terms': len(domain_signals),
                'knowledge_expansions': len(expanded_queries)
            }
        }

    def _get_query_synonyms(self, query: str) -> List[List[str]]:
        """Get synonym sets for query terms."""
        # Simple synonym expansion (would use WordNet or similar in production)
        synonym_sets = [
            ['information', 'data', 'details', 'knowledge'],
            ['understand', 'comprehend', 'grasp', 'know'],
            ['improve', 'enhance', 'optimize', 'boost'],
            ['system', 'framework', 'platform', 'infrastructure']
        ]

        return synonym_sets

    def _get_related_concepts(self, query: str, analysis: Dict[str, Any]) -> List[str]:
        """Get related concepts for query expansion."""
        related_concepts = []

        # Query-type based concepts
        if 'technical' in analysis['domain_signals']:
            related_concepts.extend(['implementation', 'architecture', 'performance', 'scalability'])

        if 'business' in analysis['domain_signals']:
            related_concepts.extend(['strategy', 'ROI', 'market', 'stakeholders'])

        # Complexity-based concepts
        if analysis['complexity_indicators']:
            related_concepts.extend(['background', 'context', 'fundamentals', 'basics'])

        return related_concepts

    def _create_abstract_queries(self, query: str, analysis: Dict[str, Any]) -> List[str]:
        """Create queries at different abstraction levels."""
        abstract_queries = []

        # More specific/abstract versions
        if analysis['word_count'] > 10:
            # Summarize to key concepts
            words = query.split()
            key_words = [w for w in words if len(w) > 4][:5]  # Longer, potentially more important words
            if key_words:
                abstract_queries.append(' '.join(key_words))

        # More general versions
        if analysis['specificity_score'] > 0.2:
            # Remove specific terms
            general_query = query
            specific_terms = ['specific', 'particular', 'exact', 'precise', 'detailed']
            for term in specific_terms:
                general_query = general_query.replace(term, '')
            if general_query != query:
                abstract_queries.append(general_query.strip())

        return abstract_queries

    def _extract_entities(self, query: str) -> List[str]:
        """Extract entities from query."""
        words = query.split()
        entities = []

        # Simple entity extraction based on capitalization and length
        for word in words:
            if (word[0].isupper() and len(word) > 3 and
                not word.endswith('.') and word not in ['The', 'A', 'An']):
                entities.append(word)

        return entities

    def _decompose_complex_query(self, query: str, analysis: Dict[str, Any]) -> List[str]:
        """Decompose complex query into simpler sub-queries."""
        sub_queries = []

        # Split on connectives
        connectives = [' and ', ' or ', ' but ', ' however ', ' therefore ', ' thus ']
        parts = [query]

        for connective in connectives:
            new_parts = []
            for part in parts:
                new_parts.extend(part.split(connective))
            parts = new_parts

        # Clean and filter parts
        for part in parts:
            part = part.strip()
            if len(part) > 10 and len(part.split()) > 3:  # Meaningful sub-query
                sub_queries.append(part)

        return sub_queries[:4]  # Limit sub-queries

    def _identify_reasoning_chains(self, query: str, analysis: Dict[str, Any]) -> List[List[str]]:
        """Identify reasoning chains in the query."""
        chains = []

        # Extract entities and relationships
        entities = self._extract_entities(query)
        relational_words = analysis['relational_signals']

        # Create simple chains based on entities and relationships
        if len(entities) >= 2 and relational_words:
            for i in range(len(entities) - 1):
                chain = [entities[i], relational_words[0], entities[i + 1]]
                chains.append(chain)

        # Add knowledge-based chains
        for entity in entities:
            related = self.entity_relationships.get(entity, [])
            if related:
                chain = [entity] + related[:2]  # Limit chain length
                chains.append(chain)

        return chains

    def _deduplicate_and_rank_queries(self, queries: List[str], original_query: str) -> List[str]:
        """Deduplicate and rank enhanced queries."""
        # Remove duplicates while preserving order
        seen = set()
        deduplicated = []

        for query in queries:
            query_lower = query.lower().strip()
            if query_lower not in seen and query_lower != original_query.lower():
                seen.add(query_lower)
                deduplicated.append(query)

        # Rank by relevance to original query
        ranked = sorted(deduplicated, key=lambda q: self._calculate_query_similarity(q, original_query), reverse=True)

        # Limit total queries
        max_queries = min(len(ranked) + 1, int(self.max_expansion_factor * len(original_query.split())))
        return ranked[:max_queries]

    def _calculate_query_similarity(self, query1: str, query2: str) -> float:
        """Calculate similarity between two queries."""
        words1 = set(query1.lower().split())
        words2 = set(query2.lower().split())

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def _estimate_recall_improvement(self, analysis: Dict[str, Any], strategies: List[str]) -> float:
        """Estimate recall improvement from applied strategies."""
        base_improvement = 0.1  # Base improvement

        # Strategy-specific improvements
        strategy_boosts = {
            'semantic_expansion': 0.15,
            'entity_based_expansion': 0.2,
            'contextual_expansion': 0.1,
            'multi_hop_reasoning': 0.25,
            'temporal_expansion': 0.1,
            'domain_specific_expansion': 0.15
        }

        total_boost = sum(strategy_boosts.get(strategy, 0) for strategy in strategies)

        # Long-tail specific boost
        if analysis['is_long_tail']:
            total_boost *= 1.3

        return min(base_improvement + total_boost, 0.5)  # Cap at 50% improvement

    def _record_enhancement_stats(self, result: Dict[str, Any]):
        """Record enhancement statistics."""
        self.enhancement_stats['expansion_factors'].append(result['expansion_factor'])
        self.enhancement_stats['strategies_used'].append(len(result['strategies_applied']))
        self.enhancement_stats['enhancement_times'].append(result['enhancement_time'])
        self.enhancement_stats['expected_improvements'].append(result['expected_recall_improvement'])

        # Keep only recent stats
        max_stats = 1000
        for key in self.enhancement_stats:
            if len(self.enhancement_stats[key]) > max_stats:
                self.enhancement_stats[key] = self.enhancement_stats[key][-max_stats:]

    def _load_domain_knowledge(self) -> Dict[str, Any]:
        """Load domain-specific knowledge for expansion."""
        # Simplified domain knowledge (would load from external sources in production)
        return {
            'algorithm': {'related': ['efficiency', 'complexity', 'optimization', 'implementation']},
            'neural': {'related': ['network', 'learning', 'training', 'architecture']},
            'scalability': {'related': ['performance', 'distributed', 'load balancing', 'throughput']},
            'optimization': {'related': ['performance', 'efficiency', 'algorithms', 'trade-offs']}
        }

    def _load_entity_relationships(self) -> Dict[str, List[str]]:
        """Load entity relationship knowledge."""
        # Simplified entity relationships (would use knowledge graph in production)
        return {
            'GraphRAG': ['retrieval', 'generation', 'knowledge graph', 'AI'],
            'machine learning': ['algorithms', 'training', 'prediction', 'models'],
            'database': ['storage', 'query', 'indexing', 'performance'],
            'API': ['interface', 'communication', 'services', 'integration']
        }

    def get_enhancement_stats(self) -> Dict[str, Any]:
        """Get enhancement statistics."""
        stats = {}

        for key, values in self.enhancement_stats.items():
            if values:
                stats[key] = {
                    'mean': np.mean(values),
                    'std': np.std(values),
                    'min': np.min(values),
                    'max': np.max(values),
                    'count': len(values)
                }
            else:
                stats[key] = {'count': 0}

        stats['target_recall'] = self.target_recall
        stats['max_expansion_factor'] = self.max_expansion_factor

        return stats

    def update_domain_knowledge(self, new_knowledge: Dict[str, Any]):
        """
        Update domain knowledge for better expansions.

        Args:
            new_knowledge: New domain knowledge to add
        """
        self.domain_knowledge.update(new_knowledge)
        logger.info(f"Updated domain knowledge with {len(new_knowledge)} new entries")

    def enable_adaptive_learning(self, enable: bool = True):
        """Enable adaptive learning from successful expansions."""
        self.adaptive_learning = enable
        logger.info(f"Adaptive learning {'enabled' if enable else 'disabled'}")
