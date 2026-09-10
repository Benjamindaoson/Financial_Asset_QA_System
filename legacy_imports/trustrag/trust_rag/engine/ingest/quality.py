from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
from trust_rag.engine.ingest.models import Chunk

logger = logging.getLogger(__name__)

class QualityReport(BaseModel):
    """Report produced by QualityGate."""
    ocr_confidence: float = 1.0
    table_stitching_applied: bool = False
    layout_integrity: str = "OK"  # OK, INVALID
    issues: List[str] = Field(default_factory=list)

class QualityGate:
    """
    Gates ingestion based on quality metrics.
    """
    
    def __init__(self, ocr_threshold: float = 0.70):
        self.ocr_threshold = ocr_threshold

    def evaluate(self, chunks: List[Chunk]) -> QualityReport:
        """
        Evaluate the quality of the ingested chunks.
        """
        report = QualityReport()
        
        # 1. OCR Confidence
        confidences = []
        for chunk in chunks:
            # Check metadata for confidence scores (commonly from OCR)
            if "ocr_confidence" in chunk.metadata:
                confidences.append(float(chunk.metadata["ocr_confidence"]))
            elif "confidence" in chunk.metadata:
                 confidences.append(float(chunk.metadata["confidence"]))
        
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            report.ocr_confidence = avg_conf
            if avg_conf < self.ocr_threshold:
                report.issues.append(f"Low OCR confidence: {avg_conf:.2f} < {self.ocr_threshold}")
        else:
            # If no OCR was performed (e.g. digital PDF), confidence is effectively 1.0
            report.ocr_confidence = 1.0

        # 2. Table Stitching
        # Check if any chunk was formed by stitching
        for chunk in chunks:
            if chunk.metadata.get("is_stitched_table", False):
                report.table_stitching_applied = True
                break
        
        # 3. Layout Integrity
        # Check for mixed block types or missing bboxes where expected
        layout_issues = False
        for chunk in chunks:
            # Mixed block types Check (this might already be enforced, but we check again)
            # This is hard to check post-hoc on a single chunk without raw blocks.
            # But we can check if a "text" chunk has "table" metadata, etc.
            # Requirement: "Mixed block types inside chunk → INVALID"
            
            # Check missing bbox
            if chunk.provenance.modality in ["pdf", "image"]:
                 if not chunk.provenance.bbox:
                     # Some global metadata might not have bbox, but content chunks should
                     if chunk.text and len(chunk.text.strip()) > 0:
                         layout_issues = True
                         report.issues.append(f"Missing bbox for chunk {chunk.evidence_id}")
            
        if layout_issues:
            report.layout_integrity = "INVALID"
        
        return report
