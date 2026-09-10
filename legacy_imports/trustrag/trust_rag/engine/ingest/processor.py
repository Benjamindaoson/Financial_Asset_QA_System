"""
Unified Document Processor for TrustRAG.
Supports PDF, DOCX, HTML, Images, and Audio processing.
"""
import os
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

from trust_rag.config import get_config
from trust_rag.engine.ingest.models import Chunk, ChunkProvenance, Granularity, ChunkTier
from .deep_parser import DeepDocumentParser
from .audio_processor import AudioEvidenceProcessor
from .image_processor import AdvancedOCRProcessor

logger = logging.getLogger(__name__)


class DocumentType(Enum):
    """Supported document types."""
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    UNKNOWN = "unknown"


@dataclass
class DocumentMetadata:
    """Document metadata extracted during processing."""
    title: Optional[str] = None
    author: Optional[str] = None
    creation_date: Optional[str] = None
    page_count: Optional[int] = None
    language: str = "unknown"
    encoding: Optional[str] = None
    file_size: int = 0
    checksum: str = ""


class DocumentProcessor:
    """
    Unified document processor supporting multiple formats.
    """

    def __init__(self):
        self.config = get_config().document_processing
        self.deep_parser = DeepDocumentParser()
        self.audio_processor = AudioEvidenceProcessor()
        self.image_processor = AdvancedOCRProcessor()

    def process_file(self, file_path: str, doc_id: Optional[str] = None) -> Tuple[List[Chunk], DocumentMetadata]:
        """
        Process a document file and return chunks with metadata.

        Args:
            file_path: Path to the document file
            doc_id: Optional document ID

        Returns:
            Tuple of (chunks, metadata)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > self.config.max_file_size_mb * 1024 * 1024:
            raise ValueError(f"File too large: {file_size} bytes > {self.config.max_file_size_mb}MB")

        # Determine document type
        doc_type = self._detect_document_type(file_path)

        # Generate doc_id if not provided
        if not doc_id:
            doc_id = self._generate_doc_id(file_path)

        # Process based on type
        try:
            if doc_type == DocumentType.PDF:
                # Use deep parser for advanced PDF processing
                chunks, skeleton = self.deep_parser.parse_document(file_path, doc_id)
                metadata = DocumentMetadata(
                    title=skeleton.title,
                    language="unknown",  # Could be enhanced
                    file_size=file_size
                )
            elif doc_type == DocumentType.DOCX:
                chunks, metadata = self._process_docx(file_path, doc_id)
            elif doc_type == DocumentType.HTML:
                chunks, metadata = self._process_html(file_path, doc_id)
            elif doc_type == DocumentType.TEXT:
                chunks, metadata = self._process_text(file_path, doc_id)
            elif doc_type == DocumentType.IMAGE:
                # Use advanced OCR processor
                chunks, ocr_metadata = self.image_processor.process_image(file_path, doc_id)
                metadata = DocumentMetadata(
                    language=self.config.ocr_languages.split('+')[0],
                    file_size=file_size
                )
                # Merge OCR metadata
                for key, value in ocr_metadata.items():
                    setattr(metadata, key, value)
            elif doc_type == DocumentType.AUDIO:
                # Use advanced audio processor
                chunks, audio_metadata = self.audio_processor.process_audio(file_path, doc_id)
                metadata = DocumentMetadata(
                    language=audio_metadata.get('language', 'unknown'),
                    file_size=file_size
                )
                # Add audio-specific metadata
                metadata.duration = audio_metadata.get('duration', 0.0)
            else:
                raise ValueError(f"Unsupported document type: {doc_type.value}")

            return chunks, metadata

        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")
            raise

    def _detect_document_type(self, file_path: str) -> DocumentType:
        """Detect document type from file extension and content."""
        ext = Path(file_path).suffix.lower()

        # Extension-based detection
        ext_mapping = {
            '.pdf': DocumentType.PDF,
            '.docx': DocumentType.DOCX,
            '.html': DocumentType.HTML,
            '.htm': DocumentType.HTML,
            '.txt': DocumentType.TEXT,
            '.md': DocumentType.TEXT,
            '.png': DocumentType.IMAGE,
            '.jpg': DocumentType.IMAGE,
            '.jpeg': DocumentType.IMAGE,
            '.webp': DocumentType.IMAGE,
            '.mp3': DocumentType.AUDIO,
            '.wav': DocumentType.AUDIO,
            '.m4a': DocumentType.AUDIO,
            '.flac': DocumentType.AUDIO,
        }

        doc_type = ext_mapping.get(ext, DocumentType.UNKNOWN)

        # Content-based detection for unknown types
        if doc_type == DocumentType.UNKNOWN:
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(512)

                # Check for PDF
                if header.startswith(b'%PDF'):
                    doc_type = DocumentType.PDF
                # Check for HTML
                elif b'<html' in header.lower() or b'<!doctype html' in header.lower():
                    doc_type = DocumentType.HTML
                # Check for text
                else:
                    try:
                        header.decode('utf-8')
                        doc_type = DocumentType.TEXT
                    except UnicodeDecodeError:
                        doc_type = DocumentType.UNKNOWN

            except Exception:
                pass

        return doc_type

    def _generate_doc_id(self, file_path: str) -> str:
        """Generate a unique document ID."""
        filename = Path(file_path).name
        file_hash = hashlib.md5(open(file_path, 'rb').read()).hexdigest()[:8]
        return f"{filename}_{file_hash}"

    def _process_pdf(self, file_path: str, doc_id: str) -> Tuple[List[Chunk], DocumentMetadata]:
        """Process PDF document."""
        chunks = []
        metadata = DocumentMetadata()

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)

            # Extract metadata
            pdf_metadata = doc.metadata
            metadata.title = pdf_metadata.get('title', Path(file_path).stem)
            metadata.author = pdf_metadata.get('author')
            metadata.creation_date = pdf_metadata.get('creationDate')
            metadata.page_count = len(doc)

            # Process each page
            for page_num, page in enumerate(doc):
                page_text = page.get_text()

                if not page_text.strip():
                    # Try OCR if text extraction failed
                    if self.config.pdf_ocr_fallback:
                        page_text = self._ocr_page(page, page_num)

                if page_text.strip():
                    # Create chunk
                    chunk_id = f"{doc_id}_p{page_num + 1}"
                    evidence_id = f"ev_{chunk_id}"

                    provenance = ChunkProvenance(
                        doc_id=doc_id,
                        page_number=page_num + 1,
                        source_path=file_path,
                        parser_name="pymupdf",
                        language="unknown",  # Could be detected
                        modality="pdf",
                        block_index=0
                    )

                    chunk = Chunk(
                        evidence_id=evidence_id,
                        text=page_text,
                        provenance=provenance,
                        granularity=Granularity.COMPOSITE,
                        tier=ChunkTier.BASE
                    )

                    chunks.append(chunk)

            doc.close()

        except ImportError:
            logger.error("PyMuPDF not installed. Install with: pip install PyMuPDF")
            raise
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            raise

        return chunks, metadata

    def _process_docx(self, file_path: str, doc_id: str) -> Tuple[List[Chunk], DocumentMetadata]:
        """Process DOCX document."""
        chunks = []
        metadata = DocumentMetadata()

        try:
            from docx import Document

            doc = Document(file_path)

            # Extract metadata
            core_props = doc.core_properties
            metadata.title = core_props.title or Path(file_path).stem
            metadata.author = core_props.author
            if core_props.created:
                metadata.creation_date = core_props.created.isoformat()

            # Extract text from paragraphs
            full_text = []
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text)

            # Also extract from tables if configured
            if self.config.docx_preserve_formatting:
                for table in doc.tables:
                    for row in table.rows:
                        row_text = [cell.text for cell in row.cells if cell.text.strip()]
                        if row_text:
                            full_text.append(" | ".join(row_text))

            # Create chunks
            if full_text:
                combined_text = "\n\n".join(full_text)

                chunk_id = f"{doc_id}_content"
                evidence_id = f"ev_{chunk_id}"

                provenance = ChunkProvenance(
                    doc_id=doc_id,
                    source_path=file_path,
                    parser_name="python-docx",
                    language="unknown",
                    modality="docx",
                    block_index=0
                )

                chunk = Chunk(
                    evidence_id=evidence_id,
                    text=combined_text,
                    provenance=provenance,
                    granularity=Granularity.COMPOSITE,
                    tier=ChunkTier.BASE
                )

                chunks.append(chunk)

        except ImportError:
            logger.error("python-docx not installed. Install with: pip install python-docx")
            raise
        except Exception as e:
            logger.error(f"DOCX processing failed: {e}")
            raise

        return chunks, metadata

    def _process_html(self, file_path: str, doc_id: str) -> Tuple[List[Chunk], DocumentMetadata]:
        """Process HTML document."""
        chunks = []
        metadata = DocumentMetadata()

        try:
            from bs4 import BeautifulSoup

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            soup = BeautifulSoup(content, 'lxml')

            # Remove unwanted elements
            if self.config.html_remove_scripts:
                for script in soup(["script", "style"]):
                    script.decompose()

            # Extract title
            title_tag = soup.find('title')
            metadata.title = title_tag.get_text().strip() if title_tag else Path(file_path).stem

            # Extract main content
            # Try common content selectors
            main_content = None

            # Try to find main content areas
            content_selectors = ['main', 'article', '.content', '#content', '.main', '#main']
            for selector in content_selectors:
                element = soup.select_one(selector)
                if element:
                    main_content = element.get_text(separator='\n', strip=True)
                    break

            # Fallback to body
            if not main_content:
                body = soup.find('body')
                if body:
                    main_content = body.get_text(separator='\n', strip=True)
                else:
                    main_content = soup.get_text(separator='\n', strip=True)

            if main_content:
                # Clean up whitespace
                import re
                main_content = re.sub(r'\n\s*\n', '\n\n', main_content)
                main_content = main_content.strip()

                chunk_id = f"{doc_id}_content"
                evidence_id = f"ev_{chunk_id}"

                provenance = ChunkProvenance(
                    doc_id=doc_id,
                    source_path=file_path,
                    parser_name="beautifulsoup",
                    language="unknown",
                    modality="html",
                    block_index=0
                )

                chunk = Chunk(
                    evidence_id=evidence_id,
                    text=main_content,
                    provenance=provenance,
                    granularity=Granularity.COMPOSITE,
                    tier=ChunkTier.BASE
                )

                chunks.append(chunk)

        except ImportError:
            logger.error("beautifulsoup4 and lxml not installed. Install with: pip install beautifulsoup4 lxml")
            raise
        except Exception as e:
            logger.error(f"HTML processing failed: {e}")
            raise

        return chunks, metadata

    def _process_text(self, file_path: str, doc_id: str) -> Tuple[List[Chunk], DocumentMetadata]:
        """Process plain text document."""
        chunks = []
        metadata = DocumentMetadata()

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            metadata.file_size = len(content.encode('utf-8'))

            if content.strip():
                chunk_id = f"{doc_id}_content"
                evidence_id = f"ev_{chunk_id}"

                provenance = ChunkProvenance(
                    doc_id=doc_id,
                    source_path=file_path,
                    parser_name="text",
                    language="unknown",
                    modality="text",
                    block_index=0
                )

                chunk = Chunk(
                    evidence_id=evidence_id,
                    text=content,
                    provenance=provenance,
                    granularity=Granularity.COMPOSITE,
                    tier=ChunkTier.BASE
                )

                chunks.append(chunk)

        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            raise

        return chunks, metadata

    def _process_image(self, file_path: str, doc_id: str) -> Tuple[List[Chunk], DocumentMetadata]:
        """Process image document using OCR."""
        chunks = []
        metadata = DocumentMetadata()

        try:
            import pytesseract
            from PIL import Image

            # Configure OCR language
            custom_config = f'--oem 3 --psm 6 -l {self.config.ocr_languages}'

            # Open image
            image = Image.open(file_path)

            # Extract text
            text = pytesseract.image_to_string(image, config=custom_config, lang=self.config.ocr_languages)

            # Get confidence scores
            data = pytesseract.image_to_data(image, config=custom_config, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in data['conf'] if conf != '-1']

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0

            if text.strip() and avg_confidence >= self.config.ocr_min_confidence:
                chunk_id = f"{doc_id}_ocr"
                evidence_id = f"ev_{chunk_id}"

                provenance = ChunkProvenance(
                    doc_id=doc_id,
                    source_path=file_path,
                    parser_name="tesseract",
                    language=self.config.ocr_languages.split('+')[0],  # Primary language
                    modality="image",
                    block_index=0
                )

                chunk = Chunk(
                    evidence_id=evidence_id,
                    text=text,
                    provenance=provenance,
                    granularity=Granularity.ATOMIC,
                    tier=ChunkTier.MICRO,
                    metadata={
                        "ocr_confidence": avg_confidence,
                        "ocr_engine": "tesseract",
                        "image_width": image.width,
                        "image_height": image.height
                    }
                )

                chunks.append(chunk)

                metadata.page_count = 1  # Images are single "pages"

        except ImportError:
            logger.error("OCR dependencies not installed. Install with: pip install pytesseract Pillow")
            raise
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            raise

        return chunks, metadata

    def _process_audio(self, file_path: str, doc_id: str) -> Tuple[List[Chunk], DocumentMetadata]:
        """Process audio document using speech recognition."""
        chunks = []
        metadata = DocumentMetadata()

        try:
            import speech_recognition as sr
            from pydub import AudioSegment

            # Load audio file
            audio = AudioSegment.from_file(file_path)

            # Convert to WAV if needed
            if audio.channels != 1 or audio.frame_rate != self.config.audio_sample_rate:
                audio = audio.set_channels(1).set_frame_rate(self.config.audio_sample_rate)

            # Export to temporary WAV file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
                audio.export(temp_path, format='wav')

            try:
                # Initialize recognizer
                recognizer = sr.Recognizer()

                # Load audio file
                with sr.AudioFile(temp_path) as source:
                    audio_data = recognizer.record(source)

                    # Perform speech recognition
                    text = recognizer.recognize_google(
                        audio_data,
                        language=self.config.asr_language
                    )

                    if text.strip():
                        # Calculate duration
                        duration_ms = len(audio)

                        chunk_id = f"{doc_id}_asr"
                        evidence_id = f"ev_{chunk_id}"

                        provenance = ChunkProvenance(
                            doc_id=doc_id,
                            source_path=file_path,
                            parser_name="speech_recognition",
                            language=self.config.asr_language,
                            modality="audio",
                            block_index=0
                        )

                        chunk = Chunk(
                            evidence_id=evidence_id,
                            text=text,
                            provenance=provenance,
                            granularity=Granularity.ATOMIC,
                            tier=ChunkTier.MICRO,
                            metadata={
                                "duration_ms": duration_ms,
                                "asr_engine": "google",
                                "sample_rate": audio.frame_rate,
                                "channels": audio.channels
                            }
                        )

                        chunks.append(chunk)

                        metadata.page_count = 1  # Audio files are single "pages"

            finally:
                # Clean up temp file
                os.unlink(temp_path)

        except ImportError:
            logger.error("ASR dependencies not installed. Install with: pip install SpeechRecognition pydub")
            raise
        except Exception as e:
            logger.error(f"Audio processing failed: {e}")
            raise

        return chunks, metadata

    def _ocr_page(self, page, page_num: int) -> str:
        """Perform OCR on a PDF page."""
        try:
            import pytesseract
            from PIL import Image
            import io

            # Convert page to image
            pix = page.get_pixmap()
            img_data = pix.tobytes("png")

            # Create PIL Image
            image = Image.open(io.BytesIO(img_data))

            # OCR
            custom_config = f'--oem 3 --psm 6 -l {self.config.ocr_languages}'
            text = pytesseract.image_to_string(image, config=custom_config)

            return text

        except Exception as e:
            logger.warning(f"OCR failed for page {page_num}: {e}")
            return ""
