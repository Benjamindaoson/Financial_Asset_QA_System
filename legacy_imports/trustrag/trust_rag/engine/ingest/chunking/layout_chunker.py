"""
Layout-Aware Chunking Module (structured).
Creates chunks based on layout structure with STRICT block-type separation.
"""
import logging
import hashlib
from typing import List, Dict, Literal, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class LayoutChunk(BaseModel):
    """Layout-aware chunk."""
    chunk_id: str
    chunk_type: Literal["table", "figure", "text", "title"]
    text: str
    section_path: List[str]  # ["Introduction", "Results", "Subsection"]
    layout_span: Dict  # {pages: [1,2], bbox: ...}
    evidence_ids: List[str]
    chunk_strategy: str = "layout_aware"  # NEW: marks strategy used
    source_block_ids: List[str] = []  # NEW: tracks source blocks
    metadata: Dict = {}

class LayoutChunker:
    """
    Creates layout-aware chunks from blocks.
    
    STRICT Rules:
    1. NO cross-block-type mixing (title/paragraph/table/ocr_block separate)
    2. Bbox-based spatial merging (same page, vertical distance < threshold, same hierarchy)
    3. Table blocks ALWAYS isolated (no merging with text)
    4. Title blocks separate from paragraphs
    """
    
    MAX_TEXT_TOKENS = 512  # Approximate token limit for text chunks
    VERTICAL_DISTANCE_THRESHOLD = 50  # pixels
    
    def __init__(self):
        pass
    
    def chunk(
        self, 
        blocks: List,
        table_artifacts: List = None,
        figure_artifacts: List = None
    ) -> List[LayoutChunk]:
        """
        Create layout-aware chunks with STRICT block-type separation.
        
        Args:
            blocks: List of Block objects
            table_artifacts: Optional list of TableArtifact (from stitcher)
            figure_artifacts: Optional list of FigureArtifact (from interpreter)
        
        Returns:
            List of LayoutChunk objects
        """
        chunks = []
        
        # Track which blocks are already chunked (tables/figures)
        chunked_evidence_ids = set()
        
        # 1. Create table chunks (ISOLATED)
        if table_artifacts:
            for table_art in table_artifacts:
                chunk = self._table_to_chunk(table_art)
                chunks.append(chunk)
                chunked_evidence_ids.update(table_art.evidence_ids)
        
        # 2. Create figure chunks
        if figure_artifacts:
            for fig_art in figure_artifacts:
                chunk = self._figure_to_chunk(fig_art)
                chunks.append(chunk)
                chunked_evidence_ids.update(fig_art.evidence_ids)
        
        # 3. Separate blocks by type
        remaining_blocks = [b for b in blocks if b.evidence_id not in chunked_evidence_ids]
        
        title_blocks = []
        text_blocks = []
        table_blocks = []
        
        # Get Profile
        from trust_rag.engine.ingest.context import get_current_profile
        profile = get_current_profile()
        title_isolation_enabled = profile.is_enabled("title_isolation")

        for block in remaining_blocks:
            block_type = self._get_block_type(block)
            
            if block_type == "title" and title_isolation_enabled:
                title_blocks.append(block)
            elif block_type == "table":
                table_blocks.append(block)
            else:
                # If title isolation is disabled, titles become text
                text_blocks.append(block)
        
        # 4. Chunk titles (each title = 1 chunk, NO merging)
        for title_block in title_blocks:
            chunk = self._create_single_block_chunk(title_block, "title")
            chunks.append(chunk)
        
        # 5. Chunk tables (each table = 1 chunk, NO merging)
        for table_block in table_blocks:
            chunk = self._create_single_block_chunk(table_block, "table")
            chunks.append(chunk)
        
        # 6. Chunk text with spatial awareness
        text_chunks = self._chunk_text_blocks_spatial(text_blocks)
        chunks.extend(text_chunks)
        
        logger.info(f"Created {len(chunks)} layout-aware chunks "
                   f"({sum(1 for c in chunks if c.chunk_type=='table')} tables, "
                   f"{sum(1 for c in chunks if c.chunk_type=='figure')} figures, "
                   f"{sum(1 for c in chunks if c.chunk_type=='title')} titles, "
                   f"{sum(1 for c in chunks if c.chunk_type=='text')} text)")
        
        return chunks
    
    def _get_block_type(self, block) -> str:
        """Extract block type from block."""
        block_type = getattr(block, 'block_type', None) or block.metadata.get('block_type', 'text')
        block_type_str = str(block_type).lower()
        
        if 'title' in block_type_str or 'heading' in block_type_str:
            return "title"
        elif 'table' in block_type_str:
            return "table"
        elif 'figure' in block_type_str or 'image' in block_type_str:
            return "figure"
        else:
            return "text"
    
    def _table_to_chunk(self, table_art) -> LayoutChunk:
        """Convert TableArtifact to LayoutChunk."""
        # Flatten table to text
        text_lines = []
        if table_art.cols:
            text_lines.append(" | ".join(table_art.cols))
        for row in table_art.rows:
            text_lines.append(" | ".join(row))
        
        text = "\n".join(text_lines)
        
        return LayoutChunk(
            chunk_id=table_art.table_id,
            chunk_type="table",
            text=text,
            section_path=[],
            layout_span={
                "pages": table_art.source_pages,
                "bbox": table_art.bbox_span
            },
            evidence_ids=table_art.evidence_ids,
            chunk_strategy="layout_aware",
            source_block_ids=table_art.evidence_ids,
            metadata={
                "rows": len(table_art.rows),
                "cols": len(table_art.cols),
                "stitched": table_art.metadata.get("stitched", False)
            }
        )
    
    def _figure_to_chunk(self, fig_art) -> LayoutChunk:
        """Convert FigureArtifact to LayoutChunk."""
        text_parts = [fig_art.semantic_summary]
        
        if fig_art.axis_labels:
            text_parts.append(f"Axes: {fig_art.axis_labels}")
        if fig_art.legend_text:
            text_parts.append(f"Legend: {', '.join(fig_art.legend_text)}")
        
        text = "\n".join(text_parts)
        
        return LayoutChunk(
            chunk_id=fig_art.figure_id,
            chunk_type="figure",
            text=text,
            section_path=[],
            layout_span={
                "pages": [fig_art.source_page],
                "bbox": None
            },
            evidence_ids=fig_art.evidence_ids,
            chunk_strategy="layout_aware",
            source_block_ids=fig_art.evidence_ids,
            metadata={
                "figure_type": fig_art.figure_type,
                "caption": fig_art.metadata.get("caption", "")
            }
        )
    
    def _create_single_block_chunk(self, block, chunk_type: str) -> LayoutChunk:
        """Create chunk from single block (title or table)."""
        text = block.text if hasattr(block, 'text') else ""
        chunk_id = f"{chunk_type}_{hashlib.sha256(text.encode()).hexdigest()[:16]}"
        
        page = block.provenance.page_number if hasattr(block, 'provenance') else 1
        bbox = block.provenance.bbox if hasattr(block, 'provenance') else None
        
        return LayoutChunk(
            chunk_id=chunk_id,
            chunk_type=chunk_type,
            text=text,
            section_path=self._extract_section_path(block),
            layout_span={"pages": [page], "bbox": bbox},
            evidence_ids=[block.evidence_id] if hasattr(block, 'evidence_id') else [],
            chunk_strategy="layout_aware",
            source_block_ids=[block.evidence_id] if hasattr(block, 'evidence_id') else [],
            metadata={"block_type": chunk_type}
        )
    
    def _chunk_text_blocks_spatial(self, blocks: List) -> List[LayoutChunk]:
        """Chunk text blocks with spatial awareness (bbox-based merging)."""
        if not blocks:
            return []
        
        chunks = []
        
        # Group by page first
        blocks_by_page = {}
        for block in blocks:
            page = block.provenance.page_number if hasattr(block, 'provenance') else 1
            if page not in blocks_by_page:
                blocks_by_page[page] = []
            blocks_by_page[page].append(block)
        
        # Process each page
        for page, page_blocks in sorted(blocks_by_page.items()):
            # Sort by vertical position (top to bottom)
            sorted_blocks = self._sort_blocks_by_position(page_blocks)
            
            # Merge spatially close blocks
            merged_groups = self._merge_spatially_close(sorted_blocks)
            
            # Create chunks from merged groups
            for group in merged_groups:
                chunk = self._create_text_chunk_from_group(group)
                chunks.append(chunk)
        
        return chunks
    
    def _sort_blocks_by_position(self, blocks: List) -> List:
        """Sort blocks by vertical position (top to bottom)."""
        def get_y_position(block):
            if hasattr(block, 'provenance') and block.provenance.bbox:
                return block.provenance.bbox[1]  # y1 (top)
            return 0
        
        return sorted(blocks, key=get_y_position)
    
    def _merge_spatially_close(self, blocks: List) -> List[List]:
        """Merge blocks that are spatially close."""
        if not blocks:
            return []
        
        groups = []
        current_group = [blocks[0]]
        
        for i in range(1, len(blocks)):
            prev_block = blocks[i-1]
            curr_block = blocks[i]
            
            # Check if should merge
            if self._should_merge_spatial(prev_block, curr_block):
                current_group.append(curr_block)
            else:
                # Start new group
                groups.append(current_group)
                current_group = [curr_block]
        
        # Add last group
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _should_merge_spatial(self, block1, block2) -> bool:
        """Check if two blocks should be merged based on spatial proximity."""
        # Check profile
        from trust_rag.engine.ingest.context import get_current_profile
        if not get_current_profile().is_enabled("free_text_merge"):
            return False

        # Must be same page
        page1 = block1.provenance.page_number if hasattr(block1, 'provenance') else 1
        page2 = block2.provenance.page_number if hasattr(block2, 'provenance') else 1
        
        if page1 != page2:
            return False
        
        # Check vertical distance
        if hasattr(block1, 'provenance') and hasattr(block2, 'provenance'):
            bbox1 = block1.provenance.bbox
            bbox2 = block2.provenance.bbox
            
            if bbox1 and bbox2:
                # Distance = top of block2 - bottom of block1
                distance = bbox2[1] - bbox1[3]
                
                if distance > self.VERTICAL_DISTANCE_THRESHOLD:
                    return False
        
        # Check token limit
        text1 = block1.text if hasattr(block1, 'text') else ""
        text2 = block2.text if hasattr(block2, 'text') else ""
        combined_tokens = (len(text1) + len(text2)) // 4
        
        if combined_tokens > self.MAX_TEXT_TOKENS:
            return False
        
        return True
    
    def _create_text_chunk_from_group(self, blocks: List) -> LayoutChunk:
        """Create text chunk from group of blocks."""
        texts = [b.text for b in blocks if hasattr(b, 'text') and b.text]
        combined_text = "\n\n".join(texts)
        
        chunk_id = f"text_{hashlib.sha256(combined_text.encode()).hexdigest()[:16]}"
        
        evidence_ids = [b.evidence_id for b in blocks if hasattr(b, 'evidence_id')]
        
        pages = list(set(
            b.provenance.page_number for b in blocks 
            if hasattr(b, 'provenance') and hasattr(b.provenance, 'page_number')
        ))
        
        section_path = self._extract_section_path(blocks[0]) if blocks else []
        
        return LayoutChunk(
            chunk_id=chunk_id,
            chunk_type="text",
            text=combined_text,
            section_path=section_path,
            layout_span={"pages": sorted(pages), "bbox": None},
            evidence_ids=evidence_ids,
            chunk_strategy="layout_aware",
            source_block_ids=evidence_ids,
            metadata={"block_count": len(blocks)}
        )
    
    def _extract_section_path(self, block) -> List[str]:
        """Extract section hierarchy from block."""
        if hasattr(block, 'hierarchy_path'):
            return block.hierarchy_path
        
        if hasattr(block, 'metadata') and 'section' in block.metadata:
            return [block.metadata['section']]
        
        return ["main"]
