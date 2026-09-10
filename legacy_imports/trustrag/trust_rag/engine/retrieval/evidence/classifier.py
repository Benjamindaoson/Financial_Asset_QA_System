"""
Evidence Role Classification, Reranking, and Selection.
Phase 6: Evidence Decision Layer for bank/regulator scenarios.
"""
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from trust_rag.engine.retrieval.scored_chunk import ScoredChunk

# ============ Evidence Role ============

class EvidenceRole(str, Enum):
    FACT_CORE = "fact_core"       # Can directly support answer
    SUPPORTING = "supporting"     # Background/context only
    WEAK = "weak"                 # Must not be core evidence

# ============ Source Authority ============

SOURCE_AUTHORITY = {
    "annual_report": 1.0,
    "audit": 0.9,
    "prospectus": 0.85,
    "regulatory_filing": 0.8,
    "news": 0.5,
    "draft": 0.3,
    "unknown": 0.4,
}

# ============ Modality Trust ============

MODALITY_TRUST = {
    "text_native": 1.0,
    "table_native": 0.95,
    "text_ocr": 0.6,
    "table_ocr": 0.55,
    "chart": 0.3,
}

# ============ Evidence Role Classifier ============

class EvidenceRoleClassifier:
    """
    Rule-based evidence role classification.
    Stable, auditable, no ML.
    """
    
    def classify(self, chunk: ScoredChunk) -> Tuple[EvidenceRole, str]:
        """
        Classify evidence role with explanation.
        Returns (role, reason).
        """
        reasons = []
        
        # Check modality
        modality = chunk.metadata.get("modality", "text_native") if hasattr(chunk, 'metadata') else "text_native"
        modality_trust = MODALITY_TRUST.get(modality, 0.5)
        
        # Check ingest status
        ingest_status = chunk.ingest_status
        
        # Check for canonical numeric
        has_canonical = self._has_canonical_value(chunk)
        
        # Check source type
        source_type = chunk.metadata.get("source_type", "unknown") if hasattr(chunk, 'metadata') else "unknown"
        source_auth = SOURCE_AUTHORITY.get(source_type, 0.4)
        
        # Is native source?
        is_native = modality in ["text_native", "table_native"]
        
        # Is OCR only?
        is_ocr_only = modality in ["text_ocr", "table_ocr"]
        
        # Is chart derived?
        is_chart = modality == "chart"
        
        # Rule 1: Chart → always SUPPORTING
        if is_chart:
            return EvidenceRole.SUPPORTING, "Chart-derived evidence (never FACT_CORE)"
        
        # Rule 2: DEGRADED ingest → downgrade one level
        if ingest_status == "DEGRADED":
            if has_canonical and is_native:
                return EvidenceRole.SUPPORTING, "DEGRADED ingest downgrades from FACT_CORE"
            return EvidenceRole.WEAK, "DEGRADED ingest with non-native source"
        
        # Rule 3: FAILED ingest → WEAK
        if ingest_status == "FAILED":
            return EvidenceRole.WEAK, "FAILED ingest status"
        
        # Rule 4: OCR-only without native alignment → WEAK
        if is_ocr_only and not self._has_native_alignment(chunk):
            return EvidenceRole.WEAK, "OCR-only without native alignment"
        
        # Rule 5: Canonical numeric + native source → FACT_CORE
        if has_canonical and is_native:
            return EvidenceRole.FACT_CORE, "Contains canonical numeric with native source"
        
        # Rule 6: High authority native → FACT_CORE
        if is_native and source_auth >= 0.8:
            return EvidenceRole.FACT_CORE, f"Native source with high authority ({source_type})"
        
        # Rule 7: Native but low authority → SUPPORTING
        if is_native and source_auth < 0.8:
            return EvidenceRole.SUPPORTING, f"Native source with lower authority ({source_type})"
        
        # Default: SUPPORTING
        return EvidenceRole.SUPPORTING, "Default classification"
    
    def _has_canonical_value(self, chunk: ScoredChunk) -> bool:
        """Check if chunk contains canonical numeric value."""
        # Check metadata for canonical values
        if hasattr(chunk, 'metadata'):
            if chunk.metadata.get("has_canonical_value"):
                return True
            if chunk.metadata.get("fact_density", 0) > 0.3:
                return True
        
        # Simple heuristic: check text for numbers
        import re
        text = chunk.text
        numeric_patterns = r'\d+[%％]|\$[\d,]+|\d{4}年|\d+\.?\d*\s*(万|亿|元|USD|CNY)'
        return bool(re.search(numeric_patterns, text))
    
    def _has_native_alignment(self, chunk: ScoredChunk) -> bool:
        """Check if OCR chunk has native text alignment."""
        if hasattr(chunk, 'metadata'):
            return chunk.metadata.get("native_aligned", False)
        return False

# ============ Evidence Reranker ============

class EvidenceReranker:
    """
    Lightweight evidence-level reranking.
    Considers: role, fact_density, authority, modality, ingest_status.
    """
    
    def __init__(self, classifier: EvidenceRoleClassifier = None):
        self.classifier = classifier or EvidenceRoleClassifier()
    
    def rerank(self, candidates: List[ScoredChunk]) -> List[ScoredChunk]:
        """
        Rerank candidates based on evidence quality factors.
        Does NOT re-expand candidate set.
        """
        if not candidates:
            return []
        
        scored_candidates = []
        
        for chunk in candidates:
            role, reason = self.classifier.classify(chunk)
            
            # Compute evidence quality score
            quality_score = self._compute_quality_score(chunk, role)
            
            # Combine with original score (weighted)
            original_score = chunk.scores.final
            combined_score = 0.6 * original_score + 0.4 * quality_score
            
            # Store role and reason in metadata (not as attribute)
            if not hasattr(chunk, 'metadata') or chunk.metadata is None:
                chunk.metadata = {}
            chunk.metadata["evidence_role"] = role.value
            chunk.metadata["role_reason"] = reason
            
            scored_candidates.append((chunk, combined_score))
        
        # Sort by combined score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Update final scores
        for chunk, score in scored_candidates:
            chunk.scores.final = score
        
        return [c[0] for c in scored_candidates]
    
    def _compute_quality_score(self, chunk: ScoredChunk, role: EvidenceRole) -> float:
        """Compute evidence quality score (0-1)."""
        score = 0.0
        
        # Role weight
        role_weights = {
            EvidenceRole.FACT_CORE: 1.0,
            EvidenceRole.SUPPORTING: 0.6,
            EvidenceRole.WEAK: 0.2,
        }
        score += role_weights.get(role, 0.5) * 0.4
        
        # Modality trust
        modality = chunk.metadata.get("modality", "text_native") if hasattr(chunk, 'metadata') else "text_native"
        score += MODALITY_TRUST.get(modality, 0.5) * 0.3
        
        # Source authority
        source_type = chunk.metadata.get("source_type", "unknown") if hasattr(chunk, 'metadata') else "unknown"
        score += SOURCE_AUTHORITY.get(source_type, 0.4) * 0.2
        
        # Ingest status penalty
        if chunk.ingest_status == "DEGRADED":
            score *= 0.7
        elif chunk.ingest_status == "FAILED":
            score *= 0.3
        
        # Fact density bonus
        if hasattr(chunk, 'metadata') and chunk.metadata.get("fact_density", 0) > 0.5:
            score += 0.1
        
        return min(score, 1.0)
