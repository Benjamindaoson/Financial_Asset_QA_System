"""
Advanced Intelligent Document Chunking.
Uses semantic understanding, sliding windows, and overlap strategies.
"""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
import hashlib

from trust_rag.engine.ingest.models import Chunk, ChunkProvenance, Granularity, ChunkTier

logger = logging.getLogger(__name__)


class ChunkingStrategy(Enum):
    """Document chunking strategies."""
    FIXED_SIZE = "fixed_size"
    SEMANTIC = "semantic"
    SLIDING_WINDOW = "sliding_window"
    HYBRID = "hybrid"


@dataclass
class ChunkingConfig:
    """Configuration for intelligent chunking."""
    strategy: ChunkingStrategy = ChunkingStrategy.HYBRID
    max_chunk_size: int = 1000  # Characters
    min_chunk_size: int = 200   # Characters
    overlap_size: int = 100     # Characters for sliding window
    preserve_structure: bool = True
    semantic_boundaries: List[str] = None  # Section headers, etc.

    def __post_init__(self):
        if self.semantic_boundaries is None:
            self.semantic_boundaries = [
                r'^#{1,6}\s',  # Markdown headers
                r'^\d+\.',     # Numbered sections
                r'^Chapter\s+\d+',
                r'^Section\s+\d+',
                r'^Part\s+\d+',
                r'^\u4e00-\u9fff{2,}',  # Chinese section headers (simplified)
            ]


class DocumentStructureAnalyzer:
    """
    Analyze document structure for intelligent chunking.
    """

    def __init__(self):
        self.section_patterns = [
            # English patterns
            (r'^#{1,6}\s+.+$', 'header'),
            (r'^\d+\.?\s+[A-Z]', 'numbered_section'),
            (r'^Chapter\s+\d+:', 'chapter'),
            (r'^Section\s+\d+:', 'section'),
            (r'^Part\s+\d+:', 'part'),
            (r'^Abstract$', 'abstract'),
            (r'^Introduction$', 'introduction'),
            (r'^Conclusion', 'conclusion'),
            (r'^References?$', 'references'),

            # Chinese patterns
            (r'^\d+\.\s*[\u4e00-\u9fff]', 'numbered_section_zh'),
            (r'^第[一二三四五六七八九十]+章', 'chapter_zh'),
            (r'^第[一二三四五六七八九十]+节', 'section_zh'),
            (r'^摘要$', 'abstract_zh'),
            (r'^引言$', 'introduction_zh'),
            (r'^结论', 'conclusion_zh'),
            (r'^参考文献', 'references_zh'),
        ]

    def analyze_structure(self, text: str) -> Dict[str, Any]:
        """Analyze document structure."""
        lines = text.split('\n')
        structure = {
            'sections': [],
            'boundaries': [],
            'hierarchy': {},
            'content_blocks': []
        }

        current_section = None
        current_content = []
        section_stack = []

        for i, line in enumerate(lines):
            line = line.strip()

            # Check for section boundaries
            section_type = self._classify_line(line)

            if section_type:
                # Save previous section
                if current_section and current_content:
                    structure['content_blocks'].append({
                        'section': current_section,
                        'content': '\n'.join(current_content),
                        'start_line': current_section['line_number'],
                        'end_line': i-1
                    })

                # Start new section
                current_section = {
                    'title': line,
                    'type': section_type,
                    'line_number': i,
                    'level': self._determine_level(line, section_type)
                }

                # Update hierarchy
                self._update_hierarchy(structure['hierarchy'], current_section, section_stack)

                structure['sections'].append(current_section)
                structure['boundaries'].append(i)

                current_content = []

                # Update section stack
                while section_stack and section_stack[-1]['level'] >= current_section['level']:
                    section_stack.pop()
                section_stack.append(current_section)

            else:
                if current_section:
                    current_content.append(line)

        # Add final section
        if current_section and current_content:
            structure['content_blocks'].append({
                'section': current_section,
                'content': '\n'.join(current_content),
                'start_line': current_section['line_number'],
                'end_line': len(lines)-1
            })

        return structure

    def _classify_line(self, line: str) -> Optional[str]:
        """Classify a line as a section boundary."""
        for pattern, section_type in self.section_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                return section_type
        return None

    def _determine_level(self, line: str, section_type: str) -> int:
        """Determine hierarchical level of section."""
        # Markdown headers
        if line.startswith('#'):
            return line.count('#')

        # Numbered sections
        if re.match(r'^\d+', line):
            numbers = re.findall(r'\d+', line)
            if numbers:
                return min(3, len(numbers))  # Max level 3

        # Chinese numbering
        chinese_nums = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
        if any(num in line for num in chinese_nums):
            return 2  # Usually subsections

        # Default levels
        type_levels = {
            'chapter': 1,
            'part': 1,
            'abstract': 1,
            'introduction': 1,
            'section': 2,
            'numbered_section': 2,
            'conclusion': 2,
            'references': 2,
            'chapter_zh': 1,
            'section_zh': 2,
            'numbered_section_zh': 2,
            'abstract_zh': 1,
            'introduction_zh': 1,
            'conclusion_zh': 2,
            'references_zh': 2,
        }

        return type_levels.get(section_type, 3)

    def _update_hierarchy(self, hierarchy: Dict, section: Dict, stack: List):
        """Update section hierarchy."""
        if stack:
            parent_id = f"sec_{stack[-1]['line_number']}"
            child_id = f"sec_{section['line_number']}"

            if parent_id not in hierarchy:
                hierarchy[parent_id] = []
            hierarchy[parent_id].append(child_id)


class IntelligentChunker:
    """
    Advanced document chunking with semantic awareness.
    """

    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.config = config or ChunkingConfig()
        self.structure_analyzer = DocumentStructureAnalyzer()

    def chunk_document(self, text: str, doc_id: str, metadata: Optional[Dict] = None) -> List[Chunk]:
        """
        Intelligently chunk document based on semantic structure.

        Args:
            text: Full document text
            doc_id: Document identifier
            metadata: Additional metadata

        Returns:
            List of document chunks
        """
        metadata = metadata or {}

        # Analyze document structure
        structure = self.structure_analyzer.analyze_structure(text)

        chunks = []

        if self.config.strategy == ChunkingStrategy.SEMANTIC:
            chunks = self._chunk_semantic(text, structure, doc_id, metadata)
        elif self.config.strategy == ChunkingStrategy.SLIDING_WINDOW:
            chunks = self._chunk_sliding_window(text, structure, doc_id, metadata)
        elif self.config.strategy == ChunkingStrategy.HYBRID:
            chunks = self._chunk_hybrid(text, structure, doc_id, metadata)
        else:  # FIXED_SIZE
            chunks = self._chunk_fixed_size(text, doc_id, metadata)

        return chunks

    def _chunk_semantic(self, text: str, structure: Dict, doc_id: str, metadata: Dict) -> List[Chunk]:
        """Chunk based on semantic boundaries."""
        chunks = []
        lines = text.split('\n')

        for block in structure['content_blocks']:
            block_content = block['content']

            if len(block_content) < self.config.min_chunk_size:
                continue

            # Create chunk from semantic block
            chunk_id = f"chunk_{doc_id}_{block['start_line']}"
            evidence_id = f"ev_{chunk_id}"

            # Get section context
            section_title = block['section']['title']
            section_type = block['section']['type']
            section_level = block['section']['level']

            provenance = ChunkProvenance(
                doc_id=doc_id,
                source_path=metadata.get('source_path', ''),
                parser_name='intelligent_chunker',
                language=metadata.get('language', 'unknown'),
                modality='document',
                block_index=block['start_line']
            )

            chunk = Chunk(
                evidence_id=evidence_id,
                text=block_content,
                provenance=provenance,
                granularity=Granularity.COMPOSITE,
                tier=ChunkTier.BASE,
                metadata={
                    'chunk_strategy': 'semantic',
                    'section_title': section_title,
                    'section_type': section_type,
                    'section_level': section_level,
                    'start_line': block['start_line'],
                    'end_line': block['end_line'],
                    'semantic_boundary': True,
                    **metadata
                }
            )

            chunks.append(chunk)

        return chunks

    def _chunk_sliding_window(self, text: str, structure: Dict, doc_id: str, metadata: Dict) -> List[Chunk]:
        """Chunk using sliding window with semantic awareness."""
        chunks = []

        # Find semantic boundaries for window placement
        boundaries = set(structure['boundaries'])

        # Split text into sentences/paragraphs
        segments = self._split_into_segments(text)

        current_chunk = ""
        chunk_start = 0
        chunk_index = 0

        for i, segment in enumerate(segments):
            potential_chunk = current_chunk + segment

            # Check if we should start a new chunk
            should_split = (
                len(potential_chunk) > self.config.max_chunk_size or
                i in boundaries or  # Semantic boundary
                self._is_natural_break(segment)
            )

            if should_split and current_chunk:
                # Create chunk
                chunk = self._create_window_chunk(
                    current_chunk, chunk_start, i-1, chunk_index,
                    doc_id, metadata, 'sliding_window'
                )
                chunks.append(chunk)

                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk, segments, i-1)
                current_chunk = overlap_text + segment
                chunk_start = max(0, i - len(overlap_text.split()))
                chunk_index += 1
            else:
                current_chunk = potential_chunk

        # Add final chunk
        if current_chunk:
            chunk = self._create_window_chunk(
                current_chunk, chunk_start, len(segments)-1, chunk_index,
                doc_id, metadata, 'sliding_window'
            )
            chunks.append(chunk)

        return chunks

    def _chunk_hybrid(self, text: str, structure: Dict, doc_id: str, metadata: Dict) -> List[Chunk]:
        """Hybrid chunking: semantic where possible, sliding window as fallback."""
        # Try semantic chunking first
        semantic_chunks = self._chunk_semantic(text, structure, doc_id, metadata)

        if semantic_chunks and self._validate_semantic_chunks(semantic_chunks):
            return semantic_chunks
        else:
            # Fall back to sliding window
            logger.info(f"Semantic chunking insufficient for {doc_id}, using sliding window")
            return self._chunk_sliding_window(text, structure, doc_id, metadata)

    def _chunk_fixed_size(self, text: str, doc_id: str, metadata: Dict) -> List[Chunk]:
        """Simple fixed-size chunking."""
        chunks = []

        for i in range(0, len(text), self.config.max_chunk_size):
            chunk_text = text[i:i + self.config.max_chunk_size]

            if len(chunk_text) < self.config.min_chunk_size:
                continue

            chunk_index = i // self.config.max_chunk_size
            chunk = self._create_basic_chunk(
                chunk_text, chunk_index, doc_id, metadata, 'fixed_size'
            )
            chunks.append(chunk)

        return chunks

    def _split_into_segments(self, text: str) -> List[str]:
        """Split text into natural segments."""
        # Split by double newlines (paragraphs) and single newlines (lines)
        segments = []

        paragraphs = text.split('\n\n')
        for para in paragraphs:
            if para.strip():
                lines = para.split('\n')
                segments.extend(line.strip() + '\n' for line in lines if line.strip())

        return segments

    def _is_natural_break(self, segment: str) -> bool:
        """Check if segment represents a natural break point."""
        segment = segment.strip()

        # End of sentence
        if segment.endswith(('.', '!', '?', ':')):
            return True

        # Short segment
        if len(segment) < 50:
            return True

        # Contains semantic markers
        semantic_markers = ['however', 'therefore', 'thus', 'consequently', 'moreover']
        if any(marker in segment.lower() for marker in semantic_markers):
            return True

        return False

    def _get_overlap_text(self, current_chunk: str, segments: List[str], end_index: int) -> str:
        """Get overlap text for sliding window."""
        overlap_segments = []

        # Get last few segments as overlap
        start_index = max(0, end_index - 2)
        for i in range(start_index, end_index + 1):
            if i < len(segments):
                overlap_segments.append(segments[i])

        overlap_text = ''.join(overlap_segments)
        return overlap_text[-self.config.overlap_size:]  # Truncate to overlap size

    def _create_window_chunk(self, text: str, start_idx: int, end_idx: int, chunk_idx: int,
                           doc_id: str, metadata: Dict, strategy: str) -> Chunk:
        """Create a sliding window chunk."""
        chunk_id = f"chunk_{doc_id}_{chunk_idx}"
        evidence_id = f"ev_{chunk_id}"

        provenance = ChunkProvenance(
            doc_id=doc_id,
            source_path=metadata.get('source_path', ''),
            parser_name='intelligent_chunker',
            language=metadata.get('language', 'unknown'),
            modality='document',
            block_index=start_idx
        )

        chunk = Chunk(
            evidence_id=evidence_id,
            text=text,
            provenance=provenance,
            granularity=Granularity.ATOMIC,
            tier=ChunkTier.BASE,
            metadata={
                'chunk_strategy': strategy,
                'window_start': start_idx,
                'window_end': end_idx,
                'chunk_index': chunk_idx,
                'overlap_size': self.config.overlap_size,
                **metadata
            }
        )

        return chunk

    def _create_basic_chunk(self, text: str, chunk_idx: int, doc_id: str,
                          metadata: Dict, strategy: str) -> Chunk:
        """Create a basic chunk."""
        chunk_id = f"chunk_{doc_id}_{chunk_idx}"
        evidence_id = f"ev_{chunk_id}"

        provenance = ChunkProvenance(
            doc_id=doc_id,
            source_path=metadata.get('source_path', ''),
            parser_name='intelligent_chunker',
            language=metadata.get('language', 'unknown'),
            modality='document',
            block_index=chunk_idx
        )

        chunk = Chunk(
            evidence_id=evidence_id,
            text=text,
            provenance=provenance,
            granularity=Granularity.ATOMIC,
            tier=ChunkTier.BASE,
            metadata={
                'chunk_strategy': strategy,
                'chunk_index': chunk_idx,
                **metadata
            }
        )

        return chunk

    def _validate_semantic_chunks(self, chunks: List[Chunk]) -> bool:
        """Validate that semantic chunks are of good quality."""
        if not chunks:
            return False

        # Check average chunk size
        total_size = sum(len(chunk.text) for chunk in chunks)
        avg_size = total_size / len(chunks)

        if avg_size < self.config.min_chunk_size:
            return False

        # Check that we have reasonable number of chunks
        if len(chunks) < 2:
            return False

        # Check semantic boundary coverage
        semantic_chunks = sum(1 for chunk in chunks
                            if chunk.metadata.get('semantic_boundary', False))

        if semantic_chunks / len(chunks) < 0.5:  # At least 50% semantic chunks
            return False

        return True


class ChunkQualityAssessor:
    """
    Assess chunk quality for retrieval effectiveness.
    """

    def assess_chunk_quality(self, chunk: Chunk) -> Dict[str, Any]:
        """Assess quality of a chunk."""
        assessment = {
            'overall_score': 0.0,
            'issues': [],
            'strengths': [],
            'recommendations': []
        }

        text = chunk.text
        metadata = chunk.metadata

        # Length assessment
        length_score = self._assess_length(text)
        assessment['length_score'] = length_score

        # Coherence assessment
        coherence_score = self._assess_coherence(text)
        assessment['coherence_score'] = coherence_score

        # Semantic assessment
        semantic_score = self._assess_semantic_quality(text, metadata)
        assessment['semantic_score'] = semantic_score

        # Strategy assessment
        strategy_score = self._assess_strategy_effectiveness(metadata)
        assessment['strategy_score'] = strategy_score

        # Overall score (weighted average)
        weights = [0.2, 0.3, 0.3, 0.2]  # length, coherence, semantic, strategy
        scores = [length_score, coherence_score, semantic_score, strategy_score]

        assessment['overall_score'] = sum(s * w for s, w in zip(scores, weights))

        # Generate issues and recommendations
        self._generate_feedback(assessment, text, metadata)

        return assessment

    def _assess_length(self, text: str) -> float:
        """Assess chunk length quality."""
        length = len(text)

        if 300 <= length <= 1200:
            return 1.0  # Optimal
        elif 150 <= length <= 1500:
            return 0.8  # Good
        elif 50 <= length <= 2000:
            return 0.6  # Acceptable
        else:
            return 0.3  # Poor

    def _assess_coherence(self, text: str) -> float:
        """Assess text coherence."""
        # Simple coherence metrics
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if len(sentences) < 2:
            return 0.5  # Too short

        # Average sentence length
        avg_sentence_len = sum(len(s.split()) for s in sentences) / len(sentences)

        if 8 <= avg_sentence_len <= 25:
            coherence = 1.0
        elif 5 <= avg_sentence_len <= 35:
            coherence = 0.8
        else:
            coherence = 0.6

        # Check for topic consistency (simplified)
        # Look for repeated keywords
        words = re.findall(r'\b\w+\b', text.lower())
        word_freq = {}

        for word in words:
            if len(word) > 3:  # Skip short words
                word_freq[word] = word_freq.get(word, 0) + 1

        # Check if top words represent a coherent topic
        if word_freq:
            max_freq = max(word_freq.values())
            if max_freq >= 3:  # Some words repeated
                coherence += 0.1

        return min(1.0, coherence)

    def _assess_semantic_quality(self, text: str, metadata: Dict) -> float:
        """Assess semantic quality."""
        score = 0.5  # Base score

        # Semantic boundaries are good
        if metadata.get('semantic_boundary'):
            score += 0.2

        # Section context is valuable
        if metadata.get('section_title'):
            score += 0.1

        # Proper chunking strategy
        strategy = metadata.get('chunk_strategy', '')
        if strategy in ['semantic', 'hybrid']:
            score += 0.2

        return min(1.0, score)

    def _assess_strategy_effectiveness(self, metadata: Dict) -> float:
        """Assess how well the chunking strategy worked."""
        strategy = metadata.get('chunk_strategy', '')

        if strategy == 'semantic':
            return 0.9  # Best for structured docs
        elif strategy == 'hybrid':
            return 0.8  # Good fallback
        elif strategy == 'sliding_window':
            return 0.7  # Decent for unstructured
        else:
            return 0.5  # Basic

    def _generate_feedback(self, assessment: Dict, text: str, metadata: Dict):
        """Generate human-readable feedback."""
        score = assessment['overall_score']

        if score >= 0.8:
            assessment['strengths'].append("High-quality chunk with good length and coherence")
        elif score >= 0.6:
            assessment['strengths'].append("Decent chunk quality")
        else:
            assessment['issues'].append("Low-quality chunk may hurt retrieval")

        # Length-specific feedback
        length = len(text)
        if length < 100:
            assessment['issues'].append("Chunk too short - may lack context")
            assessment['recommendations'].append("Consider merging with adjacent chunks")
        elif length > 1500:
            assessment['issues'].append("Chunk too long - may contain multiple topics")
            assessment['recommendations'].append("Consider splitting into smaller chunks")

        # Strategy feedback
        strategy = metadata.get('chunk_strategy', '')
        if strategy == 'fixed_size':
            assessment['recommendations'].append("Consider upgrading to semantic chunking for better results")

