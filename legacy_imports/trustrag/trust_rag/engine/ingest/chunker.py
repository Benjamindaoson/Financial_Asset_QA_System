from typing import List, Dict, Any
from trust_rag.engine.ingest.parser import ParsedChunk
import re

class SemanticChunker:
    """
    Breaks down parsed document text into retrieval-optimized units.
    Financial-specific: Tries to keep tables or metric groupings together.
    """
    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, parsed_chunks: List[ParsedChunk]) -> List[Dict[str, Any]]:
        """
        Converts ParsedChunks into flattened dicts for indexing.
        """
        final_chunks = []
        for p in parsed_chunks:
            # 1. Basic window-based chunking as baseline
            # In production, we use semantic boundaries (e.g., Headers, Periods).
            text = p.content
            
            # Simulated Semantic Splitting
            # Splits on double newlines (paragraphs)
            paragraphs = re.split(r'\n\s*\n', text)
            
            current_chunk = ""
            for para in paragraphs:
                if len(current_chunk) + len(para) < self.chunk_size:
                    current_chunk += para + "\n\n"
                else:
                    if current_chunk:
                        final_chunks.append(self._build_item(current_chunk, p))
                    # Start new chunk with overlap
                    current_chunk = para + "\n\n"
            
            if current_chunk:
                final_chunks.append(self._build_item(current_chunk, p))
                
        return final_chunks

    def _build_item(self, text: str, source: ParsedChunk) -> Dict[str, Any]:
        return {
            "id": f"{source.source_file}_p{source.page_num}_{hash(text)%10000}",
            "text": text.strip(),
            "metadata": {
                **source.metadata,
                "page": source.page_num,
                "source": source.source_file,
                "type": "financial_report"
            }
        }

class StructureAwareChunker:
    """
    Enterprise Financial Chunking:
    Uses StructureExtractor to parse the document hierarchy first,
    ensuring that chunks respect chapter/section boundaries and retain lineage.
    """
    def __init__(self, chunk_size: int = 1500, chunk_overlap: int = 200):
        from trust_rag.engine.ingest.structure_extractor import StructureExtractor
        self.extractor = StructureExtractor()
        self.semantic_chunker = SemanticChunker(chunk_size, chunk_overlap)
        
    def chunk(self, pages: List[Dict[str, Any]], source_file: str) -> List[Dict[str, Any]]:
        """
        Chunks raw page data by first extracting the document hierarchy.
        """
        # 1. Extract chapter/section hierarchy
        root_node = self.extractor.extract_structure(pages)
        
        # 2. Flatten into structure-aware text sections
        structure_sections = self.extractor.flatten_structure(root_node)
        
        final_chunks = []
        for section in structure_sections:
            # Reconstruct a ParsedChunk wrapper to reuse SemanticChunker logic 
            # while injecting the structural lineage metadata
            p_chunk = ParsedChunk(
                content=section["content"],
                page_num=section["page_number"],
                source_file=source_file,
                metadata={
                    "title_path": section["title_path"],
                    "node_id": section["node_id"],
                    "hierarchy_level": section["level"]
                }
            )
            
            # The semantic chunker will window-split long sections, 
            # but their title_path ensures they remain structurally bound.
            sub_chunks = self.semantic_chunker.chunk([p_chunk])
            final_chunks.extend(sub_chunks)
            
        return final_chunks

