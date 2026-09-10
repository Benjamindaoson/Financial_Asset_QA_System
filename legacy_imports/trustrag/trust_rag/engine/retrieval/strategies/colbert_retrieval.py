"""
ColBERT Retrieval Strategy for GraphRAG.

This module implements ColBERT-based retrieval for fine-grained
semantic matching and query term importance assessment.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel

logger = logging.getLogger(__name__)


class ColBERTRetrievalStrategy:
    """
    ColBERT-based retrieval strategy for GraphRAG.

    Uses contextualized late interaction for fine-grained
    query-document matching and term importance scoring.
    """

    def __init__(
        self,
        model_name: str = "colbert-ir/colbertv2.0",
        device: str = "auto",
        max_query_length: int = 32,
        max_doc_length: int = 256
    ):
        """
        Initialize ColBERT retrieval strategy.

        Args:
            model_name: ColBERT model name
            device: Device to run model on
            max_query_length: Maximum query token length
            max_doc_length: Maximum document token length
        """
        self.device = self._setup_device(device)
        self.model_name = model_name
        self.max_query_length = max_query_length
        self.max_doc_length = max_doc_length

        # Initialize model and tokenizer
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name).to(self.device)
            self.model.eval()
            logger.info(f"ColBERT model loaded: {model_name}")
        except Exception as e:
            logger.warning(f"Failed to load ColBERT model {model_name}: {e}")
            # Fallback to simpler model
            self._load_fallback_model()
            self.model = None

        # ColBERT parameters
        self.dim = 128  # ColBERT embedding dimension
        self.similarity_function = "cosine"  # cosine or l2

        # Pre-computed document embeddings (would be loaded from index)
        self.doc_embeddings = {}  # doc_id -> embeddings dict

    def _setup_device(self, device: str) -> str:
        """Setup compute device."""
        if device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        return device

    def _load_fallback_model(self) -> None:
        """Load fallback model if ColBERT not available."""
        try:
            self.tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
            self.model = AutoModel.from_pretrained("bert-base-uncased").to(self.device)
            self.model.eval()
            logger.info("Loaded fallback BERT model")
        except Exception as e:
            logger.warning(f"Failed to load fallback model: {e}")
            self.model = None
            self.tokenizer = None

    def encode_query(self, query: str) -> Dict[str, Any]:
        """
        Encode query using ColBERT approach.

        Args:
            query: Query string

        Returns:
            Query encoding with token-level embeddings
        """
        if not self.model or not self.tokenizer:
            return {"embeddings": np.array([]), "tokens": [], "mask": np.array([])}

        try:
            # Tokenize query
            inputs = self.tokenizer(
                query,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_query_length
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)

            # Get token-level embeddings (ColBERT style)
            embeddings = outputs.last_hidden_state[0].cpu().numpy()  # [seq_len, hidden_dim]

            # Convert token IDs to tokens
            tokens = self.tokenizer.convert_ids_to_tokens(inputs['input_ids'][0])

            # Attention mask
            mask = inputs['attention_mask'][0].cpu().numpy()

            return {
                "embeddings": embeddings,
                "tokens": tokens,
                "mask": mask,
                "query": query
            }

        except Exception as e:
            logger.error(f"Failed to encode query: {e}")
            return {"embeddings": np.array([]), "tokens": [], "mask": np.array([])}

    def encode_document(self, doc_text: str, doc_id: str = None) -> Dict[str, Any]:
        """
        Encode document using ColBERT approach.

        Args:
            doc_text: Document text
            doc_id: Document identifier

        Returns:
            Document encoding with token-level embeddings
        """
        if not self.model or not self.tokenizer:
            return {"embeddings": np.array([]), "tokens": [], "mask": np.array([])}

        try:
            # Tokenize document
            inputs = self.tokenizer(
                doc_text,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.max_doc_length
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model(**inputs)

            # Get token-level embeddings
            embeddings = outputs.last_hidden_state[0].cpu().numpy()

            # Convert token IDs to tokens
            tokens = self.tokenizer.convert_ids_to_tokens(inputs['input_ids'][0])

            # Attention mask
            mask = inputs['attention_mask'][0].cpu().numpy()

            result = {
                "embeddings": embeddings,
                "tokens": tokens,
                "mask": mask,
                "doc_text": doc_text,
                "doc_id": doc_id
            }

            # Cache embeddings for retrieval
            if doc_id:
                self.doc_embeddings[doc_id] = result

            return result

        except Exception as e:
            logger.error(f"Failed to encode document: {e}")
            return {"embeddings": np.array([]), "tokens": [], "mask": np.array([])}

    def compute_similarity(
        self,
        query_encoding: Dict[str, Any],
        doc_encoding: Dict[str, Any]
    ) -> float:
        """
        Compute ColBERT similarity between query and document.

        Args:
            query_encoding: Query encoding from encode_query
            doc_encoding: Document encoding from encode_document

        Returns:
            Similarity score
        """
        try:
            query_emb = query_encoding["embeddings"]
            doc_emb = doc_encoding["embeddings"]
            query_mask = query_encoding["mask"]
            doc_mask = doc_encoding["mask"]

            if len(query_emb) == 0 or len(doc_emb) == 0:
                return 0.0

            # ColBERT MaxSim operation
            # For each query token, find max similarity with any doc token
            similarities = []

            for i, query_token_emb in enumerate(query_emb):
                if query_mask[i] == 0:  # Skip padding
                    continue

                # Compute similarities with all doc tokens
                if self.similarity_function == "cosine":
                    # Cosine similarity
                    query_norm = np.linalg.norm(query_token_emb)
                    doc_norms = np.linalg.norm(doc_emb, axis=1)

                    if query_norm > 0 and np.any(doc_norms > 0):
                        dot_products = np.dot(doc_emb, query_token_emb)
                        token_similarities = dot_products / (doc_norms * query_norm)
                    else:
                        token_similarities = np.zeros(len(doc_emb))
                else:
                    # L2 distance (negative for similarity)
                    token_similarities = -np.linalg.norm(
                        doc_emb - query_token_emb, axis=1
                    )

                # Only consider non-padding doc tokens
                valid_similarities = token_similarities[doc_mask == 1]

                if len(valid_similarities) > 0:
                    # Max similarity for this query token
                    max_sim = np.max(valid_similarities)
                    similarities.append(max_sim)

            if not similarities:
                return 0.0

            # Average of max similarities (ColBERT score)
            score = np.mean(similarities)

            return float(score)

        except Exception as e:
            logger.error(f"Failed to compute similarity: {e}")
            return 0.0

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        candidate_docs: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents using ColBERT.

        Args:
            query: Query string
            top_k: Number of results to return
            candidate_docs: List of candidate document IDs to search

        Returns:
            List of retrieval results with scores
        """
        results = []

        try:
            # Encode query
            query_encoding = self.encode_query(query)

            if len(query_encoding["embeddings"]) == 0:
                return results

            # Determine documents to search
            if candidate_docs is None:
                candidate_docs = list(self.doc_embeddings.keys())

            # Score each candidate document
            doc_scores = []

            for doc_id in candidate_docs:
                if doc_id in self.doc_embeddings:
                    doc_encoding = self.doc_embeddings[doc_id]
                    score = self.compute_similarity(query_encoding, doc_encoding)

                    doc_scores.append({
                        "doc_id": doc_id,
                        "score": score,
                        "doc_encoding": doc_encoding
                    })

            # Sort by score and return top-k
            doc_scores.sort(key=lambda x: x["score"], reverse=True)

            for i, doc_score in enumerate(doc_scores[:top_k]):
                result = {
                    "doc_id": doc_score["doc_id"],
                    "score": doc_score["score"],
                    "rank": i + 1,
                    "query": query,
                    "retrieval_method": "colbert"
                }
                results.append(result)

        except Exception as e:
            logger.error(f"ColBERT retrieval failed: {e}")

        return results

    def get_term_importance(
        self,
        query: str,
        document: str
    ) -> Dict[str, float]:
        """
        Get term importance scores for query terms in document context.

        Args:
            query: Query string
            document: Document text

        Returns:
            Dictionary mapping query terms to importance scores
        """
        term_importance = {}

        try:
            # Encode query and document
            query_encoding = self.encode_query(query)
            doc_encoding = self.encode_document(document)

            if len(query_encoding["embeddings"]) == 0 or len(doc_encoding["embeddings"]) == 0:
                return term_importance

            query_tokens = query_encoding["tokens"]
            query_mask = query_encoding["mask"]

            # For each query token, compute importance based on max similarity
            for i, token in enumerate(query_tokens):
                if query_mask[i] == 0 or token.startswith('['):  # Skip special tokens
                    continue

                query_token_emb = query_encoding["embeddings"][i]

                # Compute similarities with document tokens
                doc_emb = doc_encoding["embeddings"]
                doc_mask = doc_encoding["mask"]

                if self.similarity_function == "cosine":
                    query_norm = np.linalg.norm(query_token_emb)
                    doc_norms = np.linalg.norm(doc_emb, axis=1)

                    if query_norm > 0 and np.any(doc_norms > 0):
                        dot_products = np.dot(doc_emb, query_token_emb)
                        similarities = dot_products / (doc_norms * query_norm)
                    else:
                        similarities = np.zeros(len(doc_emb))
                else:
                    similarities = -np.linalg.norm(doc_emb - query_token_emb, axis=1)

                # Only consider valid document tokens
                valid_similarities = similarities[doc_mask == 1]

                if len(valid_similarities) > 0:
                    max_similarity = np.max(valid_similarities)
                    term_importance[token] = float(max_similarity)

        except Exception as e:
            logger.error(f"Failed to compute term importance: {e}")

        return term_importance

    def batch_encode_documents(self, documents: List[Tuple[str, str]]) -> Dict[str, Dict[str, Any]]:
        """
        Batch encode multiple documents.

        Args:
            documents: List of (doc_id, doc_text) tuples

        Returns:
            Dictionary mapping doc_id to encodings
        """
        encodings = {}

        for doc_id, doc_text in documents:
            try:
                encoding = self.encode_document(doc_text, doc_id)
                encodings[doc_id] = encoding
            except Exception as e:
                logger.warning(f"Failed to encode document {doc_id}: {e}")

        return encodings

    def update_document_index(self, new_documents: Dict[str, Dict[str, Any]]) -> None:
        """
        Update the document index with new encodings.

        Args:
            new_documents: Dictionary of new document encodings
        """
        self.doc_embeddings.update(new_documents)
        logger.info(f"Updated document index with {len(new_documents)} new documents")

    def clear_index(self) -> None:
        """Clear the document index."""
        self.doc_embeddings.clear()
        logger.info("Document index cleared")

    def get_index_stats(self) -> Dict[str, Any]:
        """
        Get index statistics.

        Returns:
            Dictionary with index statistics
        """
        total_tokens = sum(
            len(encoding.get("tokens", []))
            for encoding in self.doc_embeddings.values()
        )

        return {
            "total_documents": len(self.doc_embeddings),
            "total_tokens": total_tokens,
            "model_name": self.model_name,
            "embedding_dim": self.dim,
            "device": self.device,
            "similarity_function": self.similarity_function
        }

    def save_index(self, path: str) -> None:
        """
        Save document index to disk.

        Args:
            path: Path to save index
        """
        try:
            # Convert numpy arrays to lists for JSON serialization
            serializable_index = {}
            for doc_id, encoding in self.doc_embeddings.items():
                serializable_encoding = {}
                for key, value in encoding.items():
                    if isinstance(value, np.ndarray):
                        serializable_encoding[key] = value.tolist()
                    else:
                        serializable_encoding[key] = value
                serializable_index[doc_id] = serializable_encoding

            import json
            with open(path, 'w') as f:
                json.dump(serializable_index, f)

            logger.info(f"Saved index to {path}")

        except Exception as e:
            logger.error(f"Failed to save index: {e}")

    def load_index(self, path: str) -> None:
        """
        Load document index from disk.

        Args:
            path: Path to load index from
        """
        try:
            import json
            with open(path, 'r') as f:
                loaded_index = json.load(f)

            # Convert lists back to numpy arrays
            self.doc_embeddings = {}
            for doc_id, encoding in loaded_index.items():
                restored_encoding = {}
                for key, value in encoding.items():
                    if key == "embeddings" and isinstance(value, list):
                        restored_encoding[key] = np.array(value)
                    elif key == "mask" and isinstance(value, list):
                        restored_encoding[key] = np.array(value)
                    else:
                        restored_encoding[key] = value
                self.doc_embeddings[doc_id] = restored_encoding

            logger.info(f"Loaded index from {path} with {len(self.doc_embeddings)} documents")

        except Exception as e:
            logger.error(f"Failed to load index: {e}")







