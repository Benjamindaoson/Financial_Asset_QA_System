"""
TrustRAG Exception Hierarchy
All exceptions inherit from TrustRAGException for unified handling.
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of errors for routing and handling."""
    INGESTION = "ingestion"
    RETRIEVAL = "retrieval"
    GENERATION = "generation"
    JUDGMENT = "judgment"
    VALIDATION = "validation"
    SYSTEM = "system"
    EXTERNAL = "external"


class ErrorSeverity(Enum):
    """Severity levels for error handling."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TrustRAGException(Exception):
    """Base exception for all TrustRAG errors."""

    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.SYSTEM,
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 technical_details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.category = category
        self.severity = severity
        self.technical_details = technical_details or {}

    def get_user_message(self) -> str:
        """Get user-friendly message."""
        return self.message


class RefusalCode(Enum):
    """Standard refusal codes for consistent user messaging."""
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    EVIDENCE_CONFLICT = "evidence_conflict"
    LOW_CONFIDENCE = "low_confidence"
    CITATION_FAILURE = "citation_failure"
    SECURITY_VIOLATION = "security_violation"
    SYSTEM_ERROR = "system_error"


class RefusalException(TrustRAGException):
    """Exception raised when system must refuse to answer."""

    def __init__(self, code: RefusalCode, message: str,
                 user_message: Optional[str] = None,
                 technical_details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.JUDGMENT,
            severity=ErrorSeverity.MEDIUM,
            technical_details=technical_details
        )
        self.code = code
        self.user_message = user_message or message


class IngestionFailedException(TrustRAGException):
    """Exception raised when document ingestion fails."""

    def __init__(self, file_path: str, reason: str,
                 technical_details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Ingestion failed for {file_path}: {reason}",
            category=ErrorCategory.INGESTION,
            severity=ErrorSeverity.HIGH,
            technical_details={
                "file_path": file_path,
                "reason": reason,
                **(technical_details or {})
            }
        )
        self.file_path = file_path


class JudgmentException(TrustRAGException):
    """Exception raised during judgment/arbitration process."""

    def __init__(self, message: str, judgment_context: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.JUDGMENT,
            severity=ErrorSeverity.HIGH,
            technical_details=judgment_context
        )


class IndexCorruptedException(TrustRAGException):
    """Exception raised when vector index is corrupted or unusable."""

    def __init__(self, index_path: str, reason: str,
                 technical_details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Index corrupted at {index_path}: {reason}",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            technical_details={
                "index_path": index_path,
                "reason": reason,
                **(technical_details or {})
            }
        )
        self.index_path = index_path


class RetrievalFailedException(TrustRAGException):
    """Exception raised when retrieval operation fails."""

    def __init__(self, query: str, reason: str,
                 technical_details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Retrieval failed for query: {reason}",
            category=ErrorCategory.RETRIEVAL,
            severity=ErrorSeverity.HIGH,
            technical_details={
                "query": query[:100] if query else "",
                "reason": reason,
                **(technical_details or {})
            }
        )
        self.query = query
        self.reason = reason

    def get_user_message(self) -> str:
        """Get user-friendly message."""
        return f"Retrieval failed: {self.reason}"


def handle_exception(exc: Exception, context: Optional[Dict[str, Any]] = None,
                    default_category: ErrorCategory = ErrorCategory.SYSTEM) -> TrustRAGException:
    """
    Wrap any exception in a TrustRAGException with proper categorization.

    Args:
        exc: The original exception
        context: Additional context for debugging
        default_category: Default category if not a TrustRAGException

    Returns:
        Properly categorized TrustRAGException
    """
    if isinstance(exc, TrustRAGException):
        # Already properly categorized
        if context:
            exc.technical_details.update(context)
        return exc

    # Wrap unknown exceptions
    technical_details = {
        "original_exception": type(exc).__name__,
        "original_message": str(exc),
        **(context or {})
    }

    return TrustRAGException(
        message=str(exc),
        category=default_category,
        severity=ErrorSeverity.MEDIUM,
        technical_details=technical_details
    )
