"""
Debate Orchestrator for Multi-Agent Debate System.

Orchestrates the debate between Proposer, Critic, and Judge agents
to verify facts and reduce hallucination.
"""
import logging
from typing import List, Any, Optional

from trust_rag.core.observability.tracing import get_tracer

from .multi_agent_debate import (
    DebateResult, DebateRound, DebateStatus, Argument, AgentRole,
    ProposerAgent, CriticAgent, JudgeAgent
)

logger = logging.getLogger(__name__)


class DebateOrchestrator:
    """
    Orchestrates multi-agent debates for fact verification.
    
    This is the main entry point for the debate system.
    """
    
    def __init__(
        self,
        max_rounds: int = 3,
        convergence_threshold: float = 0.8,
        llm_client: Any = None
    ):
        """
        Initialize debate orchestrator.
        
        Args:
            max_rounds: Maximum debate rounds before forcing verdict
            convergence_threshold: Confidence threshold for early termination
            llm_client: Optional LLM client for agent reasoning
        """
        self.max_rounds = max_rounds
        self.convergence_threshold = convergence_threshold
        self.proposer = ProposerAgent(llm_client)
        self.critic = CriticAgent(llm_client)
        self.judge = JudgeAgent(llm_client)
        self.rounds: List[DebateRound] = []
        self.all_arguments: List[Argument] = []
        self.tracer = get_tracer()
        logger.info(f"DebateOrchestrator initialized (max_rounds={max_rounds})")
    
    def run_debate(
        self,
        query: str,
        evidence: List[str],
        initial_answer: Optional[str] = None
    ) -> DebateResult:
        """
        Run a full debate to verify an answer.
        
        Args:
            query: The user's question
            evidence: Retrieved evidence chunks
            initial_answer: Optional initial answer to verify
            
        Returns:
            DebateResult with final verdict
        """
        logger.info(f"Starting debate for query: {query[:50]}...")
        self.rounds = []
        self.all_arguments = []

        with self.tracer.create_child_span(
            "debate.run",
            attributes={
                "debate.query_length": len(query),
                "debate.query_preview": query[:200],
                "debate.evidence_count": len(evidence),
                "debate.max_rounds": self.max_rounds,
                "debate.has_initial_answer": initial_answer is not None
            }
        ) as span:
            for round_num in range(1, self.max_rounds + 1):
                round_result = self._run_single_round(query, evidence, round_num)
                self.rounds.append(round_result)
                if self._should_terminate_early(round_result):
                    span.set_attribute("debate.early_termination_round", round_num)
                    logger.info(f"Early termination at round {round_num}")
                    break

            final_result = self._generate_final_result(query, evidence)
            span.set_attribute("debate.final_verdict", final_result.final_verdict)
            span.set_attribute("debate.final_confidence", final_result.confidence)
            span.set_attribute("debate.rounds_completed", final_result.rounds_completed)
            return final_result
    
    def _run_single_round(
        self,
        query: str,
        evidence: List[str],
        round_num: int
    ) -> DebateRound:
        """Run a single debate round."""
        round_data = DebateRound(round_number=round_num)

        with self.tracer.create_child_span(
            "debate.round",
            attributes={
                "debate.round": round_num,
                "debate.evidence_count": len(evidence)
            }
        ) as span:
            with self.tracer.create_child_span(
                "debate.proposer",
                attributes={"debate.round": round_num}
            ):
                proposer_arg = self.proposer.generate_argument(
                    query, evidence, self.all_arguments, round_num
                )
            round_data.proposer_argument = proposer_arg
            self.all_arguments.append(proposer_arg)

            with self.tracer.create_child_span(
                "debate.critic",
                attributes={"debate.round": round_num}
            ):
                critic_arg = self.critic.generate_argument(
                    query, evidence, self.all_arguments, round_num
                )
            round_data.critic_argument = critic_arg
            self.all_arguments.append(critic_arg)

            with self.tracer.create_child_span(
                "debate.judge",
                attributes={"debate.round": round_num}
            ):
                evaluation = self.judge.evaluate_round(proposer_arg, critic_arg, evidence)
            round_data.judge_evaluation = evaluation

            span.set_attribute("debate.proposer_confidence", proposer_arg.confidence)
            span.set_attribute("debate.critic_confidence", critic_arg.confidence)
            if evaluation:
                span.set_attribute("debate.round_winner", evaluation.get("winner"))
                span.set_attribute("debate.proposer_score", evaluation.get("proposer_score"))
                span.set_attribute("debate.critic_score", evaluation.get("critic_score"))
                span.set_attribute("debate.should_continue", evaluation.get("should_continue"))

            return round_data
    
    def _should_terminate_early(self, round_result: DebateRound) -> bool:
        """Check if debate should terminate early."""
        if not round_result.judge_evaluation:
            return False
        eval_data = round_result.judge_evaluation
        if eval_data["winner"] == "proposer" and eval_data["proposer_score"] > self.convergence_threshold:
            return True
        return not eval_data.get("should_continue", True)
    
    def _generate_final_result(self, query: str, evidence: List[str]) -> DebateResult:
        """Generate final debate result."""
        verdict, confidence, reason = self.judge.make_final_verdict(self.rounds, evidence)
        
        # Get final answer from last proposer argument
        final_answer = ""
        for arg in reversed(self.all_arguments):
            if arg.agent_role == AgentRole.PROPOSER:
                final_answer = arg.claim
                break
        
        # Collect evidence used
        evidence_used = list(set(
            e for arg in self.all_arguments for e in arg.supporting_evidence
        ))
        transcript = [arg.to_dict() for arg in self.all_arguments]
        
        # Determine status
        if verdict in ["VERIFIED", "REFUTED"]:
            status = DebateStatus.CONSENSUS_REACHED
        elif len(self.rounds) >= self.max_rounds:
            status = DebateStatus.MAX_ROUNDS_EXCEEDED
        else:
            status = DebateStatus.DEADLOCK
        
        return DebateResult(
            status=status,
            final_verdict=verdict,
            final_answer=final_answer,
            confidence=confidence,
            rounds_completed=len(self.rounds),
            consensus_reason=reason,
            evidence_used=evidence_used,
            debate_transcript=transcript
        )
