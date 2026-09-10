"""
Language-Aware Ingestion Router.
Routes inputs to appropriate parsers based on content type AND language.
"""
import logging
from typing import Literal, Tuple, Optional
from dataclasses import dataclass

from trust_rag.engine.ingest.language import LanguageDetector
from trust_rag.engine.ingest.parsers.base import BaseIngestParser
from trust_rag.engine.ingest.parsers.pdf_docling import DoclingPDFParser
from trust_rag.engine.ingest.parsers.pdf_mineru import MinerUPDFParser
from trust_rag.engine.ingest.parsers.fallback import FallbackPDFParser
from trust_rag.engine.ingest.parsers.ocr import TesseractOCRParser, PaddleOCRParser
from trust_rag.engine.ingest.parsers.asr import WhisperASRParser
from trust_rag.engine.ingest.parsers.table import TableParser
from trust_rag.engine.ingest.parsers.html import HTMLParser
from trust_rag.engine.ingest.parsers.text import TextParser

logger = logging.getLogger(__name__)

@dataclass
class RouteDecision:
    content_type: str
    language: Literal["zh", "en", "unknown"]
    parser: BaseIngestParser
    fallback_parser: Optional[BaseIngestParser]

class IngestionRouter:
    """
    Routes ingestion requests to appropriate parsers.
    Key rule: Language is detected FIRST, then parser is selected.
    """
    
    def __init__(self):
        self.lang_detector = LanguageDetector()
        
        # PDF Parsers
        self.docling_pdf = DoclingPDFParser()
        self.mineru_pdf = MinerUPDFParser()
        self.fallback_pdf = FallbackPDFParser()
        
        # OCR Parsers (LOCAL ONLY - NO CLOUD APIs)
        self.tesseract_ocr = TesseractOCRParser()
        self.paddle_ocr = PaddleOCRParser()
        
        # Other Parsers
        self.whisper_asr = WhisperASRParser()
        self.table_parser = TableParser()
        self.html_parser = HTMLParser()
        self.text_parser = TextParser()
    
    def route(self, path: str, content_type: str) -> RouteDecision:
        """
        Route an input to the appropriate parser.
        
        Args:
            path: File path
            content_type: Inferred content type (pdf, image, audio, csv, xlsx, html, text)
        
        Returns:
            RouteDecision with selected parser and fallback
        """
        # Step 1: Detect Language
        language = self.lang_detector.detect_from_file(path, content_type)
        logger.info(f"Detected language: {language} for {path}")
        
        # Step 2: Select Parser based on content type + language
        if content_type == "pdf":
            return self._route_pdf(path, language)
        elif content_type == "image":
            return self._route_image(path, language)
        elif content_type == "audio":
            return self._route_audio(path, language)
        elif content_type in ["csv", "xlsx"]:
            return self._route_table(path, language, content_type)
        elif content_type == "html":
            return self._route_html(path, language)
        else:
            # Text fallback
            return RouteDecision(
                content_type=content_type,
                language=language,
                parser=self.text_parser,
                fallback_parser=None
            )
    
    def _route_pdf(self, path: str, language: str) -> RouteDecision:
        """Route PDF based on language."""
        if language == "en":
            # English: Docling (primary) -> Fallback
            if self.docling_pdf.is_available():
                return RouteDecision(
                    content_type="pdf",
                    language=language,
                    parser=self.docling_pdf,
                    fallback_parser=self.fallback_pdf
                )
            else:
                logger.warning("Docling not available, using fallback for EN PDF")
                return RouteDecision(
                    content_type="pdf",
                    language=language,
                    parser=self.fallback_pdf,
                    fallback_parser=None
                )
        
        elif language == "zh":
            # Chinese: MinerU (primary) -> Fallback
            if self.mineru_pdf.is_available():
                return RouteDecision(
                    content_type="pdf",
                    language=language,
                    parser=self.mineru_pdf,
                    fallback_parser=self.fallback_pdf
                )
            else:
                logger.warning("MinerU not available, using fallback for ZH PDF")
                return RouteDecision(
                    content_type="pdf",
                    language=language,
                    parser=self.fallback_pdf,
                    fallback_parser=None
                )
        
        else:
            # Unknown language: Try Docling first (structure-aware), then fallback
            if self.docling_pdf.is_available():
                return RouteDecision(
                    content_type="pdf",
                    language=language,
                    parser=self.docling_pdf,
                    fallback_parser=self.fallback_pdf
                )
            return RouteDecision(
                content_type="pdf",
                language=language,
                parser=self.fallback_pdf,
                fallback_parser=None
            )
    
    def _route_image(self, path: str, language: str) -> RouteDecision:
        """Route Image based on language (LOCAL OCR ONLY)."""
        if language == "zh":
            # Chinese: PaddleOCR (local) -> Tesseract fallback
            if self.paddle_ocr.is_available():
                return RouteDecision(
                    content_type="image",
                    language=language,
                    parser=self.paddle_ocr,
                    fallback_parser=self.tesseract_ocr if self.tesseract_ocr.is_available() else None
                )
            elif self.tesseract_ocr.is_available():
                return RouteDecision(
                    content_type="image",
                    language=language,
                    parser=self.tesseract_ocr,
                    fallback_parser=None
                )
        else:
            # English/Unknown: Tesseract
            if self.tesseract_ocr.is_available():
                return RouteDecision(
                    content_type="image",
                    language=language,
                    parser=self.tesseract_ocr,
                    fallback_parser=None
                )
        
        raise ValueError(f"No OCR parser available for language: {language}")
    
    def _route_audio(self, path: str, language: str) -> RouteDecision:
        """Route Audio to Whisper."""
        if not self.whisper_asr.is_available():
            raise ValueError("Whisper ASR not available")
        
        return RouteDecision(
            content_type="audio",
            language=language,
            parser=self.whisper_asr,
            fallback_parser=None
        )
    
    def _route_table(self, path: str, language: str, content_type: str) -> RouteDecision:
        """Route Table files."""
        if not self.table_parser.is_available():
            raise ValueError("Table parser (pandas) not available")
        
        return RouteDecision(
            content_type=content_type,
            language=language,
            parser=self.table_parser,
            fallback_parser=None
        )
    
    def _route_html(self, path: str, language: str) -> RouteDecision:
        """Route HTML files."""
        if not self.html_parser.is_available():
            raise ValueError("HTML parser (beautifulsoup) not available")
        
        return RouteDecision(
            content_type="html",
            language=language,
            parser=self.html_parser,
            fallback_parser=None
        )
