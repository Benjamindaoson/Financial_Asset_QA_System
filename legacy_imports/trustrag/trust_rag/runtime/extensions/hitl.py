"""
Human-In-The-Loop (HITL) Workflow for TrustRAG.
Enables human oversight and intervention in automated processes.
"""
import logging
import json
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class HITLDecision(Enum):
    """Human decision outcomes."""
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    ESCALATE = "escalate"


class HITLPriority(Enum):
    """Priority levels for HITL requests."""
    LOW = "low"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class HITLRequest:
    """Human-in-the-loop request."""
    request_id: str
    priority: HITLPriority
    request_type: str  # "answer_review", "evidence_validation", "policy_override"
    context: Dict[str, Any]
    options: List[str] = field(default_factory=list)
    timeout_seconds: int = 3600  # 1 hour default
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    decision: Optional[HITLDecision] = None
    decision_data: Optional[Dict[str, Any]] = None
    assigned_to: Optional[str] = None


@dataclass
class HITLWorkflow:
    """HITL workflow configuration."""
    name: str
    trigger_conditions: List[Callable[[Dict[str, Any]], bool]]
    request_builder: Callable[[Dict[str, Any]], HITLRequest]
    decision_handler: Callable[[HITLRequest], Any]


class HITLManager:
    """
    Production Human-In-The-Loop manager.
    Handles escalation, approval workflows, and human oversight.
    """

    def __init__(self):
        self.workflows: Dict[str, HITLWorkflow] = {}
        self.pending_requests: Dict[str, HITLRequest] = {}
        self.completed_requests: Dict[str, HITLRequest] = {}
        self._lock = threading.Lock()

        # Register default workflows
        self._register_default_workflows()

    def _register_default_workflows(self):
        """Register production HITL workflows."""

        # Low confidence answer review
        def low_confidence_trigger(context: Dict[str, Any]) -> bool:
            confidence = context.get("confidence", 1.0)
            return confidence < 0.7

        def build_answer_review_request(context: Dict[str, Any]) -> HITLRequest:
            return HITLRequest(
                request_id=f"review_{int(time.time())}_{context.get('query', '')[:10]}",
                priority=HITLPriority.HIGH if context.get("confidence", 1.0) < 0.5 else HITLPriority.LOW,
                request_type="answer_review",
                context=context,
                options=["approve", "reject", "modify"],
                timeout_seconds=1800  # 30 minutes
            )

        def handle_answer_review_decision(request: HITLRequest) -> Dict[str, Any]:
            if request.decision == HITLDecision.APPROVE:
                return {"action": "proceed", "answer": request.context.get("answer")}
            elif request.decision == HITLDecision.REJECT:
                return {"action": "reject", "reason": request.decision_data.get("reason", "Human rejected")}
            elif request.decision == HITLDecision.MODIFY:
                return {
                    "action": "modify",
                    "modified_answer": request.decision_data.get("modified_answer"),
                    "modifications": request.decision_data.get("modifications", [])
                }
            return {"action": "escalate"}

        self.register_workflow(HITLWorkflow(
            name="low_confidence_answer_review",
            trigger_conditions=[low_confidence_trigger],
            request_builder=build_answer_review_request,
            decision_handler=handle_answer_review_decision
        ))

        # Evidence conflict resolution
        def evidence_conflict_trigger(context: Dict[str, Any]) -> bool:
            return context.get("has_evidence_conflicts", False)

        def build_conflict_resolution_request(context: Dict[str, Any]) -> HITLRequest:
            return HITLRequest(
                request_id=f"conflict_{int(time.time())}",
                priority=HITLPriority.CRITICAL,
                request_type="evidence_validation",
                context=context,
                options=["resolve_conflict", "reject_answer", "escalate"],
                timeout_seconds=3600  # 1 hour
            )

        def handle_conflict_resolution_decision(request: HITLRequest) -> Dict[str, Any]:
            if request.decision_data and request.decision_data.get("resolved_answer"):
                return {
                    "action": "resolve",
                    "resolved_answer": request.decision_data["resolved_answer"],
                    "resolution_notes": request.decision_data.get("notes", "")
                }
            return {"action": "reject", "reason": "Unable to resolve evidence conflicts"}

        self.register_workflow(HITLWorkflow(
            name="evidence_conflict_resolution",
            trigger_conditions=[evidence_conflict_trigger],
            request_builder=build_conflict_resolution_request,
            decision_handler=handle_conflict_resolution_decision
        ))

    def register_workflow(self, workflow: HITLWorkflow):
        """Register a HITL workflow."""
        self.workflows[workflow.name] = workflow
        logger.info(f"Registered HITL workflow: {workflow.name}")

    def evaluate_triggers(self, context: Dict[str, Any]) -> List[HITLRequest]:
        """
        Evaluate all workflows and create HITL requests if triggers fire.

        Args:
            context: Context data to evaluate triggers against

        Returns:
            List of HITL requests that should be created
        """
        requests = []

        for workflow in self.workflows.values():
            for trigger in workflow.trigger_conditions:
                try:
                    if trigger(context):
                        request = workflow.request_builder(context)
                        requests.append(request)
                        logger.info(f"HITL trigger fired for workflow {workflow.name}: {request.request_id}")
                        break  # Only create one request per workflow
                except Exception as e:
                    logger.error(f"Error evaluating trigger for workflow {workflow.name}: {e}")

        return requests

    def submit_request(self, request: HITLRequest) -> str:
        """
        Submit a HITL request for human processing.

        Args:
            request: HITL request to submit

        Returns:
            Request ID
        """
        with self._lock:
            self.pending_requests[request.request_id] = request

        logger.info(f"Submitted HITL request: {request.request_id} (priority: {request.priority.value})")

        # In production, this would:
        # 1. Send notification to human operators
        # 2. Update dashboard/UI
        # 3. Set up timeout handling

        return request.request_id

    def resolve_request(self, request_id: str, decision: HITLDecision,
                       decision_data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Resolve a HITL request with human decision.

        Args:
            request_id: Request to resolve
            decision: Human decision
            decision_data: Additional decision data

        Returns:
            Workflow execution result
        """
        with self._lock:
            if request_id not in self.pending_requests:
                logger.warning(f"HITL request {request_id} not found or already resolved")
                return None

            request = self.pending_requests[request_id]
            request.resolved_at = time.time()
            request.decision = decision
            request.decision_data = decision_data or {}

            # Move to completed
            self.completed_requests[request_id] = request
            del self.pending_requests[request_id]

        logger.info(f"Resolved HITL request {request_id}: {decision.value}")

        # Execute workflow decision handler
        workflow_name = self._find_workflow_for_request(request)
        if workflow_name and workflow_name in self.workflows:
            workflow = self.workflows[workflow_name]
            try:
                result = workflow.decision_handler(request)
                return result
            except Exception as e:
                logger.error(f"Error executing workflow {workflow_name} for request {request_id}: {e}")
                return {"action": "error", "error": str(e)}

        return {"action": "completed"}

    def get_pending_requests(self, priority_filter: Optional[HITLPriority] = None) -> List[HITLRequest]:
        """Get pending HITL requests, optionally filtered by priority."""
        with self._lock:
            requests = list(self.pending_requests.values())

        if priority_filter:
            requests = [r for r in requests if r.priority == priority_filter]

        # Sort by priority (critical first) and creation time
        priority_order = {HITLPriority.CRITICAL: 0, HITLPriority.HIGH: 1, HITLPriority.LOW: 2}
        requests.sort(key=lambda r: (priority_order[r.priority], r.created_at))

        return requests

    def get_request_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a HITL request."""
        with self._lock:
            if request_id in self.pending_requests:
                request = self.pending_requests[request_id]
                return {
                    "status": "pending",
                    "request": request.__dict__,
                    "time_elapsed": time.time() - request.created_at
                }
            elif request_id in self.completed_requests:
                request = self.completed_requests[request_id]
                return {
                    "status": "completed",
                    "request": request.__dict__,
                    "resolution_time": request.resolved_at - request.created_at if request.resolved_at else None
                }

        return None

    def _find_workflow_for_request(self, request: HITLRequest) -> Optional[str]:
        """Find which workflow created this request."""
        # This is a simplified implementation
        # In production, you'd track workflow associations
        for name, workflow in self.workflows.items():
            if workflow.name in request.context.get("workflow_source", ""):
                return name
        return None

    def cleanup_expired_requests(self):
        """Clean up expired HITL requests."""
        current_time = time.time()
        expired_ids = []

        with self._lock:
            for request_id, request in self.pending_requests.items():
                if current_time - request.created_at > request.timeout_seconds:
                    request.decision = HITLDecision.ESCALATE
                    request.decision_data = {"reason": "timeout"}
                    request.resolved_at = current_time

                    self.completed_requests[request_id] = request
                    expired_ids.append(request_id)

            for request_id in expired_ids:
                del self.pending_requests[request_id]

        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired HITL requests")


# Global HITL manager instance
_hitl_manager = None

def get_hitl_manager() -> HITLManager:
    """Get global HITL manager instance."""
    global _hitl_manager
    if _hitl_manager is None:
        _hitl_manager = HITLManager()
    return _hitl_manager

