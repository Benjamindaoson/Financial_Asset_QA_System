"""
Deep Document Parser - Advanced document understanding system.
Transforms documents into structured, semantic, evidence-ready representations.
"""
import os
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import re

from trust_rag.config import get_config
from trust_rag.engine.ingest.models import Chunk, ChunkProvenance, Granularity, ChunkTier

logger = logging.getLogger(__name__)


class SemanticType(Enum):
    """Semantic types for document elements."""
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    FIGURE = "figure"
    LIST = "list"
    CODE = "code"
    FORMULA = "formula"
    FOOTNOTE = "footnote"


class TableStructure(Enum):
    """Table structure confidence levels."""
    HIGH_CONFIDENCE = "high_confidence"
    MEDIUM_CONFIDENCE = "medium_confidence"
    LOW_CONFIDENCE = "low_confidence"
    STRUCTURE_LOST = "structure_lost"


@dataclass
class DocumentElement:
    """Base class for document structural elements."""
    element_id: str
    semantic_type: SemanticType
    content: str
    bbox: Optional[Tuple[float, float, float, float]] = None  # x0, y0, x1, y1
    page_number: Optional[int] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HeadingElement(DocumentElement):
    """Heading/title element with hierarchy."""
    level: int = 1  # 1=h1, 2=h2, etc.
    parent_heading: Optional[str] = None  # Parent heading element_id
    section_path: List[str] = field(default_factory=list)  # ["Chapter 1", "Section 1.2"]


@dataclass
class TableElement(DocumentElement):
    """Table element with structured data."""
    headers: List[str] = field(default_factory=list)
    rows: List[List[str]] = field(default_factory=list)
    structure_confidence: TableStructure = TableStructure.HIGH_CONFIDENCE
    table_metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_structured(self) -> bool:
        """Check if table has reliable structure."""
        return self.structure_confidence in [TableStructure.HIGH_CONFIDENCE, TableStructure.MEDIUM_CONFIDENCE]


@dataclass
class DocumentSkeleton:
    """Semantic skeleton of the entire document."""
    document_id: str
    title: Optional[str] = None
    elements: List[DocumentElement] = field(default_factory=list)
    hierarchy: Dict[str, List[str]] = field(default_factory=dict)  # element_id -> child_ids
    section_tree: Dict[str, Any] = field(default_factory=dict)  # Hierarchical section structure
    cross_page_links: List[Tuple[str, str]] = field(default_factory=list)  # (element_id1, element_id2)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceUnit:
    """Evidence-ready unit with semantic context."""
    unit_id: str
    content: str
    semantic_type: SemanticType
    source_element: DocumentElement
    section_path: List[str] = field(default_factory=list)
    confidence: float = 1.0
    evidence_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_chunk(self, doc_id: str) -> Chunk:
        """Convert to RAG chunk with provenance."""
        chunk_id = f"chunk_{self.unit_id}"

        # Determine chunk tier based on semantic type and confidence
        if self.semantic_type == SemanticType.TITLE:
            tier = ChunkTier.MACRO
        elif self.semantic_type in [SemanticType.TABLE, SemanticType.FIGURE]:
            tier = ChunkTier.BASE if self.confidence > 0.8 else ChunkTier.MICRO
        else:
            tier = ChunkTier.BASE

        # Set granularity
        if self.semantic_type in [SemanticType.TITLE, SemanticType.HEADING]:
            granularity = Granularity.COMPOSITE
        else:
            granularity = Granularity.ATOMIC

        provenance = ChunkProvenance(
            doc_id=doc_id,
            page_number=self.source_element.page_number,
            bbox=self.source_element.bbox,
            source_path=self.evidence_metadata.get('source_path', ''),
            parser_name='deep_parser',
            language='unknown',  # Will be detected
            modality='document',
            block_index=0
        )

        # Build section path for navigation
        section_path = self.section_path.copy()
        if self.semantic_type == SemanticType.TITLE and hasattr(self.source_element, 'level'):
            section_path.append(f"H{self.source_element.level}")

        chunk = Chunk(
            evidence_id=self.unit_id,
            text=self.content,
            provenance=provenance,
            granularity=granularity,
            tier=tier,
            metadata={
                'semantic_type': self.semantic_type.value,
                'section_path': section_path,
                'confidence': self.confidence,
                'source_element_id': self.source_element.element_id,
                **self.evidence_metadata
            }
        )

        return chunk


class DeepDocumentParser:
    """
    Advanced document parser that creates structured, semantic, evidence-ready representations.

    Features:
    - Structure-aware parsing with semantic element recognition
    - Cross-page structure handling (tables, headings, lists)
    - Confidence scoring and degradation handling
    - Multi-format support with unified output model
    """

    def __init__(self):
        self.config = get_config().document_processing

    def parse_document(self, file_path: str, doc_id: Optional[str] = None) -> Tuple[List[Chunk], DocumentSkeleton]:
        """
        Parse document with deep structure analysis.

        Returns:
            Tuple of (chunks, skeleton) for RAG processing and advanced analysis
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document not found: {file_path}")

        doc_type = self._detect_doc_type(file_path)

        if doc_type == "pdf":
            skeleton = self._parse_pdf_deep(file_path, doc_id or self._generate_doc_id(file_path))
        elif doc_type == "docx":
            skeleton = self._parse_docx_deep(file_path, doc_id or self._generate_doc_id(file_path))
        elif doc_type == "html":
            skeleton = self._parse_html_deep(file_path, doc_id or self._generate_doc_id(file_path))
        else:
            # Fallback to basic processing
            from trust_rag.engine.ingest.processor import DocumentProcessor
            basic_processor = DocumentProcessor()
            chunks, _ = basic_processor.process_file(file_path, doc_id)
            skeleton = DocumentSkeleton(document_id=doc_id or self._generate_doc_id(file_path))
            return chunks, skeleton

        # Convert skeleton to evidence units and chunks
        evidence_units = self._skeleton_to_evidence_units(skeleton)
        chunks = [unit.to_chunk(skeleton.document_id) for unit in evidence_units]

        return chunks, skeleton

    def _detect_doc_type(self, file_path: str) -> str:
        """Detect document type."""
        ext = Path(file_path).suffix.lower()
        ext_map = {
            '.pdf': 'pdf',
            '.docx': 'docx',
            '.html': 'html',
            '.htm': 'html'
        }
        return ext_map.get(ext, 'unknown')

    def _generate_doc_id(self, file_path: str) -> str:
        """Generate document ID."""
        filename = Path(file_path).name
        file_hash = hashlib.md5(open(file_path, 'rb').read()).hexdigest()[:8]
        return f"{filename}_{file_hash}"

    def _parse_pdf_deep(self, file_path: str, doc_id: str) -> DocumentSkeleton:
        """Deep PDF parsing with structure analysis."""
        skeleton = DocumentSkeleton(document_id=doc_id)

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)

            # Extract title from first page
            if len(doc) > 0:
                first_page = doc[0]
                text_blocks = first_page.get_text("dict")["blocks"]
                title_candidates = [b for b in text_blocks if b.get('type') == 0 and len(b.get('lines', [])) == 1]

                if title_candidates:
                    title_block = title_candidates[0]
                    title_text = "".join([span['text'] for line in title_block.get('lines', [])
                                        for span in line.get('spans', [])]).strip()
                    skeleton.title = title_text

            # Process each page
            current_heading_stack = []
            page_elements = []

            for page_num, page in enumerate(doc):
                page_elements.extend(self._parse_pdf_page(page, page_num, current_heading_stack))

            # Build cross-page relationships
            self._build_cross_page_relationships(page_elements)

            # Add elements to skeleton
            skeleton.elements = page_elements

            # Build hierarchy
            skeleton.hierarchy = self._build_element_hierarchy(page_elements)

            # Build section tree
            skeleton.section_tree = self._build_section_tree(page_elements)

            doc.close()

        except ImportError:
            logger.error("PyMuPDF not installed. Install with: pip install PyMuPDF")
            raise
        except Exception as e:
            logger.error(f"Deep PDF parsing failed: {e}")
            raise

        return skeleton

    def _parse_pdf_page(self, page, page_num: int, heading_stack: List[HeadingElement]) -> List[DocumentElement]:
        """Parse a single PDF page with structure analysis."""
        elements = []

        # Get text with layout information
        text_data = page.get_text("dict")

        # Extract text blocks with position information
        blocks = text_data["blocks"]

        current_y = 0
        for block in blocks:
            if block.get('type') == 0:  # Text block
                block_text = self._extract_text_from_block(block)

                if not block_text.strip():
                    continue

                # Determine semantic type
                semantic_type, confidence, metadata = self._classify_text_block(block_text, block)

                # Create element
                element_id = f"elem_{page_num}_{len(elements)}"

                if semantic_type in [SemanticType.TITLE, SemanticType.HEADING]:
                    # Handle heading hierarchy
                    level = self._determine_heading_level(block_text, block)
                    element = HeadingElement(
                        element_id=element_id,
                        semantic_type=semantic_type,
                        content=block_text,
                        bbox=self._extract_bbox_from_block(block),
                        page_number=page_num,
                        confidence=confidence,
                        level=level,
                        section_path=self._get_section_path(heading_stack, level)
                    )

                    # Update heading stack
                    self._update_heading_stack(heading_stack, element)

                elif semantic_type == SemanticType.TABLE:
                    # Enhanced table parsing
                    table_element = self._parse_table_from_block(block, page_num)
                    if table_element:
                        elements.append(table_element)
                        continue

                    # Fallback to text element
                    element = DocumentElement(
                        element_id=element_id,
                        semantic_type=SemanticType.PARAGRAPH,
                        content=block_text,
                        bbox=self._extract_bbox_from_block(block),
                        page_number=page_num,
                        confidence=0.5
                    )
                else:
                    element = DocumentElement(
                        element_id=element_id,
                        semantic_type=semantic_type,
                        content=block_text,
                        bbox=self._extract_bbox_from_block(block),
                        page_number=page_num,
                        confidence=confidence,
                        metadata=metadata
                    )

                elements.append(element)

        return elements

    def _parse_table_from_block(self, block, page_num: int) -> Optional[TableElement]:
        """Parse table from text block with structure preservation."""
        try:
            block_text = self._extract_text_from_block(block)

            # Simple table detection - look for tabular patterns
            lines = block_text.split('\n')
            if len(lines) < 3:  # Need at least header + data
                return None

            # Try to identify table structure
            potential_headers = []
            data_rows = []

            for i, line in enumerate(lines):
                # Look for tab-separated or space-aligned columns
                if '\t' in line:
                    columns = line.split('\t')
                else:
                    # Try to detect space-aligned columns
                    columns = re.split(r'\s{2,}', line.strip())

                if len(columns) > 1:  # Multi-column
                    if not potential_headers:
                        potential_headers = columns
                    else:
                        data_rows.append(columns)

            if len(potential_headers) > 1 and len(data_rows) > 0:
                element_id = f"table_{page_num}_{hash(block_text) % 10000}"

                # Assess structure confidence
                structure_confidence = self._assess_table_structure(potential_headers, data_rows)

                table_element = TableElement(
                    element_id=element_id,
                    semantic_type=SemanticType.TABLE,
                    content=block_text,
                    bbox=self._extract_bbox_from_block(block),
                    page_number=page_num,
                    confidence=0.8,
                    headers=potential_headers,
                    rows=data_rows,
                    structure_confidence=structure_confidence,
                    table_metadata={
                        'column_count': len(potential_headers),
                        'row_count': len(data_rows),
                        'structure_confidence': structure_confidence.value
                    }
                )

                return table_element

        except Exception as e:
            logger.debug(f"Table parsing failed for block: {e}")

        return None

    def _assess_table_structure(self, headers: List[str], rows: List[List[str]]) -> TableStructure:
        """Assess table structure confidence."""
        if not headers or not rows:
            return TableStructure.STRUCTURE_LOST

        # Check if all rows have same number of columns as headers
        header_count = len(headers)
        consistent_rows = sum(1 for row in rows if len(row) == header_count)

        consistency_ratio = consistent_rows / len(rows) if rows else 0

        if consistency_ratio >= 0.9:
            return TableStructure.HIGH_CONFIDENCE
        elif consistency_ratio >= 0.7:
            return TableStructure.MEDIUM_CONFIDENCE
        elif consistency_ratio >= 0.5:
            return TableStructure.LOW_CONFIDENCE
        else:
            return TableStructure.STRUCTURE_LOST

    def _classify_text_block(self, text: str, block) -> Tuple[SemanticType, float, Dict[str, Any]]:
        """Classify text block semantic type."""
        # Simple heuristics for semantic classification

        # Check for headings
        if self._is_heading(text, block):
            return SemanticType.HEADING, 0.9, {}

        # Check for lists
        if self._is_list(text):
            return SemanticType.LIST, 0.8, {}

        # Check for code
        if self._is_code(text):
            return SemanticType.CODE, 0.9, {}

        # Default to paragraph
        return SemanticType.PARAGRAPH, 0.7, {}

    def _is_heading(self, text: str, block) -> bool:
        """Determine if text is a heading."""
        # Font size heuristic (larger fonts are likely headings)
        if 'lines' in block:
            for line in block['lines']:
                for span in line.get('spans', []):
                    font_size = span.get('size', 12)
                    if font_size > 14:  # Larger than typical body text
                        return True

        # Text length heuristic (short lines are often headings)
        if len(text.strip()) < 100 and not text.endswith('.'):
            return True

        return False

    def _is_list(self, text: str) -> bool:
        """Check if text is a list."""
        lines = text.split('\n')
        bullet_patterns = [r'^\s*[\-\*\+]\s', r'^\s*\d+\.\s', r'^\s*\([a-zA-Z0-9]\)\s']

        bullet_lines = 0
        for line in lines[:5]:  # Check first few lines
            if any(re.match(pattern, line) for pattern in bullet_patterns):
                bullet_lines += 1

        return bullet_lines >= 2  # At least 2 bullet points

    def _is_code(self, text: str) -> bool:
        """Check if text is code."""
        # Look for code-like patterns
        code_indicators = [
            r'^\s*(def|class|if|for|while|import|from)\s',
            r'[{}();=]',
            r'function\s*\(',
            r'const\s+|let\s+|var\s+'
        ]

        code_lines = 0
        lines = text.split('\n')

        for line in lines:
            if any(re.search(pattern, line) for pattern in code_indicators):
                code_lines += 1

        return code_lines / len(lines) > 0.3 if lines else False

    def _determine_heading_level(self, text: str, block) -> int:
        """Determine heading level from font size and text patterns."""
        # Font size based levels
        if 'lines' in block:
            max_font_size = 0
            for line in block['lines']:
                for span in line.get('spans', []):
                    max_font_size = max(max_font_size, span.get('size', 12))

            if max_font_size > 18:
                return 1
            elif max_font_size > 16:
                return 2
            elif max_font_size > 14:
                return 3
            elif max_font_size > 12:
                return 4

        return 5  # Default level

    def _update_heading_stack(self, stack: List[HeadingElement], new_heading: HeadingElement):
        """Update heading hierarchy stack."""
        # Remove headings at same or deeper level
        while stack and stack[-1].level >= new_heading.level:
            stack.pop()

        # Set parent
        if stack:
            new_heading.parent_heading = stack[-1].element_id

        # Add to stack
        stack.append(new_heading)

    def _get_section_path(self, stack: List[HeadingElement], level: int) -> List[str]:
        """Get section path for current heading."""
        path = []
        for heading in stack:
            if heading.level < level:
                path.append(heading.content[:50])  # Truncate long headings
        return path

    def _build_cross_page_relationships(self, elements: List[DocumentElement]):
        """Build relationships between elements that span multiple pages."""
        # Group by semantic type
        headings = [e for e in elements if isinstance(e, HeadingElement)]
        tables = [e for e in elements if isinstance(e, TableElement)]

        # Look for continued tables
        # Look for continued tables
        table_groups = {}
        for table in tables:
            # Use headers signature for tracking same table across pages
            # Content prefix is unreliable as data changes
            if table.headers:
                # Use sorted headers to handle column reordering or minor OCR noise
                header_sig = "|".join(sorted(table.headers[:5])) # Check first 5 headers
            else:
                # Fallback to content hash if no headers
                header_sig = hashlib.md5(table.content[:200].encode('utf-8', errors='ignore')).hexdigest()
            
            key = header_sig
            if key not in table_groups:
                table_groups[key] = []
            table_groups[key].append(table)

        # Mark continued tables
        for key, group in table_groups.items():
            if len(group) > 1:
                group.sort(key=lambda x: x.page_number)
                for i in range(1, len(group)):
                    # Mark as continuation
                    group[i].metadata['continued_from'] = group[i-1].element_id
                    group[i-1].metadata['continued_to'] = group[i].element_id

    def _build_element_hierarchy(self, elements: List[DocumentElement]) -> Dict[str, List[str]]:
        """Build parent-child relationships between elements."""
        hierarchy = {}

        # Group headings by level
        headings_by_level = {}
        for element in elements:
            if isinstance(element, HeadingElement):
                level = element.level
                if level not in headings_by_level:
                    headings_by_level[level] = []
                headings_by_level[level].append(element)

        # Build hierarchy
        for element in elements:
            if isinstance(element, HeadingElement):
                # Find parent heading
                for parent_level in range(element.level - 1, 0, -1):
                    parent_candidates = headings_by_level.get(parent_level, [])
                    # Find closest parent before this element
                    for parent in reversed(parent_candidates):
                        if parent.page_number < element.page_number or \
                           (parent.page_number == element.page_number and
                            parent.bbox and element.bbox and
                            parent.bbox[1] < element.bbox[1]):  # Y position
                            hierarchy[parent.element_id] = hierarchy.get(parent.element_id, []) + [element.element_id]
                            break
                    if element.element_id in hierarchy:
                        break

        return hierarchy

    def _build_section_tree(self, elements: List[DocumentElement]) -> Dict[str, Any]:
        """Build hierarchical section tree."""
        tree = {"title": None, "sections": []}

        # Find title
        title_candidates = [e for e in elements if isinstance(e, HeadingElement) and e.level == 1]
        if title_candidates:
            tree["title"] = title_candidates[0].content

        # Build section hierarchy
        def build_section_node(heading: HeadingElement) -> Dict[str, Any]:
            node = {
                "title": heading.content,
                "level": heading.level,
                "page": heading.page_number,
                "subsections": []
            }

            # Find child headings
            child_headings = []
            for element in elements:
                if (isinstance(element, HeadingElement) and
                    element.level == heading.level + 1 and
                    element.parent_heading == heading.element_id):
                    child_headings.append(element)

            for child in child_headings:
                node["subsections"].append(build_section_node(child))

            return node

        # Find top-level sections
        top_sections = [e for e in elements if isinstance(e, HeadingElement) and e.level == 1]
        for section in top_sections:
            tree["sections"].append(build_section_node(section))

        return tree

    def _skeleton_to_evidence_units(self, skeleton: DocumentSkeleton) -> List[EvidenceUnit]:
        """Convert document skeleton to evidence units."""
        units = []

        for element in skeleton.elements:
            # Create evidence unit
            unit_id = f"ev_{element.element_id}"

            # Build section path
            section_path = []
            if hasattr(element, 'section_path'):
                section_path = element.section_path

            # Build content based on element type
            if isinstance(element, TableElement):
                content = self._table_to_evidence_content(element)
            else:
                content = element.content

            # Build evidence metadata
            evidence_metadata = {
                'source_path': skeleton.metadata.get('source_path', ''),
                'semantic_type': element.semantic_type.value,
                'confidence': element.confidence,
                'page_number': element.page_number,
                **element.metadata
            }

            unit = EvidenceUnit(
                unit_id=unit_id,
                content=content,
                semantic_type=element.semantic_type,
                source_element=element,
                section_path=section_path,
                confidence=element.confidence,
                evidence_metadata=evidence_metadata
            )

            units.append(unit)

        return units

    def _table_to_evidence_content(self, table: TableElement) -> str:
        """Convert table to evidence-ready text content."""
        if table.structure_confidence == TableStructure.HIGH_CONFIDENCE:
            # Structured representation
            content_lines = []

            # Add headers
            if table.headers:
                content_lines.append(" | ".join(table.headers))
                content_lines.append("-" * len(content_lines[-1]))

            # Add rows
            for row in table.rows:
                if len(row) == len(table.headers):
                    content_lines.append(" | ".join(row))
                else:
                    content_lines.append(" | ".join(row))

            return "\n".join(content_lines)

        elif table.structure_confidence == TableStructure.MEDIUM_CONFIDENCE:
            # Semi-structured with warnings
            content = f"[Medium confidence table structure]\n{table.content}"
            return content

        else:
            # Low confidence - mark as unstructured
            content = f"[Low confidence table - structure may be incorrect]\n{table.content}"
            return content

    # Utility methods
    def _extract_text_from_block(self, block) -> str:
        """Extract text from PDF text block."""
        text_parts = []
        for line in block.get('lines', []):
            for span in line.get('spans', []):
                text_parts.append(span.get('text', ''))
        return ''.join(text_parts)

    def _extract_bbox_from_block(self, block) -> Optional[Tuple[float, float, float, float]]:
        """Extract bounding box from PDF block."""
        if 'bbox' in block:
            return tuple(block['bbox'])
        return None

    # Placeholder methods for other document types - will be enhanced
    def _parse_docx_deep(self, file_path: str, doc_id: str) -> DocumentSkeleton:
        """Deep DOCX parsing with structure analysis."""
        skeleton = DocumentSkeleton(document_id=doc_id)
        
        try:
            import docx
            from docx.document import Document
            from docx.text.paragraph import Paragraph
            from docx.table import Table
            from docx.oxml.text.paragraph import CT_P
            from docx.oxml.table import CT_Tbl
        except ImportError:
            logger.error("python-docx not installed. Install with: pip install python-docx")
            raise

        try:
            doc = docx.Document(file_path)
            
            # Extract title (simplified)
            if doc.core_properties.title:
                skeleton.title = doc.core_properties.title
            
            elements = []
            heading_stack = []
            
            def iter_block_items(parent):
                if isinstance(parent, Document):
                    parent_elm = parent.element.body
                elif isinstance(parent, _Cell):
                    parent_elm = parent._tc
                else:
                    raise ValueError("something's not right")

                for child in parent_elm.iterchildren():
                    if isinstance(child, CT_P):
                        yield Paragraph(child, parent)
                    elif isinstance(child, CT_Tbl):
                        yield Table(child, parent)
            
            # Iterate through elements in order
            for i, block in enumerate(iter_block_items(doc)):
                element_id = f"elem_docx_{i}"
                
                if isinstance(block, Paragraph):
                    text = block.text.strip()
                    if not text:
                        continue
                        
                    # Determine style
                    style_name = block.style.name.lower() if block.style else ""
                    
                    if 'heading' in style_name:
                        try:
                            level = int(style_name.replace('heading', '').strip())
                        except:
                            level = 1
                            
                        element = HeadingElement(
                            element_id=element_id,
                            semantic_type=SemanticType.HEADING,
                            content=text,
                            page_number=1, # DOCX is flowable, page numbers hard without renderer
                            level=level,
                            confidence=1.0
                        )
                        self._update_heading_stack(heading_stack, element)
                        elements.append(element)
                        
                    elif 'list' in style_name:
                        element = DocumentElement(
                            element_id=element_id,
                            semantic_type=SemanticType.LIST,
                            content=text,
                            page_number=1
                        )
                        elements.append(element)
                    else:
                        element = DocumentElement(
                            element_id=element_id,
                            semantic_type=SemanticType.PARAGRAPH,
                            content=text,
                            page_number=1
                        )
                        elements.append(element)
                        
                elif isinstance(block, Table):
                    # Extract table data
                    rows = []
                    headers = []
                    
                    for r_idx, row in enumerate(block.rows):
                        row_data = [cell.text.strip() for cell in row.cells]
                        if r_idx == 0:
                            headers = row_data
                        rows.append(row_data)
                        
                    if rows:
                        # Serialize content
                        content = "\n".join([" | ".join(row) for row in rows])
                        
                        element = TableElement(
                            element_id=element_id,
                            semantic_type=SemanticType.TABLE,
                            content=content,
                            page_number=1,
                            headers=headers,
                            rows=rows,
                            structure_confidence=TableStructure.HIGH_CONFIDENCE
                        )
                        elements.append(element)
            
            skeleton.elements = elements
            skeleton.hierarchy = self._build_element_hierarchy(elements)
            skeleton.section_tree = self._build_section_tree(elements)
            
        except Exception as e:
            logger.error(f"DOCX parsing failed: {e}")
            raise

        return skeleton

    def _parse_html_deep(self, file_path: str, doc_id: str) -> DocumentSkeleton:
        """Deep HTML parsing with structure analysis."""
        skeleton = DocumentSkeleton(document_id=doc_id)
        
        try:
            from bs4 import BeautifulSoup
            import bs4
        except ImportError:
            logger.error("beautifulsoup4 not installed. Install with: pip install beautifulsoup4")
            raise

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f, 'html.parser')
                
            if self.config.html_remove_scripts:
                for script in soup(["script", "style"]):
                    script.decompose()
            
            if soup.title:
                skeleton.title = soup.title.string
                
            elements = []
            heading_stack = []
            
            # Linear traversal of relevant tags
            doc_tags = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul', 'ol', 'table'])
            
            for i, tag in enumerate(doc_tags):
                element_id = f"elem_html_{i}"
                text = tag.get_text().strip()
                
                if not text and tag.name != 'table':
                    continue
                    
                if tag.name.startswith('h'):
                    level = int(tag.name[1])
                    element = HeadingElement(
                        element_id=element_id,
                        semantic_type=SemanticType.HEADING,
                        content=text,
                        page_number=1,
                        level=level,
                        confidence=1.0
                    )
                    self._update_heading_stack(heading_stack, element)
                    elements.append(element)
                    
                elif tag.name == 'table':
                    # Parse table
                    headers = []
                    rows = []
                    
                    # Parse headers
                    thead = tag.find('thead')
                    if thead:
                        headers = [th.get_text().strip() for th in thead.find_all('th')]
                    else:
                        # Try first row as header if no thead
                        first_row = tag.find('tr')
                        if first_row:
                            headers = [th.get_text().strip() for th in first_row.find_all(['th', 'td'])]
                    
                    # Parse rows
                    tbody = tag.find('tbody') or tag
                    for tr in tbody.find_all('tr'):
                        row_data = [td.get_text().strip() for td in tr.find_all(['td', 'th'])]
                        if row_data:
                            rows.append(row_data)
                            
                    content = "\n".join([" | ".join(row) for row in rows])
                    
                    element = TableElement(
                        element_id=element_id,
                        semantic_type=SemanticType.TABLE,
                        content=content,
                        page_number=1,
                        headers=headers,
                        rows=rows,
                        structure_confidence=TableStructure.HIGH_CONFIDENCE
                    )
                    elements.append(element)
                    
                elif tag.name in ['ul', 'ol']:
                    element = DocumentElement(
                        element_id=element_id,
                        semantic_type=SemanticType.LIST,
                        content=text,
                        page_number=1
                    )
                    elements.append(element)
                    
                else: # p
                    element = DocumentElement(
                        element_id=element_id,
                        semantic_type=SemanticType.PARAGRAPH,
                        content=text,
                        page_number=1
                    )
                    elements.append(element)

            skeleton.elements = elements
            skeleton.hierarchy = self._build_element_hierarchy(elements)
            skeleton.section_tree = self._build_section_tree(elements)
            
        except Exception as e:
            logger.error(f"HTML parsing failed: {e}")
            raise

        return skeleton

