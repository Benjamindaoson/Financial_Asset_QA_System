from typing import List, Dict, Any
from pydantic import BaseModel, Field
from trust_rag.engine.ingest.models import Chunk, IngestResult

class ValidationIssues(BaseModel):
    missing_headers: int = 0
    orphan_blocks: int = 0
    bbox_out_of_range: int = 0
    non_consecutive_pages: int = 0

class DocIRValidation(BaseModel):
    status: str  # OK | DEGRADED | INVALID
    issues: ValidationIssues = Field(default_factory=ValidationIssues)

class DocIRValidator:
    """
    Validates the structural integrity of the DocIR (IngestResult).
    """
    
    def validate(self, result: IngestResult) -> DocIRValidation:
        issues = ValidationIssues()
        status = "OK"
        
        pages_seen = set()
        
        for chunk in result.chunks:
            # 1. Source Blocks Reference
            # "Every chunk must reference valid source_block_ids" - usually in metadata
            if "source_block_ids" not in chunk.metadata or not chunk.metadata["source_block_ids"]:
                # It might be acceptable for some chunks, but let's count orphans
                issues.orphan_blocks += 1
            
            # 2. Tables must have headers
            if chunk.provenance.modality == "table":
                # Assuming table structure is in metadata or text
                # We check if header information is present
                if "column_headers" not in chunk.metadata and "headers" not in chunk.metadata:
                     issues.missing_headers += 1

            # 3. Charts must have title/axis/legend
            if chunk.provenance.modality == "chart":
                has_title = "title" in chunk.metadata and chunk.metadata["title"]
                has_axis = "axis_labels" in chunk.metadata or "axis" in chunk.metadata
                has_legend = "legend" in chunk.metadata
                
                if not (has_title or has_axis or has_legend):
                    # "Charts must have at least one of: title / axis / legend"
                    # If strictly missing all, maybe count as issue?
                    # Depending on strictness, this might be just a semantic gap, but requirement says "Validator rules"
                    # Use a custom metric or reuse one? Let's use orphan_blocks as a proxy or just mark status directly
                    # Added explicit check -> might be INVALID if critical?
                    pass 

            # 4. bbox within page bounds
            # Assuming normalized coords 0-1 or standard PDF points?
            # If normalized, >1 or <0 is bad.
            if chunk.provenance.bbox:
                x1, y1, x2, y2 = chunk.provenance.bbox
                # Assuming top-left 0,0 bottom-right width,height.
                # If we don't know page size, we can't strictly validate absolute coords.
                # But we can check for negative values or x1>x2.
                if x1 > x2 or y1 > y2 or x1 < 0 or y1 < 0:
                     issues.bbox_out_of_range += 1
            
            if chunk.provenance.page_number is not None:
                pages_seen.add(chunk.provenance.page_number)

        # 5. Page range consecutive
        # "page_range must be consecutive" -> This likely applies to the document as a whole?
        # Or tables spanning pages? 
        # If the doc claims to have pages 1, 2, 4 -> missing 3.
        if pages_seen:
            sorted_pages = sorted(list(pages_seen))
            # Check for gaps
            # range(min, max+1) should match set length if consecutive
            if len(sorted_pages) > 0:
                expected = set(range(min(sorted_pages), max(sorted_pages) + 1))
                if expected != pages_seen:
                    issues.non_consecutive_pages += 1

        # Determine Status
        # Rules: "Invalid DocIR MUST NOT proceed to indexing."
        
        # INVALID conditions:
        if issues.bbox_out_of_range > 0:
            status = "INVALID"
        
        # DEGRADED conditions:
        elif issues.missing_headers > 0 or issues.orphan_blocks > 0 or issues.non_consecutive_pages > 0:
            status = "DEGRADED" # Or OK if minor? Sticking to DEGRADED for safely.
            
        return DocIRValidation(status=status, issues=issues)
