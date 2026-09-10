"""
Query Expansion Strategy for GraphRAG.

This module implements query expansion using BERT-based models and
ColBERT techniques to improve retrieval quality for long-tail queries.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import torch
from transformers import AutoTokenizer, AutoModel
import numpy as np

logger = logging.getLogger(__name__)


class QueryExpansionStrategy:
    """
    Query expansion using BERT and ColBERT techniques.

    Generates expanded queries to improve recall for long-tail and
    complex queries by understanding semantic relationships.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str = "auto"
    ):
        """
        Initialize query expansion strategy.

        Args:
            model_name: BERT model for query expansion
            device: Device to run model on
        """
        self.device = self._setup_device(device)
        self.model_name = model_name

        # Initialize model and tokenizer
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name).to(self.device)
            self.model.eval()
            logger.info(f"Query expansion model loaded: {model_name}")
        except Exception as e:
            logger.warning(f"Failed to load model {model_name}: {e}")
            self.model = None
            self.tokenizer = None

        # Expansion parameters
        self.max_expansions = 5
        self.expansion_similarity_threshold = 0.7
        self.term_importance_threshold = 0.3

        # Pre-defined expansion templates
        self.expansion_templates = {
            'financial': [
                "What is the {term} for {entity}?",
                "Calculate {term} of {entity}",
                "Show me {term} data for {entity}",
                "{entity} {term} analysis",
                "{term} trends for {entity}"
            ],
            'comparison': [
                "Compare {term} between {entities}",
                "{term} difference between {entities}",
                "Which has better {term}: {entities}",
                "{entities} {term} comparison"
            ],
            'temporal': [
                "{term} over time for {entity}",
                "Historical {term} of {entity}",
                "{entity} {term} change over years",
                "Trend analysis of {term} for {entity}"
            ]
        }

    def _setup_device(self, device: str) -> str:
        """Setup compute device."""
        if device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device

    def expand_query(
        self,
        query: str,
        query_profile: Optional[Dict[str, Any]] = None,
        max_expansions: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Expand query using multiple techniques.

        Args:
            query: Original query string
            query_profile: Query profiling information
            max_expansions: Maximum number of expansions to generate

        Returns:
            List of expanded queries with confidence scores
        """
        expansions = []

        try:
            # Technique 1: Template-based expansion
            template_expansions = self._template_based_expansion(query, query_profile)
            expansions.extend(template_expansions)

            # Technique 2: Synonym expansion using BERT
            if self.model is not None:
                synonym_expansions = self._synonym_expansion(query)
                expansions.extend(synonym_expansions)

            # Technique 3: Concept expansion
            concept_expansions = self._concept_expansion(query, query_profile)
            expansions.extend(concept_expansions)

            # Technique 4: ColBERT-style term importance
            if self.model is not None:
                colbert_expansions = self._colbert_expansion(query)
                expansions.extend(colbert_expansions)

            # Remove duplicates and rank by confidence
            unique_expansions = self._deduplicate_expansions(expansions)
            ranked_expansions = sorted(
                unique_expansions,
                key=lambda x: x['confidence'],
                reverse=True
            )

            return ranked_expansions[:max_expansions]

        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            return [{"query": query, "confidence": 1.0, "method": "original"}]

    def _template_based_expansion(
        self,
        query: str,
        query_profile: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate expansions using query templates.

        Args:
            query: Original query
            query_profile: Query profile information

        Returns:
            List of template-based expansions
        """
        expansions = []

        # Determine query type
        query_type = self._classify_query_type(query, query_profile)

        if query_type in self.expansion_templates:
            templates = self.expansion_templates[query_type]

            # Extract entities and terms
            entities = self._extract_entities(query)
            terms = self._extract_terms(query)

            for template in templates:
                try:
                    if "{entity}" in template and entities:
                        for entity in entities[:2]:  # Limit combinations
                            expansion = template.format(
                                term=terms[0] if terms else "value",
                                entity=entity,
                                entities=", ".join(entities[:2])
                            )
                            expansions.append({
                                "query": expansion,
                                "confidence": 0.8,
                                "method": "template",
                                "template_type": query_type
                            })

                    elif "{term}" in template and terms:
                        for term in terms[0:1]:  # Use primary term
                            expansion = template.format(
                                term=term,
                                entity=entities[0] if entities else "company"
                            )
                            expansions.append({
                                "query": expansion,
                                "confidence": 0.7,
                                "method": "template",
                                "template_type": query_type
                            })

                except (KeyError, IndexError):
                    continue

        return expansions

    def _synonym_expansion(self, query: str) -> List[Dict[str, Any]]:
        """
        Generate expansions using BERT-based synonym finding.

        Args:
            query: Original query

        Returns:
            List of synonym-based expansions
        """
        expansions = []

        if not self.model or not self.tokenizer:
            return expansions

        try:
            # Extract key terms
            terms = self._extract_terms(query)
            if not terms:
                return expansions

            # Generate embeddings for terms
            term_embeddings = self._get_embeddings(terms)

            # Find similar terms (simplified - would need a vocabulary)
            # In practice, this would use a synonym database or word embeddings
            for i, term in enumerate(terms):
                # Simple synonym mapping (placeholder)
                synonyms = self._get_simple_synonyms(term)

                for synonym in synonyms:
                    # Replace term with synonym
                    expansion = query.replace(term, synonym)
                    if expansion != query:
                        confidence = 0.6  # Lower confidence for synonyms
                        expansions.append({
                            "query": expansion,
                            "confidence": confidence,
                            "method": "synonym",
                            "original_term": term,
                            "synonym": synonym
                        })

        except Exception as e:
            logger.warning(f"Synonym expansion failed: {e}")

        return expansions

    def _concept_expansion(
        self,
        query: str,
        query_profile: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate expansions based on conceptual relationships.

        Args:
            query: Original query
            query_profile: Query profile

        Returns:
            List of concept-based expansions
        """
        expansions = []

        # Financial concept expansions
        financial_concepts = {
            'revenue': ['sales', 'income', 'earnings', 'turnover'],
            'profit': ['earnings', 'income', 'margin', 'gain'],
            'growth': ['increase', 'expansion', 'rise', 'improvement'],
            'margin': ['profitability', 'percentage', 'ratio']
        }

        terms = self._extract_terms(query)

        for term in terms:
            term_lower = term.lower()
            if term_lower in financial_concepts:
                related_terms = financial_concepts[term_lower]

                for related in related_terms:
                    expansion = query.replace(term, related)
                    if expansion != query:
                        expansions.append({
                            "query": expansion,
                            "confidence": 0.75,
                            "method": "concept",
                            "original_term": term,
                            "related_term": related
                        })

        return expansions

    def _colbert_expansion(self, query: str) -> List[Dict[str, Any]]:
        """
        Generate expansions using ColBERT-style term importance.

        Args:
            query: Original query

        Returns:
            List of ColBERT-based expansions
        """
        expansions = []

        if not self.model or not self.tokenizer:
            return expansions

        try:
            # Tokenize query
            inputs = self.tokenizer(query, return_tensors="pt", padding=True, truncation=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)
                # Get token-level embeddings (simplified ColBERT approach)
                token_embeddings = outputs.last_hidden_state[0]  # [seq_len, hidden_dim]

            # Calculate term importance (simplified)
            seq_len = token_embeddings.shape[0]
            importance_scores = []

            for i in range(seq_len):
                # Simplified importance calculation
                token_emb = token_embeddings[i]
                importance = torch.norm(token_emb).item()
                importance_scores.append((i, importance))

            # Sort by importance
            importance_scores.sort(key=lambda x: x[1], reverse=True)

            # Generate expansions focusing on important terms
            tokens = self.tokenizer.convert_ids_to_tokens(inputs['input_ids'][0])

            # Take top 3 important terms
            for token_idx, score in importance_scores[:3]:
                if score > self.term_importance_threshold:
                    token = tokens[token_idx]
                    if len(token) > 2 and not token.startswith('['):  # Skip special tokens
                        # Create expansion emphasizing this term
                        expansion = f"{query} {token}"
                        expansions.append({
                            "query": expansion,
                            "confidence": min(0.8, score),
                            "method": "colbert",
                            "important_term": token,
                            "importance_score": score
                        })

        except Exception as e:
            logger.warning(f"ColBERT expansion failed: {e}")

        return expansions

    def _classify_query_type(
        self,
        query: str,
        query_profile: Optional[Dict[str, Any]]
    ) -> str:
        """
        Classify query type for template selection.

        Args:
            query: Query string
            query_profile: Query profile

        Returns:
            Query type classification
        """
        query_lower = query.lower()

        # Check for comparison keywords
        if any(word in query_lower for word in ['compare', 'vs', 'versus', 'difference', 'better']):
            return 'comparison'

        # Check for temporal keywords
        if any(word in query_lower for word in ['trend', 'over time', 'historical', 'change', 'year']):
            return 'temporal'

        # Default to financial
        return 'financial'

    def _extract_entities(self, query: str) -> List[str]:
        """
        Extract entity mentions from query.

        Args:
            query: Query string

        Returns:
            List of extracted entities
        """
        import re

        entities = []

        # Company patterns
        companies = re.findall(r'\b[A-Z][a-zA-Z\s&]+(?:Inc|Corp|LLC| Ltd| PLC)\b', query)
        entities.extend(companies)

        # Simple capitalized words
        caps = re.findall(r'\b[A-Z][a-z]+\b', query)
        entities.extend(caps)

        return list(set(entities))  # Remove duplicates

    def _extract_terms(self, query: str) -> List[str]:
        """
        Extract key terms from query.

        Args:
            query: Query string

        Returns:
            List of key terms
        """
        import re

        # Extract financial terms
        financial_terms = [
            'revenue', 'profit', 'income', 'earnings', 'sales', 'margin',
            'growth', 'EBITDA', 'ROE', 'ROI', 'assets', 'liabilities'
        ]

        terms = []
        query_lower = query.lower()

        for term in financial_terms:
            if term in query_lower:
                terms.append(term)

        # Extract other significant words
        words = re.findall(r'\b[a-z]{3,}\b', query_lower)
        stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'had', 'by', 'from', 'they', 'his', 'has', 'have'}

        for word in words:
            if word not in stop_words and len(word) > 2:
                terms.append(word)

        return list(set(terms))[:5]  # Limit to 5 terms

    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Get embeddings for list of texts.

        Args:
            texts: List of text strings

        Returns:
            Embeddings array
        """
        if not self.model or not self.tokenizer:
            return np.array([])

        try:
            inputs = self.tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)
                # Mean pooling
                embeddings = outputs.last_hidden_state.mean(dim=1).cpu().numpy()

            return embeddings

        except Exception as e:
            logger.warning(f"Failed to get embeddings: {e}")
            return np.array([])

    def _get_simple_synonyms(self, term: str) -> List[str]:
        """
        Get simple synonyms for a term (placeholder).

        Args:
            term: Term to find synonyms for

        Returns:
            List of synonyms
        """
        # Simple synonym mapping - in practice would use WordNet or similar
        synonym_map = {
            'revenue': ['income', 'sales', 'earnings'],
            'profit': ['gain', 'earnings', 'income'],
            'growth': ['increase', 'expansion', 'rise'],
            'company': ['firm', 'corporation', 'business'],
            'price': ['cost', 'value', 'rate']
        }

        term_lower = term.lower()
        return synonym_map.get(term_lower, [])

    def _deduplicate_expansions(self, expansions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate expansions and keep highest confidence.

        Args:
            expansions: List of expansions

        Returns:
            Deduplicated expansions
        """
        seen_queries = {}
        unique_expansions = []

        for exp in expansions:
            query = exp['query']
            confidence = exp['confidence']

            if query not in seen_queries or confidence > seen_queries[query]:
                seen_queries[query] = confidence
                unique_expansions.append(exp)

        return unique_expansions

    def update_expansion_params(self, performance_metrics: Dict[str, float]) -> None:
        """
        Update expansion parameters based on performance.

        Args:
            performance_metrics: Performance metrics
        """
        try:
            if 'expansion_success_rate' in performance_metrics:
                success_rate = performance_metrics['expansion_success_rate']
                if success_rate > 0.8:
                    self.max_expansions = min(10, self.max_expansions + 1)
                elif success_rate < 0.5:
                    self.max_expansions = max(3, self.max_expansions - 1)

            logger.info(f"Updated expansion params: max_expansions={self.max_expansions}")

        except Exception as e:
            logger.warning(f"Failed to update expansion params: {e}")

    def get_expansion_stats(self) -> Dict[str, Any]:
        """
        Get expansion strategy statistics.

        Returns:
            Dictionary with expansion statistics
        """
        return {
            'model_name': self.model_name,
            'device': self.device,
            'max_expansions': self.max_expansions,
            'expansion_templates': len(self.expansion_templates),
            'model_loaded': self.model is not None
        }







