"""
MCU Tiered Chunker for Industrial-Grade TrustRAG.
Assigns chunks to Micro/Base/Macro tiers and injects summaries for Macro.
"""
from typing import List, Dict, Any, Optional
from trust_rag.engine.ingest.models import Chunk, ChunkTier, Granularity

class MCUChunker:
    """
    Assigns tier (Micro/Base/Macro) to chunks and enriches Macro with summaries.
    """
    
    # Tier assignment heuristics
    MICRO_MAX_TOKENS = 50
    BASE_MAX_TOKENS = 500
    
    def __init__(self):
        pass
    
    def assign_tiers(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Assign MCU tiers to chunks based on content type and length.
        
        Rules:
        - MICRO: Atomic chunks (table rows, clauses, list items)
        - BASE: Paragraphs, table blocks, standard text
        - MACRO: Sections, chapters (must have summary)
        """
        tiered_chunks = []
        
        for chunk in chunks:
            tier = self._determine_tier(chunk)
            chunk.tier = tier
            
            # Inject summary for MACRO
            if tier == ChunkTier.MACRO and not chunk.summary:
                chunk.summary = self._generate_summary(chunk.text)
            
            tiered_chunks.append(chunk)
        
        return tiered_chunks
    
    def _determine_tier(self, chunk: Chunk) -> ChunkTier:
        """Determine tier based on chunk characteristics."""
        
        # Atomic chunks (from TableAtomicChunker) -> MICRO
        if chunk.granularity == Granularity.ATOMIC:
            return ChunkTier.MICRO
        
        # Check token count (rough estimate)
        token_count = len(chunk.text.split())
        
        # Short chunks -> MICRO
        if token_count <= self.MICRO_MAX_TOKENS:
            return ChunkTier.MICRO
        
        # Check if it's a section/chapter (by metadata or section_path)
        modality = chunk.provenance.modality if chunk.provenance else "text"
        block_type = chunk.metadata.get("block_type", "")
        
        # Headers/Sections -> MACRO
        if block_type in ["header", "section", "chapter"]:
            return ChunkTier.MACRO
        
        # Long content with section context -> MACRO
        if token_count > self.BASE_MAX_TOKENS and chunk.section_path:
            return ChunkTier.MACRO
        
        # Default -> BASE
        return ChunkTier.BASE
    
    def _generate_summary(self, text: str, max_sentences: int = 3) -> str:
        """
        Generate extractive summary for MACRO chunks.
        Uses first N sentences as summary (fast, deterministic).
        """
        if not text:
            return ""
        
        # Simple sentence splitting
        sentences = []
        for sep in ['. ', '。', '！', '？', '! ', '? ']:
            if sep in text:
                parts = text.split(sep)
                sentences = [s.strip() + sep.strip() for s in parts if s.strip()]
                break
        
        if not sentences:
            # Fallback: first 100 chars
            return text[:100] + "..." if len(text) > 100 else text
        
        summary_sentences = sentences[:max_sentences]
        return ' '.join(summary_sentences)
    
    def build_virtual_links(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Build virtual links between table/figure chunks and their surrounding text.
        """
        for i, chunk in enumerate(chunks):
            modality = chunk.provenance.modality if chunk.provenance else "text"
            
            # Tables and figures need context links
            if modality in ["table", "figure", "chart"]:
                # Find preceding text
                if i > 0:
                    prev_chunk = chunks[i - 1]
                    prev_modality = prev_chunk.provenance.modality if prev_chunk.provenance else "text"
                    if prev_modality == "text":
                        chunk.virtual_links["preceding_text"] = prev_chunk.evidence_id
                
                # Find following text
                if i < len(chunks) - 1:
                    next_chunk = chunks[i + 1]
                    next_modality = next_chunk.provenance.modality if next_chunk.provenance else "text"
                    if next_modality == "text":
                        chunk.virtual_links["following_text"] = next_chunk.evidence_id
        
        return chunks
    
    def build_sibling_refs(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Link adjacent chunks as siblings.
        """
        for i, chunk in enumerate(chunks):
            if i > 0:
                chunk.sibling_refs.append(chunks[i - 1].evidence_id)
            if i < len(chunks) - 1:
                chunk.sibling_refs.append(chunks[i + 1].evidence_id)
        
        return chunks
