"""
Table Atomic Chunker for Phase F.
Flattens table blocks into atomic row-based chunks with semantic context injection.
"""
from typing import List, Optional, Dict, Any
from trust_rag.engine.ingest.models import Chunk, ChunkProvenance, Granularity
from trust_rag.engine.ingest.evidence_id import generate_evidence_id

class TableAtomicChunker:
    """
    Splits a composite Table chunk into atomic row chunks.
    Injects column headers and table caption into every atomic chunk.
    """
    
    def chunk_table(self, table_chunk: Chunk, table_structure: Dict[str, Any]) -> List[Chunk]:
        """
        Decompose a table chunk into atomic row chunks.
        
        Args:
            table_chunk: The original composite table chunk.
            table_structure: Parsed structure (headers, rows, caption).
                Expected format:
                {
                    "headers": ["Col1", "Col2"],
                    "rows": [["Val1", "Val2"], ...],
                    "caption": "Table 1: Example"
                }
                
        Returns:
            List of atomic chunks (one per row).
        """
        atomic_chunks = []
        headers = table_structure.get("headers", [])
        rows = table_structure.get("rows", [])
        caption = table_structure.get("caption", "")
        
        # If no headers or structure is empty, return empty list (let fallback handle it)
        if not headers or not rows:
            return []
            
        parent_id = table_chunk.evidence_id
        doc_id = table_chunk.provenance.doc_id
        page_num = table_chunk.provenance.page_number
        
        for idx, row in enumerate(rows):
            # 1. Linearize Row with Headers
            # Format: "Header: Value; Header: Value"
            row_pairs = []
            for h_idx, cell_val in enumerate(row):
                if h_idx < len(headers):
                    header = headers[h_idx]
                    # Skip empty cells if configured? keeping for now for alignment
                    row_pairs.append(f"{header}: {cell_val}")
            
            # 2. Build Text
            # "Table 1: Example. Row context: Col1: Val1; Col2: Val2"
            # We explicitly mention "Row from Table: {caption}" to boost semantics
            linearized_text = "; ".join(row_pairs)
            full_text = f"Context: {caption}. Data: {linearized_text}"
            
            # 3. Generate Evidence ID (Deterministic)
            # parent_id + row_index
            row_id = generate_evidence_id(doc_id, page_num, idx, full_text + "atomic_row")
            
            # 4. Create Chunk
            new_prov = table_chunk.provenance.copy()
            new_prov.block_index = idx # reset or offset?
            # It's better to keep provenance but maybe mark it as derived
            
            # Merge original metadata with new type info
            new_metadata = table_chunk.metadata.copy()
            new_metadata.update({
                "type": "table_row",
                "original_table_id": parent_id,
                "headers": headers # Satisfy DocIRValidator
            })

            atomic_chunk = Chunk(
                evidence_id=row_id,
                text=full_text,
                provenance=new_prov,
                metadata=new_metadata,
                parent_id=parent_id,
                semantic_context={
                    "headers": headers,
                    "caption": caption,
                    "row_index": idx
                },
                granularity=Granularity.ATOMIC
            )
            atomic_chunks.append(atomic_chunk)
            
        return atomic_chunks
