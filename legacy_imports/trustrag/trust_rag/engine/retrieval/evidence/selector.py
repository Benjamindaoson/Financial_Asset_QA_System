"""
Evidence Selector: Selects minimal sufficient evidence set.
"""
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from .classifier import EvidenceRole, EvidenceRoleClassifier, EvidenceReranker
from trust_rag.engine.retrieval.scored_chunk import ScoredChunk

# ============ Risk Flags ============

@dataclass
class RiskFlags:
    """Pre-arbitration risk indicators."""
    conflict_likely: bool = False
    disclosure_required: bool = False
    evidence_insufficient: bool = False
    ocr_only_numeric: bool = False
    modal_conflict: bool = False
    requires_human_review: bool = False

# ============ Selected Evidence Set ============

@dataclass
class SelectedEvidenceSet:
    """
    Output of evidence selection.
    Ready for EvidenceArbitrator consumption.
    Bank/regulator auditable structure.
    """
    core_evidence: List[ScoredChunk] = field(default_factory=list)  # ≤3
    supporting_evidence: List[ScoredChunk] = field(default_factory=list)
    excluded_evidence: List[ScoredChunk] = field(default_factory=list)
    selection_reason: Dict[str, str] = field(default_factory=dict)  # evidence_id -> reason
    
    # Risk flags (pre-arbitration)
    risk_flags: RiskFlags = field(default_factory=RiskFlags)
    
    # Legacy flags (backward compat)
    evidence_insufficient: bool = False
    high_risk_only: bool = False
    collapsed_tables: Dict[str, List[str]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "core_evidence": [{"id": c.evidence_id, "role": c.metadata.get("evidence_role")} 
                             for c in self.core_evidence],
            "supporting_evidence": [{"id": c.evidence_id} for c in self.supporting_evidence],
            "excluded_evidence": [{"id": c.evidence_id} for c in self.excluded_evidence],
            "selection_reasoning": self.selection_reason,
            "risk_flags": {
                "conflict_likely": self.risk_flags.conflict_likely,
                "disclosure_required": self.risk_flags.disclosure_required,
                "evidence_insufficient": self.risk_flags.evidence_insufficient,
                "ocr_only_numeric": self.risk_flags.ocr_only_numeric,
                "modal_conflict": self.risk_flags.modal_conflict,
                "requires_human_review": self.risk_flags.requires_human_review,
            },
            "collapsed_tables": self.collapsed_tables,
        }

# ============ Selection Config ============

@dataclass
class SelectionConfig:
    """Configuration for evidence selection."""
    max_core_factual: int = 3
    max_core_summary: int = 5
    max_per_source: int = 1  # For FACTUAL questions
    max_per_source_summary: int = 2
    prefer_numeric: bool = True
    block_ocr_top1: bool = True  # OCR-only cannot be Top-1 for numerics

    # Fail-closed thresholds
    min_similarity_threshold: float = 0.3  # Minimum similarity score to consider evidence
    min_confidence_threshold: float = 0.5  # Minimum confidence for evidence
    min_evidence_count: int = 1  # Minimum number of evidence items required
    max_weak_evidence_ratio: float = 0.5  # Maximum ratio of weak evidence allowed

# ============ Evidence Selector ============

class EvidenceSelector:
    """
    Selects minimal but sufficient evidence set.
    Implements: quantity limits, numeric priority, table collapse.
    """
    
    def __init__(
        self,
        classifier: EvidenceRoleClassifier = None,
        reranker: EvidenceReranker = None,
        config: SelectionConfig = None
    ):
        self.classifier = classifier or EvidenceRoleClassifier()
        self.reranker = reranker or EvidenceReranker(self.classifier)
        self.config = config or SelectionConfig()
    
    def select(
        self,
        candidates: List[ScoredChunk],
        query_type: str = "factual",  # factual, summary
        is_numeric: bool = False
    ) -> SelectedEvidenceSet:
        """
        Select evidence from candidates.
        Bank-grade: populates risk_flags for pre-arbitration detection.
        """
        result = SelectedEvidenceSet()
        
        if not candidates:
            result.evidence_insufficient = True
            result.risk_flags.evidence_insufficient = True
            return result
        
        # Step 1: Filter by thresholds (fail-closed)
        filtered_candidates = self._filter_by_thresholds(candidates)

        if not filtered_candidates:
            result.evidence_insufficient = True
            result.risk_flags.evidence_insufficient = True
            return result

        # Step 2: Rerank
        reranked = self.reranker.rerank(filtered_candidates)

        # Step 3: Classify roles
        classified = self._classify_all(reranked)

        # Step 4: Table collapse
        collapsed, collapse_map = self._collapse_tables(classified)
        result.collapsed_tables = collapse_map

        # Step 5: Check for high-risk-only scenario
        if self._is_high_risk_only(collapsed):
            result.high_risk_only = True
            result.risk_flags.disclosure_required = True

        # Step 6: Pre-conflict detection
        self._detect_pre_conflicts(collapsed, is_numeric, result)

        # Step 7: Apply selection rules
        if query_type == "factual":
            result = self._select_factual(collapsed, is_numeric, result)
        else:
            result = self._select_summary(collapsed, result)

        # Step 8: Check evidence sufficiency with fail-closed logic
        if len(result.core_evidence) < self.config.min_evidence_count:
            result.evidence_insufficient = True
            result.risk_flags.evidence_insufficient = True
        
        # Step 9: Final risk assessment
        if result.risk_flags.modal_conflict or result.risk_flags.conflict_likely:
            result.risk_flags.disclosure_required = True
        
        if result.high_risk_only and is_numeric:
            result.risk_flags.requires_human_review = True
        
        return result
    
    def _detect_pre_conflicts(
        self,
        classified: List[Tuple],
        is_numeric: bool,
        result: SelectedEvidenceSet
    ):
        """
        Pre-arbitration conflict detection.
        Detects: numeric conflicts, modality conflicts, source conflicts.
        """
        # Track numeric values by source
        numeric_values: Dict[str, List[str]] = {}  # value -> [evidence_ids]
        has_native_numeric = False
        has_ocr_numeric = False
        
        for chunk, role, reason in classified:
            modality = chunk.metadata.get("modality", "") if hasattr(chunk, 'metadata') else ""
            
            # Check for numeric content
            if self._has_numeric_content(chunk):
                if modality in ["text_native", "table_native"]:
                    has_native_numeric = True
                elif modality in ["text_ocr", "table_ocr"]:
                    has_ocr_numeric = True
                
                # Extract and track numeric values (simplified)
                numeric_str = self._extract_numeric_signature(chunk)
                if numeric_str:
                    if numeric_str not in numeric_values:
                        numeric_values[numeric_str] = []
                    numeric_values[numeric_str].append(chunk.evidence_id)
        
        # Modal conflict: OCR vs native both have numerics
        if is_numeric and has_ocr_numeric and has_native_numeric:
            result.risk_flags.modal_conflict = True
        
        # OCR-only numeric (no native source)
        if is_numeric and has_ocr_numeric and not has_native_numeric:
            result.risk_flags.ocr_only_numeric = True
            result.risk_flags.disclosure_required = True
        
        # Numeric value conflict (different values from different sources)
        if len(numeric_values) > 1:
            # Multiple distinct numeric values = potential conflict
            result.risk_flags.conflict_likely = True
    
    def _has_numeric_content(self, chunk: ScoredChunk) -> bool:
        """Check if chunk contains numeric content."""
        import re
        text = chunk.text
        patterns = r'\d+[%％]|\$[\d,]+|\d{4}年|\d+\.?\d*\s*(万|亿|元|USD|CNY|million|billion)'
        return bool(re.search(patterns, text))
    
    def _extract_numeric_signature(self, chunk: ScoredChunk) -> Optional[str]:
        """Extract a simplified numeric signature for conflict detection."""
        import re
        text = chunk.text
        # Find first significant number
        match = re.search(r'[\d,]+\.?\d*\s*(万|亿|元|%|USD|CNY|million|billion)?', text)
        if match:
            return match.group(0).strip()
        return None
    
    def _classify_all(self, chunks: List[ScoredChunk]) -> List[Tuple]:
        """Classify all chunks with roles."""
        results = []
        for chunk in chunks:
            role, reason = self.classifier.classify(chunk)
            results.append((chunk, role, reason))
        return results
    
    def _collapse_tables(
        self,
        classified: List[Tuple]
    ) -> Tuple[List[Tuple], Dict[str, List[str]]]:
        """
        Collapse multiple chunks from same table into one representative.
        """
        collapse_map: Dict[str, List[str]] = {}
        table_representatives: Dict[str, Tuple] = {}
        non_table_chunks = []
        
        for chunk, role, reason in classified:
            table_id = self._get_table_id(chunk)
            
            if table_id:
                if table_id not in table_representatives:
                    # First chunk from this table becomes representative
                    table_representatives[table_id] = (chunk, role, reason)
                    collapse_map[table_id] = []
                else:
                    # Subsequent chunks are collapsed
                    collapse_map[table_id].append(chunk.evidence_id)
            else:
                non_table_chunks.append((chunk, role, reason))
        
        # Combine: representatives + non-table
        result = list(table_representatives.values()) + non_table_chunks
        return result, collapse_map
    
    def _get_table_id(self, chunk: ScoredChunk) -> Optional[str]:
        """Get table ID if chunk is from a table."""
        if hasattr(chunk, 'metadata'):
            if chunk.metadata.get("modality") in ["table_native", "table_ocr"]:
                return chunk.metadata.get("table_id") or chunk.parent_id
        return None
    
    def _is_high_risk_only(self, classified: List[Tuple]) -> bool:
        """Check if all candidates are high-risk."""
        for chunk, role, _ in classified:
            if role == EvidenceRole.FACT_CORE:
                return False
            modality = chunk.metadata.get("modality", "") if hasattr(chunk, 'metadata') else ""
            if modality in ["text_native", "table_native"]:
                if chunk.ingest_status == "OK":
                    return False
        return True
    
    def _select_factual(
        self,
        classified: List[Tuple],
        is_numeric: bool,
        result: SelectedEvidenceSet
    ) -> SelectedEvidenceSet:
        """Selection for FACTUAL questions."""
        
        source_counts: Dict[str, int] = {}
        core_count = 0
        
        for chunk, role, reason in classified:
            # Skip OCR-only as Top-1 for numeric questions
            if is_numeric and self.config.block_ocr_top1 and core_count == 0:
                modality = chunk.metadata.get("modality", "") if hasattr(chunk, 'metadata') else ""
                if modality in ["text_ocr", "table_ocr"]:
                    result.excluded_evidence.append(chunk)
                    result.selection_reason[chunk.evidence_id] = "OCR-only blocked as Top-1 for numeric"
                    continue
            
            # Source dedup
            source_id = chunk.doc_id
            if source_id in source_counts and source_counts[source_id] >= self.config.max_per_source:
                result.excluded_evidence.append(chunk)
                result.selection_reason[chunk.evidence_id] = f"Source limit ({self.config.max_per_source}) reached"
                continue
            
            # Role-based selection
            if role == EvidenceRole.FACT_CORE:
                if core_count < self.config.max_core_factual:
                    result.core_evidence.append(chunk)
                    result.selection_reason[chunk.evidence_id] = reason
                    core_count += 1
                    source_counts[source_id] = source_counts.get(source_id, 0) + 1
                else:
                    result.supporting_evidence.append(chunk)
                    result.selection_reason[chunk.evidence_id] = "Core limit reached, demoted to supporting"
            
            elif role == EvidenceRole.SUPPORTING:
                result.supporting_evidence.append(chunk)
                result.selection_reason[chunk.evidence_id] = reason
            
            else:  # WEAK
                result.excluded_evidence.append(chunk)
                result.selection_reason[chunk.evidence_id] = reason
        
        return result
    
    def _select_summary(
        self,
        classified: List[Tuple],
        result: SelectedEvidenceSet
    ) -> SelectedEvidenceSet:
        """Selection for SUMMARY questions (more permissive)."""
        
        source_counts: Dict[str, int] = {}
        core_count = 0
        
        for chunk, role, reason in classified:
            source_id = chunk.doc_id
            
            # Source dedup (more permissive)
            if source_id in source_counts and source_counts[source_id] >= self.config.max_per_source_summary:
                result.excluded_evidence.append(chunk)
                result.selection_reason[chunk.evidence_id] = f"Source limit ({self.config.max_per_source_summary}) reached"
                continue
            
            if role in [EvidenceRole.FACT_CORE, EvidenceRole.SUPPORTING]:
                if core_count < self.config.max_core_summary:
                    result.core_evidence.append(chunk)
                    core_count += 1
                else:
                    result.supporting_evidence.append(chunk)
                result.selection_reason[chunk.evidence_id] = reason
                source_counts[source_id] = source_counts.get(source_id, 0) + 1
            else:
                result.excluded_evidence.append(chunk)
                result.selection_reason[chunk.evidence_id] = reason
        
        return result

    def _filter_by_thresholds(self, candidates: List[ScoredChunk]) -> List[ScoredChunk]:
        """
        Filter candidates based on similarity and confidence thresholds.
        Implements fail-closed mechanism.
        """
        filtered = []

        for candidate in candidates:
            # Check similarity threshold
            similarity_score = getattr(candidate.scores, 'final', 0.0)
            if similarity_score < self.config.min_similarity_threshold:
                continue

            # Check confidence threshold
            confidence_score = getattr(candidate, 'confidence', similarity_score)
            if confidence_score < self.config.min_confidence_threshold:
                continue

            # Check for weak evidence types
            is_weak_evidence = self._is_weak_evidence(candidate)
            if is_weak_evidence:
                # Allow some weak evidence but limit ratio
                weak_ratio = len([c for c in filtered if self._is_weak_evidence(c)]) / max(1, len(filtered))
                if weak_ratio >= self.config.max_weak_evidence_ratio:
                    continue

            filtered.append(candidate)

        return filtered

    def _is_weak_evidence(self, candidate: ScoredChunk) -> bool:
        """
        Determine if evidence is considered "weak" and should be limited.
        """
        # OCR evidence is considered weak for numerics
        modality = getattr(candidate, 'modality', 'text_native')
        if modality in ['image', 'ocr'] and self.config.block_ocr_top1:
            return True

        # Low confidence metadata
        metadata = getattr(candidate, 'metadata', {})
        ocr_confidence = metadata.get('ocr_confidence', 100)
        if ocr_confidence < 70:  # Below acceptable OCR confidence
            return True

        return False

# Type hint fix
from typing import Tuple
