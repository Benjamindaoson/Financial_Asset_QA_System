"""
Local OCR Parsers for Image files (NO CLOUD APIs).
"""
import logging
import os
from typing import List
from trust_rag.engine.ingest.parsers.base import BaseIngestParser
from trust_rag.engine.ingest.models import Chunk, ChunkProvenance
from trust_rag.engine.ingest.evidence_id import generate_evidence_id

logger = logging.getLogger(__name__)

class TesseractOCRParser(BaseIngestParser):
    """
    Local OCR Parser using Tesseract.
    PRIMARY for English images, fallback for others.
    """
    name = "tesseract_ocr"
    
    def is_available(self) -> bool:
        try:
            import pytesseract
            from PIL import Image
            # Test if tesseract binary is accessible
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False
    
    def parse(self, path: str, doc_id: str, language: str) -> List[Chunk]:
        import pytesseract
        from PIL import Image
        
        # Map language codes to Tesseract language packs
        lang_map = {
            "zh": "chi_sim+chi_tra",  # Simplified + Traditional Chinese
            "en": "eng",
            "unknown": "eng"
        }
        tess_lang = lang_map.get(language, "eng")
        
        try:
            img = Image.open(path)
            
            # Get OCR data with bounding boxes
            ocr_data = pytesseract.image_to_data(img, lang=tess_lang, output_type=pytesseract.Output.DICT)
            
            chunks = []
            block_index = 0
            
            # Group text by blocks/paragraphs
            current_block_text = []
            current_block_num = -1
            
            for i in range(len(ocr_data['text'])):
                text = ocr_data['text'][i].strip()
                conf = int(ocr_data['conf'][i])
                block_num = ocr_data['block_num'][i]
                
                # Skip low confidence or empty text
                if conf < 30 or not text:
                    continue
                
                # New block detected
                if block_num != current_block_num and current_block_text:
                    # Save previous block
                    block_text = " ".join(current_block_text)
                    if len(block_text) >= 5:
                        evidence_id = generate_evidence_id(doc_id, 1, block_index, block_text)
                        
                        prov = ChunkProvenance(
                            doc_id=doc_id,
                            page_number=1,
                            bbox=None,  # Could aggregate bbox from words
                            source_path=path,
                            parser_name=self.name,
                            language=language,
                            modality="image",
                            block_index=block_index
                        )
                        
                        chunks.append(Chunk(
                            evidence_id=evidence_id,
                            text=block_text,
                            provenance=prov,
                            metadata={"block_type": "ocr_block", "avg_confidence": conf}
                        ))
                        block_index += 1
                    
                    current_block_text = []
                
                current_block_num = block_num
                current_block_text.append(text)
            
            # Add final block
            if current_block_text:
                block_text = " ".join(current_block_text)
                if len(block_text) >= 5:
                    evidence_id = generate_evidence_id(doc_id, 1, block_index, block_text)
                    
                    prov = ChunkProvenance(
                        doc_id=doc_id,
                        page_number=1,
                        bbox=None,
                        source_path=path,
                        parser_name=self.name,
                        language=language,
                        modality="image",
                        block_index=block_index
                    )
                    
                    chunks.append(Chunk(
                        evidence_id=evidence_id,
                        text=block_text,
                        provenance=prov,
                        metadata={"block_type": "ocr_block"}
                    ))
            
            logger.info(f"Tesseract OCR extracted {len(chunks)} chunks from {path}")
            return chunks
            
        except Exception as e:
            logger.error(f"Tesseract OCR failed for {path}: {e}")
            raise


class PaddleOCRParser(BaseIngestParser):
    """
    Local OCR Parser using PaddleOCR (Chinese-optimized, NO CLOUD API).
    Fallback for Chinese images when DeepSeek is not available.
    """
    name = "paddle_ocr"
    
    def is_available(self) -> bool:
        try:
            from paddleocr import PaddleOCR
            return True
        except ImportError:
            return False
    
    def parse(self, path: str, doc_id: str, language: str) -> List[Chunk]:
        from paddleocr import PaddleOCR
        
        # Initialize PaddleOCR (runs locally)
        ocr = PaddleOCR(use_angle_cls=True, lang='ch' if language == 'zh' else 'en', use_gpu=False)
        
        try:
            result = ocr.ocr(path, cls=True)
            
            chunks = []
            block_index = 0
            
            # PaddleOCR returns list of pages, each page has list of lines
            for page_idx, page_result in enumerate(result):
                if not page_result:
                    continue
                
                for line in page_result:
                    bbox_coords, (text, confidence) = line
                    
                    if not text or confidence < 0.5:
                        continue
                    
                    # Convert bbox to tuple
                    bbox = tuple([coord for point in bbox_coords for coord in point])[:4]  # (x1,y1,x2,y2)
                    
                    evidence_id = generate_evidence_id(doc_id, page_idx + 1, block_index, text)
                    
                    prov = ChunkProvenance(
                        doc_id=doc_id,
                        page_number=page_idx + 1,
                        bbox=bbox,
                        source_path=path,
                        parser_name=self.name,
                        language=language,
                        modality="image",
                        block_index=block_index
                    )
                    
                    chunks.append(Chunk(
                        evidence_id=evidence_id,
                        text=text,
                        provenance=prov,
                        metadata={"block_type": "ocr_line", "confidence": confidence}
                    ))
                    block_index += 1
            
            logger.info(f"PaddleOCR extracted {len(chunks)} chunks from {path}")
            return chunks
            
        except Exception as e:
            logger.error(f"PaddleOCR failed for {path}: {e}")
            raise
