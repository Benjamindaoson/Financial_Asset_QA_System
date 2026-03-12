from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


class SemanticChunker:
    """Semantic chunking helper that only uses a local embedding model."""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        candidate = Path(model_name)
        if not candidate.exists():
            raise RuntimeError("Semantic chunker requires a local model path")
        self.model = SentenceTransformer(str(candidate), local_files_only=True)

    def chunk(self, text: str, threshold: float = 0.8) -> list[str]:
        sentences = [sentence.strip() for sentence in text.split("。") if sentence.strip()]
        if not sentences:
            return []

        embeddings = self.model.encode(sentences)
        chunks = []
        current_chunk = [sentences[0]]

        for i in range(len(sentences) - 1):
            sim = self._cosine_similarity(embeddings[i], embeddings[i + 1])
            if sim > threshold:
                current_chunk.append(sentences[i + 1])
            else:
                chunks.append("。".join(current_chunk) + "。")
                current_chunk = [sentences[i + 1]]

        chunks.append("。".join(current_chunk) + "。")
        return chunks

    def _cosine_similarity(self, v1, v2):
        return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
