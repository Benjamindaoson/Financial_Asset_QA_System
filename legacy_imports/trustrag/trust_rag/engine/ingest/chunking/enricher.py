"""
Context Enricher for Phase F.
Propagates semantic context (e.g. Section Titles) to chunk lineages.
"""
from typing import List, Dict, Any
from trust_rag.engine.ingest.models import Chunk, Granularity

class ContextEnricher:
    """
    Enriches chunks with hierarchical context.
    """
    
    def enrich(self, chunks: List[Chunk]) -> List[Chunk]:
        """
        Walk through chunks and propagate context.
        Simplistic implementation: assumes chunks are in order and have hierarchy metadata.
        In a real system, this would require a full DocIR tree traversal.
        
        For Phase F, we focus on ensuring atomic chunks have what they need from their direct parents.
        """
        enriched = []
        
        # This is a placeholder for more complex logic.
        # Currently, TableAtomicChunker already does the heavy lifting for tables.
        # This would be used for Text Hierarchy (Section -> Paragraph -> Sentence).
        
        current_section = "Unknown Section"
        
        for chunk in chunks:
            # Detect section headers (if parser supports it) -- strict heuristic for now
            if chunk.metadata.get("block_type") == "header":
                current_section = chunk.text
            
            # If atomic and missing context, inject section
            if chunk.granularity == Granularity.ATOMIC:
                if "section_title" not in chunk.semantic_context:
                    chunk.semantic_context["section_title"] = current_section
                    # Optional: Prepend to text? Or leave for Prompt Engineering?
                    # Phase F mandate: "explicitly formatted in the prompt" -> so keeping in semantic_context is correct
                    
            enriched.append(chunk)
            
        return enriched
