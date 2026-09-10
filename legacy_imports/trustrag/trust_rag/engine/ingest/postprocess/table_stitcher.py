"""
Cross-Page Table Stitching Module.
Reconstructs tables split across multiple pages into logical TableArtifacts.
"""
import logging
import hashlib
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class TableArtifact(BaseModel):
    """Logical table artifact (potentially cross-page)."""
    table_id: str
    rows: List[List[str]]
    cols: List[str]
    source_pages: List[int]
    evidence_ids: List[str]
    bbox_span: Optional[Dict] = None  # {min_page, max_page, bbox}
    metadata: Dict = {}

class TableStitcher:
    """
    Stitches tables split across pages into logical units.
    """
    
    BBOX_OVERLAP_THRESHOLD = 0.8  # 80% horizontal overlap required
    HEADER_SIMILARITY_THRESHOLD = 0.7  # 70% text similarity
    
    def __init__(self):
        pass
    
    def stitch_tables(self, blocks: List) -> List[TableArtifact]:
        """
        Stitch cross-page tables from blocks.
        
        Args:
            blocks: List of Block objects with block_type, page, bbox, text
        
        Returns:
            List of TableArtifact objects
        """
        # Group table blocks by page
        table_blocks_by_page = self._group_table_blocks_by_page(blocks)
        
        if not table_blocks_by_page:
            return []
        
        # Stitch across pages
        stitched_tables = []
        pages = sorted(table_blocks_by_page.keys())
        
        i = 0
        while i < len(pages):
            current_page = pages[i]
            current_tables = table_blocks_by_page[current_page]
            
            # Try to merge with next page
            merged = False
            if i + 1 < len(pages):
                next_page = pages[i + 1]
                next_tables = table_blocks_by_page[next_page]
                
                # Check if last table on current page continues to first table on next page
                if current_tables and next_tables:
                    last_table = current_tables[-1]
                    first_table_next = next_tables[0]
                    
                    if self._should_merge(last_table, first_table_next):
                        # Merge
                        merged_artifact = self._merge_tables(last_table, first_table_next)
                        stitched_tables.append(merged_artifact)
                        merged = True
                        
                        # Remove merged tables from groups
                        current_tables.pop()
                        next_tables.pop(0)
            
            # Add remaining tables from current page
            for table_block in current_tables:
                artifact = self._block_to_artifact(table_block)
                stitched_tables.append(artifact)
            
            i += 1
        
        logger.info(f"Stitched {len(stitched_tables)} tables from {len(blocks)} blocks")
        return stitched_tables
    
    def _group_table_blocks_by_page(self, blocks: List) -> Dict[int, List]:
        """Group table blocks by page number."""
        grouped = {}
        for block in blocks:
            # Check if block is a table
            block_type = getattr(block, 'block_type', None) or block.metadata.get('block_type', '')
            if 'table' not in str(block_type).lower():
                continue
            
            page = block.provenance.page_number if hasattr(block, 'provenance') else 1
            if page not in grouped:
                grouped[page] = []
            grouped[page].append(block)
        
        return grouped
    
    def _should_merge(self, table1, table2) -> bool:
        """Check if two tables should be merged."""
        # Check bbox horizontal overlap
        bbox1 = table1.provenance.bbox if hasattr(table1, 'provenance') else None
        bbox2 = table2.provenance.bbox if hasattr(table2, 'provenance') else None
        
        if bbox1 and bbox2:
            overlap = self._calculate_horizontal_overlap(bbox1, bbox2)
            if overlap < self.BBOX_OVERLAP_THRESHOLD:
                return False
        
        # Check header similarity (first row)
        text1 = table1.text if hasattr(table1, 'text') else ""
        text2 = table2.text if hasattr(table2, 'text') else ""
        
        # Extract first line as header
        header1 = text1.split('\n')[0] if text1 else ""
        header2 = text2.split('\n')[0] if text2 else ""
        
        similarity = self._text_similarity(header1, header2)
        
        return similarity >= self.HEADER_SIMILARITY_THRESHOLD
    
    def _calculate_horizontal_overlap(self, bbox1: Tuple, bbox2: Tuple) -> float:
        """Calculate horizontal overlap ratio between two bboxes."""
        x1_min, _, x1_max, _ = bbox1
        x2_min, _, x2_max, _ = bbox2
        
        # Calculate overlap
        overlap_start = max(x1_min, x2_min)
        overlap_end = min(x1_max, x2_max)
        
        if overlap_end <= overlap_start:
            return 0.0
        
        overlap_width = overlap_end - overlap_start
        min_width = min(x1_max - x1_min, x2_max - x2_min)
        
        return overlap_width / min_width if min_width > 0 else 0.0
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """Simple text similarity (Jaccard)."""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        return len(intersection) / len(union) if union else 0.0
    
    def _merge_tables(self, table1, table2) -> TableArtifact:
        """Merge two table blocks into one artifact."""
        # Combine text
        text1 = table1.text if hasattr(table1, 'text') else ""
        text2 = table2.text if hasattr(table2, 'text') else ""
        
        # Parse rows (simple split by newline)
        rows1 = [line.split('|') for line in text1.split('\n') if line.strip()]
        rows2 = [line.split('|') for line in text2.split('\n') if line.strip()]
        
        # Merge (skip header from table2)
        all_rows = rows1 + rows2[1:] if len(rows2) > 1 else rows1
        
        # Extract columns from first row
        cols = rows1[0] if rows1 else []
        
        # Generate stable table_id
        combined_text = text1 + text2
        table_id = f"table_{hashlib.sha256(combined_text.encode()).hexdigest()[:16]}"
        
        # Collect evidence IDs
        evidence_ids = []
        if hasattr(table1, 'evidence_id'):
            evidence_ids.append(table1.evidence_id)
        if hasattr(table2, 'evidence_id'):
            evidence_ids.append(table2.evidence_id)
        
        # Collect pages
        page1 = table1.provenance.page_number if hasattr(table1, 'provenance') else 1
        page2 = table2.provenance.page_number if hasattr(table2, 'provenance') else 1
        
        return TableArtifact(
            table_id=table_id,
            rows=all_rows,
            cols=cols,
            source_pages=[page1, page2],
            evidence_ids=evidence_ids,
            metadata={"stitched": True}
        )
    
    def _block_to_artifact(self, block) -> TableArtifact:
        """Convert single table block to artifact."""
        text = block.text if hasattr(block, 'text') else ""
        rows = [line.split('|') for line in text.split('\n') if line.strip()]
        cols = rows[0] if rows else []
        
        table_id = f"table_{hashlib.sha256(text.encode()).hexdigest()[:16]}"
        page = block.provenance.page_number if hasattr(block, 'provenance') else 1
        evidence_id = block.evidence_id if hasattr(block, 'evidence_id') else ""
        
        return TableArtifact(
            table_id=table_id,
            rows=rows,
            cols=cols,
            source_pages=[page],
            evidence_ids=[evidence_id] if evidence_id else [],
            metadata={"stitched": False}
        )
