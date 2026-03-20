"""Helpers for building frontend-facing response payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models import Document, Source, StructuredBlock, ToolResult
from app.routing import QueryRoute
from app.routing.complexity_analyzer import ComplexityScore


class AnswerAssembler:
    """Build stable, frontend-compatible response payloads."""

    def __init__(self, answer_confidence_scorer: Any, citation_validator: Any) -> None:
        self.answer_confidence_scorer = answer_confidence_scorer
        self.citation_validator = citation_validator

    def build_sources(self, tool_results: List[ToolResult]) -> List[Source]:
        sources: List[Source] = []
        seen: set[tuple[str, str, Optional[str]]] = set()
        for result in tool_results:
            payload = result.data
            if payload.get("source"):
                key = (payload["source"], payload.get("timestamp", datetime.utcnow().isoformat()), None)
                if key not in seen:
                    sources.append(Source(name=key[0], timestamp=key[1]))
                    seen.add(key)
            for item in payload.get("results", []):
                key = (
                    item.get("source") or result.tool,
                    item.get("published") or payload.get("timestamp") or datetime.utcnow().isoformat(),
                    item.get("url"),
                )
                if key not in seen:
                    sources.append(Source(name=key[0], timestamp=key[1], url=key[2]))
                    seen.add(key)
            for doc in payload.get("documents", []):
                key = (doc.get("source", result.tool), payload.get("timestamp", datetime.utcnow().isoformat()), None)
                if key not in seen:
                    sources.append(Source(name=key[0], timestamp=key[1]))
                    seen.add(key)
        return sources

    @staticmethod
    def strip_frontmatter(text: str) -> str:
        content = text.strip()
        if content.startswith("---"):
            end = content.find("---", 3)
            if end != -1:
                return content[end + 3 :].strip()
        return content

    def order_blocks(self, blocks: List[StructuredBlock], route: QueryRoute) -> List[StructuredBlock]:
        ordered_blocks: List[StructuredBlock] = []
        ordered_blocks.extend([block for block in blocks if block.type == "chart"])
        ordered_blocks.extend([block for block in blocks if block.type == "key_metrics"])
        ordered_blocks.extend([block for block in blocks if block.type == "table"])
        ordered_blocks.extend([block for block in blocks if block.type == "analysis"])
        if route.query_type.value in {"knowledge", "hybrid"}:
            ordered_blocks.extend([block for block in blocks if block.type == "quote"])
        ordered_blocks.extend([block for block in blocks if block.type in {"bullets", "news"}])
        ordered_blocks.extend([block for block in blocks if block.type == "warning"])
        return ordered_blocks

    def build_done_data(
        self,
        *,
        query: str,
        route: QueryRoute,
        tool_results: List[ToolResult],
        blocks: List[StructuredBlock],
        validation: Dict[str, Any],
        llm_used: bool,
        final_answer_text: str,
        complexity_score: ComplexityScore,
        disclaimer: str,
    ) -> Dict[str, Any]:
        knowledge_result = next(
            (result.data for result in tool_results if result.tool == "search_knowledge" and result.status == "success"),
            None,
        )

        rag_citations: List[Dict[str, Any]] = []
        if knowledge_result and knowledge_result.get("documents"):
            method_used = knowledge_result.get("method_used", "unknown")
            for index, doc in enumerate(knowledge_result["documents"][:5]):
                rag_citations.append(
                    {
                        "id": index + 1,
                        "source": doc.get("source", "unknown"),
                        "chunk_id": doc.get("chunk_id"),
                        "score": round(float(doc.get("score", 0)), 2),
                        "preview": self.strip_frontmatter(doc.get("content", ""))[:200].strip(),
                        "method": method_used,
                    }
                )

        tool_latencies = [{"tool": result.tool, "latency_ms": result.latency_ms or 0} for result in tool_results]
        knowledge_documents = (
            [Document(**doc) for doc in knowledge_result.get("documents", [])]
            if knowledge_result and knowledge_result.get("documents")
            else []
        )
        confidence_breakdown = (
            self.answer_confidence_scorer.calculate_confidence_breakdown(
                answer=final_answer_text,
                documents=knowledge_documents,
                query=query,
            )
            if final_answer_text and knowledge_documents
            else None
        )
        citation_validation = (
            self.citation_validator.validate(final_answer_text, len(knowledge_documents))
            if final_answer_text and knowledge_documents
            else None
        )

        return {
            "confidence": {"level": validation["level"], "score": validation["confidence"]},
            "blocks": [block.model_dump() for block in blocks],
            "route": {"type": route.query_type.value, "symbols": route.symbols, "range_key": route.range_key},
            "llm_used": llm_used,
            "disclaimer": disclaimer,
            "rag_citations": rag_citations,
            "tool_latencies": tool_latencies,
            "confidence_breakdown": confidence_breakdown,
            "citation_validation": citation_validation,
            "query_complexity": {
                "level": complexity_score.level,
                "score": complexity_score.score,
                "rag_top_k": complexity_score.rag_top_k,
                "reasoning": complexity_score.reasoning,
            },
        }
