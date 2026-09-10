"""
Semantic-aware chunking with overlap and boundary detection.
implementation note: respect document structure, maintain context.
"""
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A semantic chunk with metadata."""
    text: str
    chunk_id: str
    source_page: int
    start_char: int
    end_char: int
    semantic_type: str = "text"  # text, table, heading, list, etc.
    boundary_type: str = "none"  # paragraph, section, page, etc.
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkingConfig:
    """Configuration for semantic chunking."""
    max_chunk_size: int = 512
    min_chunk_size: int = 50
    overlap_size: int = 50
    respect_boundaries: bool = True
    preserve_tables: bool = True
    preserve_headings: bool = True
    preserve_lists: bool = True


class SmartChunker:
    """
    Semantic-aware document chunking with boundary detection and overlap.

    Features:
    - Semantic boundary detection (headings, paragraphs, sections)
    - Table preservation
    - Configurable overlap
    - Quality assessment
    """

    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.config = config or ChunkingConfig()

        # Semantic boundary patterns
        self.boundary_patterns = {
            'heading': re.compile(r'^(#{1,6}\s|\d+\.|\d+\)|\(\d+\)|[A-Z][^.!?]*:)$', re.MULTILINE),
            'table': re.compile(r'(\|.*\|.*\n)+', re.MULTILINE),
            'list': re.compile(r'^(\s*[-*+]\s|\s*\d+\.\s)', re.MULTILINE),
            'paragraph': re.compile(r'\n\s*\n', re.MULTILINE),
            'page_break': re.compile(r'={3,}|-{3,}|\*{3,}', re.MULTILINE)
        }

    def chunk_document(self, parsed_doc: Dict[str, Any]) -> List[Dict]:
        """
        Chunk a parsed document into semantic units.

        Args:
            parsed_doc: Result from PDFParser.parse()

        Returns:
            List of chunk dictionaries
        """
        pages = parsed_doc.get("pages", [])
        chunks = []

        for page_data in pages:
            page_chunks = self._chunk_page(page_data)
            chunks.extend(page_chunks)

        # Apply overlap and boundary respect
        if self.config.respect_boundaries:
            chunks = self._apply_boundary_respect(chunks)

        # Add overlap between chunks
        chunks = self._add_overlap(chunks)

        # Convert to dict format for JSON serialization
        return [chunk.__dict__ for chunk in chunks]

    def _chunk_page(self, page_data: Dict) -> List[Chunk]:
        """Chunk a single page."""
        chunks = []
        page_num = page_data.get("page_number", 1)
        text = page_data.get("text", "")
        tables = page_data.get("tables", [])

        # Handle tables separately if configured
        if self.config.preserve_tables and tables:
            for table_idx, table in enumerate(tables):
                table_text = self._table_to_text(table)
                if table_text:
                    chunk = Chunk(
                        text=table_text,
                        chunk_id=f"page_{page_num}_table_{table_idx}",
                        source_page=page_num,
                        start_char=0,  # Would need proper char positioning
                        end_char=len(table_text),
                        semantic_type="table",
                        boundary_type="table",
                        confidence=0.9
                    )
                    chunks.append(chunk)

        # Handle text content
        text_chunks = self._chunk_text(text, page_num)
        chunks.extend(text_chunks)

        return chunks

    def _chunk_text(self, text: str, page_num: int) -> List[Chunk]:
        """Chunk text content with semantic awareness."""
        if not text.strip():
            return []

        chunks = []

        # Split by semantic boundaries first
        segments = self._split_by_semantic_boundaries(text)

        char_offset = 0

        for segment_idx, segment in enumerate(segments):
            segment_text = segment["text"]
            boundary_type = segment["boundary_type"]
            semantic_type = segment["semantic_type"]

            # Further split segment if too long
            sub_chunks = self._split_long_segment(
                segment_text, page_num, char_offset, semantic_type, boundary_type
            )

            chunks.extend(sub_chunks)
            char_offset += len(segment_text)

        return chunks

    def _split_by_semantic_boundaries(self, text: str) -> List[Dict]:
        """Split text by semantic boundaries."""
        segments = []
        lines = text.split('\n')

        current_segment = []
        current_type = "text"
        current_boundary = "none"

        for line_idx, line in enumerate(lines):
            line = line.strip()

            if not line:
                # Empty line - potential paragraph boundary
                if current_segment:
                    segments.append({
                        "text": '\n'.join(current_segment),
                        "semantic_type": current_type,
                        "boundary_type": current_boundary
                    })
                    current_segment = []
                    current_type = "text"
                    current_boundary = "paragraph"
                continue

            # Check for semantic boundaries
            boundary_detected = self._detect_boundary(line)

            if boundary_detected and current_segment:
                # Save current segment
                segments.append({
                    "text": '\n'.join(current_segment),
                    "semantic_type": current_type,
                    "boundary_type": current_boundary
                })
                current_segment = [line]
                current_type = boundary_detected["semantic_type"]
                current_boundary = boundary_detected["boundary_type"]
            else:
                current_segment.append(line)

        # Add final segment
        if current_segment:
            segments.append({
                "text": '\n'.join(current_segment),
                "semantic_type": current_type,
                "boundary_type": current_boundary
            })

        return segments

    def _detect_boundary(self, line: str) -> Optional[Dict]:
        """Detect semantic boundary in a line."""
        # Check heading patterns
        if self.boundary_patterns['heading'].match(line):
            return {
                "semantic_type": "heading",
                "boundary_type": "section"
            }

        # Check table patterns
        if self.boundary_patterns['table'].search(line):
            return {
                "semantic_type": "table",
                "boundary_type": "table"
            }

        # Check list patterns
        if self.boundary_patterns['list'].match(line):
            return {
                "semantic_type": "list",
                "boundary_type": "list"
            }

        # Check page break patterns
        if self.boundary_patterns['page_break'].match(line):
            return {
                "semantic_type": "text",
                "boundary_type": "page_break"
            }

        return None

    def _split_long_segment(
        self,
        text: str,
        page_num: int,
        char_offset: int,
        semantic_type: str,
        boundary_type: str
    ) -> List[Chunk]:
        """Split a long segment into smaller chunks."""
        if len(text) <= self.config.max_chunk_size:
            return [Chunk(
                text=text,
                chunk_id=f"page_{page_num}_chunk_{char_offset}",
                source_page=page_num,
                start_char=char_offset,
                end_char=char_offset + len(text),
                semantic_type=semantic_type,
                boundary_type=boundary_type
            )]

        chunks = []
        words = text.split()
        current_chunk = []
        current_length = 0

        for word in words:
            word_length = len(word) + 1  # +1 for space

            if current_length + word_length > self.config.max_chunk_size and current_chunk:
                # Create chunk
                chunk_text = ' '.join(current_chunk)
                chunks.append(Chunk(
                    text=chunk_text,
                    chunk_id=f"page_{page_num}_chunk_{char_offset + sum(len(c.text) for c in chunks)}",
                    source_page=page_num,
                    start_char=char_offset + sum(len(c.text) for c in chunks),
                    end_char=char_offset + sum(len(c.text) for c in chunks) + len(chunk_text),
                    semantic_type=semantic_type,
                    boundary_type="split"  # Mark as artificially split
                ))

                current_chunk = [word]
                current_length = word_length
            else:
                current_chunk.append(word)
                current_length += word_length

        # Add final chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append(Chunk(
                text=chunk_text,
                chunk_id=f"page_{page_num}_chunk_{char_offset + sum(len(c.text) for c in chunks)}",
                source_page=page_num,
                start_char=char_offset + sum(len(c.text) for c in chunks),
                end_char=char_offset + sum(len(c.text) for c in chunks) + len(chunk_text),
                semantic_type=semantic_type,
                boundary_type="split"
            ))

        return chunks

    def _table_to_text(self, table: Dict) -> str:
        """Convert table structure to readable text."""
        # This is a simplified implementation
        # In production, you'd have more sophisticated table-to-text conversion

        if "data" in table:
            rows = table["data"]
            if rows:
                # Convert first few rows to text
                text_rows = []
                for row in rows[:5]:  # Limit to first 5 rows
                    if isinstance(row, list):
                        text_rows.append(" | ".join(str(cell) for cell in row))
                    else:
                        text_rows.append(str(row))

                return "\n".join(text_rows)

        return str(table)

    def _apply_boundary_respect(self, chunks: List[Chunk]) -> List[Chunk]:
        """Apply boundary respect rules to prevent splitting important units."""
        respected_chunks = []

        for chunk in chunks:
            if chunk.boundary_type in ["table", "heading", "section"]:
                # Don't split these types
                respected_chunks.append(chunk)
            elif len(chunk.text) > self.config.max_chunk_size:
                # Split but mark as boundary violation
                chunk.confidence *= 0.9  # Slight penalty
                respected_chunks.append(chunk)
            else:
                respected_chunks.append(chunk)

        return respected_chunks

    def _add_overlap(self, chunks: List[Chunk]) -> List[Chunk]:
        """Add overlap between consecutive chunks for better context."""
        if not self.config.overlap_size or len(chunks) <= 1:
            return chunks

        overlapped_chunks = [chunks[0]]  # First chunk unchanged

        for i in range(1, len(chunks)):
            current = chunks[i]
            previous = chunks[i-1]

            # Add overlap from previous chunk
            if len(previous.text) > self.config.overlap_size:
                overlap_text = previous.text[-self.config.overlap_size:]
                current.text = overlap_text + " " + current.text
                current.metadata["overlap_added"] = True
                current.metadata["overlap_source"] = previous.chunk_id

            overlapped_chunks.append(current)

        return overlapped_chunks

    def assess_chunk_quality(self, chunks: List[Chunk]) -> Dict[str, Any]:
        """Assess the quality of chunking."""
        if not chunks:
            return {"quality_score": 0.0, "issues": ["No chunks generated"]}

        total_length = sum(len(c.text) for c in chunks)
        avg_length = total_length / len(chunks)

        issues = []

        # Check average chunk size
        if avg_length < self.config.min_chunk_size:
            issues.append(f"Average chunk size ({avg_length:.1f}) below minimum ({self.config.min_chunk_size})")

        if avg_length > self.config.max_chunk_size * 1.5:
            issues.append(f"Average chunk size ({avg_length:.1f}) significantly above maximum ({self.config.max_chunk_size})")

        # Check boundary violations
        boundary_splits = sum(1 for c in chunk if c.boundary_type == "split")
        if boundary_splits > len(chunks) * 0.3:
            issues.append(f"Too many boundary violations: {boundary_splits}/{len(chunks)} chunks split across boundaries")

        # Calculate quality score
        quality_score = 1.0

        if issues:
            quality_score -= len(issues) * 0.1
            quality_score = max(0.0, quality_score)

        # Bonus for respecting boundaries
        semantic_chunks = sum(1 for c in chunks if c.semantic_type != "text")
        if semantic_chunks > 0:
            quality_score += 0.1

        quality_score = min(1.0, quality_score)

        return {
            "quality_score": quality_score,
            "total_chunks": len(chunks),
            "avg_chunk_size": avg_length,
            "semantic_chunks": semantic_chunks,
            "boundary_splits": boundary_splits,
            "issues": issues
        }

    def optimize_config(self, sample_text: str) -> ChunkingConfig:
        """Optimize chunking configuration based on sample text."""
        # Analyze sample text to determine optimal settings
        # This is a placeholder for more sophisticated optimization

        word_count = len(sample_text.split())
        avg_word_length = sum(len(word) for word in sample_text.split()) / word_count

        # Adjust max_chunk_size based on text characteristics
        optimal_size = int(512 * (avg_word_length / 5.0))  # Assume 5 chars per word is baseline

        return ChunkingConfig(
            max_chunk_size=min(1024, max(256, optimal_size)),
            overlap_size=int(optimal_size * 0.1)
        )

