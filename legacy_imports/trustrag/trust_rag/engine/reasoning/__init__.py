"""
Reasoning Engine for TrustRAG.

Provides advanced reasoning capabilities including:
- Multi-Agent Debate for fact verification
- Beam Search for evidence path optimization
"""
from .multi_agent_debate import (
    AgentRole,
    DebateStatus,
    Argument,
    DebateRound,
    DebateResult,
    DebateAgent,
    ProposerAgent,
    CriticAgent,
    JudgeAgent,
)
from .debate_orchestrator import DebateOrchestrator
from .beam_search_reranker import (
    EvidenceNode,
    EvidencePath,
    BeamSearchConfig,
    BeamSearchReranker,
)

__all__ = [
    # Multi-Agent Debate
    "AgentRole",
    "DebateStatus", 
    "Argument",
    "DebateRound",
    "DebateResult",
    "DebateAgent",
    "ProposerAgent",
    "CriticAgent",
    "JudgeAgent",
    "DebateOrchestrator",
    # Beam Search
    "EvidenceNode",
    "EvidencePath",
    "BeamSearchConfig",
    "BeamSearchReranker",
]

