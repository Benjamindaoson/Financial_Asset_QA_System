"""
HyDE (Hypothetical Document Embeddings) generator.
Generates a hypothetical answer to the query, whose embedding is used for retrieval.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class HyDEGenerator:
    """Generate hypothetical answer documents for HyDE retrieval."""

    PROMPT = "请用1-2句话简要回答以下问题，直接给出答案内容，不要重复问题：\n\n{query}"

    def __init__(self, model: Optional[str] = None):
        self.model = model or settings.HYDE_MODEL
        self._llm_client = None

    def _get_client(self):
        if self._llm_client is None:
            from app.core.llm_client import LLMClient
            self._llm_client = LLMClient(model=self.model)
        return self._llm_client

    async def generate(self, query: str) -> Optional[str]:
        """
        Generate a hypothetical answer for the query.

        Args:
            query: User query

        Returns:
            Hypothetical answer text, or None if generation fails
        """
        if not query or not query.strip():
            return None
        try:
            client = self._get_client()
            messages = [
                {"role": "user", "content": self.PROMPT.format(query=query.strip())},
            ]
            answer = await client.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=150,
                timeout=settings.HYDE_TIMEOUT,
            )
            if answer and answer.strip():
                return answer.strip()
        except Exception as e:
            logger.warning("[HyDE] Generation failed: %s", e)
        return None
