"""
Graph-Based Retrieval Strategy for GraphRAG.

This module implements graph-based retrieval using Neo4j and GNN techniques
to find relevant information through graph traversal and reasoning.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import numpy as np

from ...graph_db import Neo4jGraphStore, GraphQueryEngine, KnowledgeGraph
from ..scored_chunk import ScoredChunk
from ..types import RetrievalResult

logger = logging.getLogger(__name__)


class GraphRetrievalStrategy:
    """
    Graph-based retrieval strategy using Neo4j and graph algorithms.

    Supports path finding, subgraph extraction, and semantic graph search
    to retrieve contextually relevant information.
    """

    def __init__(
        self,
        graph_store: Neo4jGraphStore,
        query_engine: Optional[GraphQueryEngine] = None
    ):
        """
        Initialize graph retrieval strategy.

        Args:
            graph_store: Neo4j graph database store
            query_engine: Graph query engine (optional)
        """
        self.graph_store = graph_store
        self.query_engine = query_engine or GraphQueryEngine(graph_store)

        # Retrieval parameters
        self.max_path_depth = 3
        self.max_subgraph_nodes = 50
        self.semantic_search_top_k = 20
        self.path_search_limit = 10

        # Scoring weights
        self.scoring_weights = {
            'semantic_similarity': 0.4,
            'graph_centrality': 0.3,
            'path_relevance': 0.2,
            'entity_match': 0.1
        }

        logger.info("Graph retrieval strategy initialized")

    def retrieve(
        self,
        query: str,
        top_k: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        query_profile: Optional[Dict[str, Any]] = None
    ) -> List[ScoredChunk]:
        """
        Execute graph-based retrieval.

        Args:
            query: Query string
            top_k: Number of results to return
            filters: Optional filtering criteria
            query_profile: Query profiling information

        Returns:
            List of scored chunks from graph retrieval
        """
        logger.debug(f"Graph retrieval for query: {query[:100]}...")

        all_candidates = []

        try:
            # Strategy 1: Semantic search on graph nodes
            semantic_results = self._semantic_graph_search(query, top_k)
            all_candidates.extend(semantic_results)

            # Strategy 2: Path-based retrieval
            path_results = self._path_based_retrieval(query, top_k // 2)
            all_candidates.extend(path_results)

            # Strategy 3: Entity-centric retrieval
            entity_results = self._entity_centric_retrieval(query, query_profile)
            all_candidates.extend(entity_results)

            # Strategy 4: Subgraph extraction
            subgraph_results = self._subgraph_retrieval(query, top_k // 3)
            all_candidates.extend(subgraph_results)

            # Remove duplicates and re-score
            unique_candidates = self._deduplicate_and_rescore(all_candidates)

            # Apply filters if provided
            if filters:
                unique_candidates = self._apply_filters(unique_candidates, filters)

            # Return top-k results
            final_results = sorted(
                unique_candidates,
                key=lambda x: x.score,
                reverse=True
            )[:top_k]

            logger.debug(f"Graph retrieval returned {len(final_results)} unique results")
            return final_results

        except Exception as e:
            logger.error(f"Graph retrieval failed: {e}")
            return []

    def _semantic_graph_search(self, query: str, top_k: int) -> List[ScoredChunk]:
        """
        Perform semantic search on graph nodes using embeddings.

        Args:
            query: Query string
            top_k: Number of results

        Returns:
            List of scored chunks
        """
        results = []

        try:
            # This would require query embeddings
            # For now, perform text-based node search
            query_lower = query.lower()

            # Search for nodes containing query terms
            with self.graph_store.session_scope() as session:
                cypher_query = """
                MATCH (n:Node)
                WHERE toLower(n.label) CONTAINS $query_term
                   OR toLower(n.text) CONTAINS $query_term
                RETURN n, rand() as score
                ORDER BY score DESC
                LIMIT $limit
                """

                # Split query into terms for broader matching
                query_terms = query_lower.split()
                for term in query_terms[:3]:  # Limit to first 3 terms
                    result = session.run(cypher_query, query_term=term, limit=top_k)
                    for record in result:
                        node_data = dict(record["n"])
                        score = record["score"]

                        # Create scored chunk from node
                        chunk = self._node_to_chunk(node_data, score * 0.8)
                        if chunk:
                            results.append(chunk)

        except Exception as e:
            logger.warning(f"Semantic graph search failed: {e}")

        return results

    def _path_based_retrieval(self, query: str, limit: int) -> List[ScoredChunk]:
        """
        Retrieve information through graph path finding.

        Args:
            query: Query string
            limit: Maximum number of paths to explore

        Returns:
            List of scored chunks from path traversal
        """
        results = []

        try:
            # Extract entities from query
            query_entities = self._extract_query_entities(query)

            if len(query_entities) >= 2:
                # Find paths between entities
                paths = self.query_engine.find_paths(
                    start_node_ids=query_entities,
                    end_node_ids=[],  # All nodes as potential ends
                    max_depth=self.max_path_depth,
                    max_paths=limit
                )

                for path in paths:
                    # Convert path nodes to chunks
                    for node in path.nodes:
                        score = path.score * 0.9  # Path relevance affects node score
                        chunk = self._node_to_chunk(node.__dict__, score)
                        if chunk:
                            results.append(chunk)

            elif len(query_entities) == 1:
                # Single entity - find related nodes
                subgraph = self.query_engine.subgraph_search(
                    center_node_ids=query_entities,
                    radius=2,
                    node_types=None
                )

                for node_data in subgraph.nodes.values():
                    score = 0.7  # Default score for related nodes
                    chunk = self._node_to_chunk(node_data.__dict__, score)
                    if chunk:
                        results.append(chunk)

        except Exception as e:
            logger.warning(f"Path-based retrieval failed: {e}")

        return results

    def _entity_centric_retrieval(
        self,
        query: str,
        query_profile: Optional[Dict[str, Any]]
    ) -> List[ScoredChunk]:
        """
        Retrieve information centered around query entities.

        Args:
            query: Query string
            query_profile: Query profiling information

        Returns:
            List of entity-centric results
        """
        results = []

        try:
            # Extract entities from query
            query_entities = self._extract_query_entities(query)

            for entity_text in query_entities:
                # Find graph nodes matching entities
                entity_nodes = self.graph_store.find_nodes_by_type(
                    node_type=None,  # Search all types
                    limit=5
                )

                # Filter nodes that match entity text
                matching_nodes = [
                    node for node in entity_nodes
                    if entity_text.lower() in node.label.lower()
                ]

                for node in matching_nodes:
                    score = 0.85  # High score for entity matches
                    chunk = self._node_to_chunk(node.__dict__, score)
                    if chunk:
                        results.append(chunk)

        except Exception as e:
            logger.warning(f"Entity-centric retrieval failed: {e}")

        return results

    def _subgraph_retrieval(self, query: str, limit: int) -> List[ScoredChunk]:
        """
        Extract relevant subgraph and convert to chunks.

        Args:
            query: Query string
            limit: Maximum subgraph size

        Returns:
            List of chunks from subgraph
        """
        results = []

        try:
            # Extract key entities/concepts from query
            key_terms = self._extract_key_terms(query)

            if key_terms:
                # Find nodes matching key terms
                center_nodes = []
                for term in key_terms[:3]:  # Limit to top 3 terms
                    nodes = self.graph_store.find_nodes_by_type(None, limit=3)
                    matching_nodes = [
                        node for node in nodes
                        if term.lower() in node.label.lower()
                    ]
                    center_nodes.extend([node.id for node in matching_nodes])

                if center_nodes:
                    # Extract subgraph
                    subgraph = self.query_engine.subgraph_search(
                        center_node_ids=center_nodes,
                        radius=2,
                        node_types=None
                    )

                    # Convert subgraph nodes to chunks
                    for node in subgraph.nodes.values():
                        score = 0.6  # Default subgraph score
                        chunk = self._node_to_chunk(node.__dict__, score)
                        if chunk:
                            results.append(chunk)

        except Exception as e:
            logger.warning(f"Subgraph retrieval failed: {e}")

        return results

    def _node_to_chunk(self, node_data: Dict[str, Any], base_score: float) -> Optional[ScoredChunk]:
        """
        Convert graph node to scored chunk.

        Args:
            node_data: Node data dictionary
            base_score: Base relevance score

        Returns:
            ScoredChunk or None if conversion fails
        """
        try:
            from ..index_loader import ChunkData

            # Create chunk data from node
            chunk_data = ChunkData(
                chunk_id=node_data.get("id", f"graph_{hash(str(node_data))}"),
                doc_id=node_data.get("document_id", "graph_doc"),
                text=node_data.get("text", node_data.get("label", "")),
                metadata={
                    "source": "graph_retrieval",
                    "node_type": node_data.get("type", "unknown"),
                    "graph_score": base_score,
                    **node_data
                },
                modality="text",
                page_number=node_data.get("page_number", 0),
                chunk_index=0
            )

            # Create scored chunk
            scored_chunk = ScoredChunk(
                chunk=chunk_data,
                score=base_score,
                rank=0,  # Will be set later
                retrieval_method="graph_retrieval",
                evidence=[]
            )

            return scored_chunk

        except Exception as e:
            logger.warning(f"Failed to convert node to chunk: {e}")
            return None

    def _extract_query_entities(self, query: str) -> List[str]:
        """
        Extract entity mentions from query.

        Args:
            query: Query string

        Returns:
            List of entity IDs or texts
        """
        # Simple entity extraction - in practice would use NER
        entities = []

        # Look for capitalized words (potential entities)
        import re
        words = re.findall(r'\b[A-Z][a-z]+\b', query)
        entities.extend(words)

        # Look for quoted terms
        quoted = re.findall(r'"([^"]*)"', query)
        entities.extend(quoted)

        return list(set(entities))  # Remove duplicates

    def _extract_key_terms(self, query: str) -> List[str]:
        """
        Extract key terms from query for graph search.

        Args:
            query: Query string

        Returns:
            List of key terms
        """
        # Simple term extraction
        import re

        # Remove stop words and punctuation
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}

        words = re.findall(r'\b\w+\b', query.lower())
        key_terms = [word for word in words if word not in stop_words and len(word) > 2]

        return list(set(key_terms))[:5]  # Limit to 5 key terms

    def _deduplicate_and_rescore(self, candidates: List[ScoredChunk]) -> List[ScoredChunk]:
        """
        Remove duplicates and rescore candidates.

        Args:
            candidates: List of candidate chunks

        Returns:
            Deduplicated and rescored chunks
        """
        seen_ids = set()
        unique_candidates = []

        for candidate in candidates:
            chunk_id = candidate.chunk.chunk_id

            if chunk_id not in seen_ids:
                seen_ids.add(chunk_id)
                unique_candidates.append(candidate)
            else:
                # Update score if duplicate found (take maximum)
                existing_idx = next(
                    (i for i, c in enumerate(unique_candidates) if c.chunk.chunk_id == chunk_id),
                    None
                )
                if existing_idx is not None:
                    unique_candidates[existing_idx].score = max(
                        unique_candidates[existing_idx].score,
                        candidate.score
                    )

        return unique_candidates

    def _apply_filters(
        self,
        candidates: List[ScoredChunk],
        filters: Dict[str, Any]
    ) -> List[ScoredChunk]:
        """
        Apply filtering criteria to candidates.

        Args:
            candidates: List of candidate chunks
            filters: Filtering criteria

        Returns:
            Filtered list of chunks
        """
        filtered = []

        for candidate in candidates:
            include = True

            # Apply node type filter
            if 'node_types' in filters:
                node_type = candidate.chunk.metadata.get('node_type')
                if node_type and node_type not in filters['node_types']:
                    include = False

            # Apply document filter
            if 'doc_ids' in filters:
                doc_id = candidate.chunk.doc_id
                if doc_id and doc_id not in filters['doc_ids']:
                    include = False

            # Apply score threshold
            if 'min_score' in filters:
                if candidate.score < filters['min_score']:
                    include = False

            if include:
                filtered.append(candidate)

        return filtered

    def update_retrieval_params(self, performance_metrics: Dict[str, float]) -> None:
        """
        Update retrieval parameters based on performance.

        Args:
            performance_metrics: Performance metrics
        """
        try:
            # Adaptive parameter adjustment
            if 'avg_query_time' in performance_metrics:
                query_time = performance_metrics['avg_query_time']
                if query_time > 2.0:  # Slow queries
                    self.max_path_depth = max(2, self.max_path_depth - 1)
                    self.max_subgraph_nodes = max(20, self.max_subgraph_nodes - 10)

            if 'recall_rate' in performance_metrics:
                recall = performance_metrics['recall_rate']
                if recall < 0.7:  # Low recall
                    self.max_path_depth = min(5, self.max_path_depth + 1)
                    self.semantic_search_top_k = min(50, self.semantic_search_top_k + 5)

            logger.info(f"Updated retrieval params: depth={self.max_path_depth}, top_k={self.semantic_search_top_k}")

        except Exception as e:
            logger.warning(f"Failed to update retrieval params: {e}")

    def get_strategy_stats(self) -> Dict[str, Any]:
        """
        Get strategy statistics and configuration.

        Returns:
            Dictionary with strategy statistics
        """
        return {
            'max_path_depth': self.max_path_depth,
            'max_subgraph_nodes': self.max_subgraph_nodes,
            'semantic_search_top_k': self.semantic_search_top_k,
            'scoring_weights': self.scoring_weights,
            'graph_stats': self.graph_store.get_graph_statistics()
        }







