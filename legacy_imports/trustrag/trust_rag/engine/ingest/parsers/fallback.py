"""
Fallback PDF Parser using pdfplumber/pypdf.
"""
import logging
from typing import List
from trust_rag.engine.ingest.parsers.base import BaseIngestParser
from trust_rag.engine.ingest.models import Chunk, ChunkProvenance
from trust_rag.engine.ingest.evidence_id import generate_evidence_id

logger = logging.getLogger(__name__)

class FallbackPDFParser(BaseIngestParser):
    """
    Simple fallback PDF parser using pdfplumber or pypdf.
    Works for most text-based PDFs but has limited layout understanding.
    """
    name = "fallback_pdf"
    
    def is_available(self) -> bool:
        try:
            import pdfplumber
            return True
        except ImportError:
            try:
                from pypdf import PdfReader
                return True
            except ImportError:
                return False
    
    def parse(self, path: str, doc_id: str, language: str) -> List[Chunk]:
        chunks = []
        
        # Try pdfplumber first
        try:
            import pdfplumber
            chunks = self._parse_with_pdfplumber(path, doc_id, language)
            if chunks:
                return chunks
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}")
        
        # Fallback to pypdf
        try:
            from pypdf import PdfReader
            chunks = self._parse_with_pypdf(path, doc_id, language)
        except ImportError:
            raise ImportError("Neither pdfplumber nor pypdf available")
        except Exception as e:
            logger.error(f"pypdf also failed: {e}")
            raise
        
        return chunks
    
    def _parse_with_pdfplumber(self, path: str, doc_id: str, language: str) -> List[Chunk]:
        import pdfplumber
        
        chunks = []
        block_index = 0
        
        with pdfplumber.open(path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                
                # Split into paragraphs
                paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                
                for para in paragraphs:
                    if len(para) < 10:  # Skip very short fragments
                        continue
                    
                    evidence_id = generate_evidence_id(doc_id, page_num, block_index, para)
                    
                    prov = ChunkProvenance(
                        doc_id=doc_id,
                        page_number=page_num,
                        bbox=None,
                        source_path=path,
                        parser_name=self.name,
                        language=language,
                        modality="pdf",
                        block_index=block_index
                    )
                    
                    chunks.append(Chunk(
                        evidence_id=evidence_id,
                        text=para,
                        provenance=prov
                    ))
                    block_index += 1
        
        return chunks
    
    def _parse_with_pypdf(self, path: str, doc_id: str, language: str) -> List[Chunk]:
        from pypdf import PdfReader
        
        chunks = []
        block_index = 0
        reader = PdfReader(path)
        
        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            
            for para in paragraphs:
                if len(para) < 10:
                    continue
                
                evidence_id = generate_evidence_id(doc_id, page_num, block_index, para)
                
                prov = ChunkProvenance(
                    doc_id=doc_id,
                    page_number=page_num,
                    bbox=None,
                    source_path=path,
                    parser_name=self.name,
                    language=language,
                    modality="pdf",
                    block_index=block_index
                )
                
                chunks.append(Chunk(
                    evidence_id=evidence_id,
                    text=para,
                    provenance=prov
                ))
                block_index += 1
        
        return chunks
