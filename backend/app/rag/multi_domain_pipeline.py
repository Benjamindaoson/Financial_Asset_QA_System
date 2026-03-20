"""Multi-domain RAG pipeline with per-domain ChromaDB collections."""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

from app.models import KnowledgeResult
from app.rag.domain_router import DOMAINS, DomainRouter
from app.rag.hybrid_pipeline import HybridRAGPipeline
from app.rag.hyde_generator import HyDEGenerator

logger = logging.getLogger(__name__)

# Adjacent domains used for fallback when a domain's result is thin
_FALLBACK_ORDER: Dict[str, list] = {
    "equity":       ["macro", "risk", "general"],
    "macro":        ["fixed_income", "equity", "general"],
    "fixed_income": ["macro", "risk", "general"],
    "risk":         ["equity", "macro", "general"],
    "general":      ["equity", "macro", "fixed_income", "risk"],
}


class MultiDomainRAGPipeline:
    """Manages per-domain ChromaDB collections and BM25 indexes.

    Query flow:
      1. HyDE generates a hypothetical answer (document-language signal).
      2. DomainRouter selects the best domain using HyDE text + raw query.
      3. Only the target domain's HybridRAGPipeline is searched.
      4. If fewer than 2 docs are returned, adjacent domains are tried.

    Returns (KnowledgeResult, domain_name) tuples — domain is kept out of the
    Pydantic model to avoid schema mutation.
    """

    def __init__(self) -> None:
        self.domain_router = DomainRouter()
        self.hyde_generator = HyDEGenerator()
        self.pipelines: Dict[str, HybridRAGPipeline] = {}
        self._init_domain_pipelines()

    def _init_domain_pipelines(self) -> None:
        """Create one HybridRAGPipeline per domain with isolated collections."""
        for domain in DOMAINS:
            collection_name = f"knowledge_{domain}"
            try:
                self.pipelines[domain] = HybridRAGPipeline(
                    collection_name=collection_name
                )
                logger.info(
                    "[MultiDomain] Initialized pipeline for domain '%s' (collection: %s)",
                    domain, collection_name,
                )
            except Exception as exc:
                logger.warning(
                    "[MultiDomain] Failed to init pipeline for domain '%s': %s",
                    domain, exc,
                )

    async def search(self, query: str, top_k: int = 5) -> Tuple[KnowledgeResult, str]:
        """Search best-matching domain; fall back to adjacent domains if sparse.

        Returns:
            (KnowledgeResult, domain_name) — domain is the collection that
            produced the result (primary or fallback).
        """
        # Step 1: HyDE hypothesis (best-effort; failures are non-fatal)
        hyde_text: Optional[str] = None
        try:
            hyde_text = await self.hyde_generator.generate(query)
        except Exception as exc:
            logger.warning("[MultiDomain] HyDE failed, routing on raw query: %s", exc)

        # Step 2: domain routing
        domain = self.domain_router.route(query, hyde_text)
        logger.info("[MultiDomain] Query routed to domain '%s'", domain)

        # Step 3: primary search
        result = await self._search_domain(domain, query, top_k)
        if result and len(result.documents) >= 2:
            return result, domain

        # Step 4: fallback to adjacent domains
        fb_result, fb_domain = await self._fallback_search(
            query, domain, top_k, primary_result=result
        )
        if fb_result:
            return fb_result, fb_domain

        return KnowledgeResult(documents=[], total_found=0), domain

    async def _search_domain(
        self, domain: str, query: str, top_k: int
    ) -> Optional[KnowledgeResult]:
        pipeline = self.pipelines.get(domain)
        if pipeline is None:
            return None
        try:
            return await pipeline.search(query, top_k)
        except Exception as exc:
            logger.warning("[MultiDomain] Search failed in domain '%s': %s", domain, exc)
            return None

    async def _fallback_search(
        self,
        query: str,
        primary_domain: str,
        top_k: int,
        primary_result: Optional[KnowledgeResult],
    ) -> Tuple[Optional[KnowledgeResult], str]:
        """Try adjacent domains in priority order; return first adequate result."""
        fallback_domains = _FALLBACK_ORDER.get(primary_domain, [])
        for fallback_domain in fallback_domains:
            result = await self._search_domain(fallback_domain, query, top_k)
            if result and result.documents:
                logger.info(
                    "[MultiDomain] Fallback hit domain '%s' with %d docs",
                    fallback_domain, len(result.documents),
                )
                return result, fallback_domain
        # Return primary result even if sparse rather than nothing
        return primary_result, primary_domain
