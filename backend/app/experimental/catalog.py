"""Explicit catalog for production and experimental backend modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class ModuleClassification:
    """Classify backend modules by runtime status."""

    module: str
    path: str
    layer: str
    status: str
    notes: str

    def to_dict(self) -> dict:
        return asdict(self)


_MODULES: tuple[ModuleClassification, ...] = (
    ModuleClassification(
        module="agent.core",
        path="backend/app/agent/core.py",
        layer="agent",
        status="production",
        notes="Primary orchestration chain used by /api/chat.",
    ),
    ModuleClassification(
        module="agent.route_planner",
        path="backend/app/agent/route_planner.py",
        layer="agent",
        status="production",
        notes="Production route analysis and tool planning.",
    ),
    ModuleClassification(
        module="agent.tool_executor",
        path="backend/app/agent/tool_executor.py",
        layer="agent",
        status="production",
        notes="Production tool execution and retrieval fallback layer.",
    ),
    ModuleClassification(
        module="agent.answer_assembler",
        path="backend/app/agent/answer_assembler.py",
        layer="agent",
        status="production",
        notes="Single source of frontend-facing done payload assembly.",
    ),
    ModuleClassification(
        module="routing.router",
        path="backend/app/routing/router.py",
        layer="routing",
        status="production",
        notes="Rule-based production router.",
    ),
    ModuleClassification(
        module="routing.complexity_analyzer",
        path="backend/app/routing/complexity_analyzer.py",
        layer="routing",
        status="production",
        notes="Production query complexity scoring.",
    ),
    ModuleClassification(
        module="rag.hybrid_pipeline",
        path="backend/app/rag/hybrid_pipeline.py",
        layer="rag",
        status="production",
        notes="Primary retrieval pipeline using vector + BM25 + reranking.",
    ),
    ModuleClassification(
        module="rag.dynamic_topk",
        path="backend/app/rag/dynamic_topk.py",
        layer="rag",
        status="production",
        notes="Adaptive retrieval depth used by the production hybrid pipeline.",
    ),
    ModuleClassification(
        module="rag.multi_query_generator",
        path="backend/app/rag/multi_query_generator.py",
        layer="rag",
        status="production",
        notes="Production query expansion helper.",
    ),
    ModuleClassification(
        module="rag.mmr_reranker",
        path="backend/app/rag/mmr_reranker.py",
        layer="rag",
        status="production",
        notes="Production diversity reranking helper.",
    ),
    ModuleClassification(
        module="rag.query_processor",
        path="backend/app/rag/query_processor.py",
        layer="rag",
        status="production",
        notes="Production query cleanup and synonym expansion.",
    ),
    ModuleClassification(
        module="rag.confidence_scorer",
        path="backend/app/rag/confidence_scorer.py",
        layer="rag",
        status="production",
        notes="Production answer confidence breakdown helper.",
    ),
    ModuleClassification(
        module="rag.citation_validator",
        path="backend/app/rag/citation_validator.py",
        layer="rag",
        status="production",
        notes="Production citation validation helper.",
    ),
    ModuleClassification(
        module="routing.hybrid_router",
        path="backend/app/routing/hybrid_router.py",
        layer="routing",
        status="experimental",
        notes="Alternative routing path not used by AgentCore.",
    ),
    ModuleClassification(
        module="routing.llm_router",
        path="backend/app/routing/llm_router.py",
        layer="routing",
        status="experimental",
        notes="LLM-assisted router retained for experiments and legacy tests.",
    ),
    ModuleClassification(
        module="routing.data_source_router",
        path="backend/app/routing/data_source_router.py",
        layer="routing",
        status="experimental",
        notes="Data-source selection router not part of the production chain.",
    ),
    ModuleClassification(
        module="rag.enhanced_data_pipeline",
        path="backend/app/rag/enhanced_data_pipeline.py",
        layer="rag",
        status="experimental",
        notes="Alternative data pipeline retained for experimentation.",
    ),
    ModuleClassification(
        module="rag.enhanced_document_parser",
        path="backend/app/rag/enhanced_document_parser.py",
        layer="rag",
        status="experimental",
        notes="Experimental parser not used by the production ingest path.",
    ),
    ModuleClassification(
        module="rag.enhanced_pipeline",
        path="backend/app/rag/enhanced_pipeline.py",
        layer="rag",
        status="experimental",
        notes="Legacy enhanced retrieval pipeline outside the main chain.",
    ),
    ModuleClassification(
        module="rag.enhanced_rag_pipeline",
        path="backend/app/rag/enhanced_rag_pipeline.py",
        layer="rag",
        status="experimental",
        notes="Extended hybrid pipeline with fact-verification hooks.",
    ),
    ModuleClassification(
        module="rag.fact_verifier",
        path="backend/app/rag/fact_verifier.py",
        layer="rag",
        status="experimental",
        notes="Fact verification subsystem not wired into production answers.",
    ),
    ModuleClassification(
        module="rag.grounded_pipeline",
        path="backend/app/rag/grounded_pipeline.py",
        layer="rag",
        status="experimental",
        notes="Grounded response pipeline retained as a research branch.",
    ),
    ModuleClassification(
        module="rag.hybrid_retrieval",
        path="backend/app/rag/hybrid_retrieval.py",
        layer="rag",
        status="experimental",
        notes="Standalone retrieval implementation superseded by hybrid_pipeline.",
    ),
    ModuleClassification(
        module="rag.ultimate_pipeline",
        path="backend/app/rag/ultimate_pipeline.py",
        layer="rag",
        status="experimental",
        notes="Alternative end-to-end branch outside the production chain.",
    ),
)


def _filter_by_status(status: str) -> List[ModuleClassification]:
    return [module for module in _MODULES if module.status == status]


def get_production_modules() -> List[ModuleClassification]:
    """Return modules that define the supported production path."""

    return _filter_by_status("production")


def get_experimental_modules() -> List[ModuleClassification]:
    """Return modules that are intentionally excluded from the production path."""

    return _filter_by_status("experimental")


def iter_all_modules() -> Iterable[ModuleClassification]:
    """Iterate over all known backend module classifications."""

    return iter(_MODULES)
