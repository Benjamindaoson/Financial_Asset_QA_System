"""
structured PDF Parser using MinerU (magic-pdf).
PRIMARY parser for Chinese PDFs with complex layouts.
"""
import logging
import os
import json
from typing import List
from trust_rag.engine.ingest.parsers.base import BaseIngestParser
from trust_rag.engine.ingest.models import Chunk, ChunkProvenance
from trust_rag.engine.ingest.evidence_id import generate_evidence_id

logger = logging.getLogger(__name__)

class MinerUPDFParser(BaseIngestParser):
    """
    Production PDF Parser using MinerU (magic-pdf).
    Extracts layout, tables, and text with high accuracy for Chinese documents.
    """
    name = "mineru"
    
    def is_available(self) -> bool:
        try:
            import magic_pdf
            return True
        except ImportError:
            return False
    
    def parse(self, path: str, doc_id: str, language: str) -> List[Chunk]:
        if not self.is_available():
            raise ImportError("MinerU (magic-pdf) not installed. Run: pip install magic-pdf[full]")
        
        try:
            from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
            from magic_pdf.config.make_content_config import DropMode, MakeMode
            from magic_pdf.pipe.UNIPipe import UNIPipe
            from magic_pdf.rw.DiskReaderWriter import DiskReaderWriter
        except ImportError as e:
            logger.error(f"MinerU import failed: {e}")
            raise
        
        # Setup output directory
        output_dir = f"artifacts/ingestion/{doc_id}/mineru_temp"
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            # Read PDF
            with open(path, "rb") as f:
                pdf_bytes = f.read()
            
            # Initialize MinerU pipeline
            image_writer = DiskReaderWriter(output_dir)
            
            # Create pipe with PDF bytes
            pipe = UNIPipe(pdf_bytes, {"_pdf_type": ""}, image_writer)
            
            # Run classification
            pipe.pipe_classify()
            
            # Parse content
            pipe.pipe_parse()
            
            # Get structured content
            content_list = pipe.pipe_mk_uni_format(output_dir, MakeMode.MM_MD)
            
            # Convert to chunks
            chunks = self._convert_to_chunks(content_list, doc_id, path, language)
            
            logger.info(f"MinerU parsed {len(chunks)} chunks from {path}")
            return chunks
            
        except Exception as e:
            logger.error(f"MinerU parsing failed for {path}: {e}")
            raise
    
    def _convert_to_chunks(self, content_list: list, doc_id: str, path: str, language: str) -> List[Chunk]:
        """Convert MinerU output to Chunk objects."""
        chunks = []
        block_index = 0
        
        for item in content_list:
            # MinerU returns dict-like objects with text and metadata
            if isinstance(item, dict):
                text = item.get("text", "")
                page_num = item.get("page_idx", 0) + 1  # MinerU uses 0-indexed pages
                block_type = item.get("type", "paragraph")
                bbox = item.get("bbox")  # (x0, y0, x1, y1)
            elif isinstance(item, str):
                text = item
                page_num = 1
                block_type = "paragraph"
                bbox = None
            else:
                continue
            
            if not text or not text.strip():
                continue
            
            # Generate evidence ID
            evidence_id = generate_evidence_id(doc_id, page_num, block_index, text)
            
            # Create provenance
            prov = ChunkProvenance(
                doc_id=doc_id,
                page_number=page_num,
                bbox=tuple(bbox) if bbox else None,
                source_path=path,
                parser_name=self.name,
                language=language,
                modality="pdf",
                block_index=block_index
            )
            
            # Create chunk with block type metadata
            chunks.append(Chunk(
                evidence_id=evidence_id,
                text=text.strip(),
                provenance=prov,
                metadata={"block_type": block_type}
            ))
            block_index += 1
        
        return chunks
