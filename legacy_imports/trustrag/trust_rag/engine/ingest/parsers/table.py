"""
Table Parser for CSV/XLSX files.
"""
import logging
from typing import List
from trust_rag.engine.ingest.parsers.base import BaseIngestParser
from trust_rag.engine.ingest.models import Chunk, ChunkProvenance
from trust_rag.engine.ingest.evidence_id import generate_evidence_id

logger = logging.getLogger(__name__)

class TableParser(BaseIngestParser):
    """
    Parser for structured table files (CSV, XLSX).
    """
    name = "table_parser"
    
    def is_available(self) -> bool:
        try:
            import pandas
            return True
        except ImportError:
            return False
    
    def parse(self, path: str, doc_id: str, language: str) -> List[Chunk]:
        import pandas as pd
        import os
        
        ext = os.path.splitext(path)[1].lower()
        
        if ext == ".csv":
            df = pd.read_csv(path)
        elif ext in [".xlsx", ".xls"]:
            df = pd.read_excel(path)
        else:
            raise ValueError(f"Unsupported table format: {ext}")
        
        chunks = []
        block_index = 0
        
        # Generate schema chunk
        schema = ", ".join(df.columns.tolist())
        schema_text = f"Table Schema: {schema}"
        
        evidence_id = generate_evidence_id(doc_id, 1, block_index, schema_text)
        prov = ChunkProvenance(
            doc_id=doc_id,
            page_number=1,
            bbox=None,
            source_path=path,
            parser_name=self.name,
            language=language,
            modality="table",
            block_index=block_index
        )
        chunks.append(Chunk(
            evidence_id=evidence_id,
            text=schema_text,
            provenance=prov,
            metadata={"type": "schema", "columns": df.columns.tolist()}
        ))
        block_index += 1
        
        # Generate row chunks (searchable text view)
        # Limit to first 1000 rows to avoid massive output
        max_rows = min(len(df), 1000)
        
        for idx in range(max_rows):
            row = df.iloc[idx]
            row_text = " | ".join([f"{col}: {row[col]}" for col in df.columns])
            
            evidence_id = generate_evidence_id(doc_id, 1, block_index, row_text)
            
            prov = ChunkProvenance(
                doc_id=doc_id,
                page_number=1,
                bbox=None,
                source_path=path,
                parser_name=self.name,
                language=language,
                modality="table",
                block_index=block_index
            )
            
            chunks.append(Chunk(
                evidence_id=evidence_id,
                text=row_text,
                provenance=prov,
                metadata={"type": "row", "row_index": idx}
            ))
            block_index += 1
        
        return chunks
