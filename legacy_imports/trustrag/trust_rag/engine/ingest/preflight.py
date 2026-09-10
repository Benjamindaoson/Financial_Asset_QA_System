"""
Pre-flight Gate for Phase 1.
Validates DocIR blocks before embedding to prevent parsing pollution.
"""
import re
import math
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum

class GateStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"

class PreflightResult(BaseModel):
    """Result of pre-flight validation."""
    anomaly_score: float = 0.0  # 0-1, higher = worse
    structure_issues: List[str] = Field(default_factory=list)
    cser_estimate: Optional[float] = None
    gate_status: GateStatus = GateStatus.OK
    gate_reason: str = ""

class PreflightGate:
    """
    Validates parsed content before embedding.
    Catches OCR artifacts, structural breaks, and quality issues.
    """
    
    # Thresholds
    ANOMALY_THRESHOLD_DEGRADED = 0.15
    ANOMALY_THRESHOLD_FAILED = 0.40
    
    # Common OCR artifact patterns
    OCR_ARTIFACT_PATTERNS = [
        r'[○●◯◉]{2,}',           # Circle sequences (OCR noise)
        r'[□■◻◼]{2,}',           # Square sequences
        r'\d+[%％]\s*→\s*[a-zA-Z][%％]',  # "5%" becoming "s%"
        r'[Il1]{5,}',             # Confusable chars
        r'[\u0000-\u001F]',       # Control characters
        r'[^\x00-\x7F\u4e00-\u9fff\u3000-\u303f]{10,}',  # Long non-text sequences
    ]
    
    # Illegal character density threshold
    ILLEGAL_CHAR_DENSITY_THRESHOLD = 0.05
    
    def __init__(self):
        self.artifact_regexes = [re.compile(p) for p in self.OCR_ARTIFACT_PATTERNS]
    
    def evaluate(self, chunks: List[Any]) -> PreflightResult:
        """
        Run pre-flight checks on parsed chunks.
        
        Args:
            chunks: List of Chunk objects from parser
            
        Returns:
            PreflightResult with gate_status
        """
        if not chunks:
            return PreflightResult(gate_status=GateStatus.OK, gate_reason="Empty input")
        
        total_anomaly = 0.0
        structure_issues = []
        chunk_count = len(chunks)
        
        for chunk in chunks:
            text = chunk.text if hasattr(chunk, 'text') else str(chunk)
            metadata = chunk.metadata if hasattr(chunk, 'metadata') else {}
            provenance = chunk.provenance if hasattr(chunk, 'provenance') else None
            
            # A) Anomaly Scan
            chunk_anomaly = self._scan_anomalies(text)
            total_anomaly += chunk_anomaly
            
            # B) Structure Check (for tables)
            if provenance and getattr(provenance, 'modality', None) == 'table':
                issues = self._check_table_structure(metadata)
                structure_issues.extend(issues)
        
        # Normalize anomaly score
        avg_anomaly = total_anomaly / chunk_count if chunk_count > 0 else 0.0
        
        # Determine gate status
        status = GateStatus.OK
        reason = ""
        
        if avg_anomaly >= self.ANOMALY_THRESHOLD_FAILED:
            status = GateStatus.FAILED
            reason = f"High anomaly score: {avg_anomaly:.2f}"
        elif avg_anomaly >= self.ANOMALY_THRESHOLD_DEGRADED:
            status = GateStatus.DEGRADED
            reason = f"Elevated anomaly score: {avg_anomaly:.2f}"
        
        if structure_issues:
            if status != GateStatus.FAILED:
                status = GateStatus.DEGRADED
            reason += f"; Structure issues: {len(structure_issues)}"
        
        return PreflightResult(
            anomaly_score=avg_anomaly,
            structure_issues=structure_issues,
            gate_status=status,
            gate_reason=reason.strip("; ")
        )
    
    def _scan_anomalies(self, text: str) -> float:
        """
        Scan text for OCR artifacts and anomalies.
        Returns anomaly score 0-1.
        """
        if not text:
            return 0.0
        
        score = 0.0
        text_len = len(text)
        
        # Pattern matching
        for regex in self.artifact_regexes:
            matches = regex.findall(text)
            if matches:
                match_chars = sum(len(m) for m in matches)
                score += match_chars / text_len * 0.5
        
        # Character entropy check (very low = suspicious)
        entropy = self._char_entropy(text)
        if entropy < 2.0 and text_len > 50:
            score += 0.2
        
        # Illegal character density
        illegal_count = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t')
        if text_len > 0:
            illegal_density = illegal_count / text_len
            if illegal_density > self.ILLEGAL_CHAR_DENSITY_THRESHOLD:
                score += 0.3
        
        return min(score, 1.0)
    
    def _char_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of character distribution."""
        if not text:
            return 0.0
        freq = {}
        for c in text:
            freq[c] = freq.get(c, 0) + 1
        total = len(text)
        entropy = 0.0
        for count in freq.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy
    
    def _check_table_structure(self, metadata: Dict[str, Any]) -> List[str]:
        """
        Validate table structure integrity.
        Returns list of structure issues.
        """
        issues = []
        
        table_structure = metadata.get("table_structure", {})
        if not table_structure:
            # No structure to validate
            return issues
        
        headers = table_structure.get("headers", [])
        rows = table_structure.get("rows", [])
        
        # Check header coverage
        if not headers:
            issues.append("Missing table headers")
        
        # Check column consistency
        if headers and rows:
            expected_cols = len(headers)
            for i, row in enumerate(rows):
                if len(row) != expected_cols:
                    issues.append(f"Row {i}: column count mismatch ({len(row)} vs {expected_cols})")
                    break  # One issue is enough to flag
        
        # Check for merged cell indicators (colspan/rowspan)
        # If present but not properly closed, flag as structural issue
        if metadata.get("has_merged_cells") and not metadata.get("merged_cells_resolved"):
            issues.append("Unresolved merged cells in table")
        
        return issues
