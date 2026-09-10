"""
Chart Weak Semantics Extraction (NO CV).
Extracts structural information from charts without visual inference.
"""
import logging
import re
import hashlib
from typing import List, Dict, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ChartBlock(BaseModel):
    """Chart block with weak semantics."""
    chart_id: str
    block_type: str = "chart"
    chart_title: Optional[str] = None
    axis_x: Optional[str] = None
    axis_y: Optional[str] = None
    legend_items: List[str] = []
    ocr_text: str = ""
    page_number: int
    evidence_id: str
    metadata: Dict = {}

class ChartWeakSemantics:
    """
    Extracts weak semantics from charts using OCR text only.
    
    STRICT Rules:
    - NO CV inference
    - NO trend prediction
    - NO numerical fitting
    - ONLY structural extraction (title, axes, legend)
    """
    
    def __init__(self):
        pass
    
    def extract_chart_semantics(self, blocks: List) -> List[ChartBlock]:
        """
        Extract chart semantics from figure/image blocks.
        
        Args:
            blocks: List of Block objects with block_type=figure/image/chart
        
        Returns:
            List of ChartBlock objects
        """
        chart_blocks = []
        
        # Check profile
        from trust_rag.engine.ingest.context import get_current_profile
        if not get_current_profile().is_enabled("chart_weak_semantics"):
             return [] # Return empty list if disabled
        
        for block in blocks:
            block_type = self._get_block_type(block)
            
            if block_type not in ["figure", "image", "chart"]:
                continue
            
            chart_block = self._extract_single_chart(block)
            if chart_block:
                chart_blocks.append(chart_block)
        
        logger.info(f"Extracted {len(chart_blocks)} chart blocks")
        return chart_blocks
    
    def _get_block_type(self, block) -> str:
        """Get block type."""
        block_type = getattr(block, 'block_type', None) or block.metadata.get('block_type', '')
        return str(block_type).lower()
    
    def _extract_single_chart(self, block) -> Optional[ChartBlock]:
        """Extract semantics from single chart block."""
        # Get OCR text
        ocr_text = block.text if hasattr(block, 'text') else ""
        
        if not ocr_text or len(ocr_text) < 5:
            return None
        
        # Extract components
        chart_title = self._extract_title(ocr_text, block)
        axis_x = self._extract_axis_label(ocr_text, "x")
        axis_y = self._extract_axis_label(ocr_text, "y")
        legend_items = self._extract_legend(ocr_text)
        
        # Generate chart ID
        chart_id = f"chart_{hashlib.sha256(ocr_text.encode()).hexdigest()[:16]}"
        
        # Get metadata
        page = block.provenance.page_number if hasattr(block, 'provenance') else 1
        evidence_id = block.evidence_id if hasattr(block, 'evidence_id') else ""
        
        return ChartBlock(
            chart_id=chart_id,
            chart_title=chart_title,
            axis_x=axis_x,
            axis_y=axis_y,
            legend_items=legend_items,
            ocr_text=ocr_text,
            page_number=page,
            evidence_id=evidence_id,
            metadata={
                "caption": block.metadata.get("caption", "") if hasattr(block, 'metadata') else ""
            }
        )
    
    def _extract_title(self, text: str, block) -> Optional[str]:
        """Extract chart title."""
        # Try caption first
        if hasattr(block, 'metadata') and 'caption' in block.metadata:
            caption = block.metadata['caption']
            if caption and len(caption) > 3:
                return caption.strip()
        
        # Try to find title in OCR text
        lines = text.strip().split('\n')
        
        # First non-empty line is often the title
        for line in lines:
            line = line.strip()
            if len(line) > 5 and not self._is_axis_label(line):
                return line
        
        return None
    
    def _extract_axis_label(self, text: str, axis: str) -> Optional[str]:
        """Extract axis label (x or y)."""
        # Common patterns
        patterns = [
            rf'{axis}[-\s]?axis[:\s]+([^\n,]+)',
            rf'{axis}[:\s]+([^\n,]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                label = match.group(1).strip()
                if len(label) > 1 and len(label) < 50:
                    return label
        
        return None
    
    def _extract_legend(self, text: str) -> List[str]:
        """Extract legend items."""
        legend_items = []
        
        # Look for legend pattern
        legend_match = re.search(r'legend[:\s]+([^\n]+)', text, re.IGNORECASE)
        if legend_match:
            items_str = legend_match.group(1)
            items = [item.strip() for item in items_str.split(',') if item.strip()]
            legend_items.extend(items[:10])  # Max 10 items
        
        return legend_items
    
    def _is_axis_label(self, line: str) -> bool:
        """Check if line is an axis label."""
        line_lower = line.lower()
        return 'axis' in line_lower or line_lower.startswith('x:') or line_lower.startswith('y:')
