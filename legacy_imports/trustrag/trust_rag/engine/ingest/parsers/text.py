"""
Text Parser for plain text files.
"""
import logging
from typing import List
from trust_rag.engine.ingest.parsers.base import BaseIngestParser
from trust_rag.engine.ingest.models import Chunk, ChunkProvenance
from trust_rag.engine.ingest.evidence_id import generate_evidence_id

logger = logging.getLogger(__name__)

class TextParser(BaseIngestParser):
    """
    Parser for plain text files (.txt, .md, etc).
    """
    name = "text_parser"
    
    def is_available(self) -> bool:
        return True  # Always available
    
    def parse(self, path: str, doc_id: str, language: str) -> List[Chunk]:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        chunks = []
        block_index = 0
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        
        for para in paragraphs:
            if len(para) < 10:  # Skip very short fragments
                continue
            
            evidence_id = generate_evidence_id(doc_id, 1, block_index, para)
            
            prov = ChunkProvenance(
                doc_id=doc_id,
                page_number=1,
                bbox=None,
                source_path=path,
                parser_name=self.name,
                language=language,
                modality="text",
                block_index=block_index
            )
            
            chunks.append(Chunk(
                evidence_id=evidence_id,
                text=para,
                provenance=prov,
                metadata={
                    "source_block_ids":   [f"block_{block_index}"],
                    "ocr_confidence": 1.0
                }
            ))
            block_index += 1
        
        return chunks
