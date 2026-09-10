"""
Beam Search Path Reranking for Evidence Chain Optimization.

Implements beam search algorithm to find optimal evidence paths
through the knowledge graph for multi-hop reasoning.

Core Innovation:
- Explores multiple reasoning paths simultaneously
- Prunes low-quality paths early to save computation
- Reranks final paths based on coherence and evidence strength
"""
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from heapq import heappush, heappop, nlargest
import math

logger = logging.getLogger(__name__)


@dataclass
class EvidenceNode:
    """A node in the evidence graph."""
    node_id: str
    content: str
    node_type: str  # entity, fact, document
    confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidencePath:
    """A path through the evidence graph."""
    nodes: List[EvidenceNode]
    edges: List[str]  # Relationship types
    score: float
    coherence: float = 0.0
    
    def __lt__(self, other):
        """For heap comparison (max-heap via negation)."""
        return self.score > other.score
    
    def __len__(self):
        return len(self.nodes)
    
    def last_node(self) -> Optional[EvidenceNode]:
        return self.nodes[-1] if self.nodes else None
    
    def extend(self, node: EvidenceNode, edge: str, score_delta: float) -> 'EvidencePath':
        """Create new path by extending with a node."""
        return EvidencePath(
            nodes=self.nodes + [node],
            edges=self.edges + [edge],
            score=self.score + score_delta,
            coherence=self.coherence
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.node_id for n in self.nodes],
            "edges": self.edges,
            "score": self.score,
            "coherence": self.coherence,
            "length": len(self.nodes)
        }


@dataclass
class BeamSearchConfig:
    """Configuration for beam search."""
    beam_width: int = 5          # Number of paths to keep at each step
    max_depth: int = 4           # Maximum path length
    min_score_threshold: float = 0.3  # Minimum score to continue path
    diversity_penalty: float = 0.1    # Penalty for similar paths
    coherence_weight: float = 0.3     # Weight for path coherence


class BeamSearchReranker:
    """
    Beam search algorithm for evidence path reranking.
    
    Finds optimal paths through evidence graph using beam search,
    then reranks based on coherence and relevance to query.
    """
    
    def __init__(self, config: Optional[BeamSearchConfig] = None):
        self.config = config or BeamSearchConfig()
        self.graph: Dict[str, List[Tuple[str, EvidenceNode, float]]] = {}
        logger.info(f"BeamSearchReranker initialized (beam_width={self.config.beam_width})")
    
    def build_graph(self, nodes: List[EvidenceNode], edges: List[Dict[str, Any]]):
        """Build adjacency list from nodes and edges."""
        self.graph = {node.node_id: [] for node in nodes}
        self.node_map = {node.node_id: node for node in nodes}
        
        for edge in edges:
            src, dst = edge["source"], edge["target"]
            rel_type = edge.get("relation", "related")
            weight = edge.get("weight", 1.0)
            
            if src in self.graph and dst in self.node_map:
                self.graph[src].append((rel_type, self.node_map[dst], weight))
    
    def search(
        self,
        query: str,
        start_nodes: List[str],
        target_nodes: Optional[List[str]] = None
    ) -> List[EvidencePath]:
        """
        Perform beam search to find best evidence paths.
        
        Args:
            query: The user query for relevance scoring
            start_nodes: Node IDs to start search from
            target_nodes: Optional target node IDs (for directed search)
            
        Returns:
            List of top-k evidence paths
        """
        # Initialize beams with start nodes
        beams: List[EvidencePath] = []
        for node_id in start_nodes:
            if node_id in self.node_map:
                node = self.node_map[node_id]
                initial_score = self._compute_relevance(query, node)
                path = EvidencePath(nodes=[node], edges=[], score=initial_score)
                beams.append(path)
        
        # Keep only top beam_width paths
        beams = nlargest(self.config.beam_width, beams)
        
        # Iterative beam search
        for depth in range(self.config.max_depth - 1):
            candidates: List[EvidencePath] = []
            
            for path in beams:
                last_node = path.last_node()
                if not last_node or last_node.node_id not in self.graph:
                    candidates.append(path)  # Keep completed paths
                    continue
                
                # Expand path with neighbors
                for rel_type, neighbor, edge_weight in self.graph[last_node.node_id]:
                    # Skip if already in path (no cycles)
                    if any(n.node_id == neighbor.node_id for n in path.nodes):
                        continue
                    
                    # Compute score for extension
                    relevance = self._compute_relevance(query, neighbor)
                    transition = self._compute_transition_score(last_node, neighbor, rel_type)
                    score_delta = (relevance + transition * edge_weight) / 2
                    
                    if score_delta >= self.config.min_score_threshold:
                        new_path = path.extend(neighbor, rel_type, score_delta)
                        candidates.append(new_path)
            
            if not candidates:
                break
            
            # Apply diversity penalty and select top paths
            candidates = self._apply_diversity_penalty(candidates)
            beams = nlargest(self.config.beam_width, candidates)
        
        # Final reranking with coherence
        final_paths = self._rerank_with_coherence(beams, query)
        return final_paths

    def _compute_relevance(self, query: str, node: EvidenceNode) -> float:
        """Compute relevance score between query and node."""
        # Simple keyword overlap (can be replaced with embedding similarity)
        query_terms = set(query.lower().split())
        content_terms = set(node.content.lower().split())

        if not query_terms:
            return node.confidence

        overlap = len(query_terms & content_terms)
        relevance = overlap / len(query_terms)

        # Combine with node confidence
        return 0.6 * relevance + 0.4 * node.confidence

    def _compute_transition_score(
        self,
        from_node: EvidenceNode,
        to_node: EvidenceNode,
        relation: str
    ) -> float:
        """Compute transition score between nodes."""
        # Type compatibility bonus
        type_bonus = 0.0
        if from_node.node_type == "entity" and to_node.node_type == "fact":
            type_bonus = 0.2
        elif from_node.node_type == "fact" and to_node.node_type == "document":
            type_bonus = 0.1

        # Relation strength
        strong_relations = {"supports", "proves", "contains", "defines"}
        relation_bonus = 0.2 if relation.lower() in strong_relations else 0.0

        return 0.5 + type_bonus + relation_bonus

    def _apply_diversity_penalty(self, paths: List[EvidencePath]) -> List[EvidencePath]:
        """Apply penalty to similar paths to encourage diversity."""
        if len(paths) <= 1:
            return paths

        for i, path in enumerate(paths):
            for j, other in enumerate(paths[:i]):
                # Compute path similarity (node overlap)
                nodes_i = set(n.node_id for n in path.nodes)
                nodes_j = set(n.node_id for n in other.nodes)

                if nodes_i and nodes_j:
                    overlap = len(nodes_i & nodes_j) / len(nodes_i | nodes_j)
                    penalty = overlap * self.config.diversity_penalty
                    path.score -= penalty

        return paths

    def _rerank_with_coherence(
        self,
        paths: List[EvidencePath],
        query: str
    ) -> List[EvidencePath]:
        """Rerank paths based on coherence score."""
        for path in paths:
            coherence = self._compute_coherence(path)
            path.coherence = coherence
            # Adjust final score with coherence
            path.score = (1 - self.config.coherence_weight) * path.score + \
                         self.config.coherence_weight * coherence

        return sorted(paths, key=lambda p: p.score, reverse=True)

    def _compute_coherence(self, path: EvidencePath) -> float:
        """Compute coherence score for a path."""
        if len(path.nodes) < 2:
            return 1.0

        # Check edge type consistency
        edge_types = set(path.edges)
        type_consistency = 1.0 / (1.0 + len(edge_types) * 0.1)

        # Check confidence progression
        confidences = [n.confidence for n in path.nodes]
        avg_confidence = sum(confidences) / len(confidences)

        # Penalize large confidence drops
        drops = sum(max(0, confidences[i] - confidences[i+1])
                   for i in range(len(confidences)-1))
        drop_penalty = 1.0 / (1.0 + drops)

        return (type_consistency + avg_confidence + drop_penalty) / 3

    def get_best_path(self, query: str, start_nodes: List[str]) -> Optional[EvidencePath]:
        """Get single best evidence path."""
        paths = self.search(query, start_nodes)
        return paths[0] if paths else None

