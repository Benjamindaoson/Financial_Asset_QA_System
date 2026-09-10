"""
structured PDF Parser using Docling.
PRIMARY parser for English PDFs with good layout/structure.
"""
import logging
from typing import List
from trust_rag.engine.ingest.parsers.base import BaseIngestParser
from trust_rag.engine.ingest.models import Chunk, ChunkProvenance
from trust_rag.engine.ingest.evidence_id import generate_evidence_id

logger = logging.getLogger(__name__)

class DoclingPDFParser(BaseIngestParser):
    """
    Production PDF Parser using IBM Docling.
    Extracts structured content with layout awareness for English documents.
    """
    name = "docling"
    
    def is_available(self) -> bool:
        try:
            from docling.document_converter import DocumentConverter
            return True
        except ImportError:
            return False
    
    def parse(self, path: str, doc_id: str, language: str) -> List[Chunk]:
        if not self.is_available():
            raise ImportError("Docling not installed. Run: pip install docling")
        
        from docling.document_converter import DocumentConverter
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        
        # Configure pipeline for layout extraction
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False  # Disable OCR for text-based PDFs
        pipeline_options.do_table_structure = True  # Enable table extraction
        
        converter = DocumentConverter()
        
        try:
            result = converter.convert(path)
            doc = result.document
            
            chunks = []
            block_index = 0
            
            # Iterate through document elements
            for element, level in doc.iterate_items():
                # Extract text
                text = element.text if hasattr(element, 'text') else str(element)
                
                if not text or not text.strip():
                    continue
                
                # Extract metadata
                page_num = element.prov[0].page_no if hasattr(element, 'prov') and element.prov else 1
                
                # Determine block type from element type
                block_type = "paragraph"
                if hasattr(element, 'label'):
                    label = str(element.label).lower()
                    if 'title' in label or 'heading' in label:
                        block_type = "title"
                    elif 'table' in label:
                        block_type = "table"
                    elif 'list' in label:
                        block_type = "list"
                
                # Extract bbox if available
                bbox = None
                if hasattr(element, 'prov') and element.prov:
                    prov_item = element.prov[0]
                    if hasattr(prov_item, 'bbox'):
                        bbox_obj = prov_item.bbox
                        bbox = (bbox_obj.l, bbox_obj.t, bbox_obj.r, bbox_obj.b)
                
                # Generate evidence ID
                evidence_id = generate_evidence_id(doc_id, page_num, block_index, text)
                
                # Create provenance
                prov = ChunkProvenance(
                    doc_id=doc_id,
                    page_number=page_num,
                    bbox=bbox,
                    source_path=path,
                    parser_name=self.name,
                    language=language,
                    modality="pdf",
                    block_index=block_index
                )
                
                chunks.append(Chunk(
                    evidence_id=evidence_id,
                    text=text.strip(),
                    provenance=prov,
                    metadata={"block_type": block_type, "hierarchy_level": level}
                ))
                block_index += 1
            
            logger.info(f"Docling parsed {len(chunks)} chunks from {path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Docling parsing failed for {path}: {e}")
            raise
