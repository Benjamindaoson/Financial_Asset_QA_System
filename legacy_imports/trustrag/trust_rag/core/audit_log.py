"""
Audit Logging and Decision Traceability.

Tracks all user operations and system decisions for compliance and analysis.
"""
import json
import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from trust_rag.config import get_paths
from trust_rag.core.tenant import get_tenant_id

logger = logging.getLogger(__name__)


class OperationType(str, Enum):
    """Types of operations to audit."""
    QUERY = "query"
    INGEST = "ingest"
    INDEX_REFRESH = "index_refresh"
    CONFIG_CHANGE = "config_change"
    SCENARIO_CHANGE = "scenario_change"
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"


class DecisionType(str, Enum):
    """Types of decisions to audit."""
    VERIFIED = "verified"
    REFUSED = "refused"
    CONFLICT = "conflict"
    UPGRADE = "upgrade"
    FALLBACK = "fallback"


@dataclass
class AuditEntry:
    """Single audit log entry."""
    timestamp: str
    operation_type: OperationType
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    trace_id: Optional[str] = None
    
    # Operation details
    operation_details: Dict[str, Any] = None
    
    # Decision information
    decision_type: Optional[DecisionType] = None
    decision_reason: Optional[str] = None
    decision_metadata: Dict[str, Any] = None
    
    # Evidence trail
    evidence_ids: List[str] = None
    sources_used: List[str] = None
    
    # Performance
    duration_ms: Optional[float] = None
    
    # Error information
    error: Optional[str] = None
    error_category: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        # Convert enums to strings
        if isinstance(result.get("operation_type"), Enum):
            result["operation_type"] = result["operation_type"].value
        if isinstance(result.get("decision_type"), Enum):
            result["decision_type"] = result["decision_type"].value
        return result


class AuditLogger:
    """
    Audit logging system for compliance and traceability.
    
    Logs:
    - All user operations
    - System decisions and reasoning
    - Evidence trails
    - Performance metrics
    - Errors and failures
    """
    
    def __init__(self, log_dir: Optional[str] = None):
        """
        Initialize audit logger.
        
        Args:
            log_dir: Directory for audit logs (optional)
        """
        self.log_dir = log_dir or os.path.join(get_paths().logs_dir, "audit")
        os.makedirs(self.log_dir, exist_ok=True)
        
        self._entries: List[AuditEntry] = []
        self._max_memory_entries = 1000  # Keep last 1000 in memory
    
    def log_operation(
        self,
        operation_type: OperationType,
        operation_details: Dict[str, Any],
        user_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None
    ):
        """
        Log a user operation.
        
        Args:
            operation_type: Type of operation
            operation_details: Operation-specific details
            user_id: User identifier
            trace_id: Trace ID for correlation
            duration_ms: Operation duration
            error: Error message if failed
        """
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat(),
            operation_type=operation_type,
            user_id=user_id,
            tenant_id=get_tenant_id(),
            trace_id=trace_id,
            operation_details=operation_details or {},
            duration_ms=duration_ms,
            error=error
        )
        
        self._add_entry(entry)
    
    def log_decision(
        self,
        decision_type: DecisionType,
        decision_reason: str,
        trace_id: str,
        evidence_ids: Optional[List[str]] = None,
        sources_used: Optional[List[str]] = None,
        decision_metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ):
        """
        Log a system decision.
        
        Args:
            decision_type: Type of decision
            decision_reason: Reason for decision
            trace_id: Trace ID for correlation
            evidence_ids: Evidence IDs involved
            sources_used: Document sources used
            decision_metadata: Additional decision metadata
            user_id: User identifier
        """
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat(),
            operation_type=OperationType.QUERY,
            user_id=user_id,
            tenant_id=get_tenant_id(),
            trace_id=trace_id,
            decision_type=decision_type,
            decision_reason=decision_reason,
            decision_metadata=decision_metadata or {},
            evidence_ids=evidence_ids or [],
            sources_used=sources_used or []
        )
        
        self._add_entry(entry)
    
    def log_query(
        self,
        query: str,
        trace_id: str,
        verdict: str,
        reasons: List[str],
        evidence_ids: List[str],
        duration_ms: float,
        user_id: Optional[str] = None,
        confidence: Optional[float] = None
    ):
        """
        Log a query operation with full details.
        
        Args:
            query: User query
            trace_id: Trace ID
            verdict: System verdict (VERIFIED/REFUSED/CONFLICT)
            reasons: Decision reasons
            evidence_ids: Evidence IDs used
            duration_ms: Processing duration
            user_id: User identifier
            confidence: Confidence score
        """
        decision_type_map = {
            "VERIFIED": DecisionType.VERIFIED,
            "REFUSED": DecisionType.REFUSED,
            "CONFLICT": DecisionType.CONFLICT
        }
        
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat(),
            operation_type=OperationType.QUERY,
            user_id=user_id,
            tenant_id=get_tenant_id(),
            trace_id=trace_id,
            operation_details={
                "query": query[:200],  # Truncate long queries
                "verdict": verdict,
                "confidence": confidence
            },
            decision_type=decision_type_map.get(verdict),
            decision_reason="; ".join(reasons) if reasons else None,
            evidence_ids=evidence_ids,
            duration_ms=duration_ms
        )
        
        self._add_entry(entry)
    
    def _add_entry(self, entry: AuditEntry):
        """Add entry to log."""
        self._entries.append(entry)
        
        # Write to file immediately
        self._write_entry(entry)
        
        # Keep memory bounded
        if len(self._entries) > self._max_memory_entries:
            self._entries = self._entries[-self._max_memory_entries:]
    
    def _write_entry(self, entry: AuditEntry):
        """Write entry to log file."""
        try:
            # Use date-based log files
            date_str = datetime.utcnow().strftime("%Y%m%d")
            log_file = os.path.join(self.log_dir, f"audit_{date_str}.jsonl")
            
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit entry: {e}")
    
    def query_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        operation_type: Optional[OperationType] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> List[AuditEntry]:
        """
        Query audit logs with filters.
        
        Args:
            start_time: Start time filter
            end_time: End time filter
            operation_type: Operation type filter
            user_id: User ID filter
            tenant_id: Tenant ID filter
            trace_id: Trace ID filter
            
        Returns:
            List of matching audit entries
        """
        results = []
        
        # Search in-memory entries
        for entry in self._entries:
            if self._matches_filter(entry, start_time, end_time, operation_type, user_id, tenant_id, trace_id):
                results.append(entry)
        
        # Search log files if needed
        if start_time or end_time:
            # Would need to read from files here
            pass
        
        return results
    
    def _matches_filter(
        self,
        entry: AuditEntry,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        operation_type: Optional[OperationType],
        user_id: Optional[str],
        tenant_id: Optional[str],
        trace_id: Optional[str]
    ) -> bool:
        """Check if entry matches filter criteria."""
        entry_time = datetime.fromisoformat(entry.timestamp)
        
        if start_time and entry_time < start_time:
            return False
        if end_time and entry_time > end_time:
            return False
        if operation_type and entry.operation_type != operation_type:
            return False
        if user_id and entry.user_id != user_id:
            return False
        if tenant_id and entry.tenant_id != tenant_id:
            return False
        if trace_id and entry.trace_id != trace_id:
            return False
        
        return True
    
    def export_logs(
        self,
        output_file: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        **filters
    ) -> str:
        """
        Export audit logs to file.
        
        Args:
            output_file: Output file path
            start_time: Start time filter
            end_time: End time filter
            **filters: Additional filters
            
        Returns:
            Path to exported file
        """
        entries = self.query_logs(start_time=start_time, end_time=end_time, **filters)
        
        with open(output_file, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        
        logger.info(f"Exported {len(entries)} audit entries to {output_file}")
        return output_file


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger



