"""
Cross-Page Table Stitching (structured).
Reconstructs tables split across pages with strict validation.
"""
import logging
from typing import List, Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class CrossPageTableStitcher:
    """
    Stitches tables split across consecutive pages.
    
    Rules:
    - Pages must be consecutive (N and N+1)
    - Column count must match
    - Header text must be highly similar (>0.85)
    - No cross-entity or cross-document merging
    """
    
    HEADER_SIMILARITY_THRESHOLD = 0.85
    MIN_COLUMN_COUNT = 2
    
    def __init__(self):
        pass
    
    def stitch_cross_page_tables(self, blocks: List) -> List:
        """
        Identify and stitch cross-page tables.
        
        Args:
            blocks: List of Block objects with block_type, page, text
        
        Returns:
            List of blocks with stitched tables marked
        """
        # Check profile
        from trust_rag.engine.ingest.context import get_current_profile
        profile = get_current_profile()
        if not profile.is_enabled("cross_page_table"):
             logger.info(f"Cross-page table stitching disabled by profile {profile.name}")
             return blocks

        # Group table blocks by page
        table_blocks_by_page = self._group_table_blocks_by_page(blocks)
        
        if not table_blocks_by_page:
            return blocks
        
        # Track stitched blocks
        stitched_blocks = []
        processed_ids = set()
        
        pages = sorted(table_blocks_by_page.keys())
        
        for i in range(len(pages) - 1):
            current_page = pages[i]
            next_page = pages[i + 1]
            
            # Only stitch consecutive pages
            if next_page != current_page + 1:
                continue
            
            current_tables = table_blocks_by_page[current_page]
            next_tables = table_blocks_by_page[next_page]
            
            if not current_tables or not next_tables:
                continue
            
            # Try to stitch last table of current page with first table of next page
            last_table = current_tables[-1]
            first_table_next = next_tables[0]
            
            # Skip if already processed
            if last_table.evidence_id in processed_ids or first_table_next.evidence_id in processed_ids:
                continue
            
            if self._should_stitch(last_table, first_table_next):
                # Create stitched block
                stitched = self._create_stitched_block(last_table, first_table_next)
                stitched_blocks.append(stitched)
                
                processed_ids.add(last_table.evidence_id)
                processed_ids.add(first_table_next.evidence_id)
                
                logger.info(f"Stitched table across pages {current_page}-{next_page}")
        
        # Add all blocks (stitched and non-stitched)
        result = []
        for block in blocks:
            if block.evidence_id in processed_ids:
                continue  # Skip original blocks that were stitched
            result.append(block)
        
        # Add stitched blocks
        result.extend(stitched_blocks)
        
        return result
    
    def _group_table_blocks_by_page(self, blocks: List) -> dict:
        """Group table blocks by page number."""
        grouped = {}
        for block in blocks:
            block_type = getattr(block, 'block_type', None) or block.metadata.get('block_type', '')
            if 'table' not in str(block_type).lower():
                continue
            
            page = block.provenance.page_number if hasattr(block, 'provenance') else 1
            if page not in grouped:
                grouped[page] = []
            grouped[page].append(block)
        
        return grouped
    
    def _should_stitch(self, table1, table2) -> bool:
        """
        Determine if two tables should be stitched.
        
        Criteria:
        1. Column count matches
        2. Header similarity > threshold
        3. Both are table blocks
        """
        text1 = table1.text if hasattr(table1, 'text') else ""
        text2 = table2.text if hasattr(table2, 'text') else ""
        
        if not text1 or not text2:
            return False
        
        # Extract headers (first line)
        lines1 = text1.strip().split('\n')
        lines2 = text2.strip().split('\n')
        
        if not lines1 or not lines2:
            return False
        
        header1 = lines1[0]
        header2 = lines2[0]
        
        # Check column count (split by | or whitespace)
        cols1 = self._extract_columns(header1)
        cols2 = self._extract_columns(header2)
        
        if len(cols1) < self.MIN_COLUMN_COUNT or len(cols2) < self.MIN_COLUMN_COUNT:
            return False
        
        if len(cols1) != len(cols2):
            return False
        
        # Check header similarity
        similarity = self._calculate_header_similarity(header1, header2)
        
        return similarity >= self.HEADER_SIMILARITY_THRESHOLD
    
    def _extract_columns(self, header: str) -> List[str]:
        """Extract column names from header."""
        # Try pipe-separated first
        if '|' in header:
            return [col.strip() for col in header.split('|') if col.strip()]
        
        # Fallback to whitespace
        return [col.strip() for col in header.split() if col.strip()]
    
    def _calculate_header_similarity(self, header1: str, header2: str) -> float:
        """Calculate similarity between two headers."""
        # Normalize
        h1 = header1.lower().strip()
        h2 = header2.lower().strip()
        
        # Use SequenceMatcher for similarity
        return SequenceMatcher(None, h1, h2).ratio()
    
    def _create_stitched_block(self, table1, table2):
        """Create a stitched table block."""
        # Combine text (skip duplicate header from table2)
        text1 = table1.text if hasattr(table1, 'text') else ""
        text2 = table2.text if hasattr(table2, 'text') else ""
        
        lines1 = text1.strip().split('\n')
        lines2 = text2.strip().split('\n')
        
        # Combine: all of table1 + table2 without header
        combined_lines = lines1 + lines2[1:] if len(lines2) > 1 else lines1
        combined_text = '\n'.join(combined_lines)
        
        # Create new block (copy from table1, update fields)
        from trust_rag.engine.ingest.models import Chunk, ChunkProvenance
        
        page1 = table1.provenance.page_number if hasattr(table1, 'provenance') else 1
        page2 = table2.provenance.page_number if hasattr(table2, 'provenance') else 1
        
        # Create new provenance
        prov = ChunkProvenance(
            doc_id=table1.provenance.doc_id,
            page_number=page1,  # Start page
            bbox=table1.provenance.bbox,
            source_path=table1.provenance.source_path,
            parser_name=table1.provenance.parser_name,
            language=table1.provenance.language,
            modality=table1.provenance.modality,
            block_index=table1.provenance.block_index
        )
        
        # Generate new evidence ID for stitched table
        from trust_rag.engine.ingest.evidence_id import generate_evidence_id
        evidence_id = generate_evidence_id(
            table1.provenance.doc_id,
            page1,
            table1.provenance.block_index,
            combined_text
        )
        
        # Create stitched block
        stitched = Chunk(
            evidence_id=evidence_id,
            text=combined_text,
            provenance=prov,
            metadata={
                "block_type": "table",
                "stitched": True,
                "page_range": [page1, page2],
                "source_tables": [table1.evidence_id, table2.evidence_id]
            }
        )
        
        return stitched
