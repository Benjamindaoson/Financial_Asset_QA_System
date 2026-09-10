"""
TrustRAG 2.0 Structure-Aware Chunker

Intelligent chunking with:
1. Table atomicity protection (no 断头表)
2. Header path inheritance for semantic context
3. Greedy aggregation with overlap
4. Token-aware splitting
"""
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from trust_rag.engine.ingest.models import Chunk, ChunkProvenance, Granularity, ChunkTier
from trust_rag.engine.ingest.evidence_id import generate_evidence_id
from .markdown_structure_parser import DocNode, NodeType

logger = logging.getLogger(__name__)


class ChunkingConfig(BaseModel):
    """Configuration for structure-aware chunking"""
    max_chunk_size: int = Field(default=1000, description="Maximum chunk size in tokens")
    overlap_size: int = Field(default=100, description="Overlap size for paragraph chunks")
    table_size_threshold: float = Field(default=0.8, description="Table size threshold (% of max_chunk_size)")
    enable_semantic_injection: bool = Field(default=True, description="Inject header path context")
    min_chunk_size: int = Field(default=100, description="Minimum chunk size in tokens")


class StructureAwareChunker:
    """
    Structure-aware document chunker
    
    Key Features:
    - Table Atomicity: Tables < 80% of max_chunk_size are never split
    - Header Inheritance: Each chunk carries its hierarchical context
    - Greedy Aggregation: Maximize chunk utilization while respecting boundaries
    - Smart Overlap: Overlap for paragraphs, not for tables
    """
    
    def __init__(self, config: Optional[ChunkingConfig] = None):
        """Initialize chunker with configuration"""
        self.config = config or ChunkingConfig()
        self.header_stack: List[Tuple[int, str]] = []  # [(level, title), ...]
        self.chunk_count = 0
    
    def chunk(
        self,
        nodes: List[DocNode],
        doc_id: str,
        source_path: str = "",
        parser_name: str = "markdown_structure_parser",
        language: str = "zh"
    ) -> List[Chunk]:
        """
        Convert DocNode stream into RAG chunks
        
        Args:
            nodes: List of DocNode objects from parser
            doc_id: Document identifier
            source_path: Source file path
            parser_name: Parser name for provenance
            language: Document language
            
        Returns:
            List of Chunk objects with proper metadata
        """
        if not nodes:
            logger.warning(f"No nodes to chunk for doc_id={doc_id}")
            return []
        
        chunks: List[Chunk] = []
        current_buffer: List[DocNode] = []
        current_tokens = 0
        self.chunk_count = 0
        
        for node in nodes:
            # Update header stack if this is a header
            if node.type == NodeType.HEADER:
                self._update_header_stack(node)
            
            # Estimate tokens for this node
            node_tokens = node.token_estimate()
            
            # Handle table nodes specially
            if node.type == NodeType.TABLE:
                # Check if table is too large to be atomic
                if node_tokens > self.config.max_chunk_size * self.config.table_size_threshold:
                    # Large table: flush buffer, then add table as standalone chunk
                    if current_buffer:
                        chunk = self._create_chunk(
                            current_buffer, doc_id, source_path, parser_name, language
                        )
                        if chunk:
                            chunks.append(chunk)
                        current_buffer = []
                        current_tokens = 0
                    
                    # Add large table as its own chunk
                    chunk = self._create_chunk(
                        [node], doc_id, source_path, parser_name, language
                    )
                    if chunk:
                        chunks.append(chunk)
                    
                else:
                    # Normal table: check if it fits in current buffer
                    if current_tokens + node_tokens > self.config.max_chunk_size:
                        # Flush current buffer
                        if current_buffer:
                            chunk = self._create_chunk(
                                current_buffer, doc_id, source_path, parser_name, language
                            )
                            if chunk:
                                chunks.append(chunk)
                        
                        # Start new buffer with table
                        current_buffer = [node]
                        current_tokens = node_tokens
                    else:
                        # Add to current buffer
                        current_buffer.append(node)
                        current_tokens += node_tokens
            
            else:
                # Non-table node: greedy aggregation
                if current_tokens + node_tokens > self.config.max_chunk_size:
                    # Flush current buffer
                    if current_buffer:
                        chunk = self._create_chunk(
                            current_buffer, doc_id, source_path, parser_name, language
                        )
                        if chunk:
                            chunks.append(chunk)
                    
                    # Start new buffer
                    # For large single nodes, split them
                    if node_tokens > self.config.max_chunk_size:
                        split_chunks = self._split_large_node(
                            node, doc_id, source_path, parser_name, language
                        )
                        chunks.extend(split_chunks)
                        current_buffer = []
                        current_tokens = 0
                    else:
                        current_buffer = [node]
                        current_tokens = node_tokens
                else:
                    # Add to current buffer
                    current_buffer.append(node)
                    current_tokens += node_tokens
        
        # Flush remaining buffer
        if current_buffer:
            chunk = self._create_chunk(
                current_buffer, doc_id, source_path, parser_name, language
            )
            if chunk:
                chunks.append(chunk)
        
        logger.info(f"Created {len(chunks)} chunks from {len(nodes)} nodes for doc_id={doc_id}")
        
        return chunks
    
    def _update_header_stack(self, header_node: DocNode):
        """
        Update header hierarchy stack
        
        Maintains a stack of (level, title) tuples representing the current
        hierarchical context.
        """
        level = header_node.level
        title = header_node.content
        
        # Pop headers at same or lower level
        while self.header_stack and self.header_stack[-1][0] >= level:
            self.header_stack.pop()
        
        # Push new header
        self.header_stack.append((level, title))
    
    def _get_header_path(self) -> str:
        """
        Generate header path string from current stack
        
        Returns:
            String like "2024年报 > 第三季度 > 财务摘要"
        """
        if not self.header_stack:
            return ""
        
        return " > ".join([title for _, title in self.header_stack])
    
    def _create_chunk(
        self,
        nodes: List[DocNode],
        doc_id: str,
        source_path: str,
        parser_name: str,
        language: str
    ) -> Optional[Chunk]:
        """
        Create a chunk from a list of nodes
        
        Injects semantic context prefix if enabled
        """
        if not nodes:
            return None
        
        # Combine node contents
        node_contents = [node.content for node in nodes]
        
        # Inject semantic context prefix
        if self.config.enable_semantic_injection:
            header_path = self._get_header_path()
            if header_path:
                context_prefix = f"[Context: {header_path}]\n\n"
                chunk_text = context_prefix + "\n\n".join(node_contents)
            else:
                chunk_text = "\n\n".join(node_contents)
        else:
            chunk_text = "\n\n".join(node_contents)
        
        # Skip if chunk is too small
        estimated_tokens = len(chunk_text) // 4
        if estimated_tokens < self.config.min_chunk_size:
            logger.debug(f"Skipping small chunk ({estimated_tokens} tokens)")
            return None
        
        # Determine chunk type and granularity
        chunk_type = self._determine_chunk_type(nodes)
        granularity = Granularity.ATOMIC if len(nodes) == 1 else Granularity.COMPOSITE
        
        # Generate evidence ID
        evidence_id = generate_evidence_id(
            doc_id=doc_id,
            page=0,  # Markdown doesn't have page numbers
            block_index=self.chunk_count,
            text=chunk_text[:100]
        )
        
        # Create provenance
        provenance = ChunkProvenance(
            doc_id=doc_id,
            page_number=None,
            bbox=None,
            source_path=source_path,
            parser_name=parser_name,
            language=language,
            modality="text",
            block_index=self.chunk_count
        )
        
        # Build metadata
        metadata = {
            "chunk_type": chunk_type,
            "node_types": [node.type.value for node in nodes],
            "num_nodes": len(nodes),
            "header_path": self._get_header_path(),
            "line_range": f"{nodes[0].line_start}-{nodes[-1].line_end}"
        }
        
        # Add table-specific metadata
        if chunk_type == "table":
            table_nodes = [n for n in nodes if n.type == NodeType.TABLE]
            if table_nodes:
                metadata.update(table_nodes[0].metadata)
        
        # Create chunk
        chunk = Chunk(
            evidence_id=evidence_id,
            text=chunk_text,
            provenance=provenance,
            metadata=metadata,
            granularity=granularity,
            tier=ChunkTier.BASE,
            section_path=self._get_header_path().split(" > ") if self._get_header_path() else []
        )
        
        self.chunk_count += 1
        
        return chunk
    
    def _determine_chunk_type(self, nodes: List[DocNode]) -> str:
        """Determine the primary type of the chunk"""
        if not nodes:
            return "unknown"
        
        # If any node is a table, mark as table
        if any(node.type == NodeType.TABLE for node in nodes):
            return "table"
        
        # If all nodes are headers, mark as header
        if all(node.type == NodeType.HEADER for node in nodes):
            return "header"
        
        # If contains code, mark as code
        if any(node.type == NodeType.CODE for node in nodes):
            return "code"
        
        # If contains list, mark as list
        if any(node.type == NodeType.LIST for node in nodes):
            return "list"
        
        # Default to text
        return "text"
    
    def _split_large_node(
        self,
        node: DocNode,
        doc_id: str,
        source_path: str,
        parser_name: str,
        language: str
    ) -> List[Chunk]:
        """
        Split a large node into multiple chunks with overlap
        
        Used for very large paragraphs or code blocks
        """
        chunks: List[Chunk] = []
        content = node.content
        
        # Estimate characters per chunk (4 chars ≈ 1 token)
        chars_per_chunk = self.config.max_chunk_size * 4
        overlap_chars = self.config.overlap_size * 4
        
        start = 0
        while start < len(content):
            end = min(start + chars_per_chunk, len(content))
            
            # Try to break at sentence boundary
            if end < len(content):
                # Look for sentence endings
                for delimiter in ['。', '！', '？', '.', '!', '?', '\n\n']:
                    last_delim = content.rfind(delimiter, start, end)
                    if last_delim != -1:
                        end = last_delim + 1
                        break
            
            chunk_text = content[start:end].strip()
            
            if chunk_text:
                # Inject context
                if self.config.enable_semantic_injection:
                    header_path = self._get_header_path()
                    if header_path:
                        chunk_text = f"[Context: {header_path}]\n\n{chunk_text}"
                
                # Generate evidence ID
                evidence_id = generate_evidence_id(
                    doc_id=doc_id,
                    page=0,
                    block_index=self.chunk_count,
                    text=chunk_text[:100]
                )
                
                # Create provenance
                provenance = ChunkProvenance(
                    doc_id=doc_id,
                    page_number=None,
                    bbox=None,
                    source_path=source_path,
                    parser_name=parser_name,
                    language=language,
                    modality="text",
                    block_index=self.chunk_count
                )
                
                # Create chunk
                chunk = Chunk(
                    evidence_id=evidence_id,
                    text=chunk_text,
                    provenance=provenance,
                    metadata={
                        "chunk_type": node.type.value,
                        "is_split": True,
                        "split_index": len(chunks),
                        "header_path": self._get_header_path()
                    },
                    granularity=Granularity.COMPOSITE,
                    tier=ChunkTier.BASE,
                    section_path=self._get_header_path().split(" > ") if self._get_header_path() else []
                )
                
                chunks.append(chunk)
                self.chunk_count += 1
            
            # Move start with overlap
            start = end - overlap_chars if end < len(content) else end
        
        return chunks
